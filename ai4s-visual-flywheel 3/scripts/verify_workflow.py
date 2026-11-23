"""Exercise CLI contracts end to end using temporary test doubles, never media.

The non-synthetic trust flags below deliberately simulate a trusted upstream in a
temporary test environment. No generated certificate or training data is retained
or presented as real validation. This script measures software behavior only.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--installed", action="store_true", help="Test an installed wheel, without PYTHONPATH")
    parser.add_argument("--output", default="work/verification/workflow-results.json")
    args = parser.parse_args()
    # Keep the venv executable symlink: resolving it would invoke the host Python
    # and lose the virtual environment's installed package.
    runtime = os.path.abspath(args.python)
    environment = dict(os.environ)
    if args.installed:
        environment.pop("PYTHONPATH", None)
    else:
        environment["PYTHONPATH"] = str(ROOT / "src")
    checks = []

    with tempfile.TemporaryDirectory(prefix="flywheel-contract-") as temporary:
        directory = Path(temporary)

        def invoke(*arguments, expected=0):
            result = subprocess.run([runtime, "-m", "visual_flywheel", *arguments], cwd=directory,
                                    env=environment, text=True, capture_output=True, timeout=30)
            if result.returncode != expected:
                raise AssertionError(f"{arguments}: exit {result.returncode}; {result.stdout}; {result.stderr}")
            if "Traceback" in result.stderr:
                raise AssertionError(result.stderr)
            return result

        def save(name, data, jsonl=False):
            path = directory / name
            text = "".join(json.dumps(row) + "\n" for row in data) if jsonl else json.dumps(data)
            path.write_text(text, encoding="utf-8")
            return str(path)

        version = invoke("--version").stdout.strip()
        checks.append({"name": "outside_checkout_version", "pass": True, "version": version})
        demo = invoke("run", "--input", str(ROOT / "examples/observations.jsonl"),
                      "--output-dir", str(directory / "demo"))
        demo_counts = json.loads(demo.stdout)
        assert demo_counts["assets"] == 9 and demo_counts["sft_candidates"] == 0 and demo_counts["rl_candidates"] == 0
        checks.append({"name": "outside_checkout_defaults_and_demo", "pass": True, "result": demo_counts})

        # Obtain the exact runtime fingerprint from its own decisions, not from
        # the source checkout, so this also tests installed package defaults.
        decisions = [json.loads(line) for line in (directory / "demo/decisions.jsonl").read_text().splitlines()]
        fingerprint = decisions[0]["policy_fingerprint"]
        records = [json.loads(line) for line in (ROOT / "examples/observations.jsonl").read_text().splitlines()][:2]
        rows = []
        for ordinal, record in enumerate(records):
            record["synthetic"] = False  # Test double only; all artifacts auto-delete.
            record["cohort"] = "contract_test_doubles_segment_v1"
            label = record["observations"][0]["label"]
            reference = {"label": label, "unit_id": record["unit_id"], "status": "verified",
                         "method": "executable_oracle", "reviewer_id": "contract-test-double",
                         "reference_id": "contract-test-double-reference", "question": "Identify and locate the marked scientific content."}
            if record["modality"] == "image":
                reference["bbox"] = [.1, .1, .9, .9]
            else:
                reference.update(interval=[2, 10], duration_seconds=20)
            record["reference_reviews"] = [reference]
            for split, count in (("tune", 35), ("audit", 400)):
                for index in range(count):
                    identity = f"test-double:{ordinal}:{split}:{index}"
                    rows.append({"label": label, "modality": record["modality"], "split": split,
                                 "score": .95, "correct": True, "source_group": identity,
                                 "content_sha256": hashlib.sha256(identity.encode()).hexdigest(),
                                 "reference_id": identity, "cohort": record["cohort"],
                                 "hard_gate_eligible": True, "policy_fingerprint": fingerprint, "synthetic": False})
        gold = save("test-double-gold.jsonl", rows, True)
        certificate = str(directory / "test-double-certificate.json")
        result = invoke("calibrate", "--input", gold, "--output", certificate, "--trusted-references")
        assert json.loads(result.stdout)["certified_labels"] == 2
        checks.append({"name": "temporary_trust_boundary_certificate", "pass": True, "real_precision_claim": False})
        incoming = save("test-double-input.jsonl", records, True)
        result = invoke("run", "--input", incoming, "--calibration", certificate, "--output-dir", str(directory / "positive"))
        counts = json.loads(result.stdout)
        assert counts["statuses"] == {"accepted": 2} and counts["sft_candidates"] == counts["rl_candidates"] == 2
        tasks = [json.loads(line) for line in (directory / "positive/rl_candidates.jsonl").read_text().splitlines()]
        checks.append({"name": "image_and_video_positive_exports", "pass": True, "result": counts})
        for task in tasks:
            reference = task["reference"]
            response = {key: value for key, value in reference.items() if key in ("label", "bbox", "interval")}
            target = save("reference.json", reference)
            output = save("response.json", response)
            assert json.loads(invoke("reward", "--response", output, "--reference", target).stdout)["reward"] == 1
            response["label"] = "wrong_label"
            output = save("response.json", response)
            assert json.loads(invoke("reward", "--response", output, "--reference", target).stdout)["reward"] == 0
        checks.append({"name": "image_video_reward_correct_and_wrong", "pass": True})
        stale = json.loads(Path(certificate).read_text())
        stale["policy_fingerprint"] = "stale"
        stale_path = save("stale.json", stale)
        result = invoke("run", "--input", incoming, "--calibration", stale_path, "--output-dir", str(directory / "stale"))
        counts = json.loads(result.stdout)
        assert counts["sft_candidates"] == counts["rl_candidates"] == 0
        checks.append({"name": "stale_certificate_blocks_exports", "pass": True})
        duplicate = copy.deepcopy(rows)
        duplicate[-1]["content_sha256"] = duplicate[-2]["content_sha256"]
        bad_gold = save("duplicates.jsonl", duplicate, True)
        result = invoke("calibrate", "--input", bad_gold, "--output", certificate, "--trusted-references", expected=2)
        checks.append({"name": "renamed_duplicate_audit_content_rejected", "pass": True})
        malformed = directory / "bad.jsonl"
        malformed.write_text('{"score":NaN}\n')
        result = invoke("run", "--input", str(malformed), "--output-dir", str(directory / "bad"), expected=2)
        assert "bad.jsonl:1" in result.stderr
        checks.append({"name": "invalid_json_has_line_number_no_traceback", "pass": True})

    summary = {"software_contract_only": True, "real_media_evaluated": False,
               "installed_wheel": args.installed, "checks": checks, "passed": len(checks)}
    destination = Path(args.output)
    if not destination.is_absolute():
        destination = ROOT / destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
