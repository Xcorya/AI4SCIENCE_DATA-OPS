"""Create a source-only release ZIP without runtime data, secrets or caches."""
from pathlib import Path
import hashlib
import zipfile

root = Path(__file__).resolve().parent.parent
target = root.parent / "HELIX-science-flywheel-v0.1.0.zip"
directories = {"helix", "web", "docs", "examples", "configs", "tests", "scripts", ".github"}
files = {
    "README.md", "LICENSE", "CONTRIBUTING.md", "SECURITY.md",
    "RELEASE_NOTES.md", "pyproject.toml", "setup.py",
    ".gitignore", ".env.example",
}
members = []
with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if not path.is_file() or path.is_symlink():
            continue
        if any(part in {"__pycache__", ".git", ".venv", "node_modules"} for part in relative.parts):
            continue
        if relative.parts[0] not in directories and str(relative) not in files:
            continue
        if path.suffix in {".pyc", ".pyo", ".sqlite", ".log"} or (path.name.startswith(".env") and path.name != ".env.example"):
            continue
        archive.write(path, "helix/" + relative.as_posix())
        members.append(str(relative))
with zipfile.ZipFile(target) as archive:
    if archive.testzip() is not None:
        raise RuntimeError("ZIP integrity check failed")
checksum = hashlib.sha256(target.read_bytes()).hexdigest()
checksum_path = target.with_suffix(target.suffix + ".sha256")
checksum_path.write_text(checksum + "  " + target.name + "\n")
print("Archive:", target)
print("Files:", len(members))
print("Bytes:", target.stat().st_size)
print("SHA256:", checksum)
print("Checksum:", checksum_path)
