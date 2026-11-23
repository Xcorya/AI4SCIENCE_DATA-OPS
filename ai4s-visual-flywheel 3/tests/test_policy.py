import copy
import hashlib
import json
import unittest
from pathlib import Path

from visual_flywheel.policy import classify, classify_batch, evidence_ok, fingerprint, interval_coverage
from visual_flywheel.calibration import calibrate, precision_lower_bound, _binomial_upper_tail
from visual_flywheel.training import export_training, reward

ROOT = Path(__file__).resolve().parents[1]
POLICY = json.loads((ROOT / "configs/policy.json").read_text())
TAXONOMY = json.loads((ROOT / "configs/taxonomy.json").read_text())
FIXTURE = json.loads((ROOT / "examples/observations.jsonl").read_text().splitlines()[0])


def asset():
    result = copy.deepcopy(FIXTURE)
    result["synthetic"] = False  # Unit-test stub; no real performance measurement.
    return result


def gold_rows():
    rows = []
    for split, count in (("tune", 35), ("audit", 200)):
        for index in range(count):
            group = f"{split}-{index}"
            rows.append({"label": "appearance.plot.line", "modality": "image", "split": split,
                         "score": .95, "correct": True, "source_group": group,
                         "content_sha256": hashlib.sha256(group.encode()).hexdigest(),
                         "reference_id": f"unit-test-reference-{group}", "cohort": "synthetic_demo_v1",
                         "hard_gate_eligible": True,
                         "policy_fingerprint": fingerprint(POLICY, TAXONOMY)})
    return rows


def certificate():
    return calibrate(gold_rows(), POLICY, TAXONOMY, True)


class PolicyTests(unittest.TestCase):
    def test_no_certificate_is_provisional_and_exports_empty(self):
        result = classify(asset(), POLICY, TAXONOMY)
        self.assertEqual(result["labels"][0]["status"], "provisional")
        self.assertEqual(export_training([result], TAXONOMY), ([], []))

    def test_best_of_three_same_family_does_not_count_three(self):
        record = asset()
        record["observations"] = [copy.deepcopy(record["observations"][0]) for _ in range(3)]
        result = classify(record, POLICY, TAXONOMY, certificate())
        self.assertEqual(result["status"], "human_review")
        self.assertIn("insufficient_independent_support", result["labels"][0]["reasons"])

    def test_ocr_only_cannot_support_visual_label(self):
        record = asset()
        for item in record["observations"]:
            item["evidence"]["channel"] = "ocr"
        result = classify(record, POLICY, TAXONOMY, certificate())
        self.assertEqual(result["status"], "human_review")

    def test_grounded_contradiction_blocks_consensus(self):
        record = asset()
        contradiction = copy.deepcopy(record["observations"][0])
        contradiction.update(verdict="contradict", dependency_family="third-family")
        record["observations"].append(contradiction)
        result = classify(record, POLICY, TAXONOMY, certificate())
        self.assertIn("grounded_contradiction", result["labels"][0]["reasons"])
        self.assertEqual(result["status"], "human_review")

    def test_counterevidence_does_not_need_positive_method_signature(self):
        record = asset()
        for observation in record["observations"]:
            observation["label"] = "appearance.cad_render"
            observation["evidence"]["checks"] = {"cad_provenance_confirmed": {"passed": True, "ref": "test://cad-source"}}
        counterexample = copy.deepcopy(record["observations"][0])
        counterexample.update(verdict="contradict", dependency_family="known-photograph-source")
        del counterexample["evidence"]["checks"]
        record["observations"].append(counterexample)
        result = classify(record, POLICY, TAXONOMY)
        self.assertEqual(result["status"], "human_review")
        self.assertIn("grounded_contradiction", result["labels"][0]["reasons"])

    def test_rights_unknown_quarantines(self):
        record = asset()
        record["source"]["rights"]["status"] = "unknown"
        self.assertEqual(classify(record, POLICY, TAXONOMY)["status"], "quarantine")

    def test_child_does_not_appear_from_parent(self):
        record = asset()
        for item in record["observations"]:
            item["label"] = "appearance.plot"
        labels = classify(record, POLICY, TAXONOMY)["labels"]
        self.assertEqual([x["id"] for x in labels], ["appearance.plot"])

    def test_certificate_requires_matching_cohort_and_policy(self):
        record = asset()
        valid = certificate()
        self.assertEqual(classify(record, POLICY, TAXONOMY, valid)["status"], "accepted")
        invalid = copy.deepcopy(valid)
        invalid["cohort"] = "another-cohort"
        self.assertEqual(classify(record, POLICY, TAXONOMY, invalid)["status"], "provisional")
        invalid = copy.deepcopy(valid)
        invalid["policy_fingerprint"] = "wrong"
        self.assertEqual(classify(record, POLICY, TAXONOMY, invalid)["status"], "provisional")

    def test_cross_split_group_or_exact_copy_quarantines(self):
        a, b = asset(), asset()
        b["split"] = "test"
        b["source"]["source_group"] = "different-group"
        outcomes = classify_batch([a, b], POLICY, TAXONOMY, certificate())
        self.assertTrue(all(x["status"] == "quarantine" for x in outcomes))
        self.assertEqual(export_training(outcomes, TAXONOMY), ([], []))

    def test_temporal_sort_and_relation_validation(self):
        evidence = {"channel": "visual", "ref": "test", "interval": [0, 10],
                    "observed_times": [0, 5, 10], "time_order_verified": True}
        self.assertTrue(evidence_ok(evidence, "video", 10, True))
        evidence["observed_times"] = [10, 5, 0]
        self.assertFalse(evidence_ok(evidence, "video", 10, True))
        evidence["observed_times"] = [0, 5, 10]
        evidence["relations"] = [{"before": [5, 7], "after": [2, 4]}]
        self.assertFalse(evidence_ok(evidence, "video", 10, True))

    def test_union_coverage_avoids_double_counting(self):
        self.assertAlmostEqual(interval_coverage([[0, 5], [2, 5]], 10), .5)

    def test_invalid_box_and_nan_are_not_support(self):
        record = asset()
        record["observations"][0]["score"] = float("nan")
        record["observations"][1]["evidence"]["bbox"] = [.9, .1, .1, .9]
        self.assertEqual(classify(record, POLICY, TAXONOMY)["status"], "human_review")

    def test_unit_identity_and_quality_gate(self):
        record = asset()
        record["observations"][0]["unit_id"] = "different-panel"
        self.assertEqual(classify(record, POLICY, TAXONOMY, certificate())["status"], "human_review")
        record = asset()
        record["quality"]["usable"] = False
        self.assertIn("missing_or_failed_quality_gate", classify(record, POLICY, TAXONOMY)["warnings"])

    def test_missing_required_metadata_check_blocks_fine_tag(self):
        record = asset()
        for observation in record["observations"]:
            observation["label"] = "appearance.cad_render"
        result = classify(record, POLICY, TAXONOMY)
        self.assertEqual(result["status"], "human_review")
        for observation in record["observations"]:
            observation["evidence"]["checks"] = {"cad_provenance_confirmed": {"passed": True, "ref": "test://metadata"}}
        self.assertEqual(classify(record, POLICY, TAXONOMY)["status"], "provisional")

    def test_sparse_frames_never_count_as_whole_video_coverage(self):
        record = asset()
        record.update(modality="video", duration_seconds=20, claim_scope="whole_asset")
        for observation in record["observations"]:
            observation["evidence"] = {"channel": "visual", "ref": "test://clip", "interval": [0, 20],
                                         "observed_times": [0, 20], "observed_segments": [[0, 1], [19, 20]]}
        result = classify(record, POLICY, TAXONOMY)
        self.assertEqual(result["labels"][0]["visual_coverage"], .1)
        self.assertIn("insufficient_whole_video_coverage", result["labels"][0]["reasons"])

    def test_inconsistent_certificate_statistics_do_not_accept(self):
        invalid = certificate()
        invalid["labels"]["appearance.plot.line|image"]["audit_correct"] = 100
        self.assertEqual(classify(asset(), POLICY, TAXONOMY, invalid)["status"], "provisional")
        invalid["labels"]["appearance.plot.line|image"]["audit_n"] = "not-an-integer"
        self.assertEqual(classify(asset(), POLICY, TAXONOMY, invalid)["status"], "provisional")


