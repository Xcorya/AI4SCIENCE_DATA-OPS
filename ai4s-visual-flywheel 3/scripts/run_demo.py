"""Run the synthetic evidence-policy demo with no installation or API credentials."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from visual_flywheel.__main__ import read_json, read_jsonl, write_jsonl
from visual_flywheel.policy import classify_batch
from visual_flywheel.training import export_training


def main():
    output = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "work" / "demo"
    output.mkdir(parents=True, exist_ok=True)
    policy = read_json(ROOT / "configs" / "policy.json")
    taxonomy = read_json(ROOT / "configs" / "taxonomy.json")
    decisions = classify_batch(read_jsonl(ROOT / "examples" / "observations.jsonl"), policy, taxonomy)
    sft, rl = export_training(decisions, taxonomy)
    write_jsonl(output / "decisions.jsonl", decisions)
    write_jsonl(output / "sft_candidates.jsonl", sft)
    write_jsonl(output / "rl_candidates.jsonl", rl)
    summary = {"synthetic_demo": True, "assets": len(decisions),
               "statuses": {}, "sft_candidates": len(sft), "rl_candidates": len(rl),
               "note": "No real inference or precision evaluation. Synthetic data cannot certify or enter training."}
    for result in decisions:
        summary["statuses"][result["status"]] = summary["statuses"].get(result["status"], 0) + 1
    (output / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
