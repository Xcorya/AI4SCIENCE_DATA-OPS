import copy
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

from forge.engine import rank, validate_quote
from forge.protocol import VERSION, Invalid, digest, now, sign, validate_delivery, validate_spec
from forge.store import Store, demo_manifest, demo_records, demo_spec

KEY = "test-shared-secret-at-least-32-chars"


class ProcurementTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "forge.db", KEY)
        self.store.seed()
        self.demand = self.store.snapshot()["demands"][0]

    def ordered(self):
        quote = self.store.ranking(self.demand["id"])[0]
        order = self.store.draft(self.demand["id"], quote["id"])
        self.store.release(order["id"])
        return order

    def delivery(self):
        order = self.ordered()
        return self.store.deliver(order["id"], {"manifest": demo_manifest(), "records": demo_records()})

    def report(self, delivery, status="accepted"):
        body = {k: v for k, v in delivery.items() if k != "signature"}
        issued = datetime.now(timezone.utc)
        return sign(dict(protocol=VERSION, kind="report", report_id="RPT-test",
                         order_id=body["order_id"], delivery_id=body["delivery_id"],
                         spec_hash=body["spec_hash"], dataset_hash=body["dataset_hash"],
                         envelope_hash=digest(body), status=status, issued_at=issued.isoformat(),
                         expires_at=(issued + timedelta(days=7)).isoformat()), KEY)

    def test_hard_filters_and_value_ranking(self):
        rows = self.store.ranking(self.demand["id"])
        self.assertEqual(sum(r["eligible"] for r in rows), 2)
        self.assertIn("Lumen", rows[0]["vendor"])
        self.assertEqual(rows[0]["total_cents"], 82800)
        self.assertTrue(all(r["pareto"] for r in rows[:2]))
        self.assertFalse(next(r for r in rows if "Budget" in r["vendor"])["eligible"])

    def test_ineligible_quote_cannot_order(self):
        row = next(r for r in self.store.ranking(self.demand["id"]) if not r["eligible"])
        with self.assertRaises(Invalid):
            self.store.draft(self.demand["id"], row["id"])
        self.assertEqual(self.store.snapshot()["orders"], [])

    def test_no_delivery_before_release(self):
        q = self.store.ranking(self.demand["id"])[0]
        order = self.store.draft(self.demand["id"], q["id"])
        with self.assertRaises(Invalid):
            self.store.deliver(order["id"], {"manifest": demo_manifest(), "records": demo_records()})

    def test_concurrent_duplicate_purchase_is_blocked(self):
        q = self.store.ranking(self.demand["id"])[0]
        def attempt(_):
            try:
                self.store.draft(self.demand["id"], q["id"])
                return True
            except Invalid:
                return False
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(attempt, range(2)))
        self.assertEqual(sum(results), 1)

    def test_tampered_delivery_fails(self):
        delivery = self.delivery()
        delivery["records"][0]["text"] = "modified"
        with self.assertRaises(Invalid):
            validate_delivery(delivery, KEY)

    def test_false_full_coverage_rolls_back(self):
        order = self.ordered()
        manifest = demo_manifest()
        manifest["record_count"] = 100
        with self.assertRaises(Invalid):
            self.store.deliver(order["id"], {"manifest": manifest, "records": demo_records()})
        self.assertEqual(self.store.snapshot()["orders"][0]["state"], "ordered")
        self.assertFalse(self.store.snapshot()["deliveries"])

    def test_unsigned_or_tampered_report_cannot_accept(self):
        delivery = self.delivery()
        report = self.report(delivery)
        report["status"] = "review"
        with self.assertRaises(Invalid):
            self.store.apply_report(report)
        self.assertEqual(self.store.snapshot()["orders"][0]["state"], "delivered")

    def test_wrong_dataset_binding_fails_even_with_valid_signature(self):
        delivery = self.delivery()
        report = self.report(delivery)
        report["dataset_hash"] = "wrong"
        report = sign({k: v for k, v in report.items() if k != "signature"}, KEY)
        with self.assertRaises(Invalid):
            self.store.apply_report(report)

    def test_acceptance_is_persisted_and_identical_replay_is_idempotent(self):
        delivery = self.delivery()
        report = self.report(delivery)
        self.assertEqual(self.store.apply_report(report)["state"], "accepted")
        events = len(self.store.snapshot()["events"])
        self.store.apply_report(report)
        self.assertEqual(len(self.store.snapshot()["events"]), events)
        reopened = Store(Path(self.temp.name) / "forge.db", KEY)
        self.assertEqual(reopened.snapshot()["orders"][0]["report_id"], "RPT-test")

    def test_old_report_cannot_accept_redelivery(self):
        delivery = self.delivery()
        self.store.apply_report(self.report(delivery, "rejected"))
        self.store.deliver(delivery["order_id"], {"manifest": demo_manifest(), "records": demo_records()})
        with self.assertRaises(Invalid):
            self.store.apply_report(self.report(delivery))

    def test_expired_report_fails(self):
        delivery = self.delivery()
        report = self.report(delivery)
        report["issued_at"] = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        report["expires_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        report = sign({k: v for k, v in report.items() if k != "signature"}, KEY)
        with self.assertRaises(Invalid):
            self.store.apply_report(report)

    def test_zero_quality_ranks_without_division_by_zero(self):
        q = copy.deepcopy(self.store.snapshot()["quotes"][0])
        q["declared_quality"] = 0
        row = rank(self.demand["spec"], [q])[0]
        self.assertIsNone(row["cost_per_expected_usable"])

    def test_browser_integral_float_normalization_preserves_signature(self):
        delivery = self.delivery()
        report = self.report(delivery)
        body = {k: v for k, v in report.items() if k != "signature"}
        body["quality"] = {"defect_rate": 0.0, "wilson95": [0.0, 0.13797620467498017]}
        report = sign(body, KEY)
        browser = json.loads(json.dumps(report), parse_float=lambda v: int(float(v)) if float(v).is_integer() else float(v))
        self.assertEqual(self.store.apply_report(browser)["state"], "accepted")

    def test_boolean_quantity_and_nonfinite_quality_rejected(self):
        spec = demo_spec()
        spec["quantity"] = True
        with self.assertRaises(Invalid):
            validate_spec(spec)
        quote = copy.deepcopy(self.store.snapshot()["quotes"][0])
        quote["declared_quality"] = float("nan")
        with self.assertRaises(Invalid):
            validate_quote(quote)


if __name__ == "__main__":
    unittest.main()
