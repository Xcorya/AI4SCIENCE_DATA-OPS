"""Bounded official-API discovery and content-addressed, opt-in file ingestion."""
import ipaddress
import json
import os
import socket
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from .config import OPEN_LICENSES, MODALITIES

DEFAULT_HOSTS = {"export.arxiv.org", "arxiv.org", "api.crossref.org", "zenodo.org"}


def allowed_hosts():
    return DEFAULT_HOSTS | {h.strip() for h in os.environ.get("HELIX_DOWNLOAD_HOSTS", "").split(",") if h.strip()}


def validate_url(url):
    p = urlparse(url)
    if (p.scheme != "https" or p.username or p.password or p.port not in (None, 443)
            or p.hostname not in allowed_hosts()):
        raise ValueError("Only HTTPS URLs on configured public source hosts are allowed")
    addresses = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
        raise ValueError("Source resolves to a non-public address")


class CheckedRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, max_bytes=5_000_000):
    validate_url(url)
    opener = build_opener(CheckedRedirect())
    request = Request(url, headers={"User-Agent": "HELIX-ResearchPrototype/0.1 (bounded academic metadata client)"})
    for attempt in range(3):
        try:
            with opener.open(request, timeout=25) as response:
                size = response.headers.get("Content-Length")
                if size and int(size) > max_bytes:
                    raise ValueError("Source exceeds size limit")
                content = response.read(max_bytes + 1)
                if len(content) > max_bytes:
                    raise ValueError("Source exceeds size limit")
                return content
        except HTTPError as exc:
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
            time.sleep(min(2 ** attempt, 4))
        except URLError:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def discover(store, connector, query, limit=5):
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 240:
        raise ValueError("Query must contain 1–240 characters")
    limit = max(1, min(int(limit), 20))
    items = []
    if connector == "arxiv":
        raw = fetch("https://export.arxiv.org/api/query?" + urlencode({
            "search_query": "all:" + query, "start": 0, "max_results": limit}))
        root = ET.fromstring(raw)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        for item in root.findall("a:entry", ns):
            url = item.findtext("a:id", "", ns).replace("http://", "https://")
            title = " ".join(item.findtext("a:title", "", ns).split())
            if not title or "/abs/" not in url:
                continue
            items.append({"title": title, "source_id": url, "source_url": url,
                          "text": item.findtext("a:summary", "", ns).strip(),
                          "license": "unknown", "modality": "paper", "connector": connector,
                          "is_demo": False, "storage_status": "metadata_only",
                          "group_id": url.rsplit("v", 1)[0] if url.rsplit("v", 1)[-1].isdigit() else url})
    elif connector == "crossref":
        raw = fetch("https://api.crossref.org/works?" + urlencode({"query": query, "rows": limit}))
        payload = json.loads(raw)
        for item in payload.get("message", {}).get("items", []):
            titles = item.get("title") or []
            doi = item.get("DOI")
            if not titles or not doi:
                continue
            url = "https://doi.org/" + doi
            items.append({"title": titles[0], "source_id": doi, "source_url": url,
                          "text": item.get("abstract") or titles[0],
                          "license": "unknown", "license_candidates": item.get("license", []),
                          "modality": "paper", "connector": connector, "is_demo": False,
                          "storage_status": "metadata_only"})
    else:
        raise ValueError("Connector must be arxiv or crossref")
    created = 0
    for item in items:
        _, added = store.add_asset(item)
        created += int(added)
    return {"found": len(items), "created": created, "duplicates": len(items) - created,
            "connector": connector, "note": "Metadata only. Source license requires item-level review."}


def import_manifest(store, items, base_dir=None, download=False):
    if not isinstance(items, list) or len(items) > 500:
        raise ValueError("Manifest must be an array of at most 500 assets")
    result = {"created": 0, "duplicates": 0, "errors": []}
    for index, source in enumerate(items):
        try:
            if not isinstance(source, dict):
                raise ValueError("Each manifest entry must be an object")
            item = dict(source)
            if item.get("modality") not in MODALITIES:
                raise ValueError("Invalid modality")
            # Demo flag is a declaration, not a source of authorization.
            item.setdefault("is_demo", False)
            data = None
            if base_dir and item.get("local_file"):
                base = Path(base_dir).resolve()
                path = (base / item["local_file"]).resolve()
                if base not in path.parents or not path.is_file():
                    raise ValueError("Local asset must be inside the manifest directory")
                if path.stat().st_size > 50_000_000:
                    raise ValueError("Local asset exceeds 50 MB limit")
                data = path.read_bytes()
            elif download and item.get("download_url"):
                if item.get("license") not in OPEN_LICENSES:
                    raise ValueError("Explicitly resolve reuse rights before downloading")
                data = fetch(item["download_url"], 50_000_000)
            if data is not None:
                item["object_sha256"] = store.put_object(data)
                item["byte_size"] = len(data)
                item["storage_status"] = "stored"
                if item.get("extract"):
                    from .extractors import extract
                    item["facts"] = extract(data, item["extract"])
                    item["original_description"] = item.get("text", "")
                    item["text"] = json.dumps(item["facts"], ensure_ascii=False, sort_keys=True)
                    item["extraction"] = {"method": item["extract"]["format"] + "-v1",
                                          "source_sha256": item["object_sha256"]}
            else:
                item["storage_status"] = "metadata_only"
            _, added = store.add_asset(item)
            result["created" if added else "duplicates"] += 1
        except (ValueError, OSError, TypeError) as exc:
            result["errors"].append({"index": index, "error": str(exc)[:300]})
    return result
