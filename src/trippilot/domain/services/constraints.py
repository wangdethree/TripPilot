"""Deterministic plan constraint checks.

The model proposes candidates; this module decides whether a candidate is safe
and valid enough to publish.
"""

from collections.abc import Iterable
from datetime import time
from itertools import pairwise

from trippilot.domain.enums import (
    CheckStatus,
    ConstraintCategory,
    ConstraintSeverity,
    FreshnessStatus,
    Pace,
    TimelineItemType,
)
from trippilot.domain.models import (
    ActivityDetails,
    ConstraintResult,
    DayPlan,
    TimelineItem,
    TripPlan,
)

_PACE_LIMITS = {
    Pace.RELAXED: 3,
    Pace.MODERATE: 4,
    Pace.INTENSIVE: 5,
}


def validate_plan(plan: TripPlan) -> tuple[ConstraintResult, ...]:
    request = plan.request_snapshot
    results: list[ConstraintResult] = []
    results.append(_check_budget(plan))
    for day in plan.days:
        results.extend(
            (
                _check_timeline(day, request.daily_start_time, request.daily_end_time),
                _check_pace(day, request.pace),
                _check_interests(day, request.interests),
                _check_route_duration(day),
            )
        )
        results.extend(_check_opening_hours(day))
    results.extend(_check_required_places(plan))
    results.append(_check_source_freshness(plan))
    return tuple(results)


def has_hard_failures(results: Iterable[ConstraintResult]) -> bool:
    return any(
        result.severity is ConstraintSeverity.HARD and result.status is CheckStatus.FAIL
        for result in results
    )


def has_important_unknowns(results: Iterable[ConstraintResult]) -> bool:
    important = {
        ConstraintCategory.ROUTE,
        ConstraintCategory.WEATHER,
        ConstraintCategory.OPENING_HOURS,
        ConstraintCategory.BUDGET,
    }
    return any(
        result.status is CheckStatus.UNKNOWN and result.category in important for result in results
    )


def _check_budget(plan: TripPlan) -> ConstraintResult:
    summary = plan.budget_summary
    budget = plan.request_snapshot.budget_total
    evidence = {
        "budget_total": str(budget),
        "budget_scope_total": str(summary.budget_scope_total),
        "remaining_budget": str(summary.remaining_budget),
        "unknown_cost_count": len(summary.unknown_items),
    }
    if summary.budget_scope_total > budget:
        return _result(
            "BUDGET_LIMIT",
            ConstraintCategory.BUDGET,
            ConstraintSeverity.HARD,
            CheckStatus.FAIL,
            "已知与估算费用超过总预算",
            evidence,
            suggested_actions=("减少付费活动", "提高预算上限"),
        )
    if summary.unknown_items:
        return _result(
            "BUDGET_UNKNOWN_COSTS",
            ConstraintCategory.BUDGET,
            ConstraintSeverity.HARD,
            CheckStatus.UNKNOWN,
            "部分费用暂时无法可靠确认",
            evidence,
            affected_item_ids=tuple(
                item.item_id
                for day in plan.days
                for item in day.timeline_items
                if item.estimated_cost.amount is None
            ),
        )
    if summary.remaining_budget < summary.reserve:
        return _result(
            "BUDGET_RESERVE",
            ConstraintCategory.BUDGET,
            ConstraintSeverity.SOFT,
            CheckStatus.WARNING,
            "剩余预算不足总预算的 10%",
            evidence,
        )
    return _result(
        "BUDGET_LIMIT",
        ConstraintCategory.BUDGET,
        ConstraintSeverity.HARD,
        CheckStatus.PASS,
        "预算在确认的上限内",
        evidence,
    )


def _check_timeline(day: DayPlan, day_start: time, day_end: time) -> ConstraintResult:
    ordered = sorted(day.timeline_items, key=lambda item: item.start_time)
    affected: list[str] = []
    for previous, current in pairwise(ordered):
        if current.start_time < previous.end_time:
            affected.extend((previous.item_id, current.item_id))
    outside = [
        item.item_id for item in ordered if item.start_time < day_start or item.end_time > day_end
    ]
    affected.extend(outside)
    if affected:
        return _result(
            f"TIMELINE_{day.date.isoformat()}",
            ConstraintCategory.TIME,
            ConstraintSeverity.HARD,
            CheckStatus.FAIL,
            "时间线存在重叠或超出每日可用时间",
            {
                "date": day.date.isoformat(),
                "daily_start_time": day_start.isoformat(timespec="minutes"),
                "daily_end_time": day_end.isoformat(timespec="minutes"),
            },
            affected_item_ids=tuple(dict.fromkeys(affected)),
        )
    return _result(
        f"TIMELINE_{day.date.isoformat()}",
        ConstraintCategory.TIME,
        ConstraintSeverity.HARD,
        CheckStatus.PASS,
        "时间线无重叠且位于每日可用时间内",
        {"date": day.date.isoformat()},
    )


def _check_pace(day: DayPlan, pace: Pace) -> ConstraintResult:
    major = [
        item
        for item in day.timeline_items
        if item.item_type is TimelineItemType.ACTIVITY
        and isinstance(item.details, ActivityDetails)
        and item.details.duration_minutes >= 60
    ]
    limit = _PACE_LIMITS[pace]
    status = CheckStatus.FAIL if len(major) > limit else CheckStatus.PASS
    return _result(
        f"PACE_{day.date.isoformat()}",
        ConstraintCategory.PACE,
        ConstraintSeverity.HARD,
        status,
        "主要活动数量符合旅行节奏"
        if status is CheckStatus.PASS
        else "主要活动数量超过旅行节奏上限",
        {"date": day.date.isoformat(), "major_activity_count": len(major), "limit": limit},
        affected_item_ids=tuple(item.item_id for item in major)
        if status is CheckStatus.FAIL
        else (),
    )


