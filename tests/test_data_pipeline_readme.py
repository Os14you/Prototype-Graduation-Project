"""
Tests for the Data Pipeline README documentation.

Testing library/framework: pytest
- These tests validate presence, structure, and link integrity (relative links) of the Data Pipeline README.
- They are intentionally tolerant to repository differences while still providing meaningful checks.

If your repository places the Data Pipeline guide in a non-standard location,
adjust the candidate discovery in find_data_pipeline_readmes() below.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Iterable, List, Tuple
import urllib.parse

import pytest


# Heuristics: assume tests/ lives at repo_root/tests/
REPO_ROOT = Path(__file__).resolve().parent.parent


SKIP_DIR_NAMES = {
    ".git", ".hg", ".svn", ".tox", ".venv", "venv", "env",
    "node_modules", "dist", "build", "site-packages", ".mypy_cache",
    ".pytest_cache", ".cache", "target", "__pycache__", ".next", ".yarn"
}


def is_excluded_path(p: Path) -> bool:
    parts_lower = [part.lower() for part in p.parts]
    for name in SKIP_DIR_NAMES:
        if name in parts_lower:
            return True
    for part in parts_lower:
        if part.startswith(".") and part != ".":
            return True
    return False


def find_data_pipeline_readmes(repo_root: Path) -> List[Path]:
    """Return a prioritized list of README-like markdown files for the Data Pipeline."""
    candidates: List[Path] = []

    # Common explicit candidates
    explicit = [
        repo_root / "DATA_PIPELINE.md",
        repo_root / "data-pipeline.md",
        repo_root / "data_pipeline.md",
        repo_root / "docs" / "DATA_PIPELINE.md",
        repo_root / "docs" / "data-pipeline.md",
        repo_root / "docs" / "data_pipeline.md",
        repo_root / "docs" / "README.md",
        repo_root / "data" / "README.md",
        repo_root / "pipelines" / "README.md",
        repo_root / "data-pipeline" / "README.md",
        repo_root / "data_pipeline" / "README.md",
        repo_root / "README.md",
    ]
    for p in explicit:
        if p.exists() and p.suffix.lower() == ".md":
            candidates.append(p)

    # Dynamic discovery: any *.md where path suggests data-pipeline
    try:
        for p in repo_root.rglob("*.md"):
            if is_excluded_path(p):
                continue
            pathlower = "/".join(part.lower() for part in p.parts)
            if ("data" in pathlower and "pipeline" in pathlower) or (
                p.name.lower() == "readme.md"
                and ("data" in pathlower or "pipeline" in pathlower)
            ):
                candidates.append(p)
    except Exception:
        # Be defensive in case of permission errors in unusual repos
        pass

    # De-duplicate while preserving order
    seen = set()
    unique_candidates: List[Path] = []

    for p in candidates:
        if p not in seen:
            seen.add(p)
            unique_candidates.append(p)

    # Prioritize by heuristics
    def score(path: Path) -> int:
        s = 0
        pathlower = "/".join(part.lower() for part in path.parts)
        if "docs" in pathlower:
            s += 3
        if "data" in pathlower and "pipeline" in pathlower:
            s += 5
        if path.name.lower() != "readme.md":
            s += 1
        if path.name.lower() in {"data-pipeline.md", "data_pipeline.md", "data pipeline.md"}:
            s += 2
        return s

    unique_candidates.sort(key=score, reverse=True)
    return unique_candidates


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_headings(markdown: str) -> List[Tuple[int, str]]:
    """
    Return list of (level, text) for ATX-style headings (#, ##, ###, ...).
    """
    headings: List[Tuple[int, str]] = []
    for m in re.finditer(r"(?m)^\s*(#{1,6})\s+(.+?)\s*$", markdown):
        level = len(m.group(1))
        text = re.sub(r"\s+#\s*$", "", m.group(2)).strip()
        headings.append((level, text))
    return headings


def slugify_github(text: str) -> str:
    """
    Approximate GitHub-style anchor slug:
    - lower case
    - remove non-word characters except hyphens and spaces
    - collapse whitespace to single hyphens
    - strip leading/trailing hyphens
    """
    s = text.strip().lower()
    # Remove punctuation except spaces and hyphens
    s = re.sub(r"[^\w\s-]", "", s)
    # Replace whitespace with hyphens
    s = re.sub(r"\s+", "-", s)
    # Collapse multiple hyphens
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def extract_markdown_links(markdown: str) -> Tuple[List[str], List[str]]:
    """
    Return (links, image_links) extracted from markdown.
    Each item is the raw target inside parentheses, possibly with an anchor (#...).
    """
    # Links (exclude images via negative lookbehind for '!')
    links = re.findall(r'(?m)(?<!!)\[[^\]]*?\]\(([^)\s]+)\)', markdown)
    # Images
    image_links = re.findall(r'(?m)!\[[^\]]*?\]\(([^)\s]+)\)', markdown)
    return links, image_links


@pytest.fixture(scope="module")
def data_pipeline_md_files() -> List[Path]:
    files = find_data_pipeline_readmes(REPO_ROOT)
    return files


def test_at_least_one_data_pipeline_markdown_found(data_pipeline_md_files: List[Path]) -> None:
    assert data_pipeline_md_files, (
        "Expected to find at least one Data Pipeline README markdown file. "
        "Searched common locations and names (e.g., DATA_PIPELINE.md, docs/, data-pipeline/, README.md)."
    )


def test_title_present_as_h1_in_some_candidate(data_pipeline_md_files: List[Path]) -> None:
    """
    Ensure that at least one candidate has '# Data pipeline' (case/sep-insensitive) as a heading.
    """
    pattern = re.compile(r"(?im)^\s*#\s*data\s*[-_ ]?\s*pipeline\b")
    matched: List[Path] = []
    for p in data_pipeline_md_files:
        md = read_text(p)
        if pattern.search(md):
            matched.append(p)
    assert matched, "No '# Data pipeline' H1 title found in any candidate README."


def test_has_key_sections_in_primary_readme(data_pipeline_md_files: List[Path]) -> None:
    """
    Validate presence of several important sections. To remain tolerant across repos,
    we require a minimum number of matches rather than all.
    """
    # Choose the highest priority file
    primary = data_pipeline_md_files[0]
    md = read_text(primary)

    section_patterns = [
        r"(?im)^\s*##\s*Overview\b",
        r"(?im)^\s*##\s*(Architecture|Design)\b",
        r"(?im)^\s*##\s*(Setup|Installation)\b",
        r"(?im)^\s*##\s*(Usage|Running|Execution)\b",
        r"(?im)^\s*##\s*(Configuration|Environment\s+Variables?)\b",
        r"(?im)^\s*##\s*(Testing|Validation)\b",
        r"(?im)^\s*##\s*(Troubleshooting|FAQ)\b",
        r"(?im)^\s*##\s*(Data\s+Sources?|Inputs?)\b",
        r"(?im)^\s*##\s*(Outputs?|Sinks|Destinations)\b",
    ]
    hits = sum(bool(re.search(pat, md)) for pat in section_patterns)
    assert hits >= 3, (
        f"Expected at least 3 key sections in {primary} "
        "(e.g., Overview, Architecture, Setup, Usage, Configuration, Testing, Troubleshooting)."
    )


def _resolve_relative(base_dir: Path, target: str) -> Path:
    # Strip anchor if present
    path_part = target.split("#", 1)[0]
    return (base_dir / path_part).resolve()


def test_relative_links_resolve_to_files_when_present(data_pipeline_md_files: List[Path]) -> None:
    """
    Check that relative links in the primary README resolve to existing files within the repo.
    Absolute URLs (http/https/mailto) and pure anchors (#...) are ignored.
    """
    primary = data_pipeline_md_files[0]
    md = read_text(primary)

    links, _ = extract_markdown_links(md)
    base = primary.parent

    missing: List[str] = []
    for link in links:
        # Skip absolute URLs and pure anchors
        lower = link.lower()
        if lower.startswith(("http://", "https://", "mailto:")):
            continue
        if lower.startswith("#"):
            continue
        # Ignore absolute filesystem-like or root-absolute paths; treat them as non-checkable here
        if os.path.isabs(link) or lower.startswith("/"):
            continue

        resolved = _resolve_relative(base, link)
        if not resolved.exists():
            missing.append(link)

    assert not missing, (
        f"Found relative links in {primary} that do not resolve to files: {missing}"
    )


def test_relative_image_paths_exist(data_pipeline_md_files: List[Path]) -> None:
    """
    Ensure that relative image references exist (useful for diagrams in docs).
    """
    primary = data_pipeline_md_files[0]
    md = read_text(primary)

    _, images = extract_markdown_links(md)
    base = primary.parent

    missing_images: List[str] = []
    for img in images:
        lower = img.lower()
        if lower.startswith(("http://", "https://")):
            continue
        if os.path.isabs(img) or lower.startswith("/"):
            # Skip absolute paths - cannot validate reliably here
            continue
        resolved = _resolve_relative(base, img)
        if not resolved.exists():
            missing_images.append(img)

    # Be tolerant: only assert if images are referenced at all
    if images:
        assert not missing_images, f"Image(s) not found relative to {primary}: {missing_images}"


def test_table_of_contents_anchors_match_headings_if_toc_present(data_pipeline_md_files: List[Path]) -> None:
    """
    If a 'Table of Contents' section exists with anchors, ensure the anchors correspond to headings.
    This is tolerant: requires at least 70% of anchors to match.
    """
    primary = data_pipeline_md_files[0]
    md = read_text(primary)

    # Locate ToC block (from '## Table of Contents' until the next '## ')
    toc_start = re.search(r"(?im)^\s*##\s*Table\s+of\s+Contents\s*$", md)
    if not toc_start:
        pytest.skip("No 'Table of Contents' section present; skipping anchor validation.")

    after = md[toc_start.end():]
    next_h2 = re.search(r"(?im)^\s*##\s+.+$", after)
    toc_block = after[: next_h2.start()] if next_h2 else after

    toc_anchors = [
        m.group(1)
        for m in re.finditer(r'\[[^\]]+?\]\(#([^)#\s]+)\)', toc_block)
    ]
    if not toc_anchors:
        pytest.skip("No anchors found in Table of Contents; skipping anchor validation.")

    headings = extract_headings(md)
    heading_anchors = {slugify_github(text) for _, text in headings}

    matches = sum(1 for a in toc_anchors if a in heading_anchors)
    ratio = matches / max(len(toc_anchors), 1)
    assert ratio >= 0.7, (
        f"Only {matches}/{len(toc_anchors)} ToC anchors matched headings; expected at least 70%."
    )


def test_no_merge_conflict_markers_in_primary_readme(data_pipeline_md_files: List[Path]) -> None:
    """
    Guard against accidentally committed merge conflict markers.
    """
    primary = data_pipeline_md_files[0]
    md = read_text(primary)
    assert (
        "<<<" not in md
        and ">>>" not in md
        and "======" not in md
    ), f"Merge conflict markers detected in {primary}"