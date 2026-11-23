"""Regenerate deterministic, unsigned synthetic fixtures for both repositories."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from forge.protocol import VERSION, digest
from forge.store import demo_manifest, demo_records, demo_spec


def write(root=ROOT / "fixtures"):
    root.mkdir(parents=True, exist_ok=True)
    spec = demo_spec()
    for variant in ("clean", "defects", "rights-gap"):
        records, manifest = copy.deepcopy(demo_records()), copy.deepcopy(demo_manifest())
        if variant == "defects":
            records[1]["id"] = records[0]["id"]
            records[2]["text"] = ""
            records[3]["language"] = 42
        if variant == "rights-gap":
            manifest.pop("evidence")
            manifest["rights_verified"] = False
        body = dict(protocol=VERSION, kind="delivery", order_id="PO-SYNTHETIC-" + variant,
                    delivery_id="DLV-SYNTHETIC-" + variant, created_at="2026-11-23T00:00:00+00:00",
                    spec=spec, spec_hash=digest(spec), manifest=manifest,
                    records=records, dataset_hash=digest(records))
        (root / (variant + ".json")).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n")


if __name__ == "__main__":
    write()
