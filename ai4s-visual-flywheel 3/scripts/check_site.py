"""Check local HTML resources remain inside the standalone Pages artifact."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "docs" / "site"


class Resources(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
        self.ids = set()
        self.duplicate_ids = set()

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key == "id" and value:
                if value in self.ids:
                    self.duplicate_ids.add(value)
                self.ids.add(value)
            if key in ("href", "src") and value:
                self.urls.append(value)


def main():
    errors = []
    files = sorted(SITE.rglob("*.html"))
    parsed = {}
    for file in files:
        content = file.read_text(encoding="utf-8")
        if "\x00" in content:
            errors.append(f"{file.relative_to(SITE)}: unexpanded renderer token/NUL")
        parser = Resources(); parser.feed(content)
        parsed[file.resolve()] = parser
        for duplicate in sorted(parser.duplicate_ids):
            errors.append(f"{file.relative_to(SITE)}: duplicate id {duplicate}")
    for file in files:
        parser = parsed[file.resolve()]
        for value in parser.urls:
            url = urlsplit(value)
            if url.scheme or value.startswith("//"):
                continue
            target = (file.parent / unquote(url.path)).resolve() if url.path else file.resolve()
            if not target.is_relative_to(SITE) or not target.exists():
                errors.append(f"{file.relative_to(SITE)} -> {value}")
            elif url.fragment and target in parsed and unquote(url.fragment) not in parsed[target].ids:
                errors.append(f"{file.relative_to(SITE)}: missing fragment {value}")
    if errors:
        raise SystemExit("Broken/escaping site links:\n" + "\n".join(errors))
    print(f"Checked {len(files)} HTML files; resources, fragments, unique IDs and renderer tokens pass.")


if __name__ == "__main__":
    main()