class CalibrationTests(unittest.TestCase):
    def test_exact_lower_bound_and_general_inversion(self):
        self.assertAlmostEqual(precision_lower_bound(100, 100, .05), .05 ** .01)
        bound = precision_lower_bound(90, 100, .05)
        self.assertAlmostEqual(_binomial_upper_tail(100, 90, bound), .05, places=9)
        self.assertEqual(precision_lower_bound(0, 100, .05), 0)

    def test_great_empirical_accuracy_with_tiny_audit_is_not_certified(self):
        rows = [x for x in gold_rows() if x["split"] == "tune"] + gold_rows()[-20:]
        item = calibrate(rows, POLICY, TAXONOMY, True)["labels"]["appearance.plot.line|image"]
        self.assertFalse(item["certified"])

    def test_audit_does_not_choose_a_better_threshold(self):
        rows = gold_rows()
        for item in rows:
            if item["split"] == "audit":
                item["score"] = .94
        item = calibrate(rows, POLICY, TAXONOMY, True)["labels"]["appearance.plot.line|image"]
        self.assertEqual(item["threshold"], .95)
        self.assertEqual(item["audit_n"], 0)

    def test_cross_split_duplicate_and_repeated_groups_rejected(self):
        rows = gold_rows()
        rows[-1]["content_sha256"] = rows[0]["content_sha256"]
        with self.assertRaises(ValueError):
            calibrate(rows, POLICY, TAXONOMY, True)
        rows = gold_rows()
        rows[-1]["source_group"] = rows[-2]["source_group"]
        with self.assertRaises(ValueError):
            calibrate(rows, POLICY, TAXONOMY, True)

    def test_synthetic_and_unverified_provenance_cannot_certify(self):
        rows = gold_rows()
        self.assertFalse(any(x["certified"] for x in calibrate(rows, POLICY, TAXONOMY)["labels"].values()))
        rows[0]["synthetic"] = True
        self.assertFalse(any(x["certified"] for x in calibrate(rows, POLICY, TAXONOMY, True)["labels"].values()))

    def test_raw_observer_scores_without_hard_gate_eligibility_are_rejected(self):
        rows = gold_rows()
        del rows[0]["hard_gate_eligible"]
        with self.assertRaises(ValueError):
            calibrate(rows, POLICY, TAXONOMY, True)


