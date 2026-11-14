"""Pinned upstream builds (llm-dlc/loops/example-targets.md, runtime's R2 and decision 3): the exact commit fetched from
github.com into an isolated checkout, its ancestry checked where the sidecar records a parent, and the recorded recipe
run with the revision's own build tool and a JDK it supports, chosen by its full path. Runtime stream's; runtime.py's
`upstream-build` route calls it. Upstream builds are pipeline jobs, never run inline.

    check_recipe(revision, entry)  the artifact entry's repository, commit, parent and build, checked offline
    build(recipe, workdir, ...)    the checkout, the build and its outputs: the original JAR (the one produced JAR
                                   that holds the target class) and its runtime dependencies, each hashed

What a build records, beside the bytes:
- the checkout: the commit and its tree, the parents when one is recorded (and that it is one of them), where it was
  fetched from, and that the build left every tracked file as checked out (the original sources stay untouched);
- the toolchain: the JDK (`release` file and `java -version`), the build tool's own version, by full path, and for a
  Maven wrapper its distribution's URL, sha256 and how that was checked;
- the recorded argv and the argv run, the environment, and the settings that make Maven Central the one repository,
  with a fresh local repository, strict checksums and no user configuration;
- every JAR the build produced, with its sha256, and every file the build resolved into its local repository, with
  its sha256 (`maven/resolution.json`), the version lookups among them (metadata Maven read to pick a version) named.

Maven only, for now. A Maven wrapper's distribution is fetched from Maven Central by the sha256 its properties record,
or else checked against Central's .sha1 and recorded, then run directly: the wrapper's own download step is not.
A Gradle build is a preparation blocker: a wrapper's distribution comes from services.gradle.org, outside the downloads
policy, and an installed Gradle is not the revision's own build tool. No build-enabling patch is applied: one would be
separate recorded bytes with a scope review.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import time
import urllib.parse
import zipfile
from pathlib import Path

from targets import runtime_jdk, runtime_maven
from targets.runtime_maven import Blocked

REPOSITORY = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
TOOLS = {"maven": "mvn", "maven-wrapper": "./mvnw", "gradle": "gradle", "gradle-wrapper": "./gradlew"}
# Options preparation sets itself: a recipe that sets them would choose its own repositories or local repository.
OWN_OPTIONS = re.compile(r"^(-s|--settings|-gs|--global-settings|-Dmaven\.repo\.local(=.*)?|-o|--offline)$")
BUILD_TIMEOUT = 1800  # seconds the recorded build may run
GIT_TIMEOUT = 600
DEPENDENCY_PLUGIN = "org.apache.maven.plugins:maven-dependency-plugin:3.9.0"  # by full version: no plugin lookup
# build-classpath's scope filter and output file. Their user properties, as the plugin's descriptor (META-INF/maven/
# plugin.xml, sha256 39b04539...bba3) names them, are `includeScope` and `mdep.outputFile`: an unknown property is
# ignored, and with no filter the listing is the test classpath (the first upstream job's record, 2026-11-14).
SCOPE = "runtime"
PLUGIN_OWN = ("-Dmdep.", "-DincludeScope", "-DexcludeScope", "-DincludeTypes", "-DexcludeTypes")  # not passed through
MAVEN_CANDIDATES = Path(os.environ.get("TARGETS_MAVEN_CANDIDATES", Path.home() / ".sdkman/candidates/maven"))
BASE_ENV = {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
AUXILIARY = re.compile(r"-(sources|javadoc|tests|test-sources|test-javadoc)\.jar$")
WRAPPER_DIST = re.compile(r"^https://repo\.maven\.apache\.org/maven2/org/apache/maven/apache-maven/"
                          r"([0-9][A-Za-z0-9_.-]*)/apache-maven-\1-bin\.zip$")
REMOTE = None  # tests only: a callable from a repository URL to a local repository to fetch from instead


def check_recipe(revision, entry):
    """The upstream-build entry's repository, commit, optional parent and build (tool, argv, jdk), checked offline:
    an https repository on github.com, full commits, a known tool whose argv starts with its own command, a JDK by
    feature, and no option that would bypass the build's isolation."""
    def refuse(why, needs="an immutable upstream build recipe: a github.com repository, a full commit, the build tool, "
                          "its exact argv and a JDK", next="correct the revision's entry in target.json"):
        raise Blocked("lock", f"revision {revision}: {why}", needs=needs, next=next)

    repository = entry.get("repository")
    if not isinstance(repository, str) or not REPOSITORY.match(repository.removesuffix(".git")):
        refuse(f"{repository!r} is not an https repository on github.com, the one host commits are fetched from")
    commit, parent = entry.get("commit"), entry.get("parent")
    if not isinstance(commit, str) or not FULL_SHA.match(commit):
        refuse(f"{commit!r} is not a full commit: a branch, tag or short SHA can name other sources later")
    if parent is not None and (not isinstance(parent, str) or not FULL_SHA.match(parent)):
        refuse(f"its recorded parent {parent!r} is not a full commit")
    build = entry.get("build")
    if not isinstance(build, dict):
        refuse("the upstream-build route names no build (tool, argv, jdk)")
    tool, argv, jdk = build.get("tool"), build.get("argv"), build.get("jdk")
    if tool not in TOOLS:
        refuse(f"{tool!r} is not a known build tool ({', '.join(TOOLS)})")
    if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and a for a in argv):
        refuse("the build's argv is not a non-empty list of strings")
    if argv[0] != TOOLS[tool]:
        refuse(f"a {tool} build runs {TOOLS[tool]}, and its argv starts with {argv[0]!r}")
    own = [a for a in argv[1:] if OWN_OPTIONS.match(a)]
    if own:
        refuse(f"the argv sets {', '.join(own)}, which preparation sets itself: the build's repositories are Maven "
               f"Central alone and its local repository is fresh")
    if not isinstance(jdk, str) or not jdk.isdigit():
        refuse(f"the build's JDK {jdk!r} is not a feature release (8, 11, 17, 21, 25)")
    return {"repository": repository, "commit": commit, "parent": parent, "tool": tool, "argv": list(argv), "jdk": jdk}


