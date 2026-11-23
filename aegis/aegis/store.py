import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path

from .engine import evaluate
from .protocol import VERSION, Invalid, canonical, digest, identifier, now, sign, validate_delivery


class Store:
    def __init__(self, path, key):
        self.key, self.path = key, str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, delivery_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT, action TEXT, entity TEXT, detail TEXT);
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def inspect(self, artifact, rights_review=None):
        body = validate_delivery(artifact, self.key)
        issued = datetime.now(timezone.utc)
        result = evaluate(body, rights_review, as_of=issued)
        expires = issued + timedelta(days=7)
        if result["status"] == "accepted":
            # License dates are inclusive UTC dates, but reports must not outlive them.
            license_end = datetime.combine(date.fromisoformat(body["manifest"]["valid_until"]),
                                           time.max, tzinfo=timezone.utc)
            expires = min(expires, license_end)
        report = sign(dict(
            protocol=VERSION, kind="report", report_id="RPT-" + uuid.uuid4().hex[:12],
            order_id=body["order_id"], delivery_id=body["delivery_id"],
            spec_hash=body["spec_hash"], dataset_hash=body["dataset_hash"],
            envelope_hash=digest(body), issued_at=issued.isoformat(),
            expires_at=expires.isoformat(),
            **result), self.key)
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            existing = db.execute("SELECT body FROM deliveries WHERE id=?", (body["delivery_id"],)).fetchone()
            if existing and json.loads(existing["body"]) != artifact:
                raise Invalid("Delivery ID collision: the original artifact is immutable")
            if not existing:
                db.execute("INSERT INTO deliveries VALUES(?,?)", (body["delivery_id"], canonical(artifact).decode()))
            db.execute("INSERT INTO reports VALUES(?,?,?)",
                       (report["report_id"], body["delivery_id"], canonical(report).decode()))
            db.execute("INSERT INTO events(at,action,entity,detail) VALUES(?,?,?,?)",
                       (now(), "inspection.completed", report["report_id"],
                        canonical({"status": result["status"], "envelope_hash": digest(body)}).decode()))
        return report

    def snapshot(self):
        with self.connect() as db:
            data = {table: [json.loads(r["body"]) for r in db.execute(f"SELECT body FROM {table} ORDER BY rowid")]
                    for table in ("deliveries", "reports")}
            data["events"] = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT 40")]
        return data

    def export_artifact(self, kind, ident):
        if kind != "reports":
            raise Invalid("Only report exports are available in AEGIS")
        ident = identifier(ident)
        with self.connect() as db:
            row = db.execute("SELECT body FROM reports WHERE id=?", (ident,)).fetchone()
            if not row:
                raise Invalid("Resource not found")
            return json.loads(row["body"])

    def seed(self, artifacts):
        if self.snapshot()["reports"]:
            return
        for index, artifact in enumerate(artifacts):
            review = dict(confirmed=True, reviewer="DEMO / synthetic-fixture reviewer",
                          evidence_note="Synthetic license fixture only; no real dataset permissions.",
                          reviewed_at=now()) if index < 2 else None
            self.inspect(artifact, review)