def _check_interests(
    day: DayPlan,
    interests: tuple[str, ...],
) -> ConstraintResult:
    normalized = {interest.casefold() for interest in interests}
    matches = [
        item
        for item in day.timeline_items
        if isinstance(item.details, ActivityDetails)
        and normalized.intersection(tag.casefold() for tag in item.details.interest_tags)
    ]
    status = CheckStatus.PASS if matches else CheckStatus.WARNING
    return _result(
        f"INTEREST_{day.date.isoformat()}",
        ConstraintCategory.PREFERENCE,
        ConstraintSeverity.SOFT,
        status,
        "当日包含核心兴趣活动" if matches else "当日缺少符合核心兴趣的活动",
        {"date": day.date.isoformat(), "matched_count": len(matches)},
    )


def _check_route_duration(day: DayPlan) -> ConstraintResult:
    long_transits: list[TimelineItem] = []
    unknown_transits: list[TimelineItem] = []
    for item in day.timeline_items:
        if item.item_type is not TimelineItemType.TRANSIT:
            continue
        duration = getattr(item.details, "duration_minutes", None)
        if duration is None:
            unknown_transits.append(item)
        elif duration > 60:
            long_transits.append(item)
    if unknown_transits:
        return _result(
            f"ROUTE_{day.date.isoformat()}",
            ConstraintCategory.ROUTE,
            ConstraintSeverity.SOFT,
            CheckStatus.UNKNOWN,
            "部分路线时间无法确认",
            {"date": day.date.isoformat()},
            affected_item_ids=tuple(item.item_id for item in unknown_transits),
        )
    status = CheckStatus.WARNING if long_transits else CheckStatus.PASS
    return _result(
        f"ROUTE_{day.date.isoformat()}",
        ConstraintCategory.ROUTE,
        ConstraintSeverity.SOFT,
        status,
        "存在超过 60 分钟的连续交通" if long_transits else "路线时间符合建议",
        {"date": day.date.isoformat()},
        affected_item_ids=tuple(item.item_id for item in long_transits),
    )


def _check_opening_hours(day: DayPlan) -> tuple[ConstraintResult, ...]:
    results: list[ConstraintResult] = []
    for item in day.timeline_items:
        if not isinstance(item.details, ActivityDetails):
            continue
        status = item.details.opening_hours_status
        if status is CheckStatus.WARNING:
            status = CheckStatus.UNKNOWN
        results.append(
            _result(
                f"OPENING_HOURS_{item.item_id}",
                ConstraintCategory.OPENING_HOURS,
                ConstraintSeverity.HARD,
                status,
                {
                    CheckStatus.PASS: "活动位于已知开放时段",
                    CheckStatus.FAIL: "活动安排在已知闭馆时段",
                    CheckStatus.UNKNOWN: "开放时间无法确认",
                }[status],
                {"date": day.date.isoformat()},
                affected_item_ids=(item.item_id,),
            )
        )
    return tuple(results)


def _check_required_places(plan: TripPlan) -> tuple[ConstraintResult, ...]:
    request = plan.request_snapshot
    visited = {
        item.location.name.casefold()
        for day in plan.days
        for item in day.timeline_items
        if item.location is not None
    }
    missing = tuple(place for place in request.must_visit if place.casefold() not in visited)
    avoided = tuple(place for place in request.avoid_places if place.casefold() in visited)
    return (
        _result(
            "MUST_VISIT",
            ConstraintCategory.PREFERENCE,
            ConstraintSeverity.HARD,
            CheckStatus.FAIL if missing else CheckStatus.PASS,
            "缺少用户确认的必去地点" if missing else "已覆盖所有必去地点",
            {"missing_places": missing},
            suggested_actions=("替换非必去活动",) if missing else (),
        ),
        _result(
            "AVOID_PLACES",
            ConstraintCategory.PREFERENCE,
            ConstraintSeverity.HARD,
            CheckStatus.FAIL if avoided else CheckStatus.PASS,
            "行程包含用户明确避开的地点" if avoided else "未包含避开地点",
            {"avoided_places": avoided},
        ),
    )


def _check_source_freshness(plan: TripPlan) -> ConstraintResult:
    stale_or_unknown = [
        source.source_id
        for source in plan.sources
        if source.freshness_status is not FreshnessStatus.FRESH
    ]
    return _result(
        "SOURCE_FRESHNESS",
        ConstraintCategory.WEATHER,
        ConstraintSeverity.HARD,
        CheckStatus.UNKNOWN if stale_or_unknown else CheckStatus.PASS,
        "部分动态信息已过期或时效未知" if stale_or_unknown else "动态信息来源处于有效期内",
        {"stale_or_unknown_source_ids": stale_or_unknown},
    )


def _result(
    constraint_id: str,
    category: ConstraintCategory,
    severity: ConstraintSeverity,
    status: CheckStatus,
    message: str,
    evidence: dict[str, object],
    *,
    affected_item_ids: tuple[str, ...] = (),
    suggested_actions: tuple[str, ...] = (),
) -> ConstraintResult:
    return ConstraintResult(
        constraint_id=constraint_id,
        category=category,
        severity=severity,
        status=status,
        message=message,
        evidence=evidence,
        affected_item_ids=affected_item_ids,
        suggested_actions=suggested_actions,
    )