class Steps:
    """The processes of one build, each logged under workdir/logs/<step>.log with its argv, exit and duration."""

    def __init__(self, workdir, logs):
        self.workdir, self.logs, self.ran = Path(workdir), logs, []

    def run(self, step, argv, cwd, env, timeout):
        started = time.monotonic()
        try:
            proc = subprocess.run([str(a) for a in argv], cwd=cwd, env=env, capture_output=True, text=True,
                                  timeout=timeout, stdin=subprocess.DEVNULL, errors="replace")
            out, code = proc.stdout + proc.stderr, proc.returncode
        except subprocess.TimeoutExpired as e:
            out, code = f"timed out after {timeout}s: {e}", None
        seconds = round(time.monotonic() - started, 3)
        log = Path("logs") / f"{step}.log"
        (self.workdir / log).parent.mkdir(exist_ok=True)
        (self.workdir / log).write_text(f"$ {shlex.join(str(a) for a in argv)}\n{out}\nexit {code} after {seconds}s\n")
        if log.as_posix() not in self.logs:
            self.logs.append(log.as_posix())
        self.ran.append({"step": step, "argv": [str(a) for a in argv], "exit": code, "seconds": seconds})
        return code, out

    def must(self, step, argv, cwd, env, timeout, stage, needs, next):
        code, out = self.run(step, argv, cwd, env, timeout)
        if code != 0:
            raise Blocked(stage, f"{step} failed (exit {code}): {shlex.join(str(a) for a in argv)}\n{_tail(out)}",
                          command=shlex.join(str(a) for a in argv), needs=needs, next=next)
        return out


def _tail(text, lines=15):
    return "\n".join(text.strip().splitlines()[-lines:])


def _git():
    found = shutil.which("git")
    if not found:
        raise Blocked("toolchain", "no git on PATH to fetch the commit with", needs="git",
                      next="install git; the checkout is fetched by full commit from github.com")
    return str(Path(found).resolve())


