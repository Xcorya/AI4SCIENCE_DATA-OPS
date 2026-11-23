"""Deterministic procurement rules, never an automatic external purchase."""
from fractions import Fraction
from .protocol import Invalid, integer, number, text


def validate_quote(value):
    if not isinstance(value, dict):
        raise Invalid("quote must be an object")
    result = {
        "vendor": text(value.get("vendor"), "vendor"),
        "unit_cents": integer(value.get("unit_cents"), "unit_cents"),
        "fee_cents": integer(value.get("fee_cents", 0), "fee_cents", low=0),
        "capacity": integer(value.get("capacity"), "capacity"),
        "lead_days": integer(value.get("lead_days"), "lead_days", high=3650),
        "currency": text(value.get("currency"), "currency", 3).upper(),
        "declared_quality": number(value.get("declared_quality"), "declared_quality"),
        "evidence": text(value.get("evidence"), "evidence", 1000),
    }
    for field in ("purposes", "regions"):
        values = value.get(field)
        if not isinstance(values, list) or not values or len(values) > 30:
            raise Invalid(f"{field} must be a nonempty list")
        result[field] = [text(v, field) for v in values]
    for field in ("derivatives", "rights_verified"):
        if type(value.get(field)) is not bool:
            raise Invalid(f"{field} must be boolean")
        result[field] = value[field]
    return result


def rank(spec, quotes):
    rows = []
    for quote in quotes:
        cost = spec["quantity"] * quote["unit_cents"] + quote["fee_cents"]
        reasons = []
        checks = [
            (quote["currency"] == spec["currency"], "currency mismatch"),
            (quote["capacity"] >= spec["quantity"], "insufficient capacity"),
            (cost <= spec["budget_cents"], "over budget"),
            (quote["lead_days"] <= spec["max_days"], "late delivery"),
            (quote["rights_verified"], "rights evidence unverified"),
            (spec["purpose"] in quote["purposes"], "purpose excluded"),
            (spec["region"] in quote["regions"], "region excluded"),
            (not spec["allow_derivatives"] or quote["derivatives"], "derivatives excluded"),
        ]
        reasons = [reason for passed, reason in checks if not passed]
        usable = spec["quantity"] * quote["declared_quality"]
        exact_cost = (Fraction(cost, spec["quantity"]) / Fraction(quote["declared_quality"])
                      if quote["declared_quality"] else None)
        try:
            display_cost = round(float(exact_cost), 2) if exact_cost is not None else None
        except OverflowError:
            display_cost = None
        rows.append(dict(quote, total_cents=cost, eligible=not reasons,
                         reasons=reasons, expected_usable=round(usable, 2),
                         cost_per_expected_usable=display_cost))
    eligible = [r for r in rows if r["eligible"]]
    for row in rows:
        row["pareto"] = row["eligible"] and not any(
            other["total_cents"] <= row["total_cents"] and
            other["lead_days"] <= row["lead_days"] and
            other["declared_quality"] >= row["declared_quality"] and
            (other["total_cents"] < row["total_cents"] or
             other["lead_days"] < row["lead_days"] or
             other["declared_quality"] > row["declared_quality"])
            for other in eligible)
    return sorted(rows, key=lambda r: (
        not r["eligible"], r["declared_quality"] == 0,
        Fraction(r["total_cents"], spec["quantity"]) / Fraction(r["declared_quality"]) if r["declared_quality"] else Fraction(0),
        r["lead_days"], r["id"]))
