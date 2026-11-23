import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from forge.engine import rank
from forge.protocol import Invalid, validate_spec
from forge.store import Store, demo_manifest, demo_records, demo_spec


class AuditRegressions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = Store(Path(self.temp.name) / "forge.db", "test-secret-at-least-32-characters")
        self.store.seed()
        self.demand = self.store.snapshot()["demands"][0]
        self.quote = self.store.ranking(self.demand["id"])[0]

    def draft(self):
        return self.store.draft(self.demand["id"], self.quote["id"])

    def test_padded_demand_id_cannot_create_duplicate_purchase(self):
        self.draft()
        with self.assertRaises(Invalid):
            self.store.draft(" "+self.demand["id"]+" ", self.quote["id"])
        self.assertEqual(len(self.store.snapshot()["orders"]), 1)

    def test_padded_quote_parent_is_rejected(self):
        with self.assertRaises(Invalid):
            self.store.quote(" "+self.demand["id"], self.quote)
        self.assertEqual(len(self.store.snapshot()["quotes"]), 4)

    def test_padded_release_does_not_report_unpersisted_success(self):
        order = self.draft()
        with self.assertRaises(Invalid):
            self.store.release(order["id"]+" ")
        self.assertEqual(self.store.snapshot()["orders"][0]["state"], "draft")

    def test_padded_delivery_does_not_create_orphaned_artifact(self):
        order = self.draft()
        self.store.release(order["id"])
        with self.assertRaises(Invalid):
            self.store.deliver(" "+order["id"], {"manifest":demo_manifest(), "records":demo_records()})
        self.assertEqual(self.store.snapshot()["deliveries"], [])

    def test_subnormal_quality_remains_sortable_and_serializable(self):
        quote = copy.deepcopy(self.quote)
        quote["declared_quality"] = 5e-324
        rows = rank(self.demand["spec"], [quote])
        self.assertIsNone(rows[0]["cost_per_expected_usable"])
        json.dumps(rows, allow_nan=False)
        saved = self.store.quote(self.demand["id"], quote)
        self.store.draft(self.demand["id"], saved["id"])

    def test_ranking_uses_exact_cost_not_rounded_display(self):
        spec = demo_spec()
        spec.update(quantity=5000, budget_cents=1000000)
        cheap = copy.deepcopy(self.quote)
        cheap.update(id="cheap", capacity=5000, unit_cents=100, fee_cents=0,
                     declared_quality=1, lead_days=2)
        faster = dict(cheap, id="faster", fee_cents=1, lead_days=1)
        rows = rank(spec, [faster, cheap])
        self.assertEqual(rows[0]["cost_per_expected_usable"], rows[1]["cost_per_expected_usable"])
        self.assertEqual(rows[0]["id"], "cheap")

    def test_huge_out_of_range_integer_is_validation_error(self):
        spec = demo_spec()
        spec["max_defect_rate"] = 10**400
        with self.assertRaises(Invalid):
            validate_spec(spec)

    def test_connection_context_closes_the_connection(self):
        with self.store.connect() as connection:
            self.assertEqual(connection.execute("SELECT 1").fetchone()[0], 1)
        with self.assertRaises(sqlite3.ProgrammingError):
            connection.execute("SELECT 1")

    def test_export_preserves_integer_outside_javascript_safe_range(self):
        order = self.draft()
        self.store.release(order["id"])
        records = demo_records()
        records[0]["large_integer"] = 9007199254740993
        artifact = self.store.deliver(order["id"], {"manifest":demo_manifest(), "records":records})
        exported = self.store.export_artifact("deliveries", artifact["delivery_id"])
        self.assertEqual(exported["records"][0]["large_integer"], 9007199254740993)
        self.assertEqual(exported["signature"], artifact["signature"])
