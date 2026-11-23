import hashlib
import json
import math
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .config import DATA


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def digest(value):
    if not isinstance(value, bytes):
        value = json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    return hashlib.sha256(value).hexdigest()


def split_for(group):
    bucket = int(digest(group)[:8], 16) % 100
    return "holdout" if bucket < 10 else "validation" if bucket < 20 else "train"


class Store:
    def __init__(self, directory=DATA):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        (self.directory / "objects").mkdir(exist_ok=True)
        self.path = self.directory / "helix.sqlite"
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS assets
                  (id TEXT PRIMARY KEY, fingerprint TEXT UNIQUE NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS tasks
                  (id TEXT PRIMARY KEY, asset_id TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS runs
                  (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS feedback
                  (id TEXT PRIMARY KEY, payload TEXT NOT NULL);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=30)
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def all(self, table):
        if table not in ("assets", "tasks", "runs", "feedback"):
            raise ValueError("Unknown table")
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM " + table + " ORDER BY rowid DESC")]

    def get(self, table, item_id):
        if table not in ("assets", "tasks", "runs", "feedback"):
            raise ValueError("Unknown table")
        with self.connect() as db:
            row = db.execute("SELECT payload FROM " + table + " WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ValueError("Record not found")
        return json.loads(row[0])

    def save(self, table, value):
        if table not in ("tasks", "runs", "feedback"):
            raise ValueError("Unknown table")
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        with self.connect() as db:
            if table == "tasks":
                db.execute("INSERT OR IGNORE INTO tasks VALUES (?,?,?)",
                           (value["id"], value["asset_id"], encoded))
            else:
                db.execute("INSERT OR REPLACE INTO " + table + " VALUES (?,?)", (value["id"], encoded))

    def add_asset(self, asset):
        required = ("title", "source_id", "source_url", "modality", "license", "text")
        if any(not isinstance(asset.get(k), str) or not asset[k].strip() for k in required):
            raise ValueError("Asset requires non-empty strings: " + ", ".join(required))
        from .config import MODALITIES
        if asset["modality"] not in MODALITIES:
            raise ValueError("Unknown modality")
        for key in ("is_demo", "benchmark"):
            if key in asset and not isinstance(asset[key], bool):
                raise ValueError(key + " must be a boolean")
        if "group_id" in asset and (
                not isinstance(asset["group_id"], str) or not asset["group_id"].strip()):
            raise ValueError("group_id must be a non-empty string")
        if "facts" in asset:
            facts = asset["facts"]
            if not isinstance(facts, dict):
                raise ValueError("facts must be an object")
            if any(not isinstance(facts.get(k), str) or not facts[k].strip()
                   for k in ("quantity", "unit")):
                raise ValueError("facts require a non-empty quantity and unit")
            values = facts.get("values")
            if (not isinstance(values, list) or len(values) < 2
                    or any(isinstance(v, bool) or not isinstance(v, (int, float))
                           or not math.isfinite(v) for v in values)):
                raise ValueError("facts.values require at least two finite numbers")
        from .pipeline import classify
        asset = dict(asset)
        # Content identity, not titles or URLs, controls exact deduplication.
        fingerprint = digest(" ".join(asset["text"].split()))
        with self.connect() as db:
            old = db.execute("SELECT payload FROM assets WHERE fingerprint=?", (fingerprint,)).fetchone()
            if old:
                existing = json.loads(old[0])
                if asset.get("benchmark") is True and existing["split"] != "holdout":
                    raise ValueError("Benchmark content already exists outside holdout; audit the dataset first")
                return existing, False
            group = asset.get("group_id") or asset["source_id"]
            siblings = [json.loads(r[0]) for r in db.execute("SELECT payload FROM assets")]
            sibling = next((a for a in siblings if a["group_id"] == group), None)
            split = sibling["split"] if sibling else (
                "holdout" if asset.get("benchmark") is True else split_for(group))
            if sibling and asset.get("benchmark") and split != "holdout":
                raise ValueError("Cannot convert an existing training family into a benchmark; use a new database")
            asset.update(id="a_" + fingerprint[:16], fingerprint=fingerprint,
                         group_id=group, split=split, created_at=now())
            asset["classification"] = classify(asset)
            db.execute("INSERT INTO assets VALUES (?,?,?)",
                       (asset["id"], fingerprint, json.dumps(asset, ensure_ascii=False, allow_nan=False)))
        return asset, True

    def put_object(self, data):
        checksum = digest(data)
        target = self.directory / "objects" / checksum
        if not target.exists():
            target.write_bytes(data)
        return checksum
