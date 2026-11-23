"""Regression tests for malformed upstream data and fake independent audit counts."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_policy import POLICY, TAXONOMY, asset, certificate, gold_rows
from visual_flywheel.calibration import calibrate, precision_lower_bound
from visual_flywheel.policy import classify, classify_batch, evidence_ok
from visual_flywheel.training import export_training


class AdversarialPolicyTests(unittest.TestCase):
    def test_malformed_records_do_not_crash_or_export(self):
        records = [None, [], "upstream failure"]
        for field, value in (("source", None), ("source", []), ("quality", None),
                             ("observations", [None]), ("observations", {}),
                             ("reference_reviews", [None]), ("synthetic", "false"),
                             ("asset_id", None), ("unit_id", []), ("cohort", {})):
            record = asset(); record[field] = value; records.append(record)
        record = asset(); record["source"]["rights"] = None; records.append(record)
        record = asset(); record["source"]["source_group"] = []; records.append(record)
        record = asset(); record["observations"][0]["label"] = []; records.append(record)
        results = classify_batch(records, POLICY, TAXONOMY)
        self.assertEqual(len(results), len(records))
        self.assertTrue(all(r["status"] in {"human_review", "quarantine"} for r in results))
        self.assertEqual(export_training(results, TAXONOMY), ([], []))

    def test_bad_observer_family_and_evidence_ref_are_not_support(self):
        for field, value in (("dependency_family", []), ("observer_id", {})):
            record = asset(); record["observations"][0][field] = value
            self.assertEqual(classify(record, POLICY, TAXONOMY)["status"], "human_review")
        record = asset(); record["observations"][0]["evidence"]["ref"] = {"fake": True}
        self.assertEqual(classify(record, POLICY, TAXONOMY)["status"], "human_review")

    def test_bad_temporal_relations_fail_closed(self):
        for relations in (None, {}, [None], ["before"]):
            evidence = {"channel": "visual", "ref": "test://clip", "interval": [0, 5],
                        "observed_times": [0, 5], "time_order_verified": True, "relations": relations}
            self.assertFalse(evidence_ok(evidence, "video", 5, True))

    def test_invalid_claim_scope_cannot_skip_whole_video_gate(self):
        for scope in ("whol_asset", None, [], True):
            record = asset(); record.update(modality="video", duration_seconds=20, claim_scope=scope)
            for observation in record["observations"]:
                observation["evidence"] = {"channel": "visual", "ref": "test://clip", "interval": [0, 20]}
            self.assertEqual(classify(record, POLICY, TAXONOMY)["status"], "human_review")

    def test_case_changed_hash_does_not_evade_split_leakage(self):
        a, b = asset(), asset()
        b["split"] = "test"; b["source"]["source_group"] = "different-group"
        b["source"]["sha256"] = a["source"]["sha256"].upper()
        self.assertTrue(all(r["status"] == "quarantine" for r in classify_batch([a, b], POLICY, TAXONOMY)))

    def test_invalid_reference_label_does_not_crash_export(self):
        record = asset()
        record["reference_reviews"] = [{"label": []}]
        result = classify(record, POLICY, TAXONOMY, certificate())
        self.assertEqual(export_training([result], TAXONOMY)[1], [])

    def test_malformed_configuration_rejected_before_acceptance(self):
        for key, value in (("minimum_independent_families", 0), ("familywise_alpha", 2),
                           ("target_precision", float("nan")), ("minimum_audit_n", True)):
            policy = copy.deepcopy(POLICY); policy[key] = value
            with self.assertRaises(ValueError): classify(asset(), policy, TAXONOMY)
        taxonomy = copy.deepcopy(TAXONOMY); taxonomy["labels"][0]["parent"] = "missing-parent"
        with self.assertRaises(ValueError): classify(asset(), POLICY, taxonomy)

    def test_engine_release_change_invalidates_prior_certificate(self):
        prior_certificate = certificate()
        self.assertEqual(classify(asset(), POLICY, TAXONOMY, prior_certificate)["status"], "accepted")
        with patch("visual_flywheel.policy.ENGINE_VERSION", "0.1.2-semantics-change"):
            result = classify(asset(), POLICY, TAXONOMY, prior_certificate)
        self.assertEqual(result["status"], "provisional")
        self.assertIn("missing_matching_precision_certificate", result["labels"][0]["reasons"])


class AdversarialCalibrationTests(unittest.TestCase):
    def test_same_audit_image_cannot_count_as_many_independent_groups(self):
        rows = gold_rows()
        for row in rows:
            if row["split"] == "audit": row["content_sha256"] = "a" * 64
        with self.assertRaisesRegex(ValueError, "Repeated exact content"):
            calibrate(rows, POLICY, TAXONOMY, True)

    def test_case_changed_content_cannot_hide_duplicate(self):
        rows = gold_rows(); rows[-1]["content_sha256"] = rows[-2]["content_sha256"].upper()
        with self.assertRaises(ValueError): calibrate(rows, POLICY, TAXONOMY, True)

    def test_calibration_rejects_non_hash_and_malformed_rows(self):
        for value in ("not-a-hash", [], None):
            rows = gold_rows(); rows[0]["content_sha256"] = value
            with self.assertRaises(ValueError): calibrate(rows, POLICY, TAXONOMY, True)
        for rows in ([None], ["error"], None):
            with self.assertRaises(ValueError): calibrate(rows, POLICY, TAXONOMY, True)
        for counts in ((True, 100, .05), (1, 1, float("nan")), (1.5, 2, .05)):
            with self.assertRaises(ValueError): precision_lower_bound(*counts)

    def test_cli_reports_bad_json_line_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            input_path = Path(directory) / "bad.jsonl"
            for value in ('NaN', '1e9999', 'Infinity'):
                input_path.write_text('{"score":' + value + '}\n', encoding="utf-8")
                result = subprocess.run([sys.executable, "-m", "visual_flywheel", "run", "--input", str(input_path),
                                         "--output-dir", str(Path(directory) / "out")],
                                        text=True, capture_output=True)
                self.assertEqual(result.returncode, 2)
                self.assertIn("bad.jsonl:1", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__": unittest.main()
