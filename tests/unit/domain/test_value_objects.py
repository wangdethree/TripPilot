from datetime import date
from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st

from trippilot.domain.errors import ValidationError
from trippilot.domain.value_objects import Money, TravelDateRange, sum_money


def test_money_uses_decimal_half_up_rounding() -> None:
    assert Money.of("0.105").amount == Decimal("0.11")
    assert Money.of("0.1") + Money.of("0.2") == Money.of("0.30")


def test_money_rejects_invalid_currency_and_non_finite_value() -> None:
    with pytest.raises(ValidationError):
        Money(Decimal("1"), "USD")
    with pytest.raises(ValidationError):
        Money(Decimal("NaN"))


def test_money_arithmetic_and_formatting() -> None:
    assert Money.of("10") - Money.of("3.50") == Money.of("6.50")
    assert Money.of("2.50") * 3 == Money.of("7.50")
    assert Money.of("1") < Money.of("2")
    assert Money.of("1") <= Money.of("1")
    assert str(Money.of("1")) == "1.00"
    assert sum_money([Money.of("1"), Money.of("2")]) == Money.of("3")


@given(st.integers(min_value=1, max_value=3))
def test_date_range_from_days_is_inclusive(days: int) -> None:
    travel_range = TravelDateRange.from_days(date(2030, 1, 1), days)
    assert travel_range.days == days
    assert travel_range.contains(date(2030, 1, 1))


def test_date_range_rejects_invalid_values_and_past_date() -> None:
    with pytest.raises(ValidationError):
        TravelDateRange(date(2030, 1, 2), date(2030, 1, 1))
    with pytest.raises(ValidationError):
        TravelDateRange.from_days(date(2030, 1, 1), 4)
    travel_range = TravelDateRange.from_days(date(2030, 1, 1), 1)
    with pytest.raises(ValidationError):
        travel_range.validate_not_past(date(2030, 1, 2))
