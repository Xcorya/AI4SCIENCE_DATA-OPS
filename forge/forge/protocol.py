"""Versioned, canonical JSON handoff protocol. Kept identical in AEGIS."""
import hashlib
import hmac
import json
import math
from datetime import datetime, timezone

VERSION = "forge-aegis/1"
DEMO_KEY = "PUBLIC-DEMO-KEY-NOT-FOR-REAL-DATA"


class Invalid(ValueError):
    pass


def canonical(value):
    def normalize(item):
        if isinstance(item, dict):
            return {k: normalize(v) for k, v in item.items()}
        if isinstance(item, list):
            return [normalize(v) for v in item]
        # Browser JSON.stringify converts 0.0 → 0 and 1.0 → 1.
        # Use one representation before hashing, including negative zero.
        if type(item) is float and math.isfinite(item) and item.is_integer():
            return int(item)
        return item
    return json.dumps(normalize(value), ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if result.tzinfo is None:
            raise ValueError()
        return result
    except (ValueError, TypeError, AttributeError):
        raise Invalid("Timestamp must be an ISO 8601 date with timezone")


def sign(body, key):
    return dict(body, signature=hmac.new(key.encode(), canonical(body), hashlib.sha256).hexdigest())


def verify(value, key, kind):
    if not isinstance(value, dict):
        raise Invalid("Signed artifact must be an object")
    body = {k: v for k, v in value.items() if k != "signature"}
    expected = hmac.new(key.encode(), canonical(body), hashlib.sha256).hexdigest()
    if not isinstance(value.get("signature"), str) or not hmac.compare_digest(value["signature"], expected):
        raise Invalid("Signature mismatch: use the same FORGE_AEGIS_KEY in both apps")
    if body.get("protocol") != VERSION or body.get("kind") != kind:
        raise Invalid("Unsupported artifact kind or protocol")
    return body


def integer(value, name, low=1, high=100000000):
    if type(value) is not int or not low <= value <= high:
        raise Invalid(f"{name} must be an integer in [{low}, {high}]")
    return value


def number(value, name, low=0, high=1):
    if type(value) not in (int, float) or not low <= value <= high or not math.isfinite(value):
        raise Invalid(f"{name} must be a finite number in [{low}, {high}]")
    return value


def text(value, name, maximum=200):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise Invalid(f"{name} must be nonempty text, at most {maximum} characters")
    return value.strip()


def identifier(value, name="resource ID"):
    result = text(value, name)
    if value != result:
        raise Invalid(f"{name} cannot contain surrounding whitespace")
    return result


def validate_spec(value):
    if not isinstance(value, dict):
        raise Invalid("spec must be an object")
    result = {
        "title": text(value.get("title"), "title"),
        "quantity": integer(value.get("quantity"), "quantity", high=5000),
        "budget_cents": integer(value.get("budget_cents"), "budget_cents"),
        "currency": text(value.get("currency"), "currency", 3).upper(),
        "max_days": integer(value.get("max_days"), "max_days", high=3650),
        "purpose": text(value.get("purpose"), "purpose"),
        "region": text(value.get("region"), "region"),
        "max_defect_rate": number(value.get("max_defect_rate"), "max_defect_rate"),
    }
    if result["currency"] not in ("USD", "CNY", "EUR"):
        raise Invalid("currency must be USD, CNY or EUR")
    for field in ("allow_derivatives", "allow_pii"):
        if type(value.get(field)) is not bool:
            raise Invalid(f"{field} must be boolean")
        result[field] = value[field]
    schema = value.get("schema")
    if not isinstance(schema, dict) or not schema or len(schema) > 50:
        raise Invalid("schema must contain 1–50 required fields")
    for field, kind in schema.items():
        text(field, "schema field", 80)
        if kind not in ("string", "integer", "number", "boolean"):
            raise Invalid("schema types: string, integer, number, boolean")
    unique_key = text(value.get("unique_key"), "unique_key", 80)
    if unique_key not in schema:
        raise Invalid("unique_key must be a required schema field")
    result.update(schema=dict(schema), unique_key=unique_key)
    return result


def validate_delivery(artifact, key):
    body = verify(artifact, key, "delivery")
    for field in ("order_id", "delivery_id"):
        identifier(body.get(field), field)
    text(body.get("created_at"), "created_at")
    timestamp(body["created_at"])
    spec = validate_spec(body.get("spec"))
    if spec != body["spec"] or digest(spec) != body.get("spec_hash"):
        raise Invalid("Specification hash mismatch")
    records = body.get("records")
    if not isinstance(records, list) or not 1 <= len(records) <= 5000:
        raise Invalid("records must be a nonempty array, at most 5000 rows")
    if any(not isinstance(row, dict) for row in records):
        raise Invalid("Every record must be a JSON object")
    if digest(records) != body.get("dataset_hash"):
        raise Invalid("Dataset hash mismatch")
    manifest = body.get("manifest")
    if not isinstance(manifest, dict):
        raise Invalid("manifest must be an object")
    integer(manifest.get("record_count"), "record_count")
    if manifest.get("coverage") not in ("full", "sample"):
        raise Invalid("coverage must be full or sample")
    if manifest["coverage"] == "full" and manifest["record_count"] != len(records):
        raise Invalid("Full coverage requires record_count to equal the supplied rows")
    if manifest["record_count"] < len(records):
        raise Invalid("record_count cannot be smaller than supplied rows")
    return body
