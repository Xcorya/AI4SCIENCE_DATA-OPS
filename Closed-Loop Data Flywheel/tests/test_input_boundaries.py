"""Regressions reproduced during the live end-to-end verification."""
import json
import tempfile
import unittest
from pathlib import Path

from helix.extractors import extract
from helix.ingest import import_manifest
from helix.pipeline import run_pipeline
from helix.store import Store, split_for


class InputBoundaryTest(unittest.TestCase):
    def test_empty_xyz_is_a_validation_error(self):
        with self.assertRaisesRegex(ValueError, "atom count"):
            extract(b"", {"format": "xyz"})

    def test_missing_units_and_invalid_settings_are_validation_errors(self):
        for spec in (None, [], {"format": "csv", "column": "v"},
                     {"format": "stl", "unit": ""}):
            with self.subTest(spec=spec), self.assertRaises(ValueError):
                extract(b"v\n1\n2\n", spec)

    def test_bad_file_does_not_abort_later_manifest_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "db")
            Path(directory, "empty.xyz").write_bytes(b"")
            Path(directory, "good.csv").write_text("v\n3\n7\n")
            common = {"title": "input boundary", "source_id": "input-test",
                      "source_url": "demo://input-test", "license": "CC0-1.0",
                      "modality": "table", "text": "original input", "is_demo": True}
            items = [dict(common, local_file="empty.xyz", extract={"format": "xyz"}),
                     dict(common, local_file="good.csv",
                          extract={"format": "csv", "column": "v", "unit": "Pa"})]
            result = import_manifest(store, items, directory)
            self.assertEqual(result["created"], 1)
            self.assertEqual(len(result["errors"]), 1)
            self.assertEqual(result["errors"][0]["index"], 0)

    def test_invalid_fact_schema_is_rejected_before_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            common = {"title": "invalid facts", "source_id": "invalid-facts",
                      "source_url": "demo://invalid", "modality": "table",
                      "text": "fact validation", "license": "CC0-1.0"}
            for facts in ([], {}, {"quantity": "pressure", "unit": "Pa", "values": [True, 2]},
                          {"quantity": "pressure", "unit": "", "values": [1, 2]},
                          {"quantity": "pressure", "unit": "Pa", "values": [1, float("inf")]}):
                with self.subTest(facts=facts), self.assertRaises(ValueError):
                    store.add_asset(dict(common, facts=facts))
            self.assertEqual(store.all("assets"), [])

    def test_non_object_evidence_is_quarantined_without_batch_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(directory)
            group = next("input-" + str(i) for i in range(100)
                         if split_for("input-" + str(i)) == "train")
            store.add_asset({
                "title": "valid facts, invalid evidence", "source_id": group,
                "source_url": "demo://invalid-evidence", "modality": "table",
                "license": "CC0-1.0", "text": "[1,2,3]", "is_demo": True,
                "facts": {"quantity": "pressure", "unit": "Pa", "values": [1, 2, 3]},
            })
            result = run_pipeline(store, 4)
            self.assertEqual(result["created"], 4)
            self.assertEqual(result["accepted"], 0)
            self.assertEqual(result["errors"], [])
            self.assertTrue(all(t["status"] == "review" for t in store.all("tasks")))


if __name__ == "__main__":
    unittest.main()
