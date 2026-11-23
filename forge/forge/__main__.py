import argparse
import os
from pathlib import Path
from .httpd import serve
from .protocol import DEMO_KEY
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="FORGE local procurement workbench")
    parser.add_argument("--port", type=int, default=8041)
    parser.add_argument("--db", default="var/forge.sqlite3")
    parser.add_argument("--demo", action="store_true", help="Seed clearly synthetic data; use public key unless overridden")
    args = parser.parse_args()
    key = os.environ.get("FORGE_AEGIS_KEY", DEMO_KEY if args.demo else "")
    if not key or (not args.demo and (len(key) < 32 or key == DEMO_KEY)):
        parser.error("Set FORGE_AEGIS_KEY to a shared secret of at least 32 characters, or use --demo")
    store = Store(args.db, key)
    if args.demo:
        store.seed()
    serve(store, Path(__file__).resolve().parent.parent / "web", args.port, "forge", args.demo)


if __name__ == "__main__":
    main()
