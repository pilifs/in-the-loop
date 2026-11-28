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
import unittest.mock
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
# Prepared inputs alone: nothing the machine holds beside them (a folder of the test's that is no input stands for
# ~/.m2 and ~/.gradle), an empty /tmp, no build tool's home handed down, and the tools the operation says it reads.
test -z "${FIXTURE_NOT_AN_INPUT:-}" || test ! -e "$FIXTURE_NOT_AN_INPUT" || { echo "what is no input can be read: this is not a clean worker"; exit 10; }
test -z "$(ls -A /tmp)" && test -z "${GRADLE_USER_HOME:-}" || { echo "a /tmp or a build tool's home was inherited"; exit 10; }
test -z "${FIXTURE_TOOLCHAIN:-}" || test -f "$FIXTURE_TOOLCHAIN/jdk" || { echo "the declared toolchain cannot be read"; exit 11; }
test "$ITL_READINESS_M2" = "$view/m2" && grep -q itlReadiness "$ITL_READINESS_GRADLE_INIT" || { echo "the view's tools are not given"; exit 7; }
# What a Gradle build is given to read: the fetched modules, each whole, and nothing of the base's own.
test -f "$ITL_READINESS_FETCHED_M2/g/nested-tool/2.0/nested-tool-2.0.pom" && test -f "$ITL_READINESS_FETCHED_M2/g/nested-tool/2.0/nested-tool-2.0.jar" \
  && test ! -e "$ITL_READINESS_FETCHED_M2/g/prepared" || { echo "the fetched modules are not laid apart"; exit 6; }
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
        self.publish("g/nested-tool/2.0/nested-tool-2.0.pom",
                     b"<project><!-- do_not_remove: published-with-gradle-metadata --><artifactId>nested-tool</artifactId></project>\n")
        self.publish("g/nested-tool/2.0/nested-tool-2.0.module", b'{"formatVersion": "1.1"}\n')
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
        (self.dir / "toolchain").mkdir()
        (self.dir / "toolchain/jdk").write_text("a JDK\n")
        (self.dir / "not-an-input").mkdir()
        (self.dir / "not-an-input/settings.xml").write_text("what the machine holds beside the prepared inputs\n")
        inherited = {"GRADLE_USER_HOME": "/somewhere/else", **({"FIXTURE_NOT_AN_INPUT": str(self.dir / "not-an-input/settings.xml")}
                                                              if Path.home() in self.dir.parents else {})}
        patched = unittest.mock.patch.dict(os.environ, inherited)
        patched.start()
        self.addCleanup(patched.stop)
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
            "reads": [str(self.dir / "toolchain")],
            "task": {"steps": [{"name": "build", "run": "bash build.sh"}], "env": {"FIXTURE_TOOLCHAIN": str(self.dir / "toolchain")}},
            "outputs": [{"path": "built.txt"}], "rounds": 4}
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
                          # Its POM says it was published with Gradle's metadata, which Gradle then requires: fetched with it.
                          ["m2/g/nested-tool/2.0/nested-tool-2.0.pom", "m2/g/nested-tool/2.0/nested-tool-2.0.module",
                           "m2/g/nested-tool/2.0/nested-tool-2.0.jar"]])
        self.assertEqual(receipt["fetch"]["files"], 5)
        # What the task reads beside its base is in the receipt: a bare path is declared, and nothing vouches for it.
        self.assertEqual(receipt["reads"], [{"path": str(self.dir / "toolchain"), "verified": False}])
        # The fetched modules are also laid apart, in the same layout, for a Gradle build's file repository.
        fetched = self.dir / "work-1/view-3/itl-readiness-fetched"
        self.assertEqual(sorted(p.relative_to(fetched).as_posix() for p in fetched.rglob("*") if p.suffix in (".pom", ".module", ".jar")),
                         ["g/nested-tool/2.0/nested-tool-2.0.jar", "g/nested-tool/2.0/nested-tool-2.0.module", "g/nested-tool/2.0/nested-tool-2.0.pom",
                          "g/stage-one/1.0/stage-one-1.0.pom"])
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
        # How far "ready" goes is part of what is asked: a receipt that a task graph configures (the S batch's 98 dry
        # runs all did, and 41 of its 49 builds then failed for setup reasons) answers no request to build or read,
        # and one for a build answers none for less: each level is asked for and shown by its own task.
        for level in (lv for lv in readiness.LEVELS if lv != self.operation()["level"]):
            lower = self.operation(level=level)
            self.assertNotEqual(readiness.key(lower), first["key"], level)
            self.assertEqual(self.store.check(readiness.key(lower))["state"], "waiting", level)

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


