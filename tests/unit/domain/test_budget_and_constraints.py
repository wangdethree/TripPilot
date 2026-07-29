from dataclasses import replace
from datetime import time

from trippilot.domain.enums import CheckStatus, CostConfidence, FreshnessStatus
from trippilot.domain.models import CostEstimate, TravelRequest
from trippilot.domain.services import (
    calculate_budget,
    has_hard_failures,
    has_important_unknowns,
    validate_plan,
)
from trippilot.domain.value_objects import Money

from .conftest import activity, known_cost, make_plan, meal, transit


def test_accommodation_is_displayed_but_outside_budget_scope(
    travel_request: TravelRequest,
) -> None:
    items = (
        activity("a1", "武侯祠", time(9), time(11), amount="800"),
        meal("m1", "锦里附近", time(12), time(13)),
        transit("t1", "武侯祠", "锦里附近", time(11), time(11, 30)),
        activity("a2", "博物馆", time(14), time(16), amount="890"),
    )
    summary = calculate_budget(
        items,
        budget_total=travel_request.budget_total,
        accommodation_costs=(known_cost("800", "住宿"),),
        budget_includes_accommodation=False,
    )
    assert summary.travel_total == Money.of("2600")
    assert summary.budget_scope_total == Money.of("1800")
    assert summary.remaining_budget == Money.of("200")


def test_unknown_cost_is_not_counted_as_zero(travel_request: TravelRequest) -> None:
    item = activity("a1", "武侯祠", time(9), time(11))
    unknown = CostEstimate(
        amount=None,
        confidence=CostConfidence.UNKNOWN,
        covers_travelers=2,
        description="价格未知",
    )
    changed = replace(item, estimated_cost=unknown)
    plan = make_plan(travel_request, (changed,))
    results = validate_plan(plan)
    budget_result = next(
        result for result in results if result.constraint_id == "BUDGET_UNKNOWN_COSTS"
    )
    assert budget_result.status is CheckStatus.UNKNOWN
    assert has_important_unknowns(results)


def test_valid_plan_passes_hard_constraints(travel_request: TravelRequest) -> None:
    plan = make_plan(
        travel_request,
        (
            activity("a1", "武侯祠", time(9), time(11)),
            transit("t1", "武侯祠", "锦里", time(11), time(11, 30)),
            meal("m1", "锦里", time(12), time(13)),
        ),
    )
    results = validate_plan(plan)
    assert not has_hard_failures(results)
    assert all(
        result.status is not CheckStatus.FAIL
        for result in results
        if result.constraint_id != "SOURCE_FRESHNESS"
    )


def test_overlap_missing_place_and_avoided_place_fail(
    travel_request: TravelRequest,
) -> None:
    constrained_request = replace(
        travel_request,
        must_visit=("杜甫草堂",),
        avoid_places=("锦里",),
    )
    plan = make_plan(
        constrained_request,
        (
            activity("a1", "武侯祠", time(9), time(11)),
            activity("a2", "锦里", time(10), time(12)),
        ),
    )
    results = validate_plan(plan)
    assert has_hard_failures(results)
    failed_ids = {result.constraint_id for result in results if result.status is CheckStatus.FAIL}
    assert {"MUST_VISIT", "AVOID_PLACES"} <= failed_ids
    assert any(item.startswith("TIMELINE_") for item in failed_ids)


def test_long_and_unknown_routes_are_reported(travel_request: TravelRequest) -> None:
    long_plan = make_plan(
        travel_request,
        (transit("t1", "甲", "乙", time(9), time(10, 10), duration=70),),
    )
    long_route = next(
        result for result in validate_plan(long_plan) if result.constraint_id.startswith("ROUTE_")
    )
    assert long_route.status is CheckStatus.WARNING

    unknown_plan = make_plan(
        travel_request,
        (transit("t2", "甲", "乙", time(9), time(10), duration=None),),
    )
    unknown_route = next(
        result
        for result in validate_plan(unknown_plan)
        if result.constraint_id.startswith("ROUTE_")
    )
    assert unknown_route.status is CheckStatus.UNKNOWN


def test_stale_source_produces_unknown(travel_request: TravelRequest) -> None:
    plan = make_plan(travel_request, (activity("a1", "武侯祠", time(9), time(11)),))
    stale_sources = tuple(
        replace(source, freshness_status=FreshnessStatus.STALE) for source in plan.sources
    )
    stale_plan = replace(plan, sources=stale_sources)
    source_result = next(
        result for result in validate_plan(stale_plan) if result.constraint_id == "SOURCE_FRESHNESS"
    )
    assert source_result.status is CheckStatus.UNKNOWN
