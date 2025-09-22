# Testing library/framework: Python's built-in unittest (pytest-compatible discovery)
# These tests validate the AI models documentation quality and integrity.


import re
import unittest
import logging
from pathlib import Path
from urllib.parse import urlparse, unquote


def _repo_root() -> Path:
    # tests/ is expected; parent of this file's directory is repo root
    return Path(__file__).resolve().parents[1]


def _candidate_doc_paths(root: Path):
    return [
        root / "docs" / "ai_models.md",
        root / "docs" / "AI_MODELS.md",
        root / "docs" / "ai-models.md",
        root / "docs" / "ai_models" / "README.md",
        root / "README.md",  # fallback if project keeps a monolithic README
    ]


def _parse_headings(text: str):
    """
    Return list of (level, title) for ATX-style markdown headings.
    """
    headings = []
    for line in text.splitlines():
        m = re.match(r'^\s*(#{1,6})\s+(.+?)\s*$', line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip().rstrip('#').strip()
            headings.append((level, title))
    return headings


def _find_ai_models_doc():
    """
    Locate a Markdown document whose H1 is 'AI models' (case-insensitive).
    Returns (path, text) or (None, None) if not found.
    """
    root = _repo_root()

    # Check common locations first
    for p in _candidate_doc_paths(root):
        if p.exists():
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError as e:
                logging.debug("Failed to read %s: %s", p, e)
                continue
            if re.search(r'^\s*#\s*AI models\s*$', text, flags=re.I | re.M):
                return p, text

    # Fallback: scan docs/ then root for any *.md that has the H1
    md_paths = []
    docs_dir = root / "docs"
    if docs_dir.exists():
        md_paths.extend(docs_dir.rglob("*.md"))
    md_paths.extend(root.glob("*.md"))

    for p in md_paths:
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError as e:
            logging.debug("Failed to read %s: %s", p, e)
            continue
        if re.search(r'^\s*#\s*AI models\s*$', text, flags=re.I | re.M):
            return p, text

    return None, None


def _iter_markdown_links(text: str):
    """
    Yield hrefs for inline markdown links [text](target "title"), excluding images.
    """
    link_re = re.compile(r'(?<\!\\!)\[[^\]]+\]\(([^)\s]+)(?:\s+"[^"]*")?\)')
    for m in link_re.finditer(text):
        yield m.group(1)


def _is_external(href: str) -> bool:
    parsed = urlparse(href)
    return bool(parsed.scheme and parsed.scheme not in ("",)) or href.startswith("//")


def _split_fragment(href: str):
    if "#" in href:
        path, frag = href.split("#", 1)
        return path, frag
    return href, None


def _slugify(s: str) -> str:
    s = unquote(s.strip().lower())
    # Remove non-word chars except spaces/hyphens, then collapse spaces to hyphens
    s = re.sub(r"[^\w\s\-]", "", s)
    s = re.sub(r"\s+", "-", s)
    return s


class TestAIModelsReadme(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc_path, cls.doc_text = _find_ai_models_doc()

    def _require_doc_or_skip(self):
        if self.doc_path is None:
            self.skipTest("AI models doc not found; expected a Markdown file with H1 '# AI models' under docs/ or root.")

    def test_doc_exists(self):
        self.assertIsNotNone(
            self.doc_path,
            "AI models doc not found; create docs/ai_models.md (with H1 '# AI models').",
        )
        # Basic sanity: file is non-empty
        if self.doc_path:
            self.assertGreater(self.doc_path.stat().st_size, 0, "AI models doc is empty.")

    def test_h1_title_single_and_correct(self):
        self._require_doc_or_skip()
        headings = _parse_headings(self.doc_text)
        h1_titles = [t for lvl, t in headings if lvl == 1]
        self.assertEqual(len(h1_titles), 1, f"Expected exactly one H1 heading, found {len(h1_titles)}.")
        self.assertEqual(h1_titles[0].strip().lower(), "ai models", f"H1 should be 'AI models', got {h1_titles[0]!r}.")

    def test_contains_basic_sections(self):
        """
        Require at least one of each group to encourage actionable documentation:
        - ('Overview', 'Usage')
        - ('Supported models', 'Models')
        """
        self._require_doc_or_skip()
        headings = [t.lower() for lvl, t in _parse_headings(self.doc_text)]

        groups = [
            ("overview", "usage"),
            ("supported models", "models"),
        ]
        for group in groups:
            self.assertTrue(
                any(g in headings for g in group),
                f"Document should include at least one of the sections: {group}",
            )

    def test_no_placeholders_or_todos(self):
        self._require_doc_or_skip()
        forbidden = re.compile(r"\b(TODO|TBD|FIXME|lorem ipsum)\b", re.I)
        self.assertIsNone(forbidden.search(self.doc_text), "Remove placeholders like TODO/TBD/FIXME/lorem ipsum.")

    def test_relative_links_and_anchors_resolve(self):
        """
        Validate relative file links exist and anchors (if present) map to headings
        in the target file using a simple slugify similar to GitHub-style anchors.
        """
        self._require_doc_or_skip()
        base_dir = self.doc_path.parent
        missing = []

        for href in _iter_markdown_links(self.doc_text):
            # Skip anchors within the same document and external links
            if href.startswith("#") or _is_external(href):
                continue

            target_part, frag = _split_fragment(href)

            target_path = (base_dir / unquote(target_part)).resolve()

            if not target_path.exists():
                missing.append(href)
                continue

            if frag:
                try:
                    other_text = target_path.read_text(encoding="utf-8", errors="ignore")
                except OSError as e:
                    # Can't read target; treat as missing anchor
                    logging.debug("Failed to read %s: %s", target_path, e)
                    missing.append(href)
                    continue
                headings = _parse_headings(other_text)
                slugs = {_slugify(t) for _, t in headings}
                if _slugify(frag) not in slugs:
                    missing.append(href)

        self.assertFalse(missing, f"Broken relative links/anchors detected: {missing}")

    def test_no_excessively_long_lines(self):
        """
        Encourage readability by flagging extremely long lines (> 200 chars)
        which can hurt diffs and reviews.
        """
        self._require_doc_or_skip()
        too_long = [i + 1 for i, line in enumerate(self.doc_text.splitlines()) if len(line) > 200]
        self.assertFalse(too_long, f"Lines longer than 200 characters at: {too_long}")


if __name__ == "__main__":
    unittest.main()