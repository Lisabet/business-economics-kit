"""Reproduce the educational monthly subscription example using Decimal.

Reads JSON and prints JSON; source workbooks and inputs are preserved.
"""
from decimal import Decimal
from pathlib import Path
import argparse
import json


def calculate(params):
    def number(key):
        value = Decimal(str(params[key]))
        if not value.is_finite():
            raise ValueError(f"{key}: finite number required")
        return value

    price = number("price")
    discount = number("first_month_discount")
    renewal = number("renewal_rate")
    media = number("monthly_media")
    cpv = number("cost_per_visit")
    conversion = number("visit_to_payment")
    variable = number("variable_cost_per_paid_month")
    fixed = number("monthly_fixed_cost")
    startup = number("startup_cost")
    reserve = number("cash_reserve_rate")
    months = params["horizon_months"]
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise ValueError("horizon_months: positive integer required")
    if price <= 0 or cpv <= 0:
        raise ValueError("price and cost_per_visit: positive numbers required")
    # This example models a paid first month, followed by full-price renewals.
    if discount < 0 or discount >= 1:
        raise ValueError("first_month_discount: paid entry requires a fraction from 0 inclusive to 1 exclusive")
    for key, value in [("renewal_rate", renewal), ("visit_to_payment", conversion)]:
        if value < 0 or value > 1:
            raise ValueError(f"{key}: fraction from 0 to 1 required")
    if min(media, variable, fixed, startup, reserve) < 0:
        raise ValueError("costs and cash_reserve_rate: nonnegative numbers required")

    visits = media / cpv
    new = visits * conversion
    promo = price * (1 - discount)
    cumulative = -startup
    minimum = cumulative
    previous_paid = Decimal(0)
    rows = []
    for month in range(1, months + 1):
        returning = previous_paid * renewal
        active = new + returning
        receipts = new * promo + returning * price
        service = active * variable
        operating = receipts - service - media - fixed
        cumulative += operating
        minimum = min(minimum, cumulative)
        rows.append(dict(month=month, visits=visits, new_payments=new,
                         returning_payments=returning, active_paid=active,
                         receipts=receipts, service_cost=service,
                         operating_cash=operating, cumulative_cash=cumulative))
        previous_paid = active
    funding = max(Decimal(0), -minimum)
    return dict(rows=rows, first_month_price=promo, media_cac=(media / new if new > 0 else None),
                first_positive_operating_month=next((r["month"] for r in rows if r["operating_cash"] > 0), None),
                first_investment_return_month=next((r["month"] for r in rows if r["cumulative_cash"] >= 0), None),
                cash_required=funding, reserve=funding * reserve,
                cash_required_with_reserve=funding * (1 + reserve),
                final_cumulative_cash=cumulative)


def self_test(base):
    result = calculate(base)
    first, second, third = result["rows"][:3]
    # Independently worked identities for the published example, months 1–3.
    assert first["new_payments"] == 36
    assert first["receipts"] == Decimal("16092")
    assert first["operating_cash"] == Decimal("-36788")
    assert second["returning_payments"] == Decimal("25.2")
    assert second["receipts"] == Decimal("53640")
    assert second["operating_cash"] == Decimal("-1256")
    assert third["receipts"] == Decimal("79923.6")
    assert third["operating_cash"] == Decimal("23616.4")
    assert result["cash_required"] == 98044
    assert result["first_positive_operating_month"] == 3
    assert result["first_investment_return_month"] == 5

    for key in ("monthly_media", "visit_to_payment"):
        zero = calculate(dict(base, **{key: 0}))
        assert zero["media_cac"] is None
        assert all(r["active_paid"] == 0 for r in zero["rows"])
    no_renewals = calculate(dict(base, renewal_rate=0))
    assert all(r["returning_payments"] == 0 for r in no_renewals["rows"])
    all_renewals = calculate(dict(base, renewal_rate=1))
    assert all(r["active_paid"] == 36 * r["month"] for r in all_renewals["rows"])
    full_price = calculate(dict(base, first_month_discount=0))
    assert full_price["rows"][0]["receipts"] == 36 * 1490
    high_discount = calculate(dict(base, first_month_discount=Decimal("0.9")))
    assert high_discount["rows"][0]["receipts"] == 36 * 149
    assert high_discount["rows"][1]["receipts"] == Decimal("25.2") * 1490 + 36 * 149
    rejected = 0
    for change in ({"cost_per_visit": 0}, {"renewal_rate": 1.1}, {"monthly_media": -1}, {"horizon_months": 0}, {"first_month_discount": 1}):
        try:
            calculate(dict(base, **change))
        except ValueError:
            rejected += 1
    assert rejected == 5
    return {"status": "PASS", "base_months_checked": 3, "boundary_cases": 6, "invalid_cases": rejected}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "references" / "example-inputs.json")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    params = json.loads(args.inputs.read_text(encoding="utf-8"))
    result = self_test(params) if args.self_test else calculate(params)
    print(json.dumps(result, ensure_ascii=False,
                     default=lambda value: str(value) if isinstance(value, Decimal) else value,
                     indent=2))
