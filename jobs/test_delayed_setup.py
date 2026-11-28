#!/usr/bin/env python3
"""A running case asks for more setup, through the pipeline: the made-up nested build of jobs/test_readiness.py
as a job that needs a readiness operation, with a runner at work, a watcher's admission, and an unrelated job.

  python3 jobs/test_delayed_setup.py

What it shows is the third gate's shape on a fixture: one logical request, the consumer alone waiting, unrelated
work finishing meanwhile, a resolution job admitted through the same scheduler, the consumer woken by the receipt
and running offline on the prepared inputs, an identical request sharing the one resolution, and a withheld
readiness blocking its consumer with the outcome's name until the cause is put right and it is resolved again.
"""

import functools
import hashlib
import http.server
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ["VERIFY_MACHINE_CONFIG"] = ""
os.environ.setdefault("ITL_ORIGINALS_OFF", "1")
import readiness  # noqa: E402
import sandbox  # noqa: E402
import test_formats  # noqa: E402
import test_readiness  # noqa: E402
from test_formats import Repo  # noqa: E402
from test_readiness import BUILD, Quiet  # noqa: E402

del test_formats, test_readiness   # their tests are their own: only the helpers are used here

sys.path.append(str(HERE.parent / "lib/tools"))
from cost_tier import cost  # noqa: E402
sys.path.append(str(Path(__file__).resolve().parents[1] / "lib/tools"))
from cost_tier import cost  # noqa: E402

CONSUME = 'ITL_READINESS_OUT="$PWD" bash build.sh && mv built.txt read.txt'