def checkout(steps, recipe, dest, home, found):
    """The exact commit fetched into the new directory `dest`, with no tags, hooks, submodules or user
    configuration. `found` is filled as it goes (commit, tree, fetchedFrom, depth, git, then parents and
    parentChecked), so a refusal still says what was checked out."""
    url, commit, parent = recipe["repository"], recipe["commit"], recipe["parent"]
    source, protocols = url, ["-c", "protocol.allow=never", "-c", "protocol.https.allow=always"]
    if REMOTE is not None:  # tests: a local repository stands in for github.com
        source, protocols = str(REMOTE(url)), ["-c", "protocol.allow=never", "-c", "protocol.file.allow=always"]
    git = [_git(), "-c", "core.hooksPath=/dev/null", "-c", "transfer.fsckObjects=true", "-c", "core.autocrlf=false",
           "-c", "advice.detachedHead=false", "-c", "init.defaultBranch=checkout", *protocols]
    env = {"PATH": "/usr/bin:/bin", "HOME": str(home), "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", **BASE_ENV}
    needs = "the exact commit, fetched from github.com"
    steps.must("git-init", git + ["init", "-q", dest], steps.workdir, env, GIT_TIMEOUT, "acquire", needs,
               "check that git works; nothing was fetched")
    depth = 2 if parent else 1
    steps.must("git-fetch", git + ["-C", dest, "fetch", "--no-tags", "--no-recurse-submodules", f"--depth={depth}",
                                   source, commit], steps.workdir, env, GIT_TIMEOUT, "acquire", needs,
               f"check that {commit} is in {url} (fetched by full commit, as github.com allows) and that the network "
               f"is up: a network failure is infrastructure, not a finding")
    steps.must("git-checkout", git + ["-C", dest, "checkout", "-q", "--detach", commit], steps.workdir, env,
               GIT_TIMEOUT, "acquire", needs, "read logs/git-checkout.log")

    def ask(step, *args):
        return steps.must(step, git + ["-C", dest, *args], steps.workdir, env, GIT_TIMEOUT, "acquire", needs,
                          f"read logs/{step}.log").strip()

    head = ask("git-head", "rev-parse", "HEAD")
    if head != commit:
        raise Blocked("acquire", f"the checkout is at {head}, not {commit}", needs=needs, next="read logs/git-fetch.log")
    found.update(commit=head, tree=ask("git-tree", "rev-parse", "HEAD^{tree}"), fetchedFrom=url, depth=depth,
                 git=ask("git-version", "--version"))
    if parent:
        parents = ask("git-parents", "rev-list", "--parents", "-n", "1", "HEAD").split()[1:]
        found["parents"] = parents
        if parent not in parents:
            raise Blocked("history", f"{commit}'s parents are {', '.join(parents) or 'none fetched'}, and the sidecar "
                          f"records {parent} as its parent", command=shlex.join(git + ["-C", str(dest), "rev-list",
                                                                                       "--parents", "-n", "1", "HEAD"]),
                          needs="the recorded parent to be one of the commit's parents (the pair's selected parent)",
                          next="check the sidecar's history against upstream; the history is what is wrong, so the "
                               "lock is not changed to fit the checkout")
        found["parentChecked"] = parent
    found["submodules"] = ("declared in .gitmodules and not fetched: the build sees none" if (Path(dest) / ".gitmodules")
                           .is_file() else "none declared")
    found["changedByBuild"] = None
    return git, env


def _changed(steps, git, env, dest, step):
    out = steps.must(step, git + ["-C", dest, "status", "--porcelain", "--untracked-files=no"], steps.workdir, env,
                     GIT_TIMEOUT, "build", "a checkout git can read", f"read logs/{step}.log")
    return [line for line in out.splitlines() if line.strip()]


def _properties(path):
    """A Java properties file's key=value lines, with its backslash escapes undone (`https\\://`)."""
    out = {}
    for line in Path(path).read_text(errors="replace").splitlines():
        line = line.strip()
        if not line or line[0] in "#!":
            continue
        key, sep, value = line.partition("=")
        if sep:
            out[key.strip()] = re.sub(r"\\(.)", r"\1", value.strip())
    return out


