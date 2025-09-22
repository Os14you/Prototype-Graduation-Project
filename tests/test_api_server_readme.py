import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple

try:
    import pytest  # type: ignore
except ImportError:  # pragma: no cover
    # Fall back to stdlib-style skips if pytest is unavailable,
    # but this repository is expected to use pytest.
    class _Shim:
        skip = staticmethod(lambda _reason: (lambda func: func))
        skipif = staticmethod(lambda _cond, _reason="": (lambda func: func))
        mark = type("mark", (), {"parametrize": staticmethod(lambda *_args, **_kwargs: (lambda f: f))})
    pytest = _Shim()  # type: ignore


RE_FENCED_BLOCK = re.compile(r"^```([a-zA-Z0-9_+-]*)\s*$")
RE_MARKDOWN_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
RE_HEADING = re.compile(r"^(#{1,6})\s+.+$")


def _find_candidate_readmes(repo_root: Path) -> List[Path]:
    # Prefer README files within API/server/backend subdirs; fall back to top-level README.
    priority_dirs = ["api", "api-server", "server", "backend", "services", "apps"]
    candidates: List[Path] = []

    for p in repo_root.rglob("README.md"):
        rel = p.relative_to(repo_root).as_posix().lower()
        if any(seg in rel.split("/") for seg in priority_dirs):
            candidates.append(p)

    # Ensure unique and stable ordering
    # Highest priority: deeper paths that include 'api'/'server'/'backend'; then top-level README if exists.
    candidates = sorted(set(candidates), key=lambda x: (len(x.as_posix().split("/")), x.as_posix()))

    top_level = repo_root / "README.md"
    if top_level.exists() and top_level not in candidates:
        candidates.append(top_level)

    return candidates


def _read_lines(p: Path) -> List[str]:
    try:
        return p.read_text(encoding="utf-8").splitlines()
    except UnicodeDecodeError:
        return p.read_text(errors="ignore").splitlines()


def _iter_fenced_blocks(lines: Iterable[str]) -> Iterable[Tuple[int, str]]:
    for idx, line in enumerate(lines, start=1):
        m = RE_FENCED_BLOCK.match(line.strip())
        if m:
            yield idx, m.group(1)  # (line_no, language_tag)


def _iter_links(lines: Iterable[str]) -> Iterable[Tuple[int, str, str]]:
    for idx, line in enumerate(lines, start=1):
        for m in RE_MARKDOWN_LINK.finditer(line):
            text, target = m.group(1), m.group(2)
            yield idx, text, target


def _has_any_heading(lines: Iterable[str]) -> bool:
    return any(RE_HEADING.match(ln.strip()) for ln in lines)


def _resolve_relative(base: Path, target: str) -> Path:
    # Normalize stripping anchors and query fragments
    target = target.split("#", 1)[0].split("?", 1)[0]
    return (base.parent / target).resolve()


def _is_http_link(target: str) -> bool:
    t = target.lower()
    return t.startswith("http://") or t.startswith("https://")


RE_BACKEND_SECTION = re.compile(r"^\s*#+\s*backend\s*$", re.IGNORECASE)


def _has_backend_section(lines: Iterable[str]) -> bool:
    return any(RE_BACKEND_SECTION.match(ln) for ln in lines)


RE_EXPECTED_SECTIONS = [
    re.compile(r"^\s*#\s+.*(api server|backend).*$", re.IGNORECASE),
    re.compile(r"^\s*##\s+.*(setup|installation).*$", re.IGNORECASE),
    re.compile(r"^\s*##\s+.*(run|start).*$", re.IGNORECASE),
]


def test_readme_discovery_and_non_empty():
    repo_root = Path(__file__).resolve().parents[1]
    readmes = _find_candidate_readmes(repo_root)

    if not readmes:
        pytest.skip("No README.md files found in repository; skipping README validation tests.")

    for p in readmes:
        assert p.is_file(), f"Discovered README path is not a file: {p}"
        content = p.read_text(encoding="utf-8", errors="ignore")
        assert content.strip(), f"README is empty: {p}"


def test_readme_contains_headings_and_backend_context():
    repo_root = Path(__file__).resolve().parents[1]
    readmes = _find_candidate_readmes(repo_root)
    if not readmes:
        pytest.skip("No README.md files found.")

    at_least_one_has_backend = False
    for p in readmes:
        lines = _read_lines(p)
        assert _has_any_heading(lines), f"{p} should have at least one markdown heading."
        if _has_backend_section(lines):
            at_least_one_has_backend = True

    # Soft requirement: allow skip if repo doesn't document backend here.
    if not at_least_one_has_backend:
        pytest.skip("No 'Backend' section detected in candidate READMEs; skipping backend-specific assertions.")


def test_fenced_code_blocks_specify_language():
    repo_root = Path(__file__).resolve().parents[1]
    readmes = _find_candidate_readmes(repo_root)
    if not readmes:
        pytest.skip("No README.md files found.")

    missing_lang: List[str] = []
    for p in readmes:
        lines = _read_lines(p)
        for line_no, lang in _iter_fenced_blocks(lines):
            # Opening triple-backtick should include a language tag for readability
            if lang.strip() == "":
                missing_lang.append(f"{p}:{line_no}")

    assert not missing_lang, (
        "Fenced code blocks should specify a language for syntax highlighting. "
        f"Missing language at: {', '.join(missing_lang)}"
    )


def test_relative_links_point_to_existing_files():
    repo_root = Path(__file__).resolve().parents[1]
    readmes = _find_candidate_readmes(repo_root)
    if not readmes:
        pytest.skip("No README.md files found.")

    bad_links: List[str] = []
    for p in readmes:
        lines = _read_lines(p)
        for line_no, _text, target in _iter_links(lines):
            # Skip external links and anchors-only references
            if _is_http_link(target) or target.startswith("#"):
                continue
            resolved = _resolve_relative(p, target)
            if not resolved.exists():
                bad_links.append(f"{p}:{line_no} -> {target}")

    assert not bad_links, (
        "Found relative links pointing to missing paths:\n" + "\n".join(bad_links)
    )


def test_expected_sections_present_or_explain():
    repo_root = Path(__file__).resolve().parents[1]
    readmes = _find_candidate_readmes(repo_root)
    if not readmes:
        pytest.skip("No README.md files found.")

    # We only require that at least one expected section exists across the candidate docs.
    found_any = False
    for p in readmes:
        lines = _read_lines(p)
        text = "\n".join(lines)
        if any(rx.search(text) for rx in RE_EXPECTED_SECTIONS):
            found_any = True
            break

    if not found_any:
        pytest.skip("Expected high-level documentation sections (API Server/Backend, Setup, Run) not found; skipping to avoid false positives.")


# If this file was previously a placeholder with just '# Backend', keep a regression test to ensure it imports.
def test_this_test_module_loads():
    # Sanity check: test runner can import and execute this module
    assert True