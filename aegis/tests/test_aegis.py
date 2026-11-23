import copy
import json
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone

from aegis.engine import evaluate, wilson
from aegis.protocol import Invalid, digest, now, sign, validate_delivery, verify
from aegis.store import Store

KEY = "test-shared-secret-at-least-32-chars"
ROOT = Path(__file__).resolve().parents[1]


def fixture():
    return json.loads((ROOT / "fixtures" / "clean.json").read_text())


def review():
    return dict(confirmed=True, reviewer="Test reviewer", evidence_note="Synthetic fixture rights checked", reviewed_at=now())


class AcceptanceTests(unittest.TestCase):
    def test_clean_census_with_review_is_accepted(self):
        result = evaluate(fixture(), review())
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["quality"]["defect_rate"], 0)

    def test_supplier_cannot_self_approve_rights(self):
        result = evaluate(fixture())
        self.assertEqual(result["status"], "review")
        self.assertIn("rights.independent_review", [f["rule"] for f in result["findings"]])

    def test_real_row_defects_are_counted_without_double_counting(self):
        body = fixture()
        body["records"][1]["id"] = body["records"][0]["id"]
        body["records"][1]["text"] = ""
        body["records"][2]["language"] = 42
        result = evaluate(body, review())
        self.assertEqual(result["quality"]["duplicate_rows"], 1)
        self.assertEqual(result["quality"]["missing_rows"], 1)
        self.assertEqual(result["quality"]["schema_rows"], 1)
        self.assertEqual(result["quality"]["defect_rows"], 2)
        self.assertEqual(result["status"], "rejected")

    def test_blank_unique_keys_are_missing_not_duplicates(self):
        body = fixture()
        body["records"][0]["id"] = ""
        body["records"][1]["id"] = ""
        result = evaluate(body, review())
        self.assertEqual(result["quality"]["missing_rows"], 2)
        self.assertEqual(result["quality"]["duplicate_rows"], 0)

    def test_boolean_is_not_integer(self):
        body = fixture()
        body["spec"]["schema"]["text"] = "integer"
        body["records"][0]["text"] = True
        result = evaluate(body, review())
        self.assertEqual(result["quality"]["schema_rows"], 24)

    def test_sample_never_auto_accepts(self):
        body = fixture()
        body["manifest"].update(coverage="sample", record_count=100000)
        result = evaluate(body, review())
        self.assertEqual(result["status"], "review")
        self.assertEqual(result["quality"]["decision_basis"], "unverified_supplier_sample")

    def test_wilson_interval_known_zero_defects(self):
        low, high = wilson(0, 100)
        self.assertAlmostEqual(low, 0)
        self.assertAlmostEqual(high, .0369934982)
        self.assertEqual(wilson(0, 0), [0, 1])

    def test_missing_license_remains_review_after_human_attestation(self):
        body = fixture()
        body["manifest"].pop("license")
        self.assertEqual(evaluate(body, review())["status"], "review")

    def test_explicit_purpose_region_and_derivative_denials_reject(self):
        for field, value in (("purposes", ["evaluation"]), ("regions", ["US"]), ("derivatives", False)):
            body = fixture()
            body["manifest"][field] = value
            self.assertEqual(evaluate(body, review())["status"], "rejected")

    def test_expired_rights_and_prohibited_source_reject(self):
        for field, value in (("valid_until", "2000-01-01"), ("prohibited_source", True)):
            body = fixture()
            body["manifest"][field] = value
            self.assertEqual(evaluate(body, review())["status"], "rejected")

    def test_unknown_rights_types_do_not_pass(self):
        for field, value in (("rights_verified", "true"), ("derivatives", 1), ("purposes", "model_training")):
            body = fixture()
            body["manifest"][field] = value
            self.assertEqual(evaluate(body, review())["status"], "review")

    def test_pii_heuristic_requires_review_and_does_not_echo_data(self):
        body = fixture()
        body["records"][0]["email"] = "private@example.org"
        result = evaluate(body, review())
        self.assertEqual(result["status"], "review")
        self.assertNotIn("private@example.org", json.dumps(result))

    def test_tampering_and_forged_hashes_fail_at_protocol_boundary(self):
        artifact = sign(fixture(), KEY)
        artifact["records"][0]["text"] = "changed"
        with self.assertRaises(Invalid):
            validate_delivery(artifact, KEY)
        body = fixture()
        body["dataset_hash"] = "fake"
        with self.assertRaises(Invalid):
            validate_delivery(sign(body, KEY), KEY)

    def test_inconsistent_full_coverage_rejected(self):
        body = fixture()
        body["manifest"]["record_count"] = 25
        with self.assertRaises(Invalid):
            validate_delivery(sign(body, KEY), KEY)

    def test_stale_or_anonymous_attestation_rejected(self):
        for values in ({"reviewer": ""}, {"reviewed_at": (datetime.now(timezone.utc)-timedelta(days=2)).isoformat()}):
            value = review()
            value.update(values)
            with self.assertRaises(Invalid):
                evaluate(fixture(), value)

    def test_deliveries_are_immutable_and_reports_append(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / "aegis.db", KEY)
            artifact = sign(fixture(), KEY)
            first = store.inspect(artifact)
            second = store.inspect(artifact, review())
            self.assertNotEqual(first["report_id"], second["report_id"])
            self.assertEqual(len(store.snapshot()["reports"]), 2)
            body = fixture()
            body["records"][0]["text"] = "different"
            body["dataset_hash"] = digest(body["records"])
            with self.assertRaises(Invalid):
                store.inspect(sign(body, KEY), review())
            self.assertEqual(len(Store(Path(temp) / "aegis.db", KEY).snapshot()["reports"]), 2)

    def test_browser_integral_float_normalization_preserves_report(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp) / "aegis.db", KEY)
            report = store.inspect(sign(fixture(), KEY), review())
            browser = json.loads(json.dumps(report), parse_float=lambda v: int(float(v)) if float(v).is_integer() else float(v))
            self.assertEqual(verify(browser, KEY, "report")["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