def _installed_maven():
    """The highest Maven installed under MAVEN_CANDIDATES (not `current`), by its real path, or None."""
    if not MAVEN_CANDIDATES.is_dir():
        return None
    found = [e for e in MAVEN_CANDIDATES.iterdir()
             if e.name != "current" and not e.is_symlink() and (e / "bin/mvn").is_file()]
    if not found:
        return None
    best = max(found, key=lambda e: [int(p) if p.isdigit() else 0 for p in re.split(r"[.-]", e.name)])
    return best.resolve() / "bin/mvn"


MAVEN = _installed_maven  # tests replace it with a stand-in


def _wrapper_maven(steps, dest, workdir, cache, network):
    """The Maven distribution the checkout's wrapper names, from Maven Central by sha256 (its properties' own, or
    Central's .sha1 checked and the sha256 recorded), unpacked into a new directory: (mvn, record)."""
    props_path = Path(dest) / ".mvn/wrapper/maven-wrapper.properties"
    if not props_path.is_file():
        raise Blocked("toolchain", "the recipe's tool is maven-wrapper, and the checkout has no "
                      ".mvn/wrapper/maven-wrapper.properties", needs="the revision's own Maven wrapper",
                      next="record the tool the revision builds with (maven, if it has no wrapper)")
    props = _properties(props_path)
    named = props.get("distributionUrl", "")
    # repo1.maven.org is Maven Central under its older name: the same path is fetched from repo.maven.apache.org.
    url = re.sub(r"^https://repo1\.maven\.org/maven2/", runtime_maven.CENTRAL, named)
    match = WRAPPER_DIST.match(url)
    if not match:
        raise Blocked("toolchain", f"the Maven wrapper's distribution {named!r} is not an Apache Maven binary zip on "
                      f"Maven Central", needs="the revision's own Maven distribution, from Maven Central",
                      next="the user decides whether another host may serve it; until then the revision can't be built "
                           "with its own tool")
    version = match.group(1)
    digest, checked = props.get("distributionSha256Sum"), "distributionSha256Sum in the commit's maven-wrapper.properties"
    if digest is not None and not runtime_maven.SHA256.match(digest.lower()):
        raise Blocked("toolchain", f"the wrapper's distributionSha256Sum {digest!r} is not a sha256")
    if digest is None:
        if not network:
            raise Blocked("acquire", f"the wrapper's Maven {version} has no recorded sha256 and the plan allows no "
                          "acquisition", needs="its bytes from Maven Central", next="plan the task with acquisition")
        digest, sha1 = runtime_maven.pin_file(url, cache)
        checked = f"Maven Central's .sha1 ({sha1}), the properties recording no sha256; the sha256 recorded here"
    zipped = workdir / "tools" / f"apache-maven-{version}-bin.zip"
    zipped.parent.mkdir(parents=True, exist_ok=True)
    log = runtime_maven.acquire({"coordinates": f"org.apache.maven:apache-maven:{version}", "url": url,
                                 "sha256": digest.lower()}, zipped, cache, network=network)
    home = _unzip(zipped, workdir / "tools" / "maven")
    mvn = home / "bin/mvn"
    if not mvn.is_file():
        raise Blocked("toolchain", f"{url} holds no bin/mvn under one top directory")
    for script in (home / "bin").iterdir():
        script.chmod(0o755)
    record = {"properties": {"path": ".mvn/wrapper/maven-wrapper.properties",
                             "sha256": runtime_maven.sha256_of(props_path)},
              "distributionUrl": named, "fetchedFrom": url, "sha256": digest.lower(), "checked": checked,
              "acquire": log, "run": "the distribution's bin/mvn, in place of ./mvnw (the wrapper's own download "
                                    "step is not run)"}
    return mvn, record


def _unzip(path, into):
    """A downloaded zip into the new directory `into`, refusing an entry that would land outside it or a link; the
    one top-level directory it holds."""
    into.mkdir(parents=True)
    with zipfile.ZipFile(path) as z:
        for info in z.infolist():
            name = info.filename
            if name.startswith("/") or ".." in Path(name).parts or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise Blocked("toolchain", f"{path.name} holds {name!r}, outside its root or a link: not unpacked")
        z.extractall(into)
    tops = [p for p in into.iterdir()]
    if len(tops) != 1 or not tops[0].is_dir():
        raise Blocked("toolchain", f"{path.name} does not unpack to one top directory")
    return tops[0]


