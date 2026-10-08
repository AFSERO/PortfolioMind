"""Controlled Markdown protocol loader with strict path-traversal guards (Part 4C)."""

import os
from dataclasses import dataclass
from pathlib import Path


def resolve_protocols_dir(protocols_dir: Path | str | None = None) -> Path:
    """Safely and flexibly resolve the canonical protocols directory across execution environments."""
    if protocols_dir is not None:
        p = Path(protocols_dir).resolve()
        if p.is_dir():
            return p
        return p

    # Check environment variable
    for env_var in ("FINANCE_PROTOCOLS_DIR", "PROTOCOLS_DIR"):
        val = os.environ.get(env_var)
        if val:
            p = Path(val).resolve()
            if p.is_dir():
                return p

    # Standard relative to this source file: Finance/src/investment_intelligence/protocols.py -> Finance/system/protocols
    try:
        source_based = Path(__file__).resolve().parents[2] / "system" / "protocols"
        if source_based.is_dir():
            return source_based.resolve()
    except IndexError:
        pass

    # Walk up from this file's parents looking for Finance/system/protocols or system/protocols
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        cand1 = parent / "Finance" / "system" / "protocols"
        if cand1.is_dir():
            return cand1.resolve()
        cand2 = parent / "system" / "protocols"
        if cand2.is_dir() and (parent / "src" / "investment_intelligence").is_dir():
            return cand2.resolve()

    # Walk up from current working directory
    try:
        cwd = Path.cwd().resolve()
        for parent in [cwd, *cwd.parents]:
            cand1 = parent / "Finance" / "system" / "protocols"
            if cand1.is_dir():
                return cand1.resolve()
            cand2 = parent / "system" / "protocols"
            if cand2.is_dir():
                return cand2.resolve()
    except Exception:
        pass

    # Standard container mount locations
    for container_path in (
        Path("/Finance/system/protocols"),
        Path("/app/Finance/system/protocols"),
    ):
        if container_path.is_dir():
            return container_path.resolve()

    # Fallback to source-based default even if not yet existing
    return (Path(__file__).resolve().parents[2] / "system" / "protocols").resolve()


DEFAULT_PROTOCOLS_DIR = resolve_protocols_dir()


class ExecutionError(Exception):
    """Base exception for protocol execution layer."""


class ProtocolNotFoundError(ExecutionError, LookupError):
    """Requested protocol Markdown file does not exist or is invalid."""


@dataclass(frozen=True)
class ProtocolDefinition:
    """Loaded protocol content and canonical identifier."""

    canonical_name: str
    content: str
    path: str


def load_protocol(
    name: str,
    protocols_dir: Path | str | None = None,
) -> ProtocolDefinition:
    """Safely load a protocol Markdown file from the protocols directory.

    Guards:
    - Rejects arbitrary filesystem paths and path-traversal sequences (.., /, \\).
    - Requires alphanumeric characters and hyphens only.
    - Normalizes underscores to hyphens and lowercases the canonical name.
    - Resolves strictly inside the protocols directory.
    - Raises ProtocolNotFoundError if missing or invalid.
    """
    if not isinstance(name, str) or not name.strip():
        raise ProtocolNotFoundError("Protocol name must be non-empty text")

    clean_name = name.strip()
    if "/" in clean_name or "\\" in clean_name or "\0" in clean_name or ".." in clean_name:
        raise ProtocolNotFoundError(
            f"Invalid protocol name '{name}': path traversal or separators not allowed"
        )

    canonical_name = clean_name.lower().replace("_", "-")
    # Allow alphanumeric and hyphens only
    if not all(c.isalnum() or c == "-" for c in canonical_name):
        raise ProtocolNotFoundError(
            f"Invalid protocol name '{name}': only alphanumeric characters and hyphens allowed"
        )

    base_dir = resolve_protocols_dir(protocols_dir)
    resolved_base = base_dir.resolve()
    if not resolved_base.is_dir():
        raise ProtocolNotFoundError(
            f"Protocols directory does not exist or is not a directory: {resolved_base}"
        )

    target_file = (resolved_base / f"{canonical_name}.md").resolve()

    try:
        target_file.relative_to(resolved_base)
    except ValueError:
        raise ProtocolNotFoundError(
            f"Protocol name '{name}' resolves outside the allowed protocols directory: {resolved_base}"
        )

    if not target_file.is_file():
        available = sorted([f.stem for f in resolved_base.glob("*.md") if f.is_file()])
        avail_str = (
            f" Available protocols in {resolved_base}: {', '.join(available)}"
            if available
            else f" (no .md files found in {resolved_base})"
        )
        raise ProtocolNotFoundError(
            f"Protocol '{canonical_name}' not found at {target_file}.{avail_str}"
        )

    content = target_file.read_text(encoding="utf-8")
    return ProtocolDefinition(
        canonical_name=canonical_name,
        content=content,
        path=str(target_file),
    )


def list_available_protocols(protocols_dir: Path | str | None = None) -> list[str]:
    """List available protocol names in canonical format."""
    base_dir = resolve_protocols_dir(protocols_dir)
    if not base_dir.is_dir():
        return []
    return sorted([f.stem for f in base_dir.glob("*.md") if f.is_file()])