@cost("tool")
@unittest.skipUnless(sandbox.probe()["enforced"], "this host cannot take a step's network away (bubblewrap)")
class DelayedSetup(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp(prefix="delayed-setup-"))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.repository, self.base = self.dir / "repository", self.dir / "base"
        self.publish("g/stage-one/1.0/stage-one-1.0.pom", b"<project><packaging>pom</packaging></project>\n")
        self.publish("g/nested-tool/2.0/nested-tool-2.0.pom", b"<project><artifactId>nested-tool</artifactId></project>\n")
        self.publish("g/nested-tool/2.0/nested-tool-2.0.jar", b"the nested tool's classes\n")
        self.tool = b"the tool distribution, version 3\n"
        self.publish("dist/tool-3.tar.gz", self.tool, checksum=False)
        (self.base / "m2/g/prepared/1.0").mkdir(parents=True)
        (self.base / "m2/g/prepared/1.0/prepared-1.0.pom").write_text("<project>prepared by the first setup</project>\n")
        Quiet.seen = []
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=str(self.repository)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}/"
        self.store = readiness.Store(self.dir / "store")
        # The loopback repository counts as outside here, and two files as many: every fetch takes its turn in a
        # queue of the test's own, and a resolution that passes the rule's number says so without being stopped.
        self.repo = Repo(poll_seconds=1, fetch_allow=[self.url], readiness_dir=str(self.store.root),
                         fetch_gap=0, fetch_warn_files=2, fetch_local=[])
        self.addCleanup(self.repo.close)
        (self.dir / "not-an-input").mkdir()
        (self.dir / "not-an-input/settings.xml").write_text("what the machine holds beside the prepared inputs\n")
        self.env = {"REPOSITORY_PORT": str(self.server.server_address[1]), "GRADLE_USER_HOME": "/somewhere/else",
                    "ITL_FETCH_QUEUE": str(self.dir / "fetch-queue.lock"),
                    **({"FIXTURE_NOT_AN_INPUT": str(self.dir / "not-an-input/settings.xml")} if Path.home() in self.dir.parents else {})}
        (self.repo.dir / "build.sh").write_text(BUILD)
        self.runner = None
        self.addCleanup(self.stop)

    def publish(self, rel, data, checksum=True):
        path = self.repository / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        if checksum:
            Path(str(path) + ".sha1").write_text(hashlib.sha1(data).hexdigest() + "\n")

    def operation(self, name="op.json", **over):
        operation = {
            "schema": "itl-readiness-operation/v1", "title": "Build the made-up module with its nested tool", "consumer": "T01",
            "describes": {"project": "made-up", "revision": "0123abcd", "module": "app", "task": "build", "toolchain": {"tool": "3"}},
            "level": "builds", "base": {"path": str(self.base)}, "view": {"env": "FIXTURE_CACHE"}, "layout": {"maven": "m2"},
            "repositories": [self.url],
            "pinned": [{"path": "downloads/tool-3.tar.gz", "url": self.url + "dist/tool-3.tar.gz", "sha256": hashlib.sha256(self.tool).hexdigest()}],
            "task": {"steps": [{"name": "build", "run": "bash build.sh"}]}, "outputs": [{"path": "built.txt"}],
            "resources": {"cpus": 1, "memory": "256M", "duration": "1m"}, **over}
        (self.repo.dir / name).write_text(json.dumps(operation))
        return readiness.key(operation)

    def consumer(self, title, case, operation="op.json"):
        return self.repo.submit2(title, "build", "--case", case, "--needs-readiness", operation, "--network", "none",
                                 "--output", "read.txt", "--run", CONSUME, env=self.env)

    def start(self):
        self.runner = subprocess.Popen([sys.executable, "jobs/pipeline.py", "run", "--watch"], cwd=self.repo.dir, text=True,
                                       env=dict(os.environ, VERIFY_REPO=str(self.repo.dir), **self.env),
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, start_new_session=True)

    def stop(self):
        if self.runner and self.runner.poll() is None:
            os.killpg(self.runner.pid, signal.SIGTERM)
            try:
                self.runner.wait(timeout=30)
            except subprocess.TimeoutExpired:
                os.killpg(self.runner.pid, signal.SIGKILL)
        if self.runner:
            self.log = self.runner.stdout.read()
            self.runner.stdout.close()
            self.runner = None

    def view(self):
        return json.loads(self.repo.pipeline("view", env=self.env).stdout)

    def states(self):
        return {job["id"]: job for job in self.view()["jobs"]}

    def until(self, condition, what, seconds=60):
        end = time.monotonic() + seconds
        while not condition():
            if time.monotonic() > end:
                self.stop()
                self.fail(f"{what}\n{getattr(self, 'log', '')}\n{json.dumps(self.view().get('readiness'), indent=1)}")
            time.sleep(0.2)

    def staged(self, job_id):
        return self.repo.result(job_id, collected=False)

    @cost("tool")
    def test_one_request_the_consumer_alone_waits_unrelated_work_finishes_and_the_receipt_wakes_it(self):
        key = self.operation()
        first = self.consumer("Build and read the module, for the first case", "T01")
        self.operation("same.json", title="The same operation, asked for by another case", consumer="T02")
        second = self.consumer("Build and read the module, for the second case", "T02", "same.json")
        unrelated = self.repo.submit2("Has nothing to do with it", "build", "--run", "echo done")
        self.assertEqual(sorted(p.name for p in (self.repo.dir / "verification/readiness").glob("*.json")), [f"{key}.json"])   # one request
        self.repo.commit("two cases that need the same thing prepared, and an unrelated job")
        self.start()
        # The unrelated job finishes; the two consumers wait, and the view says for what and that nobody answers yet.
        self.until(lambda: self.states()[unrelated]["state"] == "finished", "the unrelated job did not finish during the wait")
        states = self.states()
        self.assertEqual((states[first]["state"], states[second]["state"]), ("waiting", "waiting"))
        self.assertIn("no job in the queue resolves it", states[first]["why"])
        request, = self.view()["readiness"]
        self.assertEqual((request["key"], request["unanswered"], sorted(request["wantedBy"])), (key, True, sorted([first, second])))
        self.assertEqual(Quiet.seen, [])                                           # and nothing was fetched by anyone
        # The watcher's part: one resolution job for the one request, admitted by committing it.
        said = json.loads(self.repo.pipeline("resolve", "--json", env=self.env).stdout)
        resolver = said["written"][0]["job"]
        self.assertEqual((len(said["written"]), said["written"][0]["key"]), (1, key))
        # Until that commit the job is a file in the working copy, and a second look writes no second one beside it.
        before_commit = json.loads(self.repo.pipeline("resolve", "--json", "--dry-run", env=self.env).stdout)
        self.assertEqual((before_commit["written"], [row["key"] for row in before_commit["skipped"]]), ([], [key]))
        self.repo.commit("admit the resolution")
        self.repo.pipeline("nudge")
        self.assertEqual(json.loads(self.repo.pipeline("resolve", "--json", env=self.env).stdout)["written"], [])   # it is on its way: no second one
        self.until(lambda: all(self.states()[j]["state"] == "finished" for j in (resolver, first, second)), "the consumers were not woken")
        self.stop()
        # The resolution: one job, three rounds, four files, ready; its phase is `resolve`, and its conclusion is the receipt's.
        resolved = self.staged(resolver)
        concluded = resolved["conclusion"]
        self.assertEqual((resolved["status"], concluded["verdict"], concluded["readiness"][0]["rounds"], concluded["readiness"][0]["fetch"]["files"]),
                         ("passed", "ready", 3, 4))
        self.assertEqual((resolved["steps"][0]["network"]["mode"], list(resolved["timing"]["byPhase"])), ("fetch", ["resolve"]))
        # It asked for more files than the runner's settings expect of a resolution: said for whoever triages, and it passed.
        self.assertEqual((concluded["readiness"][0]["fetch"]["outside"]["files"], len(concluded["warnings"])), (4, 1))
        self.assertIn("asked repositories outside the machine for 4 file(s)", " ".join(resolved["attention"]))
        self.assertTrue((self.dir / "fetch-queue.lock").exists())
        self.assertEqual(json.loads((self.repo.dir / "verification/.state/results" / resolver / "outputs/verification/readiness/receipts" / f"{key}.json").read_text())["state"], "ready")
        # Each consumer ran after it, offline and on the prepared inputs, and read what the task builds.
        for consumer in (first, second):
            result = self.staged(consumer)
            self.assertEqual((result["status"], result["steps"][0]["network"]["enforced"], result["readiness"][0]["key"]), ("passed", True, key),
                             result["steps"][0].get("tail"))
            self.assertEqual(result["readiness"][0]["bundleDigest"], concluded["readiness"][0]["bundleDigest"])
            self.assertGreaterEqual(result["startedAt"], resolved["finishedAt"])
            read = (self.repo.dir / "verification/.state/results" / consumer / "outputs/read.txt").read_bytes()
            self.assertIn(b"the nested tool's classes", read)
        # One resolution served both: the repository was asked once for each file (and its checksum).
        self.assertEqual(len([p for p in Quiet.seen if not p.endswith(".sha1")]), 4)
        self.assertEqual(len(self.staged(first)["attempt"]["previous"]), 0)        # the consumer ran once: no failed try per missing input
        self.assertIn(f"{first}: waiting: readiness {key[:12]} has no receipt here yet", self.log)
        self.assertIn(f"resolution job {resolver} for readiness {key[:12]} has not finished", self.log)

    def test_a_withheld_readiness_blocks_its_consumer_by_name_until_it_is_resolved_again(self):
        shutil.rmtree(self.repository / "g/stage-one")           # the BOM is withheld from every authorised source
        key = self.operation()
        consumer = self.consumer("Build and read the module", "T01")
        self.repo.commit("the case")
        resolver = json.loads(self.repo.pipeline("resolve", "--json", env=self.env).stdout)["written"][0]["job"]
        # One resolution job for a request: a second look before the commit writes no second one, and neither does
        # `--again` while the first is on its way.
        second = json.loads(self.repo.pipeline("resolve", "--json", env=self.env).stdout)
        self.assertEqual((second["written"], [row["key"] for row in second["skipped"]]), ([], [key]))
        self.assertIn("a resolution job for it is written and not committed yet", second["skipped"][0]["why"])
        self.repo.commit("admit the resolution")
        early = json.loads(self.repo.pipeline("resolve", key[:12], "--again", "--json", env=self.env).stdout)
        self.assertEqual((early["written"], early["skipped"][0]["why"]),
                         ([], f"resolution job {resolver} for it has not finished: its receipt answers the request"))
        out = self.repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout
        self.assertIn(f"{resolver}: failed", out)
        self.assertIn(f"{consumer}: blocked: readiness {key[:12]} was withheld at the fetch stage (absent)", out)
        withheld = self.staged(resolver)["conclusion"]
        self.assertEqual((withheld["verdict"], withheld["readiness"][0]["stage"], withheld["readiness"][0]["outcome"]), ("withheld", "fetch", "absent"))
        self.assertFalse((self.repo.dir / "verification/.state/results" / consumer).exists())      # the consumer did not run, and failed nothing
        self.assertFalse(self.store.bundle(key).exists())
        self.assertEqual(json.loads(self.repo.pipeline("resolve", "--json", env=self.env).stdout)["written"], [])   # answered: withheld, with a name
        # The cause is put right, and the same request is resolved again; the consumer then runs.
        self.publish("g/stage-one/1.0/stage-one-1.0.pom", b"<project><packaging>pom</packaging></project>\n")
        again = json.loads(self.repo.pipeline("resolve", key[:12], "--again", "--json", env=self.env).stdout)["written"][0]["job"]
        self.repo.commit("resolve it again")
        out = self.repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout
        self.assertIn(f"{again}: passed", out)
        self.assertIn(f"{consumer}: passed", out)
        self.assertEqual([a["outcome"] for a in self.store.receipt(key)["attempts"]], ["absent"])   # the first attempt is on record

    def test_what_a_task_reads_is_read_against_its_digest_again_before_a_job_is_handed_the_bundle(self):
        declared = self.dir / "declared"
        declared.mkdir()
        text = "an input the operation names by its digest\n"
        (declared / "settings.xml").write_text(text)
        named = readiness.read_digest(declared)[0]
        read = {"path": str(declared), "verified": True, "sha256": named, "files": 1, "bytes": len(text)}
        key = self.operation(reads=[{"path": str(declared), "sha256": named}])
        with mock.patch.dict(os.environ, self.env):   # resolved before the cases arrived
            receipt = readiness.resolve(json.loads((self.repo.dir / "op.json").read_text()), self.store, self.repo.dir, self.dir / "work", [self.url])
        self.assertEqual((receipt["state"], receipt["reads"]), ("ready", [read]), receipt.get("why"))
        first = self.consumer("Build and read the module", "T01")
        self.repo.commit("a case, for a readiness that is already certified")
        self.repo.pipeline("run", "--rev", "HEAD", env=self.env)
        result = self.staged(first)
        self.assertEqual((result["status"], result["readiness"][0]["key"], result["readiness"][0]["reads"]), ("passed", key, [read]), result["attention"])
        # The folder changes after the resolution: the next job is not handed the bundle, and is told what changed.
        (declared / "settings.xml").write_text("changed since the resolution read it\n")
        second = self.consumer("Build and read the module, later", "T02")
        self.repo.commit("a later case, for the same readiness")
        self.repo.pipeline("run", "--rev", "HEAD", env=self.env)
        result = self.staged(second)
        self.assertEqual(result["status"], "error", result["attention"])
        self.assertIn(f"readiness {key[:12]} could not be handed over: {declared} is not what the operation says its task reads", " ".join(result["attention"]))
        self.assertIn(f"the operation names {named}", " ".join(result["attention"]))

    def test_a_request_for_a_source_the_machine_has_not_allowed_waits_for_a_person_and_is_admitted_once_they_allow_it(self):
        import pipeline                      # for the grant as the person's command records it; nothing of this checkout's queue
        config = self.repo.dir / "verification/pipeline.toml"
        config.write_text(config.read_text().replace(f'fetch_allow = ["{self.url}"]', "fetch_allow = []"))
        machine = self.dir / "machine/pipeline.local.toml"       # the machine's settings: none yet, and its grants go beside them
        env = {**self.env, "VERIFY_MACHINE_CONFIG": str(machine)}
        key = self.operation()
        consumer = self.repo.submit2("Build and read the module", "build", "--case", "T01", "--needs-readiness", "op.json", "--network", "none",
                                     "--output", "read.txt", "--run", CONSUME, env=env)
        self.repo.commit("the case, on a machine that may fetch from nowhere")
        # As for a job committed in another workspace: its operation is in the commit, and not in this working copy.
        request = self.repo.dir / "verification/readiness" / f"{key}.json"
        request.unlink()
        asked = sorted([self.url, self.url + "dist/tool-3.tar.gz"])
        view = json.loads(self.repo.pipeline("view", env=env).stdout)
        waiting = next(job for job in view["jobs"] if job["id"] == consumer)
        self.assertEqual(waiting["state"], "waiting", waiting)
        self.assertIn(f"readiness {key[:12]} asks for a source this machine has not been allowed to fetch from", waiting["why"])
        self.assertEqual((view["sources"]["allowed"], [(a["url"], a["wantedBy"], a["readiness"][0]["key"]) for a in view["sources"]["asked"]]),
                         ([], [(url, [consumer], key) for url in asked]))
        self.assertEqual(view["sources"]["asked"][asked.index(self.url)]["for"], "a repository")
        # No resolution is admitted for it, and the one that keeps the queue is told what to ask the user.
        said = json.loads(self.repo.pipeline("resolve", "--json", env=env).stdout)
        self.assertEqual((said["written"], [(row["key"], sorted(row["sources"])) for row in said["skipped"]]), ([], [(key, asked)]))
        self.assertIn("allowing one is the user's decision", said["skipped"][0]["why"])
        self.assertIn(f"a source is asked for that this machine may not fetch from, and the user decides (`pipeline.py sources`): {self.url}, a repository",
                      self.repo.pipeline("status", env=env).stdout)
        # An agent's shell cannot allow one: it has no terminal. Nothing is recorded.
        refused = self.repo.pipeline("sources", "allow", self.url, env=env, check=False)
        self.assertEqual(refused.returncode, 1, refused.stdout)
        self.assertIn("refused: a person allows a source, from their own terminal", refused.stderr)
        self.assertEqual((pipeline.fetch_grants(machine.with_name(pipeline.GRANTS)), machine.parent.exists()), ([], False))
        # The person allows the repository's folder, which holds the tool distribution too: one answer for both.
        self.assertIsNotNone(pipeline.grant_source(machine.with_name(pipeline.GRANTS), self.url, "the made-up repository", pipeline.now()))
        self.assertIsNone(pipeline.grant_source(machine.with_name(pipeline.GRANTS), self.url, "again", pipeline.now()))
        listed = json.loads(self.repo.pipeline("sources", "--json", env=env).stdout)
        self.assertEqual(([(a["url"], a["granted"]["reason"]) for a in listed["allowed"]], listed["asked"]), ([(self.url, "the made-up repository")], []))
        resolver = json.loads(self.repo.pipeline("resolve", "--json", env=env).stdout)["written"][0]["job"]
        self.assertEqual(readiness.key(json.loads(request.read_text())), key)     # read at the asking job's commit, and written here
        self.repo.commit("admit the resolution, now that its source is allowed")
        out = self.repo.pipeline("run", "--rev", "HEAD", env=env).stdout
        self.assertIn(f"{resolver}: passed", out)
        self.assertIn(f"{consumer}: passed", out)
        for wrong, why in (("ftp://repo.example.org/", "scheme"), ("https://user@repo.example.org/", "a user"), ("https:///maven2/", "no host"),
                           ("https://repo.example.org/a/../b/", "`..`"), ("https://repo.example.org/maven2/?x=1", "a query")):
            self.assertIn(why, pipeline.source_problem(wrong) or "", wrong)
        self.assertIsNone(pipeline.source_problem("https://repo.example.org/maven2/"))

    def test_a_bundle_changed_after_its_receipt_is_handed_to_nobody_and_a_runner_that_may_not_fetch_resolves_nothing(self):
        key = self.operation()
        with mock.patch.dict(os.environ, self.env):   # resolved before the case arrived, as an initial setup would have
            receipt = readiness.resolve(json.loads((self.repo.dir / "op.json").read_text()), self.store, self.repo.dir, self.dir / "work", [self.url])
        self.assertEqual(receipt["state"], "ready", receipt.get("why"))
        consumer = self.consumer("Build and read the module", "T01")
        self.repo.commit("the case, for a readiness that is already certified")
        tampered = self.store.bundle(key) / "downloads/tool-3.tar.gz"
        tampered.chmod(0o644)
        tampered.write_text("another tool\n")
        out = self.repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout
        self.assertIn(f"{consumer}: blocked: readiness {key[:12]}: its bundle is not what the receipt names: downloads/tool-3.tar.gz", out)
        # A resolution is admitted for it again, and the runner's settings then name no source to fetch from.
        resolver = json.loads(self.repo.pipeline("resolve", key[:12], "--again", "--json", env=self.env).stdout)["written"][0]["job"]
        config = self.repo.dir / "verification/pipeline.toml"
        config.write_text(config.read_text().replace(f'fetch_allow = ["{self.url}"]', "fetch_allow = []"))
        self.repo.commit("resolve it again, where nothing may be fetched")
        out = self.repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout
        # A resolution job runs where no source is allowed (a mirror on the machine needs none), and its fetcher refuses
        # this repository, which stands for one outside the machine in these tests: withheld by name, nothing fetched.
        self.assertIn(f"{resolver}: failed", out)
        self.assertEqual((self.store.receipt(key)["stage"], self.store.receipt(key)["outcome"]), ("fetch", "unauthorized-source"))
        self.assertIn(f"{consumer}: blocked: readiness {key[:12]} was withheld at the fetch stage (unauthorized-source)", out)

    def test_a_mirror_on_this_machine_is_resolved_from_where_no_outside_source_is_allowed(self):
        # The settings a machine has by default: its loopback is itself, and no outside source is allowed.
        config = self.repo.dir / "verification/pipeline.toml"
        text = config.read_text()
        self.assertIn("fetch_local = []", text)
        config.write_text(text.replace("fetch_local = []", 'fetch_local = ["127.0.0.1", "localhost", "::1"]')
                              .replace(f'fetch_allow = ["{self.url}"]', "fetch_allow = []"))
        key = self.operation()
        consumer = self.consumer("Build and read the module", "T01")
        self.repo.commit("the case, with its repository on this machine")
        self.assertEqual(self.view()["sources"], {"allowed": [], "asked": []})        # nothing to ask anyone for
        resolver = json.loads(self.repo.pipeline("resolve", "--json", env=self.env).stdout)["written"][0]["job"]
        self.repo.commit("admit the resolution")
        out = self.repo.pipeline("run", "--rev", "HEAD", env=self.env).stdout
        self.assertIn(f"{resolver}: passed", out)
        self.assertIn(f"{consumer}: passed", out)
        receipt = self.store.receipt(key)
        self.assertEqual((receipt["fetch"]["files"], receipt["fetch"]["outside"]["files"], "warnings" in receipt), (4, 0, False))


if __name__ == "__main__":
    unittest.main()
