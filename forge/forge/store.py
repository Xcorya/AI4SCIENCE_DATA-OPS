import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .engine import rank, validate_quote
from .protocol import VERSION, Invalid, canonical, digest, identifier, now, sign, timestamp, validate_spec, validate_delivery, verify


def uid(prefix):
    return prefix + "-" + uuid.uuid4().hex[:12]


def demo_spec():
    return dict(title="多语种科研摘要 · 首批交付", quantity=24, budget_cents=120000,
                currency="CNY", max_days=14, purpose="model_training", region="CN",
                max_defect_rate=0.05, allow_derivatives=True, allow_pii=False,
                schema={"id": "string", "text": "string", "language": "string"}, unique_key="id")


def demo_records():
    return [{"id": f"synthetic-{i:03}", "text": f"Synthetic research abstract number {i}.",
             "language": "en" if i % 2 else "zh"} for i in range(1, 25)]


def demo_manifest():
    return dict(coverage="full", record_count=24, source="Synthetic fixture generated locally",
                license="Synthetic-Research-Grant-1.0", evidence="fixtures/RIGHTS.md",
                rights_verified=True, purposes=["model_training"], regions=["CN", "EU"],
                derivatives=True, valid_until="2030-12-31", prohibited_source=False, synthetic=True)


class Store:
    def __init__(self, path, key):
        self.key = key
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.path = str(path)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS demands(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS quotes(id TEXT PRIMARY KEY, demand_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS orders(id TEXT PRIMARY KEY, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS deliveries(id TEXT PRIMARY KEY, order_id TEXT NOT NULL, body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports(id TEXT PRIMARY KEY, body TEXT NOT NULL);
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

    @staticmethod
    def event(db, action, entity, detail):
        db.execute("INSERT INTO events(at,action,entity,detail) VALUES(?,?,?,?)",
                   (now(), action, entity, json.dumps(detail, ensure_ascii=False)))

    @staticmethod
    def get(db, table, ident):
        if table not in ("demands", "quotes", "orders", "deliveries", "reports"):
            raise Invalid("Unknown resource")
        ident = identifier(ident)
        row = db.execute(f"SELECT body FROM {table} WHERE id=?", (ident,)).fetchone()
        if not row:
            raise Invalid("Resource not found")
        return json.loads(row["body"])

    def demand(self, value):
        spec = validate_spec(value)
        body = dict(id=uid("REQ"), spec=spec, spec_hash=digest(spec), created_at=now())
        with self.connect() as db:
            db.execute("INSERT INTO demands VALUES(?,?)", (body["id"], canonical(body).decode()))
            self.event(db, "demand.created", body["id"], {"spec_hash": body["spec_hash"]})
        return body

    def quote(self, demand_id, value):
        quote = dict(validate_quote(value), id=uid("QTE"), demand_id=demand_id, created_at=now())
        with self.connect() as db:
            self.get(db, "demands", demand_id)
            db.execute("INSERT INTO quotes VALUES(?,?,?)", (quote["id"], demand_id, canonical(quote).decode()))
            self.event(db, "quote.created", quote["id"], {"demand_id": demand_id})
        return quote

    def ranking(self, demand_id):
        with self.connect() as db:
            demand = self.get(db, "demands", demand_id)
            quotes = [json.loads(r["body"]) for r in db.execute(
                "SELECT body FROM quotes WHERE demand_id=?", (demand_id,))]
        return rank(demand["spec"], quotes)

    def draft(self, demand_id, quote_id):
        rows = self.ranking(demand_id)
        selected = next((r for r in rows if r["id"] == quote_id), None)
        if not selected or not selected["eligible"]:
            raise Invalid("Only an eligible quote can become a purchase draft")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            demand = self.get(db, "demands", demand_id)
            existing = [json.loads(row["body"]) for row in db.execute("SELECT body FROM orders")]
            if any(order["demand_id"] == demand_id for order in existing):
                raise Invalid("This demand already has an order; use a new demand for another purchase")
            order = dict(id=uid("PO"), demand_id=demand_id, spec=demand["spec"],
                         spec_hash=demand["spec_hash"], quote=selected, state="draft",
                         created_at=now(), delivery_id=None, report_id=None)
            db.execute("INSERT INTO orders VALUES(?,?)", (order["id"], canonical(order).decode()))
            self.event(db, "order.drafted", order["id"], {"total_cents": selected["total_cents"]})
        return order

    def release(self, order_id):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            order = self.get(db, "orders", order_id)
            if order["state"] != "draft":
                raise Invalid("Only a draft order can be released")
            order.update(state="ordered", ordered_at=now())
            db.execute("UPDATE orders SET body=? WHERE id=?", (canonical(order).decode(), order_id))
            self.event(db, "order.released", order_id, {"local_only": True})
        return order

    def deliver(self, order_id, value):
        if not isinstance(value, dict):
            raise Invalid("Delivery input must be an object")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            order = self.get(db, "orders", order_id)
            if order["state"] not in ("ordered", "review", "rejected"):
                raise Invalid("Delivery allowed after release or a review/rejection")
            body = dict(protocol=VERSION, kind="delivery", order_id=order_id,
                        delivery_id=uid("DLV"), created_at=now(), spec=order["spec"],
                        spec_hash=order["spec_hash"], manifest=value.get("manifest"),
                        records=value.get("records"), dataset_hash=digest(value.get("records")))
            artifact = sign(body, self.key)
            validate_delivery(artifact, self.key)
            db.execute("INSERT INTO deliveries VALUES(?,?,?)",
                       (body["delivery_id"], order_id, canonical(artifact).decode()))
            order.update(state="delivered", delivery_id=body["delivery_id"], report_id=None)
            db.execute("UPDATE orders SET body=? WHERE id=?", (canonical(order).decode(), order_id))
            self.event(db, "delivery.registered", order_id, {"delivery_id": body["delivery_id"], "hash": digest(body)})
        return artifact

    def apply_report(self, artifact):
        body = verify(artifact, self.key, "report")
        for field in ("report_id", "order_id", "delivery_id"):
            identifier(body.get(field), field)
        issued = timestamp(body.get("issued_at"))
        expires = timestamp(body.get("expires_at"))
        current = datetime.now(timezone.utc)
        if issued > current + timedelta(minutes=5) or expires <= current or expires <= issued or expires - issued > timedelta(days=7):
            raise Invalid("Report expired or invalid validity window")
        if body.get("status") not in ("accepted", "review", "rejected"):
            raise Invalid("Invalid report status")
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            order = self.get(db, "orders", body["order_id"])
            if order["delivery_id"] != body["delivery_id"] or order["spec_hash"] != body.get("spec_hash"):
                raise Invalid("Report does not match the current delivery/specification")
            delivery = self.get(db, "deliveries", body["delivery_id"])
            if digest({k: v for k, v in delivery.items() if k != "signature"}) != body.get("envelope_hash") or delivery["dataset_hash"] != body.get("dataset_hash"):
                raise Invalid("Report content binding mismatch")
            existing = db.execute("SELECT body FROM reports WHERE id=?", (body["report_id"],)).fetchone()
            if existing:
                if json.loads(existing["body"]) != artifact:
                    raise Invalid("Report identity reused with different content")
                return order
            if order["state"] != "delivered":
                raise Invalid("Current delivery already has a decision; submit a new delivery")
            db.execute("INSERT INTO reports VALUES(?,?)", (body["report_id"], canonical(artifact).decode()))
            order.update(state=body["status"], report_id=body["report_id"])
            db.execute("UPDATE orders SET body=? WHERE id=?", (canonical(order).decode(), order["id"]))
            self.event(db, "acceptance.applied", order["id"], {"report_id": body["report_id"], "status": body["status"]})
        return order

    def snapshot(self):
        with self.connect() as db:
            data = {table: [json.loads(r["body"]) for r in db.execute(f"SELECT body FROM {table} ORDER BY rowid")]
                    for table in ("demands", "quotes", "orders", "deliveries", "reports")}
            data["events"] = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY seq DESC LIMIT 40")]
        data["demo_input"] = {"manifest": demo_manifest(), "records": demo_records()}
        return data

    def export_artifact(self, kind, ident):
        if kind != "deliveries":
            raise Invalid("Only delivery exports are available in FORGE")
        with self.connect() as db:
            return self.get(db, "deliveries", ident)

    def seed(self):
        if self.snapshot()["demands"]:
            return
        demand = self.demand(demo_spec())
        for vendor, unit, days, quality, verified in [
            ("Lumen Data · synthetic", 3200, 10, .97, True),
            ("Atlas Supply · synthetic", 3900, 6, .99, True),
            ("Budget Pool · synthetic", 1800, 9, .90, False),
            ("Meridian Lab · synthetic", 5200, 21, .995, True),
        ]:
            self.quote(demand["id"], dict(vendor=vendor, unit_cents=unit, fee_cents=6000,
                       capacity=100, lead_days=days, currency="CNY", declared_quality=quality,
                       evidence="fixtures/RIGHTS.md · synthetic evidence only", purposes=["model_training"],
                       regions=["CN", "EU"], derivatives=True, rights_verified=verified))
