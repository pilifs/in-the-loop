#!/usr/bin/env python3
"""Tests of jobs/readiness.py on a made-up nested build: a stand-in for a build tool whose second stage asks for
a prerequisite nobody knew of, a repository served on this machine, and a base of prepared inputs.

  python3 jobs/test_readiness.py

Nothing leaves the machine: the repository is an HTTP server on 127.0.0.1, which the consumer, in its network
namespace, cannot reach. That it cannot is part of what the consumer checks.
"""

import functools
import hashlib
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import readiness  # noqa: E402
import sandbox  # noqa: E402

sys.path.append(str(HERE.parent / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

# The consumer: a build in two stages. The first needs a tool distribution and a BOM; the second, a nested tool,
# asks for its own module only once the first is satisfied. It refuses to pass if it can reach the repository, or
# if it can write into the prepared inputs.
BUILD = r'''
set -u
view="$FIXTURE_CACHE"
test -f "$view/downloads/tool-3.tar.gz" || { echo "the tool distribution is missing"; exit 3; }
test -f "$view/m2/g/stage-one/1.0/stage-one-1.0.pom" || { echo "> Could not find g:stage-one:1.0."; exit 1; }
test -f "$view/m2/g/nested-tool/2.0/nested-tool-2.0.jar" || { echo "[ERROR] Could not find artifact g:nested-tool:jar:2.0 in central"; exit 1; }
if python3 -c "import socket,sys; socket.create_connection(('127.0.0.1', int(sys.argv[1])), 1)" "$REPOSITORY_PORT" 2>/dev/null; then
  echo "the repository can be reached: this is not offline"; exit 9
fi
if echo tampered >> "$view/m2/g/prepared/1.0/prepared-1.0.pom" 2>/dev/null; then echo "the prepared inputs can be written"; exit 8; fi
cat "$view/m2/g/prepared/1.0/prepared-1.0.pom" "$view/m2/g/stage-one/1.0/stage-one-1.0.pom" "$view/m2/g/nested-tool/2.0/nested-tool-2.0.jar" > "$ITL_READINESS_OUT/built.txt"
echo built
'''


class Quiet(http.server.SimpleHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def do_GET(self):
        Quiet.seen.append(self.path)
        super().do_GET()


@cost("tool")
@unittest.skipUnless(sandbox.probe()["enforced"], "this host cannot take a command's network away (bubblewrap)")
class NestedBuild(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="readiness-test-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.repository, self.base, self.cwd = self.dir / "repository", self.dir / "base", self.dir / "checkout"
        self.publish("g/stage-one/1.0/stage-one-1.0.pom", b"<project><packaging>pom</packaging></project>\n")
        self.publish("g/nested-tool/2.0/nested-tool-2.0.pom", b"<project><artifactId>nested-tool</artifactId></project>\n")
        self.publish("g/nested-tool/2.0/nested-tool-2.0.jar", b"the nested tool's classes\n")
        self.tool = b"the tool distribution, version 3\n"
        self.publish("dist/tool-3.tar.gz", self.tool, checksum=False)
        prepared = self.base / "m2/g/prepared/1.0/prepared-1.0.pom"
        prepared.parent.mkdir(parents=True)
        prepared.write_text("<project>prepared by the first setup</project>\n")
        (self.base / "tools").mkdir()
        (self.base / "tools/launcher").write_text("a wrapper\n")
        self.cwd.mkdir()
        (self.cwd / "build.sh").write_text(BUILD)
        Quiet.seen = []
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.repository)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        os.environ["REPOSITORY_PORT"] = str(self.server.server_address[1])
        self.store = readiness.Store(self.dir / "store")

    def publish(self, rel, data, checksum=True):
        path = self.repository / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if checksum:
            Path(str(path) + ".sha1").write_text(hashlib.sha1(data).hexdigest() + "\n")

    def operation(self, **over):
        operation = {
            "schema": "itl-readiness-operation/v1", "title": "Build the made-up module with its nested tool", "consumer": "T01",
            "describes": {"project": "made-up", "revision": "0123abcd", "module": "app", "task": "build", "toolchain": {"tool": "3"}},
            "level": "builds", "base": {"path": str(self.base)}, "view": {"env": "FIXTURE_CACHE"}, "layout": {"maven": "m2"},
            "repositories": [self.url],
            "pinned": [{"path": "downloads/tool-3.tar.gz", "url": self.url + "dist/tool-3.tar.gz", "sha256": hashlib.sha256(self.tool).hexdigest()}],
            "task": {"steps": [{"name": "build", "run": "bash build.sh"}]}, "outputs": [{"path": "built.txt"}], "rounds": 4}
        operation.update(over)
        return operation

    def resolve(self, operation=None, allow=None, n=1):
        return readiness.resolve(operation or self.operation(), self.store, self.cwd, self.dir / f"work-{n}", [self.url] if allow is None else allow,
                                 by={"job": "made-up"})

    def base_bytes(self):
        return {p.relative_to(self.base).as_posix(): p.read_bytes() for p in self.base.rglob("*") if p.is_file()}


class OneRequestResolvesTheWholeTask(NestedBuild):
    def test_the_second_stage_asks_for_what_nobody_knew_of_and_the_bundle_is_published_once_it_ran_offline(self):
        before = self.base_bytes()
        receipt = self.resolve()
        self.assertEqual((receipt["state"], receipt["outcome"], len(receipt["rounds"])), ("ready", "ready", 3), receipt.get("why"))
        # Round 1 had the declared tool fetched and found the BOM missing; round 2 found the nested tool's module,
        # which no one had named; round 3 ran through.
        self.assertEqual([(r["missing"], r["result"]) for r in receipt["rounds"]],
                         [(["g:stage-one:1.0"], "failed"), (["g:nested-tool:2.0"], "failed"), ([], "passed")])
        self.assertEqual([[f["path"] for f in r["fetched"]] for r in receipt["rounds"]],
                         [["downloads/tool-3.tar.gz"], ["m2/g/stage-one/1.0/stage-one-1.0.pom"],
                          ["m2/g/nested-tool/2.0/nested-tool-2.0.pom", "m2/g/nested-tool/2.0/nested-tool-2.0.jar"]])
        self.assertEqual(receipt["fetch"]["files"], 4)
        # Offline was shown, not assumed: the probe saw loopback alone, and the consumer itself could not reach the repository.
        self.assertEqual((receipt["offline"]["network"]["enforced"], receipt["offline"]["network"]["probe"]["interfaces"]), (True, ["lo"]))
        self.assertEqual(receipt["offline"]["outputs"][0]["path"], "built.txt")
        # The bundle is in the store, read-only, each file with its source and what vouched for it; staging is gone.
        bundle = self.store.bundle(receipt["key"])
        by_path = {f["path"]: f for f in receipt["bundle"]["files"]}
        self.assertEqual(by_path["downloads/tool-3.tar.gz"]["verifiedBy"], "the operation's sha256")
        self.assertEqual(by_path["m2/g/stage-one/1.0/stage-one-1.0.pom"]["verifiedBy"], "the repository's sha1")
        self.assertEqual((bundle / "m2/g/nested-tool/2.0/nested-tool-2.0.jar").read_bytes(), b"the nested tool's classes\n")
        self.assertFalse(os.access(bundle / "downloads/tool-3.tar.gz", os.W_OK))
        self.assertEqual(list((self.store.root / "staging").iterdir()), [])
        self.assertEqual(self.base_bytes(), before)                     # the prepared inputs are as they were
        self.assertEqual(self.store.check(receipt["key"])["state"], "satisfied")

    def test_an_identical_request_reuses_the_receipt_and_another_toolchain_is_another_request(self):
        first = self.resolve()
        asked = len(Quiet.seen)
        again = self.resolve(self.operation(title="The same thing, asked by another case", consumer="T02"), n=2)
        self.assertEqual((again.get("reused"), again["key"], len(Quiet.seen)), (True, first["key"], asked))
        other = self.operation()
        other["describes"] = {**other["describes"], "toolchain": {"tool": "4"}}
        self.assertNotEqual(readiness.key(other), first["key"])
        self.assertEqual(readiness.key(self.operation(requestedBy="someone else")), first["key"])
        steps = self.operation()
        steps["task"] = {"steps": [{"name": "build", "run": "bash build.sh --another-goal"}]}
        self.assertNotEqual(readiness.key(steps), first["key"])            # another task is another request

    def test_a_bundle_that_changed_since_its_receipt_is_not_handed_out_and_is_resolved_again(self):
        receipt = self.resolve()
        tampered = self.store.bundle(receipt["key"]) / "m2/g/stage-one/1.0/stage-one-1.0.pom"
        tampered.chmod(0o644)
        tampered.write_text("<project>something else</project>\n")
        said = self.store.check(receipt["key"])
        self.assertEqual(said["state"], "failed")
        self.assertIn("its bundle is not what the receipt names: m2/g/stage-one/1.0/stage-one-1.0.pom", said["why"])
        again = self.resolve(n=2)
        self.assertEqual((again["state"], again.get("reused"), [a["state"] for a in again["attempts"]]), ("ready", None, ["ready"]))
        self.assertEqual(self.store.check(receipt["key"])["state"], "satisfied")
        self.assertEqual(tampered.read_bytes(), b"<project><packaging>pom</packaging></project>\n")


class WhatIsWithheld(NestedBuild):
    def withheld(self, receipt, stage, outcome):
        self.assertEqual((receipt["state"], receipt["stage"], receipt["outcome"]), ("failed", stage, outcome), receipt.get("why"))
        self.assertFalse(self.store.bundle(receipt["key"]).exists())        # nothing was published
        said = self.store.check(receipt["key"])
        self.assertEqual(said["state"], "failed")
        self.assertIn(f"withheld at the {stage} stage ({outcome})", said["why"])

    def test_a_module_no_authorised_source_has_is_absent_and_names_the_stage(self):
        shutil.rmtree(self.repository / "g/stage-one")
        receipt = self.resolve()
        self.withheld(receipt, "fetch", "absent")
        self.assertIn("g:stage-one:1.0", receipt["why"])
        self.assertEqual([r["result"] for r in receipt["rounds"]], ["failed", None])      # it stopped fetching for round 2

    def test_a_tool_distribution_with_another_digest_is_refused_and_nothing_of_it_is_kept_for_use(self):
        operation = self.operation()
        operation["pinned"][0]["sha256"] = "0" * 64
        receipt = self.resolve(operation)
        self.withheld(receipt, "fetch", "digest-mismatch")
        self.assertEqual(receipt["offline"], None)                                        # the consumer never ran on it

    def test_a_repository_that_does_not_answer_on_a_cold_cache_is_unavailable_not_absent(self):
        operation = self.operation()
        operation["repositories"] = ["http://127.0.0.1:9/"]       # the discard port: nothing listens
        receipt = self.resolve(operation, allow=[self.url, "http://127.0.0.1:9/"])
        self.withheld(receipt, "fetch", "repository-unavailable")

    def test_a_source_the_runner_does_not_authorise_is_not_asked(self):
        receipt = self.resolve(allow=["https://repo.example.invalid/"])
        self.withheld(receipt, "fetch", "unauthorized-source")
        self.assertEqual(Quiet.seen, [])

    def test_a_consumer_that_fails_and_names_nothing_or_asks_again_for_what_it_was_given_ends_the_rounds(self):
        (self.cwd / "build.sh").write_text("echo 'something else went wrong'; exit 5\n")
        receipt = self.resolve()
        self.withheld(receipt, "consumer", "undiagnosed")
        self.assertIn("something else went wrong", receipt["why"])
        (self.cwd / "build.sh").write_text("echo 'Could not find g:stage-one:1.0.'; exit 1\n")   # whatever it is given
        receipt = self.resolve(dict(self.operation(), describes={"another": "operation"}), n=2)
        self.withheld(receipt, "consumer", "no-progress")

    def test_an_output_that_is_not_what_was_declared_withholds_readiness_though_the_task_ran(self):
        operation = self.operation()
        operation["outputs"] = [{"path": "built.txt", "sha256": "0" * 64}, {"path": "never-written.txt"}]
        receipt = self.resolve(operation)
        self.withheld(receipt, "outputs", "output-mismatch")
        self.assertIn("never-written.txt was not written", receipt["why"])


class AnOperation(unittest.TestCase):
    def test_what_is_wrong_with_one_is_said(self):
        said = readiness.problems({"schema": "itl-readiness-operation/v1", "level": "ready", "pinned": [{"path": "x"}], "consumer": "T01"})
        self.assertEqual(len(said), 5)
        self.assertIn("level 'ready' is not one of configures, resolves, builds, tests-run, readable", said)

    def test_a_view_lays_files_over_a_base_and_leaves_paths_out_without_touching_it(self):
        with tempfile.TemporaryDirectory() as d:
            base, extra, dest = Path(d) / "base", Path(d) / "extra", Path(d) / "view"
            for rel in ("m2/a/a.pom", "m2/b/b.pom", "big/cache/blob", "downloads/old.tar"):
                (base / rel).parent.mkdir(parents=True, exist_ok=True)
                (base / rel).write_text(rel)
            extra.mkdir()
            (extra / "new.pom").write_text("new")
            links = lambda view: sorted(p.relative_to(view).as_posix() for p in view.rglob("*") if p.is_symlink())
            readiness.overlay(base, ["m2/b", "downloads/old.tar", "scratch/"], {"m2/c/c.pom": extra / "new.pom"}, dest)
            # A folder on the way to something laid over or left out is made; everything else is one link.
            self.assertEqual(links(dest), ["big", "m2/a", "m2/c/c.pom"])
            self.assertEqual(((dest / "m2/c/c.pom").read_text(), (dest / "m2/a/a.pom").read_text(), (dest / "big/cache/blob").read_text()),
                             ("new", "m2/a/a.pom", "big/cache/blob"))
            self.assertFalse((dest / "m2/b").exists() or (dest / "downloads/old.tar").exists())
            self.assertEqual(list((dest / "scratch").iterdir()), [])     # left out, with an empty folder of the view's own
            self.assertTrue((base / "m2/b/b.pom").exists())              # the base is as it was
            # A folder a tool walks is laid file by file: a walk does not follow a linked folder.
            walked = Path(d) / "walked"
            readiness.overlay(base, ["m2/b"], {"m2/c/c.pom": extra / "new.pom"}, walked, walk=["m2"])
            self.assertEqual(links(walked), ["big", "downloads", "m2/a/a.pom", "m2/c/c.pom"])

    def test_what_a_build_tool_says_it_lacks_is_read_as_coordinates(self):
        log = """> Could not find g:stage-one:1.0.
> Could not download activemq-bom-6.1.8.pom (org.apache.activemq:activemq-bom:6.1.8): No cached version available for offline mode
[ERROR] Could not find artifact g:nested-tool:jar:2.0 in central (https://repo.example.invalid)
   > No cached version of com.example:lib:3.1 available for offline mode.
Cannot access central in offline mode and the artifact org.x:y:pom:4 has not been downloaded from it before."""
        self.assertEqual(readiness.missing_coordinates(log),
                         [("com.example", "lib", "3.1"), ("g", "nested-tool", "2.0"), ("g", "stage-one", "1.0"),
                          ("org.apache.activemq", "activemq-bom", "6.1.8"), ("org.x", "y", "4")])


if __name__ == "__main__":
    unittest.main()
