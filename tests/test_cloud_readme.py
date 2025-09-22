"""
Tests for Cloud/Infra README documentation.

Testing library and framework: pytest.

Scope:
- Focus on validating Cloud README(s) content and structure as part of this PR's diff.
- These tests intentionally verify documentation quality to prevent regressions.
"""

import os
import re
from pathlib import Path
import pytest

# Configuration: candidate README paths to check. Extend if your repo uses different paths.
CANDIDATE_READMES = [
    Path("cloud/README.md"),
    Path("infra/README.md"),
    Path("infrastructure/README.md"),
    Path("README.md"),  # fallback if the main README documents cloud infra
]

# Required sections to be present in the Cloud README (case-insensitive).
REQUIRED_SECTIONS = [
    r"Architecture",
    r"Provisioning|Deployment|How to Deploy",
    r"Environments",
    r"Security",
    r"Cost|Costs|Budget",
    r"Operations|Observability|Monitoring|Logging",
    r"Backup|Disaster Recovery|DR",
]

H1_PATTERN = re.compile(r"^#\s+Cloud Infrastructure\s*$", re.IGNORECASE)
HEADER_PATTERN = re.compile(r"^(?P<level>#{1,6})\s+(?P<text>.+?)\s*$")
LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

def _read_first_existing(paths):
    for p in paths:
        if p.is_file():
            return p.read_text(encoding="utf-8"), p
    return None, None

@pytest.fixture(scope="module")
def cloud_readme_text_and_path():
    text, path = _read_first_existing([Path(p) for p in CANDIDATE_READMES])
    if text is None:
        pytest.skip(
            "No Cloud README found in expected locations. "
            "Consider adding cloud/README.md (preferred) or infra/README.md"
        )
    return text, path

def test_title_is_cloud_infrastructure(cloud_readme_text_and_path):
    text, path = cloud_readme_text_and_path
    first_nonempty = next((ln for ln in text.splitlines() if ln.strip()), "")
    assert H1_PATTERN.match(first_nonempty) is not None, (
        f"{path}: First non-empty line should be '# Cloud Infrastructure'"
    )

def test_required_sections_present(cloud_readme_text_and_path):
    text, path = cloud_readme_text_and_path
    # Build a map of lowercased headers for quick membership tests
    headers = [m.group("text").strip().lower() for m in HEADER_PATTERN.finditer(text)]
    def section_present(pattern: str) -> bool:
        rx = re.compile(pattern, re.IGNORECASE)
        return any(rx.search(h) for h in headers)

    missing = [pat for pat in REQUIRED_SECTIONS if not section_present(pat)]
    assert not missing, f"{path}: Missing required sections matching: {missing}"

def test_no_empty_sections(cloud_readme_text_and_path):
    text, path = cloud_readme_text_and_path
    lines = text.splitlines()
    for i, line in enumerate(lines[:-1]):
        m = HEADER_PATTERN.match(line)
        if not m:
            continue
        # find next non-empty line
        j = i + 1
        while j < len(lines) and lines[j].strip() == "":
            j += 1
        assert j < len(lines), f"{path}: Section '{line.strip()}' has no content."
        assert not HEADER_PATTERN.match(lines[j]), (
            f"{path}: Section '{line.strip()}' is empty (followed immediately by another header)."
        )

def _is_relative_link(url: str) -> bool:
    return not re.match(r"^[a-z]+://", url) and not url.startswith("#") and not url.startswith("mailto:")

def test_relative_links_resolve(cloud_readme_text_and_path):
    text, path = cloud_readme_text_and_path
    repo_root = Path(".").resolve()
    doc_dir = path.parent.resolve()

    unresolved = []
    for m in LINK_PATTERN.finditer(text):
        url = m.group(2).strip()
        if not _is_relative_link(url):
            continue
        # strip anchors like file.md#section
        file_part = url.split("#", 1)[0]
        candidate = (doc_dir / file_part).resolve()
        # Normalize to repo root if link starts with '/'
        if file_part.startswith("/"):
            candidate = (repo_root / file_part.lstrip("/")).resolve()
        if not candidate.exists():
            unresolved.append(url)

    assert not unresolved, (
        f"{path}: Found unresolved relative links: {unresolved}. "
        "Ensure referenced files exist or adjust links."
    )

@pytest.mark.parametrize(
    "bad_title",
    [
        "# cloud infrastructure (typo case allowed only if exact header matches is required here)",
        "# Infrastructure",
        "Cloud Infrastructure",
        "## Cloud Infrastructure",
        "# Cloud  Infrastructure",  # double space
    ],
)
def test_title_strictness_examples(bad_title, tmp_path):
    """
    Edge-case demonstration: a temporary README with an incorrect title should fail H1 strictness.
    This does not depend on repo files; it validates the regex and expectations.
    """
    content = bad_title + "\n\n## Architecture\nSome details.\n"
    p = tmp_path / "README.md"
    p.write_text(content, encoding="utf-8")

    text = p.read_text(encoding="utf-8")
    first_nonempty = next((ln for ln in text.splitlines() if ln.strip()), "")
    assert H1_PATTERN.match(first_nonempty) is None

def test_section_detection_tolerates_variants(tmp_path):
    """
    Validates REQUIRED_SECTIONS patterns accept reasonable synonyms/variants.
    """
    body = """# Cloud Infrastructure

## Deployment
...

## Environments
...

## Security
...

## Costs
...

## Observability
...

## DR
...
"""
    p = tmp_path / "README.md"
    p.write_text(body, encoding="utf-8")
    text = p.read_text(encoding="utf-8")

    headers = [m.group("text").strip().lower() for m in HEADER_PATTERN.finditer(text)]

    def section_present(pattern: str) -> bool:
        rx = re.compile(pattern, re.IGNORECASE)
        return any(rx.search(h) for h in headers)

    missing = [pat for pat in REQUIRED_SECTIONS if not section_present(pat)]
    assert not missing, f"Should accept synonyms; missing: {missing}"