class WhatARealGraphAsksFor(NestedBuild):
    """What the S batch's first setup pass left out, in small: a module with a parent, a file beside a module's
    JAR, two pins that lack different things, and the same files needed by one case after another."""

    def script(self, text):
        (self.cwd / "build.sh").write_text('set -u\nview="$FIXTURE_CACHE"\n' + text)

    def test_a_module_comes_with_its_parents_and_a_file_the_tool_names_is_fetched_by_its_name(self):
        parent = b"<project><parent><groupId>g</groupId><artifactId>grand</artifactId><version>1</version></parent><packaging>pom</packaging></project>\n"
        self.publish("g/child/1.0/child-1.0.pom", b"<project><!-- <parent><groupId>no</groupId><artifactId>no</artifactId><version>0</version></parent> -->\n"
                     b"<parent>\n <groupId>g</groupId>\n <artifactId>parent</artifactId>\n <version>1</version>\n</parent></project>\n")
        self.publish("g/child/1.0/child-1.0.jar", b"classes\n")
        self.publish("g/child/1.0/child-1.0-linux.jar", b"a native library\n")
        self.publish("g/parent/1/parent-1.pom", parent)                 # its own parent, g:grand:1, is in no repository here
        self.script('m="$view/m2/g/child/1.0"\n'
                    'test -f "$m/child-1.0.pom" || { echo "> Could not find g:child:1.0."; exit 1; }\n'
                    'test -f "$view/m2/g/parent/1/parent-1.pom" || { echo "the parent did not come with its module"; exit 4; }\n'
                    'test -f "$m/child-1.0-linux.jar" || { echo "   > Could not find child-1.0-linux.jar (g:child:1.0)."; exit 1; }\n'
                    'echo built > "$ITL_READINESS_OUT/built.txt"\n')
        receipt = self.resolve(self.operation(pinned=[]))
        self.assertEqual((receipt["state"], [r["result"] for r in receipt["rounds"]]), ("ready", ["failed", "failed", "passed"]), receipt.get("why"))
        self.assertEqual([[(f["path"], f.get("for")) for f in r["fetched"]] for r in receipt["rounds"]],
                         [[], [("m2/g/child/1.0/child-1.0.pom", None), ("m2/g/child/1.0/child-1.0.jar", None),
                               ("m2/g/parent/1/parent-1.pom", "the parent of g:child:1.0")],
                          [("m2/g/child/1.0/child-1.0-linux.jar", None)]])
        self.assertEqual(receipt["rounds"][1]["missingFiles"], ["g:child:1.0 child-1.0-linux.jar"])
        # The parent's own parent was asked for and is nowhere: that is left to the task, which did not need it.
        self.assertIn("/g/grand/1/grand-1.pom", Quiet.seen)
        self.assertEqual(readiness.parent_of(parent.decode()), ("g", "grand", "1"))
        self.assertIsNone(readiness.parent_of("<project><parent><groupId>g</groupId><artifactId>a</artifactId><version>${revision}</version></parent></project>"))

    def test_steps_that_are_independent_each_run_and_one_round_learns_what_both_pins_lack(self):
        for pin in ("fix", "parent"):
            self.publish(f"g/{pin}-only/1.0/{pin}-only-1.0.pom", b"<project><packaging>pom</packaging></project>\n")
        self.script('test -f "$view/m2/g/$1-only/1.0/$1-only-1.0.pom" || { echo "> Could not find g:$1-only:1.0."; exit 1; }\n'
                    'echo built > "$ITL_READINESS_OUT/$1.txt"\n')
        steps = [{"name": pin, "run": f"bash build.sh {pin}"} for pin in ("fix", "parent")]
        outputs = [{"path": "fix.txt"}, {"path": "parent.txt"}]
        one_by_one = self.resolve(self.operation(pinned=[], task={"steps": steps}, outputs=outputs))
        self.assertEqual([r["missing"] for r in one_by_one["rounds"]], [["g:fix-only:1.0"], ["g:parent-only:1.0"], []])
        together = self.resolve(self.operation(pinned=[], task={"steps": steps, "independent": True}, outputs=outputs), n=2)
        self.assertEqual((together["state"], [r["missing"] for r in together["rounds"]]), ("ready", [["g:fix-only:1.0", "g:parent-only:1.0"], []]))
        self.assertEqual([s["exitCode"] for s in together["offline"]["steps"]], [0, 0])

    def test_a_file_this_runner_fetched_and_verified_is_not_asked_of_its_source_again_by_another_operation(self):
        first = self.resolve()
        asked = list(Quiet.seen)
        self.assertEqual((first["fetch"]["files"], first["fetch"]["reused"]), (5, 0))
        other = self.operation(consumer="T02")
        other["describes"] = {**other["describes"], "module": "another module that needs the same inputs"}
        second = self.resolve(other, n=2)
        self.assertNotEqual(second["key"], first["key"])
        self.assertEqual((second["state"], second["fetch"]["files"], second["fetch"]["reused"], second["fetch"]["reusedBytes"]),
                         ("ready", 5, 5, first["fetch"]["bytes"]))
        self.assertEqual(Quiet.seen, asked)                              # nothing was asked of the repository
        self.assertTrue(all(f["reused"] and f["verifiedBy"] for r in second["rounds"] for f in r["fetched"]))
        # Each bundle has bytes of its own, and the checksum beside each file as before.
        mine, theirs = (self.store.bundle(r["key"]) / "m2/g/nested-tool/2.0/nested-tool-2.0.jar" for r in (first, second))
        self.assertEqual((mine.read_bytes(), mine.stat().st_ino != theirs.stat().st_ino), (theirs.read_bytes(), True))
        self.assertEqual(Path(str(theirs) + ".sha1").read_text().split()[0], hashlib.sha1(theirs.read_bytes()).hexdigest())
        # A pooled file that is no longer the bytes recorded for it is fetched again, not handed on.
        kept, _ = self.store.pooled(self.url + "g/nested-tool/2.0/nested-tool-2.0.jar")
        kept.write_text("something else\n")
        third = self.operation(consumer="T03")
        third["describes"] = {**third["describes"], "module": "a third"}
        third = self.resolve(third, n=3)
        self.assertEqual((third["state"], third["fetch"]["reused"]), ("ready", 4))
        self.assertEqual(Quiet.seen[len(asked):], ["/g/nested-tool/2.0/nested-tool-2.0.jar", "/g/nested-tool/2.0/nested-tool-2.0.jar.sha1"])
        # A source the runner no longer authorises is not served from the pool either.
        fourth = self.operation(consumer="T04")
        fourth["describes"] = {**fourth["describes"], "module": "a fourth"}
        self.assertEqual(self.resolve(fourth, allow=[], n=4)["outcome"], "unauthorized-source")

    def test_what_nothing_vouches_for_is_never_published_and_a_line_read_as_a_module_no_source_has_does_not_end_the_rounds(self):
        # A parent POM with no checksum beside it: fetched to be read, never verified, so not kept, laid or published.
        self.publish("g/child/1.0/child-1.0.pom", b"<project><parent><groupId>g</groupId><artifactId>unvouched</artifactId><version>1</version></parent>"
                     b"<packaging>pom</packaging></project>\n")
        self.publish("g/unvouched/1/unvouched-1.pom", b"<project><packaging>pom</packaging></project>\n", checksum=False)
        self.script('test -f "$view/m2/g/child/1.0/child-1.0.pom" || { echo "> Could not find g:child:1.0."; echo "> Could not find g:garbled:jar:9."; exit 1; }\n'
                    'test ! -e "$view/m2/g/unvouched" || { echo "an unverified file was laid"; exit 4; }\n'
                    'echo built > "$ITL_READINESS_OUT/built.txt"\n')
        receipt = self.resolve(self.operation(pinned=[]))
        self.assertEqual((receipt["state"], [r["result"] for r in receipt["rounds"]]), ("ready", ["failed", "passed"]), receipt.get("why"))
        self.assertEqual(sorted(f["path"] for f in receipt["bundle"]["files"]), ["m2/g/child/1.0/child-1.0.pom", "m2/g/child/1.0/child-1.0.pom.sha1"])
        self.assertIn("g:garbled:9", receipt["rounds"][1]["absent"][0])       # said in the round, and the task did not need it
        # Asked for by name, the same file withholds readiness, with a name of its own.
        self.script('echo "> Could not find g:unvouched:1."; exit 1\n')
        named = self.resolve(dict(self.operation(pinned=[]), describes={"another": "operation"}), n=2)
        self.assertEqual((named["state"], named["stage"], named["outcome"]), ("failed", "fetch", "unverifiable"), named.get("why"))

    def test_at_the_level_tests_run_a_task_that_ran_through_and_shows_no_test_is_withheld(self):
        # R49 and R50 (VF-070, item 11): a job that passed 8 of 8 steps while its builds had stopped before any test.
        self.script('echo "BUILD SUCCESSFUL"; echo built > "$ITL_READINESS_OUT/built.txt"\n')
        receipt = self.resolve(self.operation(pinned=[], level="tests-run"))
        self.assertEqual((receipt["state"], receipt["stage"], receipt["outcome"]), ("failed", "level", "tests-not-shown"), receipt.get("why"))
        self.assertIn("0 test(s) executed, and the step promised at least 1", receipt["why"])
        self.assertFalse(self.store.bundle(receipt["key"]).exists())
        self.assertEqual(self.resolve(self.operation(pinned=[], level="builds"), n=2)["state"], "ready")     # as a build, it is one
        report = '<testsuite name="a.Tests"><testcase classname="a.Tests" name="one"/><testcase classname="a.Tests" name="two"/></testsuite>'
        self.script('mkdir -p "$ITL_READINESS_OUT/reports"\n'
                    f"echo '{report}' > \"$ITL_READINESS_OUT/reports/TEST-a.xml\"\n"
                    'echo built > "$ITL_READINESS_OUT/built.txt"\n')
        shown = self.resolve(self.operation(pinned=[], level="tests-run", task={"steps": [{"name": "test", "run": "bash build.sh"}],
                                                                                 "tests": {"reports": ["reports/*.xml"], "min": 2}}), n=3)
        self.assertEqual((shown["state"], shown["offline"]["evidence"]["executed"], shown["offline"]["evidence"]["suites"]), ("ready", 2, ["a.Tests"]), shown.get("why"))


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

    def test_a_tool_the_operation_says_it_reads_and_the_runner_lacks_withholds_at_the_base(self):
        receipt = self.resolve(self.operation(reads=[str(self.dir / "toolchain"), "/no/such/jdk"]))
        self.withheld(receipt, "base", "absent")
        self.assertIn("/no/such/jdk", receipt["why"])
        self.assertIn("each begins with / or ~/", " ".join(readiness.problems(self.operation(reads=["relative/jdk"]))))

    def test_what_the_task_reads_is_not_what_the_operation_names_by_its_digest_and_no_round_runs_on_it(self):
        tools = self.dir / "toolchain"
        named = readiness.read_digest(tools)[0]
        (tools / "added-since").write_text("not there when the digest was taken\n")
        receipt = self.resolve(self.operation(reads=[{"path": str(tools), "sha256": named}]))
        self.withheld(receipt, "base", "digest-mismatch")
        self.assertIn(f"the operation names {named}", receipt["why"])
        self.assertEqual((receipt["rounds"], Quiet.seen), ([], []))        # the task did not run on it, and nothing was fetched for it

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
        self.assertIn("g:stage-one:1.0. The files are under m2/ in Maven's layout, and what asks now does not read them there: "
                      "Could not find g:stage-one:1.0.", receipt["why"])

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

    def test_an_earlier_state_of_a_base_is_what_was_written_by_a_time(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "base"
            early, late = 1_700_000_000, 1_700_009_000
            for rel, when in (("cache/files/g/first/1/aa/first-1.pom", early), ("cache/files/g/first/1/bb/first-1.jar", late),
                              ("cache/files/g/second/2/cc/second-2.pom", late), ("cache/files/h/third/3/dd/third-3.pom", late),
                              ("cache/records/g/first/1/descriptor.bin", early), ("cache/index.bin", late), ("other/new.txt", late)):
                (base / rel).parent.mkdir(parents=True, exist_ok=True)
                (base / rel).write_text(rel)
                os.utime(base / rel, (when, when))
            operation = {"base": {"path": str(base), "without": ["tmp/"], "asOf": {"time": "2023-11-14T23:00:00+00:00", "by": "mtime", "under": ["cache/files", "cache/records", "cache/none"]}}}
            # A folder written whole after the time is left out as one path; beside an older file, only the newer one.
            self.assertEqual(readiness.left_out(operation), ["tmp/", "cache/files/g/first/1/bb", "cache/files/g/second", "cache/files/h"])
            view = readiness.overlay(base, readiness.left_out(operation), {}, Path(d) / "view")
            self.assertEqual(sorted((Path(folder) / name).relative_to(view).as_posix() for folder, _, names in os.walk(view, followlinks=True) for name in names),
                             ["cache/files/g/first/1/aa/first-1.pom", "cache/index.bin", "cache/records/g/first/1/descriptor.bin", "other/new.txt"])
            # Everything under a folder written after the time: the folder stays, empty.
            later = {"base": {"path": str(base), "asOf": {"time": "2023-11-14T20:00:00Z", "by": "mtime", "under": ["cache/files"]}}}
            self.assertEqual(readiness.left_out(later), ["cache/files/g", "cache/files/h"])
            # By default a file's time is the later of its content's and its entry's: Maven gives a downloaded file its
            # repository's last-modified time, years back, and these files, set back just now, count as written now.
            by_entry = {"base": {"path": str(base), "asOf": {"time": "2023-11-14T23:00:00Z", "under": ["cache/files", "cache/records"]}}}
            self.assertEqual(readiness.left_out(by_entry), ["cache/files/g", "cache/files/h", "cache/records/g"])
            # A receipt remembers what its base was laid without, and a view laid later is compared with it.
            receipt = {"operation": operation, "base": {"asOf": {"time": "t", "leftOut": 3, "digest": readiness.laid_without(operation)["digest"]}}}
            self.assertIsNone(readiness.drift(receipt))
            os.utime(base / "cache/files/g/first/1/aa/first-1.pom", (late, late))
            self.assertIn("leaves out 2 path(s) now and left out 3 when it was resolved", readiness.drift(receipt))
        said = readiness.problems({"schema": "itl-readiness-operation/v1", "level": "builds", "describes": {"x": 1}, "task": {"steps": [{"run": "true"}]},
                                   "base": {"path": "/base", "without": ["../outside/", "/etc"], "asOf": {"time": "2026-11-27 09:00", "under": ["cache"]}},
                                   "pinned": [{"path": "../../x", "url": "u", "sha256": "0"}]})
        self.assertEqual(len(said), 4, said)
        self.assertIn("a path is relative to the base and stays inside it: './m2//x'",
                      readiness.problems({"base": {"path": "/base", "without": ["./m2//x"]}}))
        # The same request, whatever the prose and the budget of rounds; another earlier state is another.
        asked = lambda **base: readiness.key({"describes": {"x": 1}, "rounds": base.pop("rounds", 5), "base": {"path": "/base", **base}})
        self.assertEqual(asked(why="as it was", rounds=5), asked(why="as it was, said better", rounds=14))
        self.assertNotEqual(asked(without=["a"]), asked(without=["b"]))
        self.assertIn("base.asOf needs a `time` with its zone (2026-11-27T09:00:00Z) and the folders `under` which it holds", said)
        self.assertIn("a path is relative to the base and stays inside it: '../outside/'", said)

    def test_a_read_with_a_digest_is_read_in_full_against_it_and_a_bare_path_is_only_declared(self):
        sha = lambda data: hashlib.sha256(data).hexdigest()         # noqa: E731
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "repository"
            (folder / "g/a/1").mkdir(parents=True)
            (folder / "g/a/1/a-1.pom").write_bytes(b"<project/>")
            (folder / "g/a/1/a-1.jar").write_bytes(b"jar")
            os.symlink("a-1.jar", folder / "g/a/1/a-latest.jar")
            named, files, size = readiness.read_digest(folder)
            # As a bundle's digest is made: the files by their paths, each with its own digest; a link by where it points.
            self.assertEqual(named, sha(json.dumps([["g/a/1/a-1.jar", sha(b"jar")], ["g/a/1/a-1.pom", sha(b"<project/>")],
                                                    ["g/a/1/a-latest.jar", "link:a-1.jar"]]).encode()))
            self.assertEqual((files, size), (3, 13))
            pom = folder / "g/a/1/a-1.pom"
            operation = {"reads": [str(pom.parent), {"path": str(folder), "sha256": named}, {"path": str(pom), "sha256": sha(b"<project/>")}]}
            self.assertEqual(readiness.check_reads(operation),
                             [{"path": str(pom.parent), "verified": False},
                              {"path": str(folder), "verified": True, "sha256": named, "files": 3, "bytes": 13},
                              {"path": str(pom), "verified": True, "sha256": sha(b"<project/>"), "files": 1, "bytes": 10}])
            pom.write_bytes(b"<project>changed</project>")
            with self.assertRaises(readiness.Withheld) as refused:
                readiness.check_reads(operation)
            self.assertEqual((refused.exception.stage, refused.exception.outcome), ("base", "digest-mismatch"))
            self.assertIn(f"the operation names {named}", refused.exception.why)
        written = {"schema": "itl-readiness-operation/v1", "level": "builds", "describes": {"x": 1}, "task": {"steps": [{"run": "true"}]}, "base": {"path": "/base"}}
        self.assertEqual(readiness.problems({**written, "reads": ["/jdk", {"path": "~/inputs", "sha256": "0" * 64}]}), [])
        for wrong in ({"path": "/jdk", "sha256": "abc"}, {"path": "inputs", "sha256": "0" * 64}, {"path": "/jdk"}, {"path": "/jdk", "sha256": "0" * 64, "more": 1}):
            self.assertIn("with the digest it must have", " ".join(readiness.problems({**written, "reads": [wrong]})), wrong)

    def test_a_source_is_allowed_by_its_parts_and_a_line_that_names_no_module_is_not_one(self):
        allow = ["https://repo.example.org/maven2", "file:///mirror/"]
        for url in ("https://repo.example.org/maven2/g/a/1/a-1.pom", "file:///mirror/g/a/1/a-1.pom"):
            readiness.authorise(url, allow)
        for url in ("https://repo.example.org.evil.example/maven2/g/a-1.pom", "https://repo.example.org@evil.example/maven2/a.pom",
                    "https://repo.example.org/maven2-other/a.pom", "https://repo.example.org/maven2/../secret", "http://repo.example.org/maven2/a.pom",
                    "https://repo.example.org:8443/maven2/a.pom", "file:///mirror-of-something-else/a.pom"):
            with self.assertRaises(readiness.Withheld, msg=url):
                readiness.authorise(url, allow)
        log = """> Could not find g:a:.
[ERROR] Failure to find org.x:lib:jar:tests:1.0 in https://repo.example.org/maven2 was cached in the local repository
[ERROR] Could not find artifact org.x:dist:tar.gz:bin:2.0 in central
> Plugin [id: 'com.example.conventions', version: '1.4'] was not found in any of the following sources:"""
        self.assertEqual(readiness.missing_coordinates(log), [("com.example.conventions", "com.example.conventions.gradle.plugin", "1.4"),
                                                              ("org.x", "dist", "2.0"), ("org.x", "lib", "1.0")])
        self.assertEqual(readiness.missing_files(log), [("org.x", "dist", "2.0", "dist-2.0-bin.tar.gz"), ("org.x", "lib", "1.0", "lib-1.0-tests.jar")])

    def test_a_file_of_a_module_that_a_tool_names_is_read_with_its_module(self):
        log = """   > Could not find netty-transport-native-epoll-4.2.9.Final-linux-x86_64.jar (io.netty:netty-transport-native-epoll:4.2.9.Final).
     Searched in the following locations:
         file:/view/itl-readiness-fetched/io/netty/netty-transport-native-epoll/4.2.9.Final/netty-transport-native-epoll-4.2.9.Final-linux-x86_64.jar
   > Could not download spring-core-7.0.0-SNAPSHOT-test-fixtures.jar (org.springframework:spring-core:7.0.0-SNAPSHOT): No cached version available for offline mode
> Could not find g:stage-one:1.0."""
        self.assertEqual(readiness.missing_files(log),
                         [("io.netty", "netty-transport-native-epoll", "4.2.9.Final", "netty-transport-native-epoll-4.2.9.Final-linux-x86_64.jar"),
                          ("org.springframework", "spring-core", "7.0.0-SNAPSHOT", "spring-core-7.0.0-SNAPSHOT-test-fixtures.jar")])

    def test_what_a_build_tool_says_it_lacks_is_read_as_coordinates(self):
        log = """> Could not find g:stage-one:1.0.
> Could not download activemq-bom-6.1.8.pom (org.apache.activemq:activemq-bom:6.1.8): No cached version available for offline mode
[ERROR] Could not find artifact g:nested-tool:jar:2.0 in central (https://repo.example.invalid)
   > Could not find plexus-utils-3.6.0.jar (org.codehaus.plexus:plexus-utils:3.6.0).
   > No cached version of com.example:lib:3.1 available for offline mode.
Cannot access central in offline mode and the artifact org.x:y:pom:4 has not been downloaded from it before."""
        self.assertEqual(readiness.missing_coordinates(log),
                         [("com.example", "lib", "3.1"), ("g", "nested-tool", "2.0"), ("g", "stage-one", "1.0"),
                          ("org.apache.activemq", "activemq-bom", "6.1.8"), ("org.codehaus.plexus", "plexus-utils", "3.6.0"),
                          ("org.x", "y", "4")])


if __name__ == "__main__":
    unittest.main()
