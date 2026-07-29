"""Decimal money value object for deterministic CNY calculations."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Self

from trippilot.domain.errors import ValidationError

_CENT = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class Money:
    amount: Decimal
    currency: str = "CNY"

    def __post_init__(self) -> None:
        if self.currency != "CNY":
            raise ValidationError("第一版只支持人民币", field="currency")
        if not self.amount.is_finite():
            raise ValidationError("金额必须是有限十进制数", field="amount")
        object.__setattr__(
            self,
            "amount",
            self.amount.quantize(_CENT, rounding=ROUND_HALF_UP),
        )

    @classmethod
    def of(cls, value: Decimal | int | str) -> Self:
        try:
            return cls(Decimal(str(value)))
        except InvalidOperation as exc:
            raise ValidationError("金额格式不正确", field="amount") from exc

    @classmethod
    def zero(cls) -> Self:
        return cls(Decimal("0"))

    def __add__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount + other.amount, self.currency)

    def __sub__(self, other: Money) -> Money:
        self._ensure_same_currency(other)
        return Money(self.amount - other.amount, self.currency)

    def __mul__(self, multiplier: int | Decimal) -> Money:
        return Money(self.amount * Decimal(multiplier), self.currency)

    def __lt__(self, other: Money) -> bool:
        self._ensure_same_currency(other)
        return self.amount < other.amount

    def __le__(self, other: Money) -> bool:
        self._ensure_same_currency(other)
        return self.amount <= other.amount

    def __str__(self) -> str:
        return f"{self.amount:.2f}"

    def _ensure_same_currency(self, other: Money) -> None:
        if self.currency != other.currency:
            raise ValidationError("不能计算不同币种的金额", field="currency")


def sum_money(values: tuple[Money, ...] | list[Money]) -> Money:
    total = Money.zero()
    for value in values:
        total += value
    return total
