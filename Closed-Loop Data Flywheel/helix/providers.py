"""Optional OpenAI-compatible Chat Completions adapter; credentials stay server-side."""
import json
import os
from urllib.parse import urlparse
from urllib.request import Request, urlopen


def available():
    return bool(os.environ.get("HELIX_MODEL_KEY") and os.environ.get("HELIX_MODEL"))


def complete(prompt, system="You are a scientific assistant. Return valid JSON only."):
    key = os.environ.get("HELIX_MODEL_KEY")
    model = os.environ.get("HELIX_MODEL")
    base = os.environ.get("HELIX_MODEL_BASE_URL", "https://api.openai.com/v1").rstrip("/")
    if not key or not model:
        raise ValueError("Set HELIX_MODEL_KEY and HELIX_MODEL on the server")
    parsed = urlparse(base)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Model endpoint must use HTTPS without URL credentials")
    body = json.dumps({
        "model": model, "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": prompt}],
        "temperature": 0.5, "max_tokens": 1800,
        "response_format": {"type": "json_object"},
    }).encode()
    request = Request(base + "/chat/completions", data=body, headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urlopen(request, timeout=60) as response:
        raw = response.read(2_000_001)
        if len(raw) > 2_000_000:
            raise ValueError("Model response too large")
        data = json.loads(raw)
    text = data["choices"][0]["message"]["content"]
    if not isinstance(json.loads(text), dict):
        raise ValueError("Model must return a JSON object")
    return text
