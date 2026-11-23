import json
import mimetypes
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from .config import ROOT
from .store import Store
from .demo import seed
from .pipeline import snapshot, run_pipeline, synthesize_artifact, record_feedback, export_rows
from .ingest import discover, import_manifest


def make_server(store, host="127.0.0.1", port=8765):
    token = uuid.uuid4().hex
    run_lock = threading.Lock()
    jobs = {}
    jobs_lock = threading.Lock()

    class Handler(BaseHTTPRequestHandler):
        server_version = "HELIX/0.1"

        def send(self, status, payload, content_type="application/json; charset=utf-8", filename=None):
            if not isinstance(payload, bytes):
                payload = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
                             "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
            if filename:
                self.send_header("Content-Disposition", 'attachment; filename="' + filename + '"')
            self.end_headers()
            self.wfile.write(payload)

        def valid_host(self):
            hostname = self.headers.get("Host", "").split(":")[0]
            return hostname in ("localhost", "127.0.0.1", host)

        def do_GET(self):
            if not self.valid_host():
                return self.send(403, {"error": "Invalid host"})
            parsed = urlparse(self.path)
            query = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/state":
                    return self.send(200, snapshot(store))
                if parsed.path == "/api/session":
                    return self.send(200, {"token": token})
                if parsed.path == "/api/jobs":
                    with jobs_lock:
                        return self.send(200, list(jobs.values()))
                if parsed.path == "/api/export":
                    fmt = query.get("format", ["rl"])[0]
                    split = query.get("split", ["train"])[0]
                    demo = query.get("demo", ["false"])[0] == "true"
                    rows = export_rows(store, fmt, split, demo)
                    data = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows).encode()
                    return self.send(200, data, "application/x-ndjson", f"helix-{fmt}-{split}.jsonl")
                if parsed.path == "/api/handbook":
                    return self.send(200, {"markdown": (ROOT / "docs" / "HANDBOOK.zh-CN.md").read_text()})
                path = (ROOT / "web" / (parsed.path.lstrip("/") or "index.html")).resolve()
                if (ROOT / "web").resolve() not in path.parents or not path.is_file():
                    return self.send(404, {"error": "Not found"})
                mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
                return self.send(200, path.read_bytes(), mime + ("; charset=utf-8" if mime.startswith("text") else ""))
            except (ValueError, TypeError) as exc:
                return self.send(400, {"error": str(exc)})

        def do_POST(self):
            if not self.valid_host() or self.headers.get("X-Helix-Token") != token:
                return self.send(403, {"error": "Invalid session"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                if not 0 < length <= 2_000_000:
                    return self.send(413, {"error": "Request must contain 1 byte to 2 MB"})
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("Body must be an object")
                path = urlparse(self.path).path
                if path == "/api/demo":
                    return self.send(200, seed(store))
                if path == "/api/feedback":
                    return self.send(200, record_feedback(store, body["task_id"], body["prediction"], body["model"]))
                if path == "/api/import":
                    return self.send(200, import_manifest(store, body["assets"]))
                if path not in ("/api/run", "/api/discover", "/api/synthesize"):
                    return self.send(404, {"error": "Not found"})
                if not run_lock.acquire(blocking=False):
                    return self.send(409, {"error": "A job is already running"})
                job_id = "j_" + uuid.uuid4().hex[:12]
                with jobs_lock:
                    jobs[job_id] = {"id": job_id, "status": "running", "action": path}

                def work():
                    try:
                        if path == "/api/run":
                            result = run_pipeline(store, body.get("limit", 24), body.get("provider", "demo"))
                        elif path == "/api/discover":
                            result = discover(store, body.get("connector"), body.get("query"), body.get("limit", 5))
                        else:
                            result = synthesize_artifact(store, body["asset_id"], body["kind"],
                                                         body.get("provider", "demo"))
                        with jobs_lock:
                            jobs[job_id].update(status="completed", result=result)
                    except Exception as exc:
                        with jobs_lock:
                            jobs[job_id].update(status="failed",
                                               error=str(exc) if isinstance(exc, (ValueError, KeyError)) else type(exc).__name__)
                    finally:
                        run_lock.release()
                threading.Thread(target=work, daemon=True).start()
                return self.send(202, {"job_id": job_id})
            except (KeyError, ValueError, TypeError) as exc:
                return self.send(400, {"error": str(exc)})

        def log_message(self, format, *args):
            pass

    return ThreadingHTTPServer((host, port), Handler)


def serve(store=None, host="127.0.0.1", port=8765):
    server = make_server(store or Store(), host, port)
    print(f"HELIX running at http://{host}:{port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
