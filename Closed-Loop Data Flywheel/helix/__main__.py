import argparse
import json
from pathlib import Path
from .store import Store, digest, now
from .demo import seed
from .pipeline import run_pipeline, export_rows, record_feedback, synthesize_artifact
from .ingest import discover, import_manifest


def main():
    parser = argparse.ArgumentParser(description="HELIX science data flywheel")
    parser.add_argument("--data-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("seed", help="Import original synthetic demo fixtures")
    serve = sub.add_parser("serve", help="Start the local dashboard")
    serve.add_argument("--port", type=int, default=8765)
    run = sub.add_parser("run", help="Construct and verify numeric training tasks")
    run.add_argument("--limit", type=int, default=24)
    run.add_argument("--provider", choices=["demo", "model"], default="demo")
    fetch = sub.add_parser("discover", help="Fetch official API metadata")
    fetch.add_argument("connector", choices=["arxiv", "crossref"])
    fetch.add_argument("query")
    fetch.add_argument("--limit", type=int, default=5)
    ingest = sub.add_parser("import", help="Import a JSON manifest and optional raw files")
    ingest.add_argument("manifest")
    ingest.add_argument("--download", action="store_true")
    export = sub.add_parser("export")
    export.add_argument("--format", choices=["rl", "sft", "dpo"], default="rl")
    export.add_argument("--split", choices=["train", "validation"], default="train")
    export.add_argument("--include-demo", action="store_true")
    export.add_argument("--output", required=True)
    feedback = sub.add_parser("feedback")
    feedback.add_argument("file", help="JSONL with task_id, prediction, model")
    synth = sub.add_parser("synthesize")
    synth.add_argument("asset_id")
    synth.add_argument("--kind", choices=["qa", "pipeline", "paper"], default="qa")
    synth.add_argument("--provider", choices=["demo", "model"], default="demo")
    args = parser.parse_args()
    store = Store(args.data_dir) if args.data_dir else Store()
    if args.command == "serve":
        from .server import serve
        return serve(store, port=args.port)
    if args.command == "seed":
        result = seed(store)
    elif args.command == "run":
        result = run_pipeline(store, args.limit, args.provider)
    elif args.command == "discover":
        result = discover(store, args.connector, args.query, args.limit)
    elif args.command == "import":
        path = Path(args.manifest)
        result = import_manifest(store, json.loads(path.read_text()), path.parent, args.download)
    elif args.command == "export":
        rows = export_rows(store, args.format, args.split, args.include_demo)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        blob = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
        output.write_bytes(blob)
        result = {"rows": len(rows), "sha256": digest(blob), "format": args.format,
                  "split": args.split, "include_demo": args.include_demo, "created_at": now()}
        output.with_suffix(".manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "synthesize":
        result = synthesize_artifact(store, args.asset_id, args.kind, args.provider)
    else:
        records = [json.loads(line) for line in Path(args.file).read_text().splitlines() if line.strip()]
        result = [record_feedback(store, r["task_id"], r["prediction"], r["model"]) for r in records]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
