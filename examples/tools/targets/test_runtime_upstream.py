#!/usr/bin/env python3
"""Tests of the upstream-build route (runtime.py with runtime_upstream.py, R2), the runtime stream's: a local git
repository stands in for github.com (runtime_upstream.REMOTE) and a stand-in `mvn` (runtime_upstream.MAVEN) builds
the fixture's sources with javac and records how it was called, so nothing here uses the network or a real Maven.
The real build of a pinned upstream revision is a pipeline job (runtime_slice.py --case numbers). Also constructed
mutants on the upstream-build and published-artifact routes (the published one against test_runtime.py's stand-in for
Maven Central), whose real run is a job too (runtime_slice.py --case simplematch-mutant).

  python3 examples/tools/targets/test_runtime_upstream.py
"""

import dataclasses
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "fixtures"))
from targets import interfaces, runtime, runtime_jdk, runtime_maven, runtime_upstream, upstream_artifact  # noqa: E402
from targets import test_runtime as base  # noqa: E402  (its helpers; its tests stay in its own module)
sys.path.append(str(Path(__file__).resolve().parents[3] / "lib/tools"))
from cost_tier import cost  # noqa: E402

GIT_ENV = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.invalid", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@example.invalid", "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z",
           "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}

# The stand-in for Maven: it records each call, answers --version, writes the dependency listing the plugin would,
# and otherwise "builds" the gate module with the JDK it was given (JAVA_HOME), as told by standin.json beside it.
STANDIN = r'''#!{python}
import json, os, shutil, subprocess, sys
from pathlib import Path
here = Path(__file__).resolve().parent
knobs = json.loads((Path({knobs!r})).read_text())
with open({calls!r}, "a") as f:
    f.write(json.dumps({{"argv": sys.argv, "cwd": os.getcwd(), "env": dict(os.environ)}}) + "\n")
args = sys.argv[1:]
if args == ["--version"]:
    print("Apache Maven 0.0 (stand-in)"); sys.exit(0)
repo = Path(next(a for a in args if a.startswith("-Dmaven.repo.local=")).split("=", 1)[1])
if any(a.endswith(":build-classpath") for a in args):
    out = Path(next(a for a in args if a.startswith("-Dmdep.outputFile=")).split("=", 1)[1])
    paths = []
    # the plugin's own filter: `includeScope` (an unknown property, such as mdep.includeScope, is ignored, and the
    # listing is then the test classpath); runtime means the compile and runtime scopes
    scope = next((a.split("=", 1)[1] for a in args if a.startswith("-DincludeScope=")), "test")
    allowed = {{"runtime": {{"compile", "runtime"}}, "compile": {{"compile", "provided", "system"}}}}.get(scope)
    for rel, source, *dep_scope in knobs.get("dependencies", []):
        if allowed is not None and (dep_scope or ["compile"])[0] not in allowed:
            continue
        (repo / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, repo / rel)
        paths.append(str(repo / rel))
    (repo / "org/apache/maven/plugins/maven-dependency-plugin/maven-metadata-central.xml").parent.mkdir(parents=True, exist_ok=True)
    (repo / "org/apache/maven/plugins/maven-dependency-plugin/maven-metadata-central.xml").write_text(
        "<metadata><versioning><latest>9</latest></versioning></metadata>")
    out.write_text(os.pathsep.join(paths)); sys.exit(0)
if knobs.get("fail"):
    print("[ERROR] BUILD FAILURE (stand-in)"); sys.exit(1)
if knobs.get("touch"):
    Path("gate/src/main/java/fixture/Gate.java").write_text("// changed by the build\n")
java = Path(os.environ["JAVA_HOME"]) / "bin"
classes = Path("gate/target/classes"); classes.mkdir(parents=True, exist_ok=True)
sources = sorted(str(p) for p in Path("gate/src/main/java").rglob("*.java"))
subprocess.run([str(java / "javac"), "--release", "21", "-d", str(classes), *sources], check=True)
(repo / "org/example/plugin/1.0").mkdir(parents=True, exist_ok=True)
(repo / "org/example/plugin/1.0/plugin-1.0.jar").write_bytes(b"plugin bytes")
if not knobs.get("noJar"):
    subprocess.run([str(java / "jar"), "--create", "--file", "gate/target/gate-1.0.jar", "-C", str(classes), "."], check=True)
    subprocess.run([str(java / "jar"), "--create", "--file", "gate/target/gate-1.0-sources.jar", "-C", str(classes), "."], check=True)
if knobs.get("extraJar"):
    subprocess.run([str(java / "jar"), "--create", "--file", "gate/target/gate-1.0-all.jar", "-C", str(classes), "."], check=True)
print("[INFO] BUILD SUCCESS (stand-in)")
'''


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True).stdout.strip()


def make_upstream(root, extra=None):
    """A two-commit repository, before then after, holding the fixture's Gate sources as a Maven-shaped module
    (gate/pom.xml, gate/src/main/java), and the files `extra` names ({path: text}) in both: (path, before, after)."""
    root.mkdir(parents=True)
    git(root, "init", "-q", "-b", "main")
    module = root / "gate/src/main/java/fixture"
    module.mkdir(parents=True)
    (root / "pom.xml").write_text("<project><modules><module>gate</module></modules></project>\n")
    (root / "gate/pom.xml").write_text("<project><artifactId>gate</artifactId></project>\n")
    (root / ".gitignore").write_text("target/\n")
    for path, text in (extra or {}).items():
        (root / path).parent.mkdir(parents=True, exist_ok=True)
        (root / path).write_text(text)
    shutil.copyfile(base.FIXTURES / "gate/both/fixture/RegexGate.java", module / "RegexGate.java")
    commits = []
    for revision in ("before", "after"):
        shutil.copyfile(base.FIXTURES / f"gate/{revision}/fixture/Gate.java", module / "Gate.java")
        git(root, "add", "-A")
        git(root, "commit", "-q", "-m", revision)
        commits.append(git(root, "rev-parse", "HEAD"))
    return root, commits[0], commits[1]


ARGV = ["mvn", "--batch-mode", "--projects", "gate", "-Dmaven.test.skip=true", "-Pquick", "package"]


def upstream_plan(folder, revisions, commits, parents=None, tool="maven", argv=ARGV, jdk="21", network=True,
                  repository="https://github.com/example/gate", task="replay", **extra):
    artifacts = tuple({"revision": r, "route": "upstream-build", "repository": repository, "commit": commits[r],
                       **({"parent": parents[r]} if parents and r in parents else {}),
                       "build": {"tool": tool, "argv": list(argv), "jdk": jdk},
                       "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"], "jdks": ["21", "25"], **extra}
                      for r in revisions)
    return interfaces.TaskPlan(
        example="999", task=task, kind="replay", relation="security", target="fixture.Gate#allowed(I)Z",
        revisions=tuple(revisions), claim={"task": task}, prerequisites=(), artifacts=artifacts,
        tools={"required": ["java", "javac"], "optional": []}, engine=None, gaps=None, expected=None,
        outputs={"receipts": f"receipts/{task}"}, folder=str(folder), network=network)


