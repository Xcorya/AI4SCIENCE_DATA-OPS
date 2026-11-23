from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from importlib.resources import files
from . import __version__
from .calibration import calibrate
from .policy import classify_batch
from .training import export_training, reward


def _reject_nonfinite(value):
    raise ValueError(f"Non-standard JSON constant {value} is not permitted")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"JSON number {value} exceeds finite floating-point range")
    return number


def read_jsonl(path):
    with open(path, encoding="utf-8") as stream:
        rows = []
        for number, line in enumerate(stream, 1):
            if line.strip():
                try:
                    rows.append(json.loads(line, parse_constant=_reject_nonfinite, parse_float=_finite_float))
                except ValueError as error:
                    raise ValueError(f"{path}:{number}: {error}") from error
        return rows


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"), parse_constant=_reject_nonfinite,
                          parse_float=_finite_float)
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error


def read_config(path, filename):
    """Explicit override, source-checkout defaults, or installed wheel defaults."""
    if path is not None:
        return read_json(path)
    checkout = Path(__file__).resolve().parents[2] / "configs" / filename
    if checkout.is_file():
        return read_json(checkout)
    text = files("visual_flywheel").joinpath("data", filename).read_text(encoding="utf-8")
    return json.loads(text, parse_constant=_reject_nonfinite, parse_float=_finite_float)


def write_jsonl(path, records):
    Path(path).write_text("".join(json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in records), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Offline policy reference; upstream vision observations required")
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Gate precomputed evidence and export supported training candidates")
    run.add_argument("--input", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--calibration")
    cal = sub.add_parser("calibrate", help="Tune and independently audit per-label thresholds")
    cal.add_argument("--input", required=True)
    cal.add_argument("--output", required=True)
    cal.add_argument("--trusted-references", action="store_true",
                     help="Assert external gold review provenance has been verified; this tool cannot verify it")
    for command in (run, cal):
        command.add_argument("--policy", help="Policy JSON override; packaged defaults are used when omitted")
        command.add_argument("--taxonomy", help="Taxonomy JSON override; packaged defaults are used when omitted")
    score = sub.add_parser("reward", help="Evaluate a response against an externally verified reference")
    score.add_argument("--response", required=True)
    score.add_argument("--reference", required=True)
    args = parser.parse_args()
    try:
        return execute(args)
    except (ValueError, OSError, UnicodeError) as error:
        parser.error(str(error))


def execute(args):
    if args.command == "reward":
        print(json.dumps(reward(read_json(args.response), read_json(args.reference)), ensure_ascii=False))
        return
    policy, taxonomy = read_config(args.policy, "policy.json"), read_config(args.taxonomy, "taxonomy.json")
    if args.command == "calibrate":
        result = calibrate(read_jsonl(args.input), policy, taxonomy, args.trusted_references)
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps({"certified_labels": sum(x["certified"] for x in result["labels"].values()),
                          "synthetic": result["synthetic"]}))
        return
    calibration = read_json(args.calibration) if args.calibration else None
    decisions = classify_batch(read_jsonl(args.input), policy, taxonomy, calibration)
    sft, rl = export_training(decisions, taxonomy)
    output = Path(args.output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "decisions.jsonl", decisions)
    write_jsonl(output / "sft_candidates.jsonl", sft)
    write_jsonl(output / "rl_candidates.jsonl", rl)
    counts = {}
    for decision in decisions:
        counts[decision["status"]] = counts.get(decision["status"], 0) + 1
    print(json.dumps({"assets": len(decisions), "statuses": counts,
                      "sft_candidates": len(sft), "rl_candidates": len(rl)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
