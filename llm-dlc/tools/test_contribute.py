#!/usr/bin/env python3
"""Tests for contribute.py: what of a runtime checkout's work travels upstream, what stays, and what stops a
prepared contribution. Run: python3 llm-dlc/tools/test_contribute.py
Every name and path is made up, and the made-up home directory is assembled at run time."""
import unittest

import contribute
import mode

HOME = "/ho" + "me/" + "qzuser"
NAMES = {"the home directory": HOME, "the user name": "qzuser", "the host name": "qzhost"}
TRAILER = f"{mode.RUNTIME_TRAILER}: 1.2.3 sha256:{'ab' * 32}"


def commit(summary="Add a model of java.util.Objects", trailer=True, conflict=False, extra=""):
    return {"change": "kkkkkkkkkkkk", "summary": summary, "conflict": conflict,
            "description": f"{summary}\n\nWhat it adds.\n\n{extra}{TRAILER if trailer else ''}\n"}


def diff(path, *added, start=1):
    return "\n".join([f"diff --git a/{path} b/{path}", f"--- a/{path}", f"+++ b/{path}",
                      f"@@ -{start},0 +{start},{len(added)} @@", *("+" + line for line in added)]) + "\n"


class ClassifyTest(unittest.TestCase):
    def test_the_library_the_tools_and_the_documentation_travel(self):
        for path in ("lib/src/models/objects.rs", "lib/tests/objects.rs", "examples/tools/targets/runtime.py",
                     "examples/schema/target.schema.json", "lib/README.md", "examples/README.md", "llm-dlc/runtime.md"):
            self.assertEqual(contribute.classify(path), "travels", path)

    def test_the_machine_s_own_record_stays(self):
        for path in ("verification/jobs/20261115-101010-example-901.json", "verification/results/index.json",
                     "verification/findings.md", "llm-dlc/traces/README.md", "llm-dlc/index.json"):
            self.assertEqual(contribute.classify(path), "stays", path)
        self.assertEqual(contribute.classify("verification/README.md"), "travels")
        self.assertEqual(contribute.classify("verification/pipeline.py"), "travels")

    def test_an_example_is_told_by_its_number(self):
        self.assertEqual(contribute.classify("examples/901-acme-orders-rounding/target.json"), "example 901")
        self.assertEqual(contribute.classify("examples/apps/quorum/README.md"), "travels")


class DiffTest(unittest.TestCase):
    def test_added_lines_carry_their_place_in_the_new_file(self):
        text = "\n".join(["diff --git a/a.txt b/a.txt", "--- a/a.txt", "+++ b/a.txt", "@@ -3,3 +3,4 @@", " kept",
                          "-removed", "+added one", "+added two", " kept"]) + "\n"
        self.assertEqual(list(contribute.added_lines(text)), [("a.txt", 4, "added one"), ("a.txt", 5, "added two")])

    def test_a_deleted_file_adds_nothing(self):
        text = "diff --git a/a.txt b/a.txt\n--- a/a.txt\n+++ /dev/null\n@@ -1,1 +0,0 @@\n-gone\n"
        self.assertEqual(list(contribute.added_lines(text)), [])

    def test_a_line_that_names_the_user_is_found_and_never_quoted(self):
        found = contribute.personal(diff("lib/README.md", "an ordinary line", f"built in {HOME}/code", "on qzhost"), NAMES)
        self.assertEqual(found, ["lib/README.md:2 names the home directory", "lib/README.md:2 names the user name",
                                 "lib/README.md:3 names the host name"])
        self.assertFalse(any(HOME in line for line in found))

    def test_a_short_or_generic_user_name_is_not_looked_for(self):
        import getpass
        import socket
        from unittest import mock
        with mock.patch.object(getpass, "getuser", lambda: "bo"), mock.patch.object(socket, "gethostname", lambda: "ubuntu"):
            self.assertEqual(list(contribute.identifying()), ["the home directory"])

    def test_an_example_that_points_at_this_machine_is_local(self):
        sidecar = "examples/330-acme-orders-rounding/target.json"
        self.assertEqual(contribute.local_sources(diff(sidecar, '"repository": "file:///srv/acme/orders",')),
                         [f"{sidecar}:1 points at a local path"])
        self.assertEqual(contribute.local_sources(diff(sidecar, '"repository": "https://github.com/acme/orders",')), [])
        self.assertEqual(contribute.local_sources(diff("lib/README.md", "a file:// URL in prose")), [])


class ProblemsTest(unittest.TestCase):
    def test_a_clean_contribution_has_none(self):
        paths = ["lib/src/models/objects.rs", "examples/330-acme-orders-rounding/target.json"]
        text = diff(paths[0], "fn model() {}") + diff(paths[1], '"repository": "https://github.com/acme/orders"')
        self.assertEqual(contribute.problems([commit()], paths, text, NAMES), [])

    def test_each_thing_that_stops_one_is_named(self):
        paths = ["verification/results/index.json", "examples/901-acme-orders-rounding/target.json", "lib/src/a.rs"]
        text = diff(paths[1], '"repository": "file:///srv/acme/orders",') + diff(paths[2], f"// see {HOME}/notes")
        found = contribute.problems([commit(trailer=False), commit(conflict=True),
                                     commit(extra="LLM-Trace: 0f0f0f0f-1111-4222-8333-444455556666 sha256:00\n")],
                                    paths, text, NAMES)
        for expected in ("has no In-The-Loop-Runtime trailer", "has conflicts", "carries a trace trailer",
                         "verification/results/index.json stays on this machine", "is under a runtime number (901)",
                         "target.json:1 points at a local path", "lib/src/a.rs:1 names the home directory"):
            self.assertTrue(any(expected in problem for problem in found), (expected, found))


if __name__ == "__main__":
    unittest.main()