def _gradle_blocker(recipe, dest):
    if recipe["tool"] == "gradle":
        return Blocked("toolchain", "a gradle build without its wrapper names no Gradle version: the installed Gradle "
                       "isn't the revision's own build tool, and Gradle plugins resolve from plugins.gradle.org, outside "
                       "the downloads policy", needs="the revision's own Gradle, from an allowed host by sha256",
                       next="the user decides whether a Gradle distribution host may be used; until then use the "
                            "published-artifact route where the revision is a release")
    props = _properties(dest / "gradle/wrapper/gradle-wrapper.properties") \
        if (dest / "gradle/wrapper/gradle-wrapper.properties").is_file() else {}
    url = props.get("distributionUrl")
    host = urllib.parse.urlsplit(url).hostname if url else None
    return Blocked("toolchain", f"the Gradle wrapper's distribution {url or '(none named)'} is on {host or 'no host'}, "
                   f"outside the downloads policy (github.com and Maven Central); its recorded sha256 is "
                   f"{props.get('distributionSha256Sum') or 'missing'}",
                   command=shlex.join(recipe["argv"]),
                   needs="the revision's own Gradle distribution, from an allowed host, checked against the commit's "
                         "distributionSha256Sum",
                   next="the user decides whether services.gradle.org may serve a wrapper distribution checked against "
                        "the commit's distributionSha256Sum (and how plugins.gradle.org is handled); until then use "
                        "the published-artifact route where the revision is a release")


def _settings(path, repository):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "<settings>\n"
        f"  <localRepository>{repository}</localRepository>\n"
        "  <interactiveMode>false</interactiveMode>\n"
        "  <offline>false</offline>\n"
        "  <mirrors>\n"
        "    <mirror><id>central-only</id><mirrorOf>*</mirrorOf>"
        f"<url>{runtime_maven.CENTRAL.rstrip('/')}</url></mirror>\n"
        "  </mirrors>\n"
        "</settings>\n")
    return path


