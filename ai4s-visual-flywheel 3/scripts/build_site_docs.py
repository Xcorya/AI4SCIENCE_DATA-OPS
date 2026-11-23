"""Render this repository's Markdown subset to standalone, dependency-free HTML.

The source of truth remains the Markdown. Math and Mermaid stay readable source
blocks; this intentionally does not load third-party rendering code or CDNs.
"""
from pathlib import Path
import html
import json
import re
import shutil
from urllib.parse import urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "site" / "reference"
DOCS = [ROOT / "README.md", ROOT / "VALIDATION.md"] + sorted((ROOT / "docs").glob("*.md"))


def output_name(path):
    return "readme.html" if path.name == "README.md" else path.stem + ".html"


def slug(text):
    return re.sub(r"[^\w\s\-]", "", text.lower()).replace(" ", "-")


def local_url(value, source):
    parts = urlsplit(value)
    if parts.scheme or value.startswith("//") or not parts.path:
        return value
    target = (source.parent / unquote(parts.path)).resolve()
    if not target.is_relative_to(ROOT):
        return "#"
    if target.suffix == ".md" and target in DOCS:
        url = output_name(target)
    elif target.is_dir():
        url = "files.html"
    elif target.is_file():
        url = "files/" + target.relative_to(ROOT).as_posix()
        dest = OUT / url
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, dest)
    else:
        raise ValueError(f"Broken source link in {source.name}: {value}")
    return url + ("#" + parts.fragment if parts.fragment else "")


def inline(text, source):
    stash = []

    def protect(value):
        stash.append(value)
        return f"\x00{len(stash)-1}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: protect("<code>" + html.escape(m[1]) + "</code>"), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", lambda m: protect(
        '<a href="' + html.escape(local_url(m[2], source), quote=True) + '">' + html.escape(m[1]) + '</a>'), text)
    text = html.escape(text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    # Later protected links may contain an earlier protected inline-code label.
    # Expand outer tokens first, then their inner tokens.
    for i in reversed(range(len(stash))):
        text = text.replace(f"\x00{i}\x00", stash[i])
    return text


def render(source):
    lines = source.read_text(encoding="utf-8").splitlines()
    result, paragraph, index = [], [], 0

    def flush():
        if paragraph:
            result.append("<p>" + inline(" ".join(paragraph), source) + "</p>")
            paragraph.clear()

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush()
            language, block = line[3:].strip(), []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                block.append(lines[index]); index += 1
            result.append('<pre tabindex="0"><code data-language="' + html.escape(language) + '">' + html.escape("\n".join(block)) + '</code></pre>')
        elif line.startswith("$$"):
            flush(); block = [line]
            if not (len(line) > 2 and line.endswith("$$")):
                index += 1
                while index < len(lines):
                    block.append(lines[index])
                    if lines[index].endswith("$$"):
                        break
                    index += 1
            result.append('<pre class="formula">' + html.escape("\n".join(block)) + '</pre>')
        elif re.match(r"^#{1,6} ", line):
            flush(); level = len(line) - len(line.lstrip("#")); title = line[level+1:]
            result.append(f'<h{level} id="{html.escape(slug(title))}">' + inline(title, source) + f'</h{level}>')
        elif line.startswith("|") and index + 1 < len(lines) and re.match(r"^\|[\s:|\-]+\|$", lines[index+1]):
            flush(); headers = [s.strip() for s in line.strip("|").split("|")]
            result.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + inline(s, source) + '</th>' for s in headers) + '</tr></thead><tbody>')
            index += 2
            while index < len(lines) and lines[index].startswith("|"):
                cells = [s.strip() for s in lines[index].strip("|").split("|")]
                result.append('<tr>' + ''.join('<td>' + inline(s, source) + '</td>' for s in cells) + '</tr>'); index += 1
            result.append('</tbody></table></div>'); index -= 1
        elif re.match(r"^(- |\d+\. )", line):
            flush(); ordered = bool(re.match(r"^\d+\. ", line)); tag = 'ol' if ordered else 'ul'
            result.append('<' + tag + '>')
            while index < len(lines) and re.match(r"^(- |\d+\. )", lines[index]):
                result.append('<li>' + inline(re.sub(r"^(- |\d+\. )", "", lines[index]), source) + '</li>'); index += 1
            result.append('</' + tag + '>'); index -= 1
        elif line.startswith("> "):
            flush(); result.append('<blockquote>' + inline(line[2:], source) + '</blockquote>')
        elif not line.strip():
            flush()
        else:
            paragraph.append(line)
        index += 1
    flush()
    return "\n".join(result)


STYLE = '''body{margin:0;color:#23324a;background:#f5f8fc;font:17px/1.85 system-ui,-apple-system,"PingFang SC",sans-serif}header{background:#101b34;color:white;padding:20px max(24px,calc((100vw - 1000px)/2));display:flex;gap:24px;flex-wrap:wrap}header a{color:#8de6d9}main{max-width:1000px;margin:32px auto 80px;padding:32px 44px;background:white;border:1px solid #dce4ef;border-radius:16px}h1{font-size:2rem;line-height:1.4}h2{margin-top:2.4em;padding-top:.3em;border-top:1px solid #e2e8f0;font-size:1.5rem}h3{margin-top:1.8em;font-size:1.15rem}a{color:#126c87;text-underline-offset:3px}code{font:.9em/1.6 ui-monospace,monospace;background:#edf2f8;border-radius:4px;padding:2px 5px}pre{background:#111d34;color:#e5edf7;overflow:auto;padding:20px;border-radius:10px;white-space:pre;font-size:14px;line-height:1.7}pre code{background:none;color:inherit;padding:0;font-size:inherit}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;margin:22px 0;font-size:16px}th,td{border:1px solid #dce4ef;text-align:left;vertical-align:top;padding:12px}th{background:#edf3f8}blockquote{border-left:3px solid #328d95;padding:8px 20px;margin-left:0;background:#edf8f6}.reader-note{font-size:14px;color:#526079}.formula{white-space:pre-wrap;overflow-wrap:anywhere}li{margin:9px 0}@media(max-width:680px){main{margin:16px 10px;padding:22px 18px}h1{font-size:1.6rem}header{padding:18px}th,td{min-width:140px}}'''


def page(title, body):
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + html.escape(title) + '</title><style>' + STYLE + '</style><header><strong>VISUAL FLYWHEEL</strong><a href="../index.html">交互演示</a><a href="readme.html">文档目录</a><a href="whitepaper.html">技术说明</a></header><main>' + body + '<p class="reader-note">静态文档副本由仓库 Markdown 生成。数学与流程图代码保留源形式；完整格式与版本以仓库文件为准。</p></main></html>'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for source in DOCS:
        content = render(source)
        (OUT / output_name(source)).write_text(page(source.stem, content), encoding="utf-8")
    for name in ("taxonomy", "policy"):
        shutil.copyfile(ROOT / "configs" / (name + ".json"), OUT / (name + ".json"))
    files = sorted((ROOT / "src").rglob("*.py")) + sorted((ROOT / "examples").glob("*.json*"))
    entries = []
    for file in files:
        url = local_url(file.relative_to(ROOT).as_posix(), ROOT / "README.md")
        entries.append('<li><a href="' + url + '">' + html.escape(file.relative_to(ROOT).as_posix()) + '</a></li>')
    (OUT / "files.html").write_text(page("代码与示例", '<h1>代码与示例</h1><ul>' + ''.join(entries) + '</ul>'), encoding="utf-8")
    print(json.dumps({"rendered_documents": len(DOCS), "static_reference_files": len(files)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
