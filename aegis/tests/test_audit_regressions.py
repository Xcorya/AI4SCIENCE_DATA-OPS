import json
import sqlite3
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from aegis.engine import evaluate
from aegis.protocol import digest, now, sign, validate_delivery
from aegis.store import Store

ROOT = Path(__file__).resolve().parents[1]
KEY = "test-secret-at-least-32-characters"


def fixture():
    return json.loads((ROOT/"fixtures"/"clean.json").read_text())


def review():
    return dict(confirmed=True, reviewer="Synthetic audit reviewer",
                evidence_note="Synthetic fixture grant verified", reviewed_at=now())


class AuditRegressions(unittest.TestCase):
    def test_integer_valued_float_has_same_decision_before_and_after_storage(self):
        body = fixture()
        body["spec"]["schema"]["id"] = "integer"
        body["records"] = [dict(row, id=float(i)) for i, row in enumerate(body["records"])]
        body["spec_hash"], body["dataset_hash"] = digest(body["spec"]), digest(body["records"])
        artifact = sign(body, KEY)
        self.assertEqual(evaluate(body, review())["status"], "accepted")
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)/"aegis.db", KEY)
            first = store.inspect(artifact, review())
            saved = store.snapshot()["deliveries"][0]
            validate_delivery(saved, KEY)
            second = store.inspect(saved, review())
            self.assertEqual(first["status"], second["status"])
            self.assertEqual(first["quality"], second["quality"])

    def test_fractional_number_still_violates_integer_schema(self):
        body = fixture()
        body["spec"]["schema"]["id"] = "integer"
        body["records"] = [dict(row, id=i+.5) for i, row in enumerate(body["records"])]
        result = evaluate(body, review())
        self.assertEqual(result["quality"]["schema_rows"], 24)
        self.assertEqual(result["status"], "rejected")

    def test_accepted_report_does_not_outlive_license(self):
        body = fixture()
        body["manifest"]["valid_until"] = datetime.now(timezone.utc).date().isoformat()
        with tempfile.TemporaryDirectory() as temp:
            report = Store(Path(temp)/"aegis.db",KEY).inspect(sign(body,KEY),review())
        self.assertEqual(report["status"], "accepted")
        expected = datetime.combine(date.fromisoformat(body["manifest"]["valid_until"]), time.max, tzinfo=timezone.utc)
        self.assertEqual(datetime.fromisoformat(report["expires_at"]), expected)

    def test_long_license_still_caps_report_at_seven_days(self):
        with tempfile.TemporaryDirectory() as temp:
            report = Store(Path(temp)/"aegis.db",KEY).inspect(sign(fixture(),KEY),review())
        self.assertEqual(datetime.fromisoformat(report["expires_at"])-datetime.fromisoformat(report["issued_at"]),
                         timedelta(days=7))

    def test_expired_license_can_still_produce_a_consumable_rejection(self):
        body = fixture()
        body["manifest"]["valid_until"] = "2000-01-01"
        with tempfile.TemporaryDirectory() as temp:
            report = Store(Path(temp)/"aegis.db",KEY).inspect(sign(body,KEY),review())
        self.assertEqual(report["status"], "rejected")
        self.assertGreater(datetime.fromisoformat(report["expires_at"]), datetime.fromisoformat(report["issued_at"]))

    def test_raw_delivery_and_report_exports_keep_binding(self):
        body = fixture()
        body["records"][0]["large_integer"] = 9007199254740993
        body["dataset_hash"] = digest(body["records"])
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)/"aegis.db",KEY)
            report = store.inspect(sign(body,KEY),review())
            exported = store.export_artifact("reports",report["report_id"])
            self.assertEqual(exported["signature"], report["signature"])
            saved = store.snapshot()["deliveries"][0]
            self.assertEqual(saved["records"][0]["large_integer"],9007199254740993)
            validate_delivery(saved,KEY)

    def test_connection_context_closes_connection(self):
        with tempfile.TemporaryDirectory() as temp:
            store = Store(Path(temp)/"aegis.db",KEY)
            with store.connect() as connection:
                connection.execute("SELECT 1")
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute("SELECT 1")
