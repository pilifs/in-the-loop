#!/usr/bin/env python3
"""Tests for the pages a reader starts from, ARCHITECTURE.md and README.md: every file they send a reader to is in
the repository, and every heading they link to is on the page they name.

ARCHITECTURE.md says which file owns each decision, so a link there that leads nowhere is the page describing a
repository that is not this one: a file was moved or removed and the map was not updated with it. The check is of
links only. Whether a sentence is true is for whoever changes the owner (the page's last section).

Run: python3 llm-dlc/tools/test_architecture.py"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGES = ("ARCHITECTURE.md", "README.md")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
HEADING = re.compile(r"^#{1,6} +(.+?)\s*$")


def prose(text: str) -> list[str]:
    """A page's lines outside its fenced blocks: a diagram's or a command's brackets are not links."""
    out, fenced = [], False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced:
            out.append(line)
    return out


def slug(heading: str) -> str:
    """The anchor GitHub gives a heading: lower case, a link's text without its target, punctuation dropped but for
    hyphens and underscores, and each space a hyphen."""
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", heading).lower()
    return re.sub(r"[^\w\- ]", "", text).replace(" ", "-")


def anchors(text: str) -> set[str]:
    """Every anchor of a page: each heading's, and `-1`, `-2` for a heading that repeats."""
    seen: dict[str, int] = {}
    out = set()
    for line in prose(text):
        if m := HEADING.match(line):
            s = slug(m[1])
            n = seen.get(s, 0)
            seen[s] = n + 1
            out.add(s if n == 0 else f"{s}-{n}")
    return out


def broken(page: Path, root: Path) -> list[str]:
    """The links of a page that lead to no file under ROOT, or to no heading of the page they name. Links to
    another site are not followed."""
    out = []
    text = page.read_text()
    for line in prose(text):
        for target in LINK.findall(line):
            if re.match(r"[a-z][a-z0-9+.-]*:", target):
                continue  # https:, mailto:
            path, _, anchor = target.partition("#")
            to = (page.parent / path).resolve() if path else page
            if root.resolve() not in (to, *to.parents) or not to.exists():
                out.append(f"{page.name}: {target}: no such file")
            elif anchor and to.is_file() and to.suffix == ".md" and anchor not in anchors(to.read_text()):
                out.append(f"{page.name}: {target}: no such heading in {to.relative_to(root.resolve())}")
    return out


class TheCheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def put(self, name: str, text: str) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def test_a_link_to_a_file_or_a_heading_that_is_not_there_is_found(self):
        self.put("tools/owner.py", "pass\n")
        self.put("docs/other.md", "# Other\n\n## A single agent's run\n\n## Twice\n\n## Twice\n")
        page = self.put("PAGE.md", "# Page\n\n## Who owns what\n\n"
                        "[here](tools/owner.py), [gone](tools/moved.py), [up](../outside.md), [site](https://example.org/x).\n"
                        "[a run](docs/other.md#a-single-agents-run), [second](docs/other.md#twice-1), [no](docs/other.md#thrice),\n"
                        "[own](#who-owns-what), [own, gone](#who-owned-what), [a folder](tools/).\n\n"
                        "```mermaid\nA[\"a box\"](not-a-link.md)\n```\n")
        self.assertEqual(broken(page, self.root),
                         ["PAGE.md: tools/moved.py: no such file", "PAGE.md: ../outside.md: no such file",
                          "PAGE.md: docs/other.md#thrice: no such heading in docs/other.md",
                          "PAGE.md: #who-owned-what: no such heading in PAGE.md"])

    def test_a_headings_anchor_is_the_one_github_gives_it(self):
        for heading, anchor in (("A single agent's run", "a-single-agents-run"),
                                ("For agents making changes: submitting a job", "for-agents-making-changes-submitting-a-job"),
                                ("Backends: other machines and the cloud", "backends-other-machines-and-the-cloud"),
                                ("plugin-and-runtime-mode", "plugin-and-runtime-mode"),
                                ("The `check` and [its page](x.md)", "the-check-and-its-page")):
            self.assertEqual(slug(heading), anchor)


class ThePages(unittest.TestCase):
    def test_every_link_of_the_front_pages_leads_somewhere(self):
        for name in PAGES:
            with self.subTest(page=name):
                self.assertEqual(broken(REPO / name, REPO), [])

    def test_the_architecture_page_names_its_owners_by_links(self):
        # the control for the test above: the page has links for it to follow, into each part of the repository
        targets = {t.partition("#")[0] for line in prose((REPO / "ARCHITECTURE.md").read_text()) for t in LINK.findall(line)}
        for part in ("llm-dlc/tools/", "verification/", "examples/tools/", "lib/"):
            self.assertTrue(any(t.startswith(part) for t in targets), part)
        self.assertGreater(len(targets), 30)


if __name__ == "__main__":
    unittest.main()
