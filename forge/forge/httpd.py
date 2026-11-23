"""Bounded, loopback-only JSON HTTP transport for the local workbench."""
import json
import mimetypes
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .protocol import Invalid

MAX_BODY = 8 * 1024 * 1024
READ_TIMEOUT = 5


def serve(store, webroot, port, mode, demo=False):
    root = Path(webroot).resolve()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(READ_TIMEOUT)

        def headers_for(self, status, content_type, length):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()

        def output(self, value, status=200):
            content = json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
            self.headers_for(status, "application/json; charset=utf-8", len(content))
            self.wfile.write(content)

        def trusted_host(self):
            hosts = self.headers.get_all("Host", [])
            return len(hosts) == 1 and hosts[0] in (f"127.0.0.1:{port}", f"localhost:{port}")

        def do_GET(self):
            try:
                self.get_response()
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except Invalid as exc:
                self.output({"error": str(exc)}, 400)
            except Exception as exc:
                self.log_error("GET failed (%s)", type(exc).__name__)
                self.output({"error": "Internal error"}, 500)

        def get_response(self):
            if not self.trusted_host():
                return self.output({"error": "Invalid host"}, 403)
            path = unquote(urlsplit(self.path).path)
            if path == "/api/state":
                return self.output(dict(store.snapshot(), app=mode, demo=demo, protocol="forge-aegis/1"))
            if path == "/api/health":
                return self.output({"ok": True, "app": mode, "version": "0.1.0"})
            if path.startswith("/api/export/"):
                parts = path.split("/")
                if len(parts) != 5:
                    return self.output({"error": "Not found"}, 404)
                return self.output(store.export_artifact(parts[3], parts[4]))
            if mode == "forge" and path.startswith("/api/rank/"):
                return self.output(store.ranking(path.split("/")[-1]))
            if "\x00" in path:
                return self.output({"error": "Not found"}, 404)
            target = (root / (path.lstrip("/") or "index.html")).resolve()
            if root not in target.parents or not target.is_file():
                return self.output({"error": "Not found"}, 404)
            content = target.read_bytes()
            mime = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
            self.headers_for(200, mime + ("; charset=utf-8" if mime.startswith("text/") else ""), len(content))
            self.wfile.write(content)

        def do_POST(self):
            try:
                self.post_response()
            except (BrokenPipeError, ConnectionResetError):
                self.close_connection = True
            except socket.timeout:
                self.close_connection = True
                self.output({"error": "Request body read timed out"}, 408)
            except (Invalid, ValueError, TypeError, RecursionError, OverflowError) as exc:
                self.output({"error": str(exc)}, 400)
            except Exception as exc:
                self.log_error("POST failed (%s)", type(exc).__name__)
                self.output({"error": "Internal error"}, 500)

        def post_response(self):
            origins = self.headers.get_all("Origin", [])
            if not self.trusted_host() or len(origins) > 1 or origins and origins[0] not in (
                    f"http://127.0.0.1:{port}", f"http://localhost:{port}"):
                return self.output({"error": "Cross-origin mutation refused"}, 403)
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                return self.output({"error": "Use application/json"}, 415)
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) > 1 or self.headers.get("Transfer-Encoding") is not None:
                raise Invalid("Ambiguous or unsupported request framing")
            size = int(lengths[0]) if lengths else 0
            if not 0 < size <= MAX_BODY:
                return self.output({"error": "Body limit: 8 MiB"}, 413)
            raw = self.rfile.read(size)
            if len(raw) != size:
                raise Invalid("Incomplete request body")

            def reject_constant(value):
                raise Invalid("Non-finite JSON numbers are forbidden")

            data = json.loads(raw, parse_constant=reject_constant)
            if not isinstance(data, dict):
                raise Invalid("Request must be a JSON object")
            path = urlsplit(self.path).path
            if mode == "forge":
                routes = {
                    "/api/demands": lambda: store.demand(data),
                    "/api/quotes": lambda: store.quote(data.get("demand_id"), data.get("quote")),
                    "/api/orders": lambda: store.draft(data.get("demand_id"), data.get("quote_id")),
                    "/api/orders/release": lambda: store.release(data.get("order_id")),
                    "/api/deliveries": lambda: store.deliver(data.get("order_id"), data.get("delivery", data)),
                    "/api/reports/import": lambda: store.apply_report(data.get("report")),
                }
            else:
                routes = {"/api/inspect": lambda: store.inspect(data.get("delivery"), data.get("rights_review"))}
            if path not in routes:
                return self.output({"error": "Not found"}, 404)
            self.output(routes[path](), 201)

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"{mode.upper()} → http://127.0.0.1:{port}  demo={demo}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
