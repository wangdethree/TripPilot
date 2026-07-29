"""Deterministic budget aggregation."""

from collections.abc import Iterable

from trippilot.domain.enums import CostConfidence, TimelineItemType
from trippilot.domain.models import BudgetSummary, CostBucket, CostEstimate, TimelineItem
from trippilot.domain.value_objects import Money, sum_money


def calculate_budget(
    items: Iterable[TimelineItem],
    *,
    budget_total: Money,
    accommodation_costs: Iterable[CostEstimate] = (),
    budget_includes_accommodation: bool,
    reserve_ratio: str = "0.10",
) -> BudgetSummary:
    categories: dict[str, list[CostEstimate]] = {
        "accommodation": list(accommodation_costs),
        "transportation": [],
        "tickets": [],
        "meals": [],
        "other": [],
    }
    all_items = list(items)
    for item in all_items:
        category = {
            TimelineItemType.TRANSIT: "transportation",
            TimelineItemType.ACTIVITY: "tickets",
            TimelineItemType.MEAL: "meals",
            TimelineItemType.REST: "other",
        }[item.item_type]
        categories[category].append(item.estimated_cost)

    buckets = {name: _bucket(costs) for name, costs in categories.items()}
    known_total = sum_money([bucket.known for bucket in buckets.values()])
    estimated_total = sum_money([bucket.estimated for bucket in buckets.values()])
    accommodation_total = buckets["accommodation"].total
    budget_scope_total = known_total + estimated_total
    if not budget_includes_accommodation:
        budget_scope_total -= accommodation_total
    unknown_items = tuple(
        cost
        for costs in categories.values()
        for cost in costs
        if cost.confidence is CostConfidence.UNKNOWN
    )
    reserve = budget_total * Money.of(reserve_ratio).amount
    return BudgetSummary(
        accommodation=buckets["accommodation"],
        transportation=buckets["transportation"],
        tickets=buckets["tickets"],
        meals=buckets["meals"],
        other=buckets["other"],
        reserve=reserve,
        known_total=known_total,
        estimated_total=estimated_total,
        budget_scope_total=budget_scope_total,
        unknown_items=unknown_items,
        remaining_budget=budget_total - budget_scope_total,
    )


def _bucket(costs: Iterable[CostEstimate]) -> CostBucket:
    materialized = list(costs)
    known = [
        cost.amount
        for cost in materialized
        if cost.confidence is CostConfidence.KNOWN and cost.amount is not None
    ]
    estimated = [
        cost.amount
        for cost in materialized
        if cost.confidence is CostConfidence.ESTIMATED and cost.amount is not None
    ]
    return CostBucket(
        known=sum_money(known),
        estimated=sum_money(estimated),
    )