def build(recipe, workdir, target_class, logs, record, network=True, cache=None):
    """Build `recipe` (check_recipe's) in workdir/checkout: [(path, sha256, role, coordinates, origin)] for the
    original JAR (the one non-auxiliary JAR the build produced that holds `target_class`, internal name) copied to
    built/, then its runtime dependencies, in Maven's order, copied to lib/. `record` is filled as it goes
    (checkout, toolchain, outputs), so a failure still says what exists; `logs` gets each step's log."""
    workdir = Path(workdir)
    cache = cache or runtime_maven.Cache()
    steps = Steps(workdir, logs)
    record["steps"] = steps.ran
    if not network:
        raise Blocked("acquire", "an upstream build fetches its commit from github.com and its build's plugins and "
                      "dependencies from Maven Central, and the task's plan allows no acquisition (network: false)",
                      needs="acquisition", next="plan the task with acquisition (TaskPlan.network)")
    if recipe["tool"] == "gradle":
        raise _gradle_blocker(recipe, None)
    home = workdir / "home"  # HOME for every step: no user configuration is read
    home.mkdir(parents=True, exist_ok=True)
    dest = workdir / "checkout"
    record["checkout"] = found = {}
    git, git_env = checkout(steps, recipe, dest, home, found)
    if recipe["tool"] == "gradle-wrapper":
        raise _gradle_blocker(recipe, dest)
    if _changed(steps, git, git_env, dest, "git-status-before"):
        raise Blocked("acquire", "the fresh checkout already differs from its commit", next="read logs/git-status-before.log")

    jdk = runtime_jdk.home(recipe["jdk"])
    if jdk is None:
        raise Blocked("toolchain", f"no JDK {recipe['jdk']} under {runtime_jdk.CANDIDATES}, which the recipe builds with",
                      needs=f"JDK {recipe['jdk']}, the one the revision's build supports",
                      next=f"install Temurin {recipe['jdk']} with sdkman (without making it the default)")
    toolchain = {"tool": recipe["tool"], "jdk": runtime_jdk.identity(jdk)}
    record["toolchain"] = toolchain
    if recipe["tool"] == "maven-wrapper":
        mvn, toolchain["wrapper"] = _wrapper_maven(steps, dest, workdir, cache, network)
    else:
        mvn = MAVEN()
        if mvn is None:
            raise Blocked("toolchain", f"no Maven under {MAVEN_CANDIDATES}", needs="Maven",
                          next="install Maven with sdkman")
    env = {"PATH": f"{jdk}/bin:/usr/bin:/bin", "JAVA_HOME": str(jdk), "HOME": str(home), "MAVEN_SKIP_RC": "1",
           **BASE_ENV}
    repository = workdir / "maven/repository"
    repository.mkdir(parents=True)
    settings = _settings(workdir / "maven/settings.xml", repository)
    isolation = [mvn, "-s", settings, "-gs", settings, f"-Dmaven.repo.local={repository}", "--strict-checksums"]
    version = steps.must("maven-version", [mvn, "--version"], dest, env, GIT_TIMEOUT, "toolchain",
                         "a Maven that runs on the recipe's JDK", "read logs/maven-version.log")
    toolchain.update(maven={"path": str(mvn), "version": version.strip().splitlines()[:3]},
                     argv={"recorded": recipe["argv"], "run": [str(a) for a in isolation + recipe["argv"][1:]]},
                     env=env, settings={"path": "maven/settings.xml", "sha256": runtime_maven.sha256_of(settings),
                                        "meaning": "Maven Central the one repository (a mirror of every other), a "
                                                   "fresh local repository, strict checksums, no user settings "
                                                   "(HOME is the work directory's, MAVEN_SKIP_RC)"})

    code, out = steps.run("build", isolation + recipe["argv"][1:], dest, env, BUILD_TIMEOUT)
    if code != 0:
        raise Blocked("build", f"the recorded build failed ({'timed out' if code is None else f'exit {code}'}): "
                      f"{shlex.join(recipe['argv'])}\n{_tail(out)}", command=shlex.join(recipe["argv"]),
                      needs="a build of the pinned commit that completes with its own tool and a JDK it supports",
                      next="read logs/build.log: a plugin or dependency Maven Central doesn't serve, a JDK the revision "
                           "doesn't support, or a check the recipe doesn't skip; a build-enabling patch would be "
                           "separate recorded bytes with a scope review")
    changed = _changed(steps, git, git_env, dest, "git-status-after")
    found["changedByBuild"] = changed
    if changed:
        raise Blocked("build", f"the build changed tracked files of the checkout: {'; '.join(changed[:10])}",
                      needs="a recipe that leaves the original sources as checked out",
                      next="a build-enabling change goes in as separate recorded bytes with a scope review, never "
                           "into the checkout unrecorded")

    produced = _produced(steps, git, git_env, dest)
    record["outputs"] = {"jars": produced}
    entry = f"{target_class}.class"
    holders = [j["path"] for j in produced if not j["auxiliary"] and entry in _names(dest / j["path"])]
    if not holders:
        raise Blocked("build", f"no JAR the build produced holds {entry} (produced: "
                      f"{', '.join(j['path'] for j in produced) or 'none'})",
                      needs="the recipe to package the module that declares the target",
                      next="select the target's module in the recipe's argv (--projects), with a phase that packages it")
    if len(holders) > 1:
        raise Blocked("classpath", f"{len(holders)} JARs the build produced hold {entry}: {', '.join(holders)}",
                      needs="one produced JAR as the original", next="narrow the recipe to the target's module")
    original = workdir / "built" / Path(holders[0]).name
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(dest / holders[0], original)
    out_files = [(original.relative_to(workdir).as_posix(), runtime_maven.sha256_of(original), "original", None,
                  f"built by {recipe['tool']} from {recipe['repository']} at {recipe['commit']}: {holders[0]}")]
    record["outputs"]["original"] = holders[0]

    module = (dest / holders[0]).parent.parent
    pom = module / "pom.xml"
    if not pom.is_file():
        raise Blocked("build", f"{holders[0]} isn't under a Maven module (no {pom.relative_to(dest)})")
    listing = workdir / "maven/classpath.txt"
    passed = [a for a in recipe["argv"][1:] if a.startswith(("-D", "-P")) and not a.startswith(PLUGIN_OWN)]
    steps.must("dependencies", isolation + ["--batch-mode", "--no-transfer-progress", "-f", pom, *passed,
                                            f"{DEPENDENCY_PLUGIN}:build-classpath", f"-Dmdep.outputFile={listing}",
                                            f"-DincludeScope={SCOPE}"],
               dest, env, BUILD_TIMEOUT, "build", "the module's runtime dependencies, resolved from Maven Central",
               "read logs/dependencies.log")
    entries = [e for e in (listing.read_text().strip().split(os.pathsep) if listing.is_file() else []) if e]
    for e in entries:
        path = Path(e).resolve()
        if not path.is_relative_to(repository.resolve()) or not path.is_file():
            raise Blocked("classpath", f"{e} is on the module's runtime classpath and isn't a file in the build's "
                          f"local repository (a reactor module's classes)",
                          needs="every dependency as a JAR the build resolved or installed",
                          next="build with `install` so reactor modules are installed in the build's own local "
                               "repository")
        rel = path.relative_to(repository.resolve())
        parts = rel.parts
        coords = f"{'.'.join(parts[:-3])}:{parts[-3]}:{parts[-2]}" if len(parts) >= 4 else None
        installed = (path.parent.parent / "maven-metadata-local.xml").is_file()
        copied = workdir / "lib" / rel
        copied.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, copied)
        out_files.append((copied.relative_to(workdir).as_posix(), runtime_maven.sha256_of(copied), "dependency", coords,
                          "installed in the build's local repository by the recipe" if installed else
                          "resolved by Maven from Maven Central (the build's one repository), checksums strict"))
    record["outputs"]["dependencies"] = {"order": "Maven's runtime classpath order (dependency:build-classpath)",
                                         "command": f"{DEPENDENCY_PLUGIN}:build-classpath -DincludeScope={SCOPE}",
                                         "scope": f"{SCOPE}: the compile and runtime scopes, no test or provided",
                                         "passed": passed}
    toolchain["resolution"] = _resolution(repository, workdir)
    shutil.rmtree(repository)  # every file it held is hashed in the resolution record; what is used is copied
    return out_files


