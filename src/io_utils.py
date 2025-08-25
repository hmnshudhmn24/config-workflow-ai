from pathlib import Path
import json
import yaml
import difflib
from colorama import Fore, Style

def detect_format(path: Path):
    s = path.suffix.lower()
    if s in [".yaml", ".yml"]:
        return "yaml"
    if s == ".json":
        return "json"
    # best-effort: peek
    txt = path.read_text(encoding="utf-8")
    t = txt.strip()
    if t.startswith("{") or t.startswith("["):
        return "json"
    return "yaml"

def read_any(path: Path):
    fmt = detect_format(path)
    if fmt == "json":
        return json.loads(path.read_text(encoding="utf-8")), fmt
    else:
        return yaml.safe_load(path.read_text(encoding="utf-8")), fmt

def write_any(obj, path: Path, fmt=None):
    fmt = fmt or detect_format(path)
    if fmt == "json":
        path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        path.write_text(yaml.safe_dump(obj, sort_keys=False), encoding="utf-8")

def dumps_json(obj):
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"

def load_yaml_multi(path: Path):
    return list(yaml.safe_load_all(path.read_text(encoding="utf-8")))

def dump_yaml_multi(documents):
    return [yaml.safe_dump(d, sort_keys=False).rstrip() for d in documents]

def make_backup(path: Path):
    bak = path.with_suffix(path.suffix + ".bak")
    bak.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
    return bak

def color_diff(a_text: str, b_text: str):
    diff = difflib.unified_diff(
        a_text.splitlines(), b_text.splitlines(),
        fromfile="before", tofile="after", lineterm=""
    )
    lines = []
    for line in diff:
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(Fore.GREEN + line + Style.RESET_ALL)
        elif line.startswith("-") and not line.startswith("---"):
            lines.append(Fore.RED + line + Style.RESET_ALL)
        elif line.startswith("@@"):
            lines.append(Fore.CYAN + line + Style.RESET_ALL)
        else:
            lines.append(line)
    return "\n".join(lines)
