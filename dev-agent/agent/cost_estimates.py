"""Decimal-only cost estimation from explicitly supplied provider rate cards.

Rates are USD per million tokens and must be independently verified before
use. This module does not fetch prices or claim that token limits bound all
possible provider charges.
"""
from dataclasses import dataclass
from decimal import Decimal, ROUND_UP

@dataclass(frozen=True)
class RateCard:
    model: str
    input_per_million: Decimal
    output_per_million: Decimal

    def __post_init__(self):
        if not isinstance(self.model,str) or not self.model.strip():
            raise ValueError("Model required")
        for value in (self.input_per_million,self.output_per_million):
            if not isinstance(value,Decimal) or not value.is_finite() or value < 0:
                raise ValueError("Invalid token rate")

def estimated_cost(card: RateCard, input_tokens: int, output_tokens: int) -> Decimal:
    if (type(input_tokens) is not int or type(output_tokens) is not int or
        input_tokens < 0 or output_tokens < 0):
        raise ValueError("Invalid token counts")
    return ((card.input_per_million*Decimal(input_tokens) +
             card.output_per_million*Decimal(output_tokens))/Decimal(1000000)
            ).quantize(Decimal("0.000001"),rounding=ROUND_UP)

def reservation_for_request(card: RateCard, max_input_tokens: int,
                            max_output_tokens: int, *,
                            multiplier: Decimal=Decimal("2")) -> Decimal:
    if not isinstance(multiplier,Decimal) or not multiplier.is_finite() or multiplier < 1:
        raise ValueError("Invalid safety multiplier")
    estimate=estimated_cost(card,max_input_tokens,max_output_tokens)
    return (estimate*multiplier).quantize(Decimal("0.000001"),rounding=ROUND_UP)
