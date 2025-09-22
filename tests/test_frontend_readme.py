"""
Tests for Frontend README documentation quality and structure.

Testing framework: pytest.

These tests validate the presence and structure of the Frontend README. They don't hit the network;
link checks are syntactic only. If your README lives in a different path, add it to README_CANDIDATES.
"""

from __future__ import annotations
import os
import re
from pathlib import Path
import pytest

# Candidate README locations for the frontend; extend as needed
README_CANDIDATES = [
    Path("frontend/README.md"),
    Path("web/README.md"),
    Path("apps/frontend/README.md"),
    Path("packages/frontend/README.md"),
    Path("client/README.md"),
    Path("ui/README.md"),
    Path("README.md"),  # fallback: root
]

# Minimal required sections for good developer UX
REQUIRED_HEADINGS = [
    r"^#\s+Frontend\b",
]

RECOMMENDED_SECTIONS = [
    r"^##\s+(Getting\s+Started|Setup)\b",
    r"^##\s+(Scripts|Available\s+Scripts|Commands)\b",
    r"^##\s+(Tech\s*Stack|Stack)\b",
    r"^##\s+(Testing|Tests)\b",
    r"^##\s+(Environment\s*Variables|Configuration)\b",
]

LINK_PATTERN = re.compile(
    r"\[(?P<text>[^\]]+)\]\((?P<url>[^)\s]+)(?:\s+\"[^\"]*\")?\)"
)

CODE_FENCE_PATTERN = re.compile(r"^```[a-zA-Z0-9_-]*\s*$")
HEADING_PATTERN = re.compile(r"^#{1,6}\s+\S+")

def _find_existing_readme() -> Path:
    for p in README_CANDIDATES:
        if p.is_file():
            return p
    pytest.skip("No Frontend README found in expected locations. "
                "Add one of the candidate paths in README_CANDIDATES.")
    return Path()  # unreachable, for type checkers

@pytest.fixture(scope="module")
def readme_path() -> Path:
    return _find_existing_readme()

@pytest.fixture(scope="module")
def readme_text(readme_path: Path) -> str:
    return readme_path.read_text(encoding="utf-8", errors="ignore")

def test_readme_exists_at_known_location(readme_path: Path):
    assert readme_path.exists(), f"Expected README at {readme_path}."

def test_contains_required_top_heading(readme_text: str):
    lines = readme_text.splitlines()
    # Look for a line that satisfies any required heading regex
    found = any(re.search(pattern, line) for pattern in REQUIRED_HEADINGS for line in lines)
    assert found, "README should start with a '# Frontend' heading (or update REQUIRED_HEADINGS)."

@pytest.mark.parametrize("pattern", RECOMMENDED_SECTIONS, ids=lambda p: p.strip("^$"))
def test_contains_recommended_sections(readme_text: str, pattern: str):
    if not re.search(pattern, readme_text, flags=re.MULTILINE):
        pytest.skip(f"Recommended section not found: {pattern}. "
                    "This is a soft recommendation; skipping rather than failing.")

def test_has_at_least_one_code_block(readme_text: str):
    # Ensure there is at least one fenced code block
    lines = readme_text.splitlines()
    fences = [i for i, line in enumerate(lines) if CODE_FENCE_PATTERN.match(line)]
    assert len(fences) >= 2, "Expected at least one fenced code block (opening and closing ```)."

def test_headings_are_well_formed(readme_text: str):
    # Basic heading sanity: each heading line starts with # and has text
    for i, line in enumerate(readme_text.splitlines(), start=1):
        if line.startswith("#"):
            assert HEADING_PATTERN.match(line), f"Malformed heading at line {i}: {line!r}"

def test_links_are_well_formed(readme_text: str):
    # Validate markdown link syntax and that URLs are non-empty/non-placeholder
    bad_links = []
    for match in LINK_PATTERN.finditer(readme_text):
        url = match.group("url")
        text = match.group("text").strip()
        if not url or url in {"#", "TODO", "TBD", "http://", "https://"}:
            bad_links.append((text, url))
        if any(s in url for s in [" ", "\n", "\t", "<", ">"]):
            bad_links.append((text, url))
    assert not bad_links, f"Found malformed or placeholder links: {bad_links}"

def test_table_of_contents_if_present_has_anchors(readme_text: str):
    # If there's a 'Table of Contents' section, ensure it contains at least one anchor link
    toc_match = re.search(r"^##\s+Table\s+of\s+Contents\s*$", readme_text, flags=re.MULTILINE | re.IGNORECASE)
    if not toc_match:
        pytest.skip("No Table of Contents section detected; skipping.")
    section_text = readme_text[toc_match.end():]
    # Consider up to the next H2 as the ToC block
    next_h2 = re.search(r"^##\s+\S+", section_text, flags=re.MULTILINE)
    toc_block = section_text[: next_h2.start()] if next_h2 else section_text
    anchors = LINK_PATTERN.findall(toc_block)
    assert anchors, "Table of Contents present but contains no anchor links."

def test_scripts_section_lists_commands_if_present(readme_text: str):
    # If Scripts section exists, assert at least one bullet with a code-like fragment
    m = re.search(r"^##\s+(Scripts|Available\s+Scripts|Commands)\s*$",
                  readme_text, flags=re.MULTILINE | re.IGNORECASE)
    if not m:
        pytest.skip("No Scripts/Commands section; skipping.")
    section = readme_text[m.end():]
    next_h2 = re.search(r"^##\s+\S+", section, flags=re.MULTILINE)
    block = section[: next_h2.start()] if next_h2 else section
    # Look for bullets with inline code (e.g., `npm run dev`, yarn, pnpm, etc.)
    has_cmd = re.search(r"^\s*[-*+]\s+.*`[^`]+`", block, flags=re.MULTILINE)
    assert has_cmd, "Scripts section should contain at least one bullet with an inline code command."

def test_images_have_alt_text(readme_text: str):
    # Markdown image syntax \![alt](url)
    img_pattern = re.compile(r"\!\[(?P<alt>[^\]]*)\]\((?P<url>[^)]+)\)")
    bad = []
    for m in img_pattern.finditer(readme_text):
        alt = (m.group("alt") or "").strip()
        url = (m.group("url") or "").strip()
        if not alt or not url:
            bad.append((alt, url))
    if bad:
        pytest.skip(f"Images without alt text or URL found (best practice, soft check): {bad}")

def test_badges_if_present_are_first_lines(readme_text: str):
    # If badge images exist, they should be near the top (first 15 lines)
    badge = re.compile(r"\!\[[^\]]*\]\(https?://[^)]+(shields\.io|badge|status)[^)]+?\)")
    lines = readme_text.splitlines()
    badge_lines = [i for i, line in enumerate(lines[:15], start=1) if badge.search(line)]
    if any(badge.search(line) for line in lines) and not badge_lines:
        pytest.skip("Badges found but not near the top; soft guidance only.")

def test_no_long_lines_exceeding_180_chars(readme_text: str):
    long_lines = []
    for i, line in enumerate(readme_text.splitlines(), start=1):
        # ignore code fences and URLs which can be long legitimately
        if line.strip().startswith("```") or "http" in line:
            continue
        if len(line) > 180:
            long_lines.append(i)
    if long_lines:
        pytest.skip(f"Found lines exceeding 180 characters at {long_lines} (style recommendation).")