class TrainingTests(unittest.TestCase):
    def test_rl_requires_independent_external_reference(self):
        record = asset()
        result = classify(record, POLICY, TAXONOMY, certificate())
        sft, rl = export_training([result], TAXONOMY)
        self.assertEqual(len(sft), 1)
        self.assertEqual(rl, [])
        record["reference_reviews"] = [{"label": "appearance.plot.line", "status": "verified",
                                         "unit_id": record["unit_id"],
                                         "method": "human", "reviewer_id": "test-reviewer",
                                         "reference_id": "test-gold", "bbox": [.1, .1, .9, .9],
                                         "question": "Identify and locate the plot in the left panel."}]
        result = classify(record, POLICY, TAXONOMY, certificate())
        _, rl = export_training([result], TAXONOMY)
        self.assertEqual(len(rl), 1)
        self.assertNotIn("appearance.plot.line", rl[0]["prompt"])
        self.assertNotIn("target_locator", rl[0])
        record["reference_reviews"][0]["method"] = "vlm_self_judge"
        self.assertEqual(export_training([classify(record, POLICY, TAXONOMY, certificate())], TAXONOMY)[1], [])

    def test_wrong_label_cannot_win_grounding_reward(self):
        reference = {"label": "appearance.plot.line", "bbox": [.1, .1, .9, .9]}
        self.assertEqual(reward({"label": "appearance.plot.bar", "bbox": [.1, .1, .9, .9]}, reference)["reward"], 0)
        self.assertEqual(reward({"label": "appearance.plot.line", "bbox": [.1, .1, .9, .9]}, reference)["reward"], 1)
        self.assertEqual(reward({"label": "appearance.plot.line", "bbox": [0, 0, .1, .1]}, reference)["reward"], 0)

    def test_temporal_reward_rejects_out_of_duration_and_malformed_refs(self):
        reference = {"label": "event.fluid_flow", "interval": [2, 4], "duration_seconds": 4}
        self.assertEqual(reward({"label": "event.fluid_flow", "interval": [2, 4]}, reference)["reward"], 1)
        # IoU=2/3 would pass without the actual source duration boundary.
        self.assertEqual(reward({"label": "event.fluid_flow", "interval": [2, 5]}, reference)["reward"], 0)
        self.assertEqual(reward({"label": "event.fluid_flow", "interval": [2, 4]}, {"label": "event.fluid_flow", "interval": [2, 4]})["reward"], 0)
        self.assertEqual(reward({"bbox": [0, 0, 1, 1]}, {"bbox": [0, 0, 1, 1]})["reward"], 0)
        self.assertEqual(reward({"label": "event.fluid_flow", "interval": [2, 4], "extra": True}, reference)["reward"], 0)

    def test_video_reference_must_match_actual_source_duration(self):
        record = asset()
        record.update(modality="video", duration_seconds=4)
        for observation in record["observations"]:
            observation["evidence"] = {"channel": "visual", "ref": "test://clip", "interval": [2, 4]}
        rows = gold_rows()
        for row in rows:
            row["modality"] = "video"
        video_certificate = calibrate(rows, POLICY, TAXONOMY, True)
        record["reference_reviews"] = [{"label": "appearance.plot.line", "unit_id": record["unit_id"],
                                         "status": "verified", "method": "human", "reviewer_id": "reviewer",
                                         "reference_id": "gold", "question": "Identify the plot shown in the last segment.",
                                         "interval": [2, 4], "duration_seconds": 100}]
        result = classify(record, POLICY, TAXONOMY, video_certificate)
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(export_training([result], TAXONOMY)[1], [])
        record["reference_reviews"][0]["duration_seconds"] = 4
        result = classify(record, POLICY, TAXONOMY, video_certificate)
        rl = export_training([result], TAXONOMY)[1]
        self.assertEqual(len(rl), 1)
        self.assertEqual(rl[0]["reference"]["duration_seconds"], 4)

    def test_synthetic_never_exports(self):
        result = classify(copy.deepcopy(FIXTURE), POLICY, TAXONOMY, certificate())
        self.assertEqual(export_training([result], TAXONOMY), ([], []))

    def test_validation_and_test_never_enter_training(self):
        for split in ("validation", "test", "tune", "audit"):
            record = asset()
            record["split"] = split
            result = classify(record, POLICY, TAXONOMY, certificate())
            self.assertEqual(result["status"], "accepted")
            self.assertEqual(export_training([result], TAXONOMY), ([], []))


if __name__ == "__main__":
    unittest.main()
