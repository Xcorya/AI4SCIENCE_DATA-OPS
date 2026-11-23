"""Census quality checks and conservative rights/policy evaluation."""
import re
from datetime import date, datetime, timezone
from math import sqrt
import math

from .protocol import Invalid, canonical, text, timestamp

RULESET = "aegis-rules/1.0.1"


def wilson(bad, total):
    if not total:
        return [0.0, 1.0]
    z = 1.959963984540054
    p = bad / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    margin = z * sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return [max(0.0, centre - margin), min(1.0, centre + margin)]


def matches(value, kind):
    if kind == "string":
        return isinstance(value, str)
    if kind == "integer":
        return type(value) is int or type(value) is float and math.isfinite(value) and value.is_integer()
    if kind == "number":
        return type(value) in (int, float)
    return type(value) is bool


def evaluate(body, rights_review=None, as_of=None):
    current = as_of or datetime.now(timezone.utc)
    spec, records, manifest = body["spec"], body["records"], body["manifest"]
    missing, schema, duplicates, pii = set(), set(), set(), set()
    unique, exact = set(), set()
    examples = []
    for index, row in enumerate(records):
        reasons = []
        for field, kind in spec["schema"].items():
            value = row.get(field)
            if value is None or (isinstance(value, str) and not value.strip()):
                missing.add(index)
                reasons.append("missing:" + field)
            elif not matches(value, kind):
                schema.add(index)
                reasons.append("type:" + field)
        key = row.get(spec["unique_key"])
        key_valid = key is not None and not (isinstance(key, str) and not key.strip())
        key_hash, row_hash = canonical(key), canonical(row)
        if row_hash in exact or (key_valid and key_hash in unique):
            duplicates.add(index)
            reasons.append("duplicate")
        exact.add(row_hash)
        if key_valid:
            unique.add(key_hash)
        # This is a narrow heuristic, never a completeness guarantee.
        if any(str(field).lower() in ("email", "phone", "ssn", "passport", "身份证", "手机号") and value not in (None, "")
               or isinstance(value, str) and re.search(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", value)
               for field, value in row.items()):
            pii.add(index)
            reasons.append("possible_pii")
        if reasons and len(examples) < 12:
            examples.append({"row": index + 1, "reasons": reasons})  # Never echo raw sensitive values.
    bad = missing | schema | duplicates
    rate = len(bad) / len(records)
    interval = wilson(len(bad), len(records))
    full = manifest["coverage"] == "full"
    findings = []

    def add(rule, severity, message):
        findings.append(dict(rule=rule, severity=severity, message=message))

    if manifest["record_count"] < spec["quantity"]:
        add("quantity", "reject", "Declared delivery quantity is below the ordered quantity.")
    if full and rate > spec["max_defect_rate"]:
        add("quality.census", "reject", "Observed defect rate exceeds the contractual threshold.")
    if not full:
        add("coverage.sample", "review", "A supplier-provided sample cannot establish full-delivery quality; request the full file.")
        if interval[1] > spec["max_defect_rate"]:
            add("quality.uncertainty", "review", "95% Wilson upper bound exceeds the threshold; sample uncertainty remains.")
    if pii and not spec["allow_pii"]:
        add("privacy.heuristic", "review", "Possible personal data detected; verify consent and redaction before release.")
    if manifest.get("prohibited_source") is True:
        add("source.prohibited", "reject", "The manifest declares a prohibited source.")
    elif manifest.get("prohibited_source") is not False:
        add("source.unknown", "review", "Source prohibition status is missing or invalid.")
    for field in ("source", "license", "evidence"):
        if not isinstance(manifest.get(field), str) or not manifest[field].strip():
            add("rights." + field, "review", f"Missing {field} evidence.")
    if manifest.get("rights_verified") is not True:
        add("rights.claim", "review", "Supplier rights verification is missing; it is only a declaration.")
    for field, needed in (("purposes", spec["purpose"]), ("regions", spec["region"])):
        values = manifest.get(field)
        if not isinstance(values, list) or not values or any(not isinstance(v, str) for v in values):
            add("rights." + field, "review", f"{field} permission is unspecified.")
        elif needed not in values:
            add("rights." + field, "reject", f"Requested {field} permission is explicitly excluded.")
    if spec["allow_derivatives"]:
        if manifest.get("derivatives") is False:
            add("rights.derivatives", "reject", "Derivatives are explicitly prohibited.")
        elif manifest.get("derivatives") is not True:
            add("rights.derivatives", "review", "Derivatives permission is unspecified.")
    try:
        expiry = date.fromisoformat(manifest["valid_until"])
        if expiry < current.date():
            add("rights.expired", "reject", "Declared license has expired.")
    except (KeyError, TypeError, ValueError):
        add("rights.validity", "review", "License expiration must be an explicit ISO date.")
    review = None
    if rights_review is not None:
        if not isinstance(rights_review, dict) or rights_review.get("confirmed") is not True:
            raise Invalid("Rights review requires an explicit confirmed=true attestation")
        review = {
            "confirmed": True,
            "reviewer": text(rights_review.get("reviewer"), "reviewer"),
            "evidence_note": text(rights_review.get("evidence_note"), "evidence_note", 2000),
            "reviewed_at": rights_review.get("reviewed_at"),
        }
        reviewed = timestamp(review["reviewed_at"])
        if abs((current - reviewed).total_seconds()) > 86400:
            raise Invalid("Rights review must be recorded within the last 24 hours")
    else:
        add("rights.independent_review", "review", "An independent reviewer must attest the license evidence.")
    status = "rejected" if any(f["severity"] == "reject" for f in findings) else "review" if findings else "accepted"
    return dict(
        status=status, ruleset=RULESET, findings=findings, rights_review=review,
        quality=dict(scanned=len(records), declared_total=manifest["record_count"],
                     coverage=manifest["coverage"], missing_rows=len(missing), schema_rows=len(schema),
                     duplicate_rows=len(duplicates), possible_pii_rows=len(pii), defect_rows=len(bad),
                     defect_rate=rate, threshold=spec["max_defect_rate"],
                     wilson95=interval, decision_basis="census" if full else "unverified_supplier_sample",
                     examples=examples),
        limitations=[
            "Rights review is an attributed human attestation, not an automated legal opinion.",
            "PII detection covers selected keys and email patterns only; it is not exhaustive.",
            "Full coverage is the signed submitter's assertion; external source completeness is not verified.",
        ])