def _names(jar):
    try:
        with zipfile.ZipFile(jar) as z:
            return set(z.namelist())
    except (OSError, zipfile.BadZipFile):
        return set()


def _produced(steps, git, env, dest):
    """Every JAR the build left in the checkout that git doesn't track, with its sha256."""
    out = steps.must("git-untracked", git + ["-C", dest, "ls-files", "-z", "--others"], steps.workdir, env,
                     GIT_TIMEOUT, "build", "a checkout git can read", "read logs/git-untracked.log")
    jars = sorted(n for n in out.split("\0") if n.endswith(".jar"))
    return [{"path": n, "sha256": runtime_maven.sha256_of(dest / n), "auxiliary": bool(AUXILIARY.search(n))}
            for n in jars]


def _resolution(repository, workdir):
    """Every file in the build's local repository, hashed, in maven/resolution.json; the version lookups (artifact
    metadata Maven read from the repository to choose a version: a range, a plugin without a version) named."""
    files, lookups = [], []
    for path in sorted(p for p in repository.rglob("*") if p.is_file()):
        rel = path.relative_to(repository).as_posix()
        files.append({"path": rel, "sha256": runtime_maven.sha256_of(path), "size": path.stat().st_size})
        if path.name.startswith("maven-metadata-") and not path.name.endswith("-local.xml") \
                and "<versioning>" in path.read_text(errors="replace"):
            lookups.append(rel)
    out = workdir / "maven/resolution.json"
    out.write_text(json.dumps({"repository": "the build's own local repository, fresh, Maven Central its one source",
                               "files": files, "versionLookups": lookups}, indent=1) + "\n")
    return {"path": "maven/resolution.json", "sha256": runtime_maven.sha256_of(out), "files": len(files),
            "versionLookups": lookups,
            "meaning": "a version lookup is metadata Maven read to choose a version: recorded, and the bytes it chose "
                       "are hashed, but a later build may choose differently"}
