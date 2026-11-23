import argparse
import json
import os
from pathlib import Path
from .httpd import serve
from .protocol import DEMO_KEY
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="AEGIS local dataset acceptance workbench")
    parser.add_argument("--port", type=int, default=8042)
    parser.add_argument("--db", default="var/aegis.sqlite3")
    parser.add_argument("--demo", action="store_true", help="Seed clearly synthetic reports; use public key unless overridden")
    args = parser.parse_args()
    key = os.environ.get("FORGE_AEGIS_KEY", DEMO_KEY if args.demo else "")
    if not key or (not args.demo and (len(key) < 32 or key == DEMO_KEY)):
        parser.error("Set FORGE_AEGIS_KEY to a shared secret of at least 32 characters, or use --demo")
    store = Store(args.db, key)
    root = Path(__file__).resolve().parent.parent
    if args.demo:
        from .protocol import sign
        artifacts = [sign(json.loads((root / "fixtures" / name).read_text()), key)
                     for name in ("clean.json", "defects.json", "rights-gap.json")]
        store.seed(artifacts)
    serve(store, root / "web", args.port, "aegis", args.demo)


if __name__ == "__main__":
    main()