class UpstreamCase(base.FixtureCopy):
    """The stand-ins for github.com and Maven, and the plan and preparation helpers; the tests are its subclasses'."""

    def setUp(self):
        super().setUp()
        if "21" not in runtime_jdk.homes():
            self.skipTest(f"JDK 21 is not under {runtime_jdk.CANDIDATES}")
        self.upstream, before, after = make_upstream(self.dir / "upstream")
        self.commits = {"before": before, "after": after}
        self.calls, self.knobs = self.dir / "calls.jsonl", self.dir / "standin.json"
        self.dep = base.dependency_jar(self.dir / "util.jar", ["fixture/util/Helper"])
        self.set_knobs()
        self.mvn = self.standin(self.dir / "maven/bin/mvn")
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(runtime_upstream, "REMOTE", self.remote).start()
        mock.patch.object(runtime_upstream, "MAVEN", lambda: self.mvn).start()
        mock.patch.object(runtime_maven, "CACHE", self.dir / "cache").start()
        self.remotes = []

    def remote(self, url):
        self.remotes.append(url)
        return self.upstream

    def standin(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(STANDIN.format(python=sys.executable, knobs=str(self.knobs), calls=str(self.calls)))
        path.chmod(0o755)
        return path

    def set_knobs(self, **knobs):
        # a compile dependency, and a test-scope one the runtime classpath must leave out (here the same bytes, so
        # leaving it in would also be a shadowing blocker)
        knobs.setdefault("dependencies", [["fixture/example/gate-util/2.0/gate-util-2.0.jar", str(self.dep)],
                                          ["org/junit/junit-api/5.0/junit-api-5.0.jar", str(self.dep), "test"]])
        self.knobs.write_text(json.dumps(knobs))

    def made_calls(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.is_file() else []

    def plan(self, revisions=("after",), **kw):
        kw.setdefault("parents", {"after": self.commits["before"]})
        return upstream_plan(self.folder, revisions, kw.pop("commits", self.commits), **kw)

    def prepare(self, revision="after", workdir=None, plan=None, **kw):
        return runtime.prepare(plan or self.plan((revision,), **kw), revision, workdir or self.work / revision)



class UpstreamTest(UpstreamCase):
    @cost("tool")
    def test_an_upstream_lock_fetches_nothing_and_refuses_a_recipe_that_is_not_immutable(self):
        with mock.patch.object(runtime_upstream, "REMOTE", side_effect=AssertionError("a source lock fetched")), \
                mock.patch.object(subprocess, "run", side_effect=AssertionError("a source lock ran a process")):
            locked = runtime.lock(self.plan(), "after")
        self.assertEqual((locked.stage, locked.commit), ("source-locked", self.commits["after"]), locked.diagnostic)
        self.assertEqual(locked.source["history"], {"commit": self.commits["after"], "parent": self.commits["before"]})
        self.assertEqual(locked.source["upstream"], {"tool": "maven", "argv": ARGV, "jdk": "21"})
        self.assertEqual(locked.source["driver"]["main"], "fixture.driver.GateDriver")
        refused = {
            "a host other than github.com": dict(repository="https://gitlab.com/example/gate"),
            "plain http": dict(repository="http://github.com/example/gate"),
            "a short commit": dict(commits={"after": self.commits["after"][:12]}),
            "a branch": dict(commits={"after": "main"}),
            "a short parent": dict(parents={"after": self.commits["before"][:7]}),
            "an unknown tool": dict(tool="ant"),
            "an argv that is not the tool's": dict(argv=["./mvnw", "package"]),
            "its own settings": dict(argv=["mvn", "-s", "/tmp/settings.xml", "package"]),
            "its own local repository": dict(argv=["mvn", "-Dmaven.repo.local=/tmp/r", "package"]),
            "offline": dict(argv=["mvn", "-o", "package"]),
            "a JDK that is no feature": dict(jdk="latest"),
        }
        for why, change in refused.items():
            value = runtime.lock(self.plan(**change), "after")
            self.assertEqual(value.failedStage, "lock", why)
            self.assertIn("next", value.blocker, why)
        self.assertEqual(self.remotes, [])

    @cost("tool")
    def test_artifacts_ready_records_the_checkout_toolchain_build_and_every_output(self):
        with mock.patch.dict(os.environ, {"MAVEN_OPTS": "-Dleak=1", "JAVA_TOOL_OPTIONS": "-Dleak=2",
                                          "MAVEN_ARGS": "-Dleak=3"}):
            prepared = self.prepare()
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        work = self.work / "after"
        checkout = prepared.source["checkout"]
        self.assertEqual(checkout["commit"], self.commits["after"])
        self.assertEqual(checkout["tree"], git(self.upstream, "rev-parse", f"{self.commits['after']}^{{tree}}"))
        self.assertEqual((checkout["parents"], checkout["parentChecked"]), ([self.commits["before"]], self.commits["before"]))
        self.assertEqual((checkout["fetchedFrom"], checkout["changedByBuild"]), ("https://github.com/example/gate", []))
        self.assertEqual(self.remotes, ["https://github.com/example/gate"])
        # the produced JARs, auxiliary ones included and marked; the original is the one main JAR holding the target
        built = prepared.source["built"]
        self.assertEqual([(j["path"], j["auxiliary"]) for j in built["jars"]],
                         [("gate/target/gate-1.0-sources.jar", True), ("gate/target/gate-1.0.jar", False)])
        self.assertEqual(built["original"], "gate/target/gate-1.0.jar")
        self.assertEqual(prepared.classpath, ("driver.jar", "adapter-after.jar", "built/gate-1.0.jar",
                                              "lib/fixture/example/gate-util/2.0/gate-util-2.0.jar"))
        by_path = {a.path: a for a in prepared.artifacts}
        self.assertEqual(by_path["built/gate-1.0.jar"].sha256, built["jars"][1]["sha256"])
        self.assertIn(self.commits["after"], by_path["built/gate-1.0.jar"].origin)
        dep = by_path["lib/fixture/example/gate-util/2.0/gate-util-2.0.jar"]
        self.assertEqual((dep.role, dep.coordinates, dep.sha256), ("dependency", "fixture.example:gate-util:2.0",
                                                                   runtime.sha256(self.dep)))
        recipe = runtime_upstream.check_recipe("after", self.plan().artifacts[0])
        products = [dataclasses.asdict(by_path[p]) for p in prepared.classpath if by_path[p].role in ("original", "dependency")]
        captured = {"schema": "upstream-jar-build/v1", "recipe": self.plan().artifacts[0], "artifacts": products,
                    "build": {"checkout": checkout, "outputs": built}}
        entries = upstream_artifact.products(captured, recipe)
        for name, digest, _, _, _ in entries:
            runtime_maven.Cache().store(work / name, digest)
        self.assertTrue(upstream_artifact.restore(entries, self.dir / "fresh"))
        self.assertEqual([runtime.sha256(self.dir / "fresh" / e[0]) for e in entries], [e[1] for e in entries])
        with self.assertRaisesRegex(runtime_maven.Blocked, "different recipe"):
            upstream_artifact.products(captured, {**recipe, "commit": self.commits["before"]})
        captured["artifacts"][0] = {**products[0], "sha256": "0" * 64}
        with self.assertRaisesRegex(runtime_maven.Blocked, "Maven output"):
            upstream_artifact.products(captured, recipe)
        self.assertEqual(prepared.source["target"]["loadedFrom"], "built/gate-1.0.jar")
        # the toolchain: the JDK by full path, the tool's version, the argv recorded and run, the isolation
        upstream = prepared.toolchain["upstream"]
        self.assertEqual(upstream["jdk"]["home"], runtime_jdk.home("21"))
        self.assertEqual(upstream["maven"]["version"], ["Apache Maven 0.0 (stand-in)"])
        self.assertEqual(upstream["argv"]["recorded"], ARGV)
        run = upstream["argv"]["run"]
        self.assertEqual((run[0], run[1:3], run[5:7]), (str(self.mvn), ["-s", str(work / "maven/settings.xml")],
                                                        [f"-Dmaven.repo.local={work / 'maven/repository'}",
                                                         "--strict-checksums"]))
        self.assertEqual(run[7:], ARGV[1:])
        settings = (work / "maven/settings.xml").read_text()
        self.assertIn("<mirrorOf>*</mirrorOf><url>https://repo.maven.apache.org/maven2</url>", settings)
        self.assertEqual(upstream["settings"]["sha256"], runtime.sha256(work / "maven/settings.xml"))
        # what the build resolved, hashed; the version lookup named; the local repository itself gone
        resolution = json.loads((work / "maven/resolution.json").read_text())
        self.assertIn("org/example/plugin/1.0/plugin-1.0.jar", [f["path"] for f in resolution["files"]])
        self.assertEqual(upstream["resolution"]["versionLookups"],
                         ["org/apache/maven/plugins/maven-dependency-plugin/maven-metadata-central.xml"])
        self.assertFalse((work / "maven/repository").exists())
        # each Maven call: in the checkout, with a fixed environment that inherits nothing
        calls = self.made_calls()
        self.assertEqual([c["argv"][1:] == ["--version"] for c in calls], [True, False, False])
        for call in calls:
            self.assertEqual(Path(call["cwd"]).resolve(), (work / "checkout").resolve())
            env = call["env"]
            self.assertFalse({"MAVEN_OPTS", "JAVA_TOOL_OPTIONS", "MAVEN_ARGS"} & set(env), env)
            self.assertEqual((env["HOME"], env["JAVA_HOME"], env["MAVEN_SKIP_RC"]),
                             (str(work / "home"), runtime_jdk.home("21"), "1"))
        listing = calls[2]["argv"]
        self.assertIn(f"{runtime_upstream.DEPENDENCY_PLUGIN}:build-classpath", listing)
        self.assertIn("-Pquick", listing)
        self.assertEqual([a for a in listing if "Scope" in a], ["-DincludeScope=runtime"])
        self.assertEqual(prepared.source["built"]["dependencies"]["command"],
                         f"{runtime_upstream.DEPENDENCY_PLUGIN}:build-classpath -DincludeScope=runtime")
        self.assertTrue(prepared.source["built"]["dependencies"]["scope"].startswith("runtime: "))
        self.assertIn(str(work / "checkout/gate/pom.xml"), listing)
        # the checkout is as fetched, and the logs say what ran
        self.assertEqual(git(work / "checkout", "status", "--porcelain", "--untracked-files=no"), "")
        for log in ("logs/git-fetch.log", "logs/build.log", "logs/dependencies.log"):
            self.assertIn(log, prepared.logs)
        self.assertEqual(json.loads((work / runtime.RECORD).read_text()), json.loads(json.dumps(prepared.as_dict())))

    @cost("tool")
    def test_a_parent_the_commit_does_not_have_is_a_history_blocker(self):
        prepared = self.prepare(parents={"after": "1" * 40})
        self.assertEqual(prepared.failedStage, "history", prepared.diagnostic)
        self.assertIn("1" * 40, prepared.diagnostic)
        self.assertIn("history", prepared.blocker["next"])
        self.assertEqual(prepared.source["checkout"]["parents"], [self.commits["before"]])
        self.assertEqual(self.made_calls(), [], "a build ran on a history that is wrong")

    @cost("tool")
    def test_a_commit_the_repository_lacks_is_an_acquire_blocker_with_its_command(self):
        prepared = self.prepare(commits={"after": "f" * 40}, parents={})
        self.assertEqual(prepared.failedStage, "acquire", prepared.diagnostic)
        self.assertIn("fetch", prepared.blocker["command"])
        self.assertIn("logs/git-fetch.log", prepared.logs)

    @cost("tool")
    def test_without_acquisition_nothing_is_fetched_or_built(self):
        prepared = self.prepare(network=False)
        self.assertEqual(prepared.failedStage, "acquire", prepared.diagnostic)
        self.assertEqual((self.remotes, self.made_calls()), ([], []))

    @cost("tool")
    def test_a_failing_build_or_one_that_changes_tracked_sources_is_refused(self):
        self.set_knobs(fail=True)
        failed = self.prepare(workdir=self.work / "fail")
        self.assertEqual(failed.failedStage, "build", failed.diagnostic)
        self.assertIn("BUILD FAILURE", failed.diagnostic)
        self.assertEqual(failed.blocker["command"], " ".join(ARGV))
        self.assertIn("logs/build.log", failed.logs)
        self.set_knobs(touch=True)
        touched = self.prepare(workdir=self.work / "touch")
        self.assertEqual(touched.failedStage, "build", touched.diagnostic)
        self.assertIn("changed tracked files", touched.diagnostic)
        self.assertEqual(touched.source["checkout"]["changedByBuild"], [" M gate/src/main/java/fixture/Gate.java"])

    @cost("tool")
    def test_the_original_is_the_one_produced_jar_that_holds_the_target(self):
        self.set_knobs(noJar=True)
        none = self.prepare(workdir=self.work / "none")
        self.assertEqual(none.failedStage, "build", none.diagnostic)
        self.assertIn("no JAR the build produced holds fixture/Gate.class", none.diagnostic)
        self.set_knobs(extraJar=True)
        two = self.prepare(workdir=self.work / "two")
        self.assertEqual(two.failedStage, "classpath", two.diagnostic)
        self.assertIn("gate/target/gate-1.0-all.jar", two.diagnostic)

    @cost("tool")
    def test_a_dependency_that_repeats_the_targets_class_is_refused_as_shadowing(self):
        shadow = base.dependency_jar(self.dir / "shadow.jar", ["fixture/Gate"])
        self.set_knobs(dependencies=[["x/y/shadow/1.0/shadow-1.0.jar", str(shadow)]])
        prepared = self.prepare()
        self.assertEqual(prepared.failedStage, "classpath", prepared.diagnostic)
        self.assertIn("fixture.Gate", prepared.diagnostic)

    @cost("tool")
    def test_gradle_is_a_toolchain_blocker_naming_the_distribution_it_would_need(self):
        props = ("distributionUrl=https\\://services.gradle.org/distributions/gradle-8.5-bin.zip\n"
                 "distributionSha256Sum=" + "a" * 64 + "\n")
        self.upstream, before, after = make_upstream(self.dir / "gradle-upstream",
                                                     {"gradle/wrapper/gradle-wrapper.properties": props})
        commits = {"before": before, "after": after}
        wrapper = self.prepare(plan=self.plan(commits=commits, parents={}, tool="gradle-wrapper",
                                              argv=["./gradlew", "--no-daemon", "jar"]), workdir=self.work / "wrapper")
        self.assertEqual(wrapper.failedStage, "toolchain", wrapper.diagnostic)
        self.assertIn("https://services.gradle.org/distributions/gradle-8.5-bin.zip", wrapper.diagnostic)
        self.assertIn("a" * 64, wrapper.diagnostic)
        self.assertIn("no Gradle route yet", wrapper.diagnostic, "services.gradle.org is allowed: the route is missing")
        self.assertNotIn("user decides", wrapper.blocker["next"])
        self.assertEqual(wrapper.source["checkout"]["commit"], after)
        self.remotes.clear()
        plain = self.prepare(plan=self.plan(commits=commits, parents={}, tool="gradle", argv=["gradle", "jar"]),
                             workdir=self.work / "plain")
        self.assertEqual(plain.failedStage, "toolchain", plain.diagnostic)
        self.assertEqual((self.remotes, self.made_calls()), ([], []))

    @cost("tool")
    def test_a_gradle_distribution_on_any_other_host_is_still_outside_the_policy(self):
        props = "distributionUrl=https\\://downloads.gradle.org/distributions/gradle-8.5-bin.zip\n"
        self.upstream, before, after = make_upstream(self.dir / "gradle-other",
                                                     {"gradle/wrapper/gradle-wrapper.properties": props})
        wrapper = self.prepare(plan=self.plan(commits={"before": before, "after": after}, parents={},
                                              tool="gradle-wrapper", argv=["./gradlew", "jar"]),
                               workdir=self.work / "other")
        self.assertEqual(wrapper.failedStage, "toolchain", wrapper.diagnostic)
        self.assertIn("downloads.gradle.org, outside the downloads policy", wrapper.diagnostic)
        self.assertIn("missing", wrapper.diagnostic)
        self.assertIn("user decides", wrapper.blocker["next"])
        self.assertEqual(self.made_calls(), [])

    @cost("tool")
    def test_a_maven_wrapper_runs_its_own_distribution_from_central_by_sha256(self):
        dist = self.dir / "dist/apache-maven-9.9.9-bin.zip"
        dist.parent.mkdir()
        script = self.standin(self.dir / "dist-src/mvn")
        with zipfile.ZipFile(dist, "w") as z:
            z.write(script, "apache-maven-9.9.9/bin/mvn")
        url = "https://repo.maven.apache.org/maven2/org/apache/maven/apache-maven/9.9.9/apache-maven-9.9.9-bin.zip"
        import hashlib
        files = {url: dist.read_bytes(), url + ".sha1": hashlib.sha1(dist.read_bytes()).hexdigest().encode()}
        fetched = []

        def fetch(u, dest):
            fetched.append(u)
            Path(dest).write_bytes(files[u])
        mock.patch.object(runtime_maven, "FETCH", fetch).start()
        # an older wrapper's properties: escaped, and Central under its older name
        props = "distributionUrl=https\\://repo1.maven.org/maven2/org/apache/maven/apache-maven/9.9.9/apache-maven-9.9.9-bin.zip\n"
        self.upstream, before, after = make_upstream(self.dir / "wrapper-upstream",
                                                     {".mvn/wrapper/maven-wrapper.properties": props})
        plan = self.plan(commits={"before": before, "after": after}, parents={}, tool="maven-wrapper",
                         argv=["./mvnw", *ARGV[1:]])
        prepared = self.prepare(plan=plan)
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        wrapper = prepared.toolchain["upstream"]["wrapper"]
        self.assertEqual((wrapper["fetchedFrom"], wrapper["sha256"]), (url, runtime.sha256(dist)))
        self.assertIn(".sha1", wrapper["checked"])
        self.assertEqual(fetched, [url, url + ".sha1"], "fetched once, checked, then restored from the cache")
        ran = self.work / "after/tools/maven/apache-maven-9.9.9/bin/mvn"
        self.assertEqual([c["argv"][0] for c in self.made_calls()], [str(ran)] * 3)
        # a recorded distributionSha256Sum the bytes don't match: refused, never run
        self.upstream, before, after = make_upstream(self.dir / "wrong-upstream", {
            ".mvn/wrapper/maven-wrapper.properties": props + "distributionSha256Sum=" + "0" * 64 + "\n"})
        mock.patch.object(runtime_maven, "CACHE", self.dir / "cache2").start()
        wrong = self.prepare(plan=self.plan(commits={"before": before, "after": after}, parents={},
                                            tool="maven-wrapper", argv=["./mvnw", *ARGV[1:]]), workdir=self.work / "wrong")
        self.assertEqual(wrong.failedStage, "acquire", wrong.diagnostic)
        self.assertIn("not the recorded", wrong.diagnostic)

    @cost("tool")
    def test_a_zip_entry_outside_its_root_is_never_unpacked(self):
        evil = self.dir / "evil.zip"
        with zipfile.ZipFile(evil, "w") as z:
            z.writestr("apache-maven-1/../../escaped", "x")
        with self.assertRaises(runtime_maven.Blocked):
            runtime_upstream._unzip(evil, self.dir / "into")
        self.assertFalse((self.dir / "escaped").exists())

    @cost("tool")
    def test_each_built_revision_runs_in_its_own_jvm(self):
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        plan = self.plan(("before", "after"))
        attempt = self.work / "attempt"
        prepared = {r: runtime.prepare(plan, r, attempt / "prepare" / r) for r in plan.revisions}
        self.assertEqual({r: p.stage for r, p in prepared.items()}, {"before": "artifacts-ready", "after": "artifacts-ready"})
        records = runtime.run_controls(plan, prepared, attempt / "controls")
        self.assertEqual([(r.revision, r.identities["jdkFeature"], r.status, r.exitCode) for r in records],
                         [("before", "21", "exited", 0), ("before", "25", "exited", 0),
                          ("after", "21", "exited", 0), ("after", "25", "exited", 0)])
        problems = {}
        for r in records:
            self.assertEqual(r.identities["commit"], self.commits[r.revision])
            problems.setdefault(r.revision, set()).add(
                tuple(c for c, _ in base.oracle().check([json.dumps(o) for o in r.observations])))
        self.assertEqual(problems, {"before": {(97,)}, "after": {()}}, "the built revisions replay as the fixture's")


def gate_patch(path="gate/src/main/java/fixture/Gate.java"):
    """The fixture's after-to-mutant change as a patch on the upstream stand-in's module, as git apply -p1 reads it."""
    import difflib
    after = (base.FIXTURES / "gate/after/fixture/Gate.java").read_text().splitlines(keepends=True)
    mutant = (base.FIXTURES / "gate/mutant/fixture/Gate.java").read_text().splitlines(keepends=True)
    return "".join(difflib.unified_diff(after, mutant, f"a/{path}", f"b/{path}"))


class MutantRoutesTest(UpstreamCase):
    """A constructed mutant (workflow's W1 entry) of the stand-in's `after` commit, on the upstream-build route (the
    checkout patched, then built by the recipe) and on the published-artifact route (the checkout patched, the patched
    file compiled against the published JARs and its classes put into a copy of the base JAR)."""

    def setUp(self):
        super().setUp()
        (self.folder / "gate/mutant.patch").write_text(gate_patch())
        self.mutant = {"base": {"revision": "after", "commit": self.commits["after"]},
                       "patch": {"path": "gate/mutant.patch", "sha256": runtime.sha256(self.folder / "gate/mutant.patch")},
                       "description": "the fix normalizes one side only: 65 allowed again"}

    def upstream_entry(self):
        entry = dict(upstream_plan(self.folder, ("after",), self.commits).artifacts[0], revision="mutant",
                     mutant=self.mutant)
        del entry["commit"]
        return entry

    def published(self, jar=None):
        """The base JAR (build_fixtures.py's after.jar, unless `jar`) and a dependency on the stand-in for Central."""
        self.central = base.Repository(self, self.dir / "central")
        dep = self.central.publish("fixture.example:gate-util:2.0", self.dep)
        after = self.central.publish("fixture.example:gate:1.1", jar or Path(base.manifest()["dir"]) / "after.jar")
        return [after, dep]

    def published_entry(self, items, revision="mutant"):
        entry = {"revision": revision, "route": "published-artifact", "repository": "https://github.com/example/gate",
                 "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"], "jdks": ["21", "25"]}
        if revision == "mutant":
            return {**entry, "mutant": {**self.mutant, "base": {**self.mutant["base"], "published": items}}}
        return {**entry, "commit": self.commits["after"], "published": items}

    def plan_of(self, entries, network=True):
        return dataclasses.replace(base.mutant_plan(self.folder, entries, revisions=tuple(e["revision"] for e in entries)),
                                   network=network)

    def replay(self, plan):
        attempt = self.work / "attempt"
        prepared = {r: runtime.prepare(plan, r, attempt / "prepare" / r) for r in plan.revisions}
        for r, p in prepared.items():
            self.assertEqual(p.stage, "artifacts-ready", f"{r}: {p.diagnostic}")
        problems = {}
        for r in runtime.run_controls(plan, prepared, attempt / "controls"):
            self.assertEqual((r.status, r.exitCode), ("exited", 0))
            problems.setdefault(r.revision, set()).add(
                tuple(c for c, _ in base.oracle().check([json.dumps(o) for o in r.observations])))
        return prepared, problems

    def test_an_upstream_mutant_is_its_base_commit_patched_then_built_by_the_recipe(self):
        prepared = runtime.prepare(self.plan_of([self.upstream_entry()]), "mutant", self.work / "mutant")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        digest = self.mutant["patch"]["sha256"]
        self.assertEqual(prepared.commit, f"mutant:{self.commits['after']}+{digest}")
        checkout = prepared.source["checkout"]
        self.assertEqual(checkout["commit"], self.commits["after"], "the base commit is what is checked out")
        self.assertEqual([f["path"] for f in checkout["patched"]["files"]], ["gate/src/main/java/fixture/Gate.java"])
        self.assertEqual(checkout["changedByBuild"], [], "the build left the checkout as patched")
        self.assertEqual(prepared.source["mutant"]["applied"], checkout["patched"])
        original = next(a for a in prepared.artifacts if a.role == "original")
        self.assertTrue(original.origin.startswith("constructed: built by maven"), original.origin)
        self.assertIn(f"(sha256 {digest}) was applied", original.origin)

    def test_a_build_that_changes_the_patched_file_again_is_refused(self):
        self.set_knobs(touch=True)
        prepared = runtime.prepare(self.plan_of([self.upstream_entry()]), "mutant", self.work / "mutant")
        self.assertEqual(prepared.failedStage, "build", prepared.diagnostic)
        self.assertIn("gate/src/main/java/fixture/Gate.java (after the patch)", prepared.diagnostic)

    def test_the_upstream_mutation_pair_replays_as_the_fixtures(self):
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        after = upstream_plan(self.folder, ("after",), self.commits).artifacts[0]
        _, problems = self.replay(self.plan_of([after, self.upstream_entry()]))
        self.assertEqual(problems, {"after": {()}, "mutant": {(65,)}})

    def test_a_published_mutant_replaces_the_patched_classes_in_a_copy_of_the_base_jar(self):
        items = self.published()
        prepared = runtime.prepare(self.plan_of([self.published_entry(items)]), "mutant", self.work / "mutant")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        roles = {a.path: a.role for a in prepared.artifacts}
        self.assertEqual(roles["lib/fixture.example/gate-1.1.jar"], "base")
        self.assertEqual(roles["mutant/gate-1.1.jar"], "original")
        self.assertNotIn("lib/fixture.example/gate-1.1.jar", prepared.classpath, "the base JAR is off the classpath")
        self.assertEqual(prepared.classpath[2:], ("mutant/gate-1.1.jar", "lib/fixture.example/gate-util-2.0.jar"))
        m = prepared.source["mutant"]
        self.assertEqual([c["class"] for c in m["jar"]["classes"]], ["fixture/Gate"])
        work = self.work / "mutant"
        mutant_gate = runtime.runtime_jar.read_class(work / "mutant/gate-1.1.jar", "fixture/Gate")
        jars = Path(base.manifest()["dir"])
        self.assertEqual(mutant_gate, runtime.runtime_jar.read_class(jars / "mutant.jar", "fixture/Gate"),
                         "the recompiled class is build_fixtures.py's own mutant class: same --release, same flags")
        self.assertEqual(runtime.runtime_jar.read_class(work / "mutant/gate-1.1.jar", "fixture/RegexGate"),
                         runtime.runtime_jar.read_class(jars / "after.jar", "fixture/RegexGate"), "the rest is the base's")
        self.assertEqual((prepared.toolchain["mutant"]["release"], prepared.toolchain["mutant"]["flags"]),
                         ("21", ["-parameters"]), "the base's classes carry MethodParameters, so the recompile keeps them")
        self.assertEqual([(c["class"], c["identical"]) for c in prepared.toolchain["mutant"]["unpatchedRecompile"]["classes"]],
                         [("fixture/Gate", True)], "the same javac and flags give the base's own bytes back, unpatched")
        self.assertEqual(prepared.source["checkout"]["commit"], self.commits["after"])
        self.assertEqual(prepared.source["target"]["loadedFrom"], "mutant/gate-1.1.jar")

    def test_the_published_mutation_pair_replays_as_the_fixtures(self):
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        items = self.published()
        _, problems = self.replay(self.plan_of([self.published_entry(items, "after"), self.published_entry(items)]))
        self.assertEqual(problems, {"after": {()}, "mutant": {(65,)}})

    def test_a_published_mutant_is_refused_offline_or_when_the_copy_would_keep_stale_classes(self):
        items = self.published()
        offline = runtime.prepare(self.plan_of([self.published_entry(items)], network=False), "mutant", self.work / "a")
        self.assertEqual(offline.failedStage, "acquire")
        stale = self.dir / "stale.jar"
        shutil.copyfile(Path(base.manifest()["dir"]) / "after.jar", stale)
        with zipfile.ZipFile(stale, "a") as z:
            z.writestr("fixture/Gate$Old.class", runtime.runtime_jar.read_class(stale, "fixture/Gate"))
        items = self.published(stale)
        prepared = runtime.prepare(self.plan_of([self.published_entry(items)]), "mutant", self.work / "b")
        self.assertEqual(prepared.failedStage, "mutant", prepared.diagnostic)
        self.assertIn("fixture.Gate$Old", prepared.diagnostic)
        self.assertIn("stale bytes", prepared.diagnostic)

    def test_on_the_published_route_a_patch_may_only_change_java_sources(self):
        (self.folder / "gate/mutant.patch").write_text(gate_patch("gate/pom.xml"))
        self.mutant["patch"]["sha256"] = runtime.sha256(self.folder / "gate/mutant.patch")
        locked = runtime.lock(self.plan_of([self.published_entry(self.published())]), "mutant")
        self.assertEqual(locked.failedStage, "lock")
        self.assertIn("only Java sources are recompiled", locked.diagnostic)


GATE = "gate/src/main/java/fixture/Gate.java"


class SliceRouteTest(UpstreamCase):
    """The source-slice route: the stand-in's commit checked out, the slice's files compiled alone by the recorded JDK
    and flags against the recorded JARs (here a dependency on the stand-in for Central), the classes put in a JAR.
    With the fixture recipe's own flags, the slice's Gate is build_fixtures.py's byte for byte."""

    FLAGS = ["-parameters", "--release", "21", "-encoding", "UTF-8"]

    def setUp(self):
        super().setUp()
        self.central = base.Repository(self, self.dir / "central")
        self.items = [self.central.publish("fixture.example:gate-util:2.0", self.dep)]

    def entry(self, revision="after", files=(GATE,), flags=None, jdk="21", **extra):
        entry = {"revision": revision, "route": "source-slice", "repository": "https://github.com/example/gate",
                 "commit": self.commits[revision], **({"parent": self.commits["before"]} if revision == "after" else {}),
                 "slice": {"files": list(files), "jdk": jdk, "flags": list(self.FLAGS if flags is None else flags)},
                 "published": self.items, "adapters": ["gate/adapter/fixture/adapter/GateAdapter.java"],
                 "jdks": ["21", "25"]}
        entry.update(extra)
        return entry

    def mutant_entry(self):
        (self.folder / "gate/mutant.patch").write_text(gate_patch())
        base_entry = self.entry()
        return {"revision": "mutant", "route": "source-slice", "repository": base_entry["repository"],
                "mutant": {"base": {"revision": "after", **{k: base_entry[k] for k in ("commit", "published", "slice")}},
                           "patch": {"path": "gate/mutant.patch",
                                     "sha256": runtime.sha256(self.folder / "gate/mutant.patch")},
                           "description": "the fix normalizes one side only: 65 allowed again"},
                "adapters": base_entry["adapters"], "jdks": base_entry["jdks"]}

    def plan_of(self, entries, network=True):
        return dataclasses.replace(base.mutant_plan(self.folder, entries, revisions=tuple(e["revision"] for e in entries),
                                                    task="replay"), network=network)

    def test_a_slice_lock_fetches_nothing_and_refuses_a_recipe_it_cant_pin(self):
        with mock.patch.object(runtime_upstream, "REMOTE", side_effect=AssertionError("a source lock fetched")):
            locked = runtime.lock(self.plan_of([self.entry()]), "after")
        self.assertEqual((locked.stage, locked.commit), ("source-locked", self.commits["after"]), locked.diagnostic)
        self.assertEqual(locked.source["slice"]["files"], [GATE])
        self.assertEqual(locked.source["slice"]["scope"], runtime.SCOPES["extracted-source-slice"])
        self.assertEqual([i["role"] for i in locked.source["published"]], ["dependency"])
        self.assertIn("never the commit's own build", locked.source["provenance"])
        for change, says in (({"flags": ["-g", "-processorpath", "x"]}, "not one a slice may set"),
                             ({"flags": ["-d", "/tmp"]}, "not one a slice may set"),
                             ({"flags": ["-source"]}, "needs a value"),
                             ({"files": ["../x/Gate.java"]}, "not distinct .java paths"),
                             ({"files": ["gate/pom.xml"]}, "not distinct .java paths"),
                             ({"files": []}, "not distinct .java paths"),
                             ({"jdk": "x"}, "not a feature release")):
            with self.subTest(change=change):
                entry = self.entry()
                entry["slice"].update(change)
                refused = runtime.lock(self.plan_of([entry]), "after")
                self.assertEqual(refused.failedStage, "lock")
                self.assertIn(says, refused.diagnostic)
        no_recipe = self.entry()
        del no_recipe["slice"]
        self.assertIn("names no slice", runtime.lock(self.plan_of([no_recipe]), "after").diagnostic)

    @cost("tool")
    def test_the_slice_compiles_only_its_files_and_gives_the_fixture_recipes_bytes(self):
        prepared = runtime.prepare(self.plan_of([self.entry()]), "after", self.work / "after")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        self.assertEqual(prepared.classpath, ("driver.jar", "adapter-after.jar", "slice/after.jar",
                                              "lib/fixture.example/gate-util-2.0.jar"))
        work = self.work / "after"
        self.assertEqual(sorted(runtime.runtime_jar.classes(work / "slice/after.jar")), ["fixture/Gate"],
                         "RegexGate, in the same package of the checkout, is not compiled: only the slice's files are")
        self.assertEqual(runtime.runtime_jar.read_class(work / "slice/after.jar", "fixture/Gate"),
                         runtime.runtime_jar.read_class(Path(base.manifest()["dir"]) / "after.jar", "fixture/Gate"))
        compiled = prepared.source["slice"]["compiled"]
        self.assertEqual([(c["path"], c["gitBlob"]) for c in compiled],
                         [(GATE, git(self.upstream, "rev-parse", f"{self.commits['after']}:{GATE}"))])
        self.assertEqual(prepared.source["checkout"]["parentChecked"], self.commits["before"])
        self.assertEqual(prepared.toolchain["slice"]["jdk"]["feature"], "21")
        self.assertIn("-implicit:none", prepared.toolchain["slice"]["javac"])
        original = next(a for a in prepared.artifacts if a.role == "original")
        self.assertTrue(original.origin.startswith("an extracted source slice of"), original.origin)
        self.assertEqual(prepared.source["target"]["loadedFrom"], "slice/after.jar")

    @cost("tool")
    def test_a_file_the_commit_lacks_offline_or_a_stray_class_is_refused(self):
        missing = runtime.prepare(self.plan_of([self.entry(files=("gate/src/main/java/fixture/Nope.java",))]), "after",
                                  self.work / "a")
        self.assertEqual(missing.failedStage, "lock", missing.diagnostic)
        self.assertIn("is not a file of", missing.diagnostic)
        fetched = len(self.remotes)
        offline = runtime.prepare(self.plan_of([self.entry()], network=False), "after", self.work / "b")
        self.assertEqual(offline.failedStage, "acquire")
        self.assertEqual(len(self.remotes), fetched, "offline, nothing is checked out")
        shutil.rmtree(self.upstream)
        self.upstream, before, after = make_upstream(self.dir / "upstream2", {
            "gate/src/main/java/fixture/Pair.java": "package fixture;\npublic class Pair {}\nclass Stray {}\n"})
        self.commits = {"before": before, "after": after}
        stray = runtime.prepare(self.plan_of([self.entry(files=(GATE, "gate/src/main/java/fixture/Pair.java"))]),
                                "after", self.work / "c")
        self.assertEqual(stray.failedStage, "build", stray.diagnostic)
        self.assertIn("fixture/Stray", stray.diagnostic)
        entry = self.entry(files=(GATE, "gate/src/main/java/fixture/Pair.java"))
        entry["slice"]["companionClasses"] = ["fixture.Stray"]
        admitted = runtime.prepare(self.plan_of([entry]), "after", self.work / "declared")
        self.assertEqual(admitted.stage, "artifacts-ready", admitted.diagnostic)
        self.assertEqual(admitted.source["slice"]["companionSources"], {"fixture/Stray": "Pair.java"})

    def test_a_slice_class_is_checked_byte_for_byte_against_its_published_reference(self):
        """slice.matches (307's check of before against Spring Security 5.2.0.M4, the user's decision of 2026-11-15):
        the published JAR is fetched by its sha256 into reference/, off the classpath; a class that differs, a JAR
        without the entry, an entry whose bytes aren't the recorded ones, or a class the slice doesn't give, each fail
        the preparation."""
        import hashlib
        fixture = Path(base.manifest()["dir"])

        def published(jar_name, coords, cls_bytes, entry="fixture/Gate.class"):
            path = self.dir / jar_name
            with zipfile.ZipFile(path, "w") as z:
                z.writestr(entry, cls_bytes)
            return self.central.publish(coords, path)

        same = runtime.runtime_jar.read_class(fixture / "after.jar", "fixture/Gate")
        other = runtime.runtime_jar.read_class(fixture / "mutant.jar", "fixture/Gate")
        self.assertNotEqual(same, other)
        good = published("gate-pub.jar", "fixture.example:gate:1.0", same)
        match = {"class": "fixture/Gate.class", "sha256": hashlib.sha256(same).hexdigest(), "jar": good}
        entry = self.entry()
        entry["slice"]["matches"] = [match]
        locked = runtime.lock(self.plan_of([entry]), "after")
        self.assertEqual(locked.stage, "source-locked", locked.diagnostic)
        self.assertEqual(locked.source["slice"]["matches"][0]["jar"]["role"], "reference")
        prepared = runtime.prepare(self.plan_of([entry]), "after", self.work / "same")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        self.assertEqual(prepared.source["slice"]["matched"],
                         [{"class": "fixture/Gate.class", "sha256": match["sha256"], "identical": True,
                           "jar": {k: good[k] for k in ("coordinates", "url", "sha256")}}])
        self.assertTrue((self.work / "same/reference/gate-1.0.jar").is_file())
        self.assertNotIn("reference/gate-1.0.jar", prepared.classpath)
        self.assertNotIn(good["sha256"], [a.sha256 for a in prepared.artifacts], "the reference is no artifact of it")

        bad = published("gate-bad.jar", "fixture.example:gate:2.0", other)
        empty = published("gate-empty.jar", "fixture.example:gate:3.0", same, entry="fixture/Other.class")
        for name, m, stage, says in (
                ("differs", {"class": "fixture/Gate.class", "sha256": hashlib.sha256(other).hexdigest(), "jar": bad},
                 "build", "doesn't reproduce the published build"),
                ("no entry", {**match, "jar": empty}, "acquire", "has no entry fixture/Gate.class"),
                ("wrong hash", {**match, "sha256": "0" * 64}, "acquire", "not the recorded"),
                ("no class", {**match, "class": "fixture/Nope.class"}, "build", "gives no class fixture/Nope")):
            with self.subTest(name):
                e = self.entry()
                e["slice"]["matches"] = [m]
                refused = runtime.prepare(self.plan_of([e]), "after", self.work / name.replace(" ", "-"))
                self.assertEqual(refused.failedStage, stage, refused.diagnostic)
                self.assertIn(says, refused.diagnostic)
                self.assertIsNotNone(refused.blocker)
        for change, says in (([{"class": "Gate.java", "sha256": match["sha256"], "jar": good}], "not a class entry"),
                             ([{"class": "fixture/Gate.class", "jar": good}], "no published sha256"),
                             ([], "not a non-empty list"),
                             ([match, match], "matched twice")):
            with self.subTest(change=change):
                e = self.entry()
                e["slice"]["matches"] = change
                self.assertIn(says, runtime.lock(self.plan_of([e]), "after").diagnostic)

    def test_a_slice_receipts_claim_records_the_published_class_match_its_preparation_made(self):
        """Review item 7 (2026-11-15): 307's receipt says that before's class is Spring Security 5.2.0.M4's, byte for
        byte. The claim's target.matched carries each revision's matches from the preparation (source.slice.matched):
        the class entry, its sha256, and the JAR by coordinates, URL and sha256. A preparation that doesn't record a
        match its plan declares, or records another, is not bound; a revision with no matches adds nothing."""
        import hashlib
        from targets import workflow_ingest
        fixture = Path(base.manifest()["dir"])
        same = runtime.runtime_jar.read_class(fixture / "after.jar", "fixture/Gate")
        path = self.dir / "gate-pub.jar"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("fixture/Gate.class", same)
        good = self.central.publish("fixture.example:gate:1.0", path)
        match = {"class": "fixture/Gate.class", "sha256": hashlib.sha256(same).hexdigest(), "jar": good}
        entry = self.entry()
        entry["slice"]["matches"] = [match]
        plan = self.plan_of([entry])
        prepared = runtime.prepare(plan, "after", self.work / "after")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        bound = {"after": (entry, prepared, self.commits["after"])}
        expected = {"after": [{"class": "fixture/Gate.class", "sha256": match["sha256"],
                               "jar": {k: good[k] for k in ("coordinates", "url", "sha256")}}]}
        self.assertEqual(workflow_ingest.published_matches(bound), expected)
        record = workflow_ingest.claim_record(plan, self.folder / "target.json", bound, (), None)
        self.assertEqual(record["target"]["matched"], expected)
        self.assertEqual(record["target"]["scopes"], {"after": "extracted-source-slice"})
        import jsonschema
        schema = json.loads((Path(__file__).resolve().parents[2] / "schema/result.schema.json").read_text())
        target_schema = schema["properties"]["claim"]["properties"]["target"]
        jsonschema.validate(record["target"], target_schema)
        for bad in ({"after": []}, {"after": [{**expected["after"][0], "identical": True}]},
                    {"after": [{**expected["after"][0], "jar": {"coordinates": "x"}}]}):
            with self.subTest(schema=bad), self.assertRaises(jsonschema.ValidationError):
                jsonschema.validate({**record["target"], "matched": bad}, target_schema)

        source = dict(prepared.source)
        for name, slice_ in (("not recorded", {k: v for k, v in source["slice"].items() if k != "matched"}),
                             ("another class", {**source["slice"], "matched": [{**source["slice"]["matched"][0],
                                                                                 "sha256": "0" * 64}]})):
            with self.subTest(name):
                other = dataclasses.replace(prepared, source={**source, "slice": slice_})
                with self.assertRaises(workflow_ingest.Refused) as refused:
                    workflow_ingest.published_matches({"after": (entry, other, self.commits["after"])})
                self.assertIn("published-class match", refused.exception.reason)

        plain = self.entry()
        unmatched = runtime.prepare(self.plan_of([plain]), "after", self.work / "plain")
        self.assertEqual(unmatched.stage, "artifacts-ready", unmatched.diagnostic)
        self.assertIsNone(workflow_ingest.published_matches({"after": (plain, unmatched, self.commits["after"])}))
        self.assertNotIn("matched", workflow_ingest.claim_record(
            self.plan_of([plain]), self.folder / "target.json", {"after": (plain, unmatched, self.commits["after"])},
            (), None)["target"], "305's slice, which has no matches, keeps its claim as it was")

    def test_a_slice_mutant_is_its_base_commit_patched_then_compiled_as_the_base(self):
        prepared = runtime.prepare(self.plan_of([self.mutant_entry()]), "mutant", self.work / "mutant")
        self.assertEqual(prepared.stage, "artifacts-ready", prepared.diagnostic)
        self.assertTrue(prepared.commit.startswith(f"mutant:{self.commits['after']}+"))
        self.assertEqual(runtime.runtime_jar.read_class(self.work / "mutant/slice/mutant.jar", "fixture/Gate"),
                         runtime.runtime_jar.read_class(Path(base.manifest()["dir"]) / "mutant.jar", "fixture/Gate"),
                         "after patched and compiled by the slice's recipe is build_fixtures.py's mutant class")
        self.assertEqual([f["path"] for f in prepared.source["mutant"]["applied"]["files"]], [GATE])
        outside = self.mutant_entry()
        outside["mutant"]["base"]["slice"] = {**outside["mutant"]["base"]["slice"],
                                              "files": ["gate/src/main/java/fixture/RegexGate.java"]}
        refused = runtime.lock(self.plan_of([outside]), "mutant")
        self.assertEqual(refused.failedStage, "lock")
        self.assertIn("which the base's slice doesn't compile", refused.diagnostic)

    def test_the_slice_mutation_pair_replays_as_the_fixtures(self):
        if not {"21", "25"} <= set(runtime_jdk.homes()):
            self.skipTest(f"JDKs 21 and 25 are not both under {runtime_jdk.CANDIDATES}")
        plan = self.plan_of([self.entry(), self.mutant_entry()])
        attempt = self.work / "attempt"
        prepared = {r: runtime.prepare(plan, r, attempt / "prepare" / r) for r in plan.revisions}
        for r, p in prepared.items():
            self.assertEqual(p.stage, "artifacts-ready", f"{r}: {p.diagnostic}")
        problems = {}
        for r in runtime.run_controls(plan, prepared, attempt / "controls"):
            self.assertEqual((r.status, r.exitCode), ("exited", 0))
            problems.setdefault(r.revision, set()).add(
                tuple(c for c, _ in base.oracle().check([json.dumps(o) for o in r.observations])))
        self.assertEqual(problems, {"after": {()}, "mutant": {(65,)}})


class NumbersCaseTest(unittest.TestCase):
    """The case the upstream-build job runs (runtime_slice.py --case numbers, runtime_numbers/): example 105's two
    pinned commons-numbers commits. Nothing here fetches or builds; the job does."""

    def setUp(self):
        import runtime_slice
        self.slice = runtime_slice
        self.folder = runtime_slice.CASES["numbers"]["folder"]
        self.target = json.loads((self.folder / "target.json").read_text())
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(runtime_upstream, "REMOTE", side_effect=AssertionError("the case's tests fetched")).start()

    def test_the_sidecar_is_valid_and_both_commits_lock_offline_with_the_recipe(self):
        from targets import sidecar
        sidecar.check(self.target, self.folder)
        p = self.slice.plan(self.folder, network=True, example="316")
        self.assertEqual((p.example, p.kind, p.revisions), ("316", "replay", ("before", "after")))
        before, after = "e7c172d2f4c7d171fed9060e77b5f91a20c36c91", "8cfc04e8719d00bde40b3faba19180cc92e20f9e"
        for revision, commit, parent in (("before", before, None), ("after", after, before)):
            locked = runtime.lock(p, revision)
            self.assertEqual((locked.stage, locked.commit), ("source-locked", commit), locked.diagnostic)
            self.assertEqual(locked.source["history"].get("parent"), parent)
            self.assertEqual(locked.source["upstream"]["jdk"], "11")
            self.assertEqual(locked.source["upstream"]["argv"][:5],
                             ["mvn", "--batch-mode", "--no-transfer-progress", "--projects", "commons-numbers-core"])
            self.assertEqual(locked.source["driver"]["main"], "upstream.driver.PowDriver")

    def test_offline_the_build_is_a_blocker_at_acquire(self):
        p = self.slice.plan(self.folder, network=False, example="316")
        with tempfile.TemporaryDirectory(prefix="test-numbers-") as d:
            prepared = runtime.prepare(p, "after", Path(d) / "attempt/prepare/after")
        self.assertEqual(prepared.failedStage, "acquire", prepared.diagnostic)
        self.assertTrue(all(prepared.blocker[k] for k in ("command", "needs", "next")))

    def test_the_oracle_is_not_vacuous_and_tells_the_two_commits_apart(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("numbers_oracle", self.folder / "oracle.py")
        oracle = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(oracle)

        def int32(v):
            return (v + 2 ** 31) % 2 ** 32 - 2 ** 31

        def model(fixed, wrap=False, deny=False):  # Python stand-ins for implementations, right and wrong
            def pow_(k, e):
                if deny:
                    return "threw", "java.lang.ArithmeticException"
                if e < 0:
                    return "threw", "java.lang.IllegalArgumentException"
                if k in (0, 1, -1):
                    return "returned", k ** e
                if e >= (32 if fixed else 31) and not wrap:
                    return "threw", "java.lang.ArithmeticException"
                exact = k ** e if e <= 64 else None
                if exact is not None and -2 ** 31 <= exact < 2 ** 31:
                    return "returned", exact
                return ("returned", int32(k ** min(e, 64))) if wrap else ("threw", "java.lang.ArithmeticException")
            return pow_

        def lines(impl):
            out = []
            for k, e in oracle.PROBES:
                outcome, what = impl(k, e)
                out.append(json.dumps({"input": [k, e], "outcome": outcome,
                                       **({"value": what} if outcome == "returned" else {"exception": what})}))
            return out

        self.assertEqual([p for p, _ in oracle.check(lines(model(fixed=True)))], [])
        self.assertEqual([p for p, _ in oracle.check(lines(model(fixed=False)))],
                         self.slice.CASES["numbers"]["expected"]["before"])
        self.assertGreater(len(oracle.check(lines(model(fixed=True, deny=True)))), 10)
        self.assertGreater(len(oracle.check(lines(model(fixed=True, wrap=True)))), 5)
        with self.assertRaises(ValueError):
            oracle.check(lines(model(fixed=True))[1:])


if __name__ == "__main__":
    unittest.main()
