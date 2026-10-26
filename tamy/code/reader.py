"""Read-only access to a clone of the product code. Every path is checked against the clone root.

The model picks the path and the pattern, so both are data: a path never leaves the root, a secret
file is never shown, and a pattern is always passed to `git grep` as a pattern, never as an option.
"""

from __future__ import annotations

import fnmatch
import subprocess
from pathlib import Path

MAX_LINES = 400
MAX_CHARS = 20000
MAX_HITS = 60
GREP_TIMEOUT_S = 20

SECRET_PATTERNS = (".env", ".env.*", "*.pem", "*.key", "*secret*", "*credential*", "id_rsa*", "id_ed25519*", "*.p12")
HIDDEN_PARTS = {".git"}


class CodeError(Exception):
    pass


def _is_secret(path: Path) -> bool:
    return any(part in HIDDEN_PARTS for part in path.parts) or any(
        fnmatch.fnmatch(part.lower(), pattern) for part in path.parts for pattern in SECRET_PATTERNS
    )


def _resolve(root: Path, relative: str) -> Path:
    if relative.startswith("/") or ".." in Path(relative).parts:
        raise CodeError("O caminho precisa ficar dentro do repositório.")
    target = (root / relative).resolve()
    if root.resolve() != target and root.resolve() not in target.parents:
        raise CodeError("O caminho precisa ficar dentro do repositório.")
    if _is_secret(target.relative_to(root.resolve())):
        raise CodeError("Esse arquivo é bloqueado: pode conter segredo.")
    return target


def read_file(root: Path, relative: str, start: int = 1, end: int | None = None) -> str:
    target = _resolve(root, relative)
    if not target.is_file():
        raise CodeError(f"{relative} não é um arquivo.")
    lines = target.read_text(errors="replace").splitlines()
    first = max(start, 1)
    last = min(end or first + MAX_LINES - 1, first + MAX_LINES - 1, len(lines))
    body = "\n".join(f"{number}: {lines[number - 1]}" for number in range(first, last + 1))
    return body[:MAX_CHARS] + (f"\n(arquivo tem {len(lines)} linhas)" if last < len(lines) else "")


def list_dir(root: Path, relative: str = "") -> str:
    target = _resolve(root, relative)
    if not target.is_dir():
        raise CodeError(f"{relative or '.'} não é uma pasta.")
    names = []
    for entry in sorted(target.iterdir()):
        if _is_secret(entry.relative_to(root.resolve())):
            continue
        names.append(entry.name + ("/" if entry.is_dir() else ""))
    return "\n".join(names)


def search(root: Path, pattern: str, relative: str = "") -> str:
    scope = _resolve(root, relative).relative_to(root.resolve())
    try:
        done = subprocess.run(
            ["git", "-C", str(root), "grep", "-n", "-I", "-E", "--max-count", "5", "-e", pattern, "--", str(scope) or "."],
            capture_output=True,
            text=True,
            timeout=GREP_TIMEOUT_S,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise CodeError("A busca demorou demais. Use um padrão mais específico.") from None
    hits = [line for line in done.stdout.splitlines() if not _is_secret(Path(line.split(":", 1)[0]))]
    if not hits:
        return "no matches"
    return "\n".join(hits[:MAX_HITS])[:MAX_CHARS]
