"""Export one allow-listed upstream view. No case directories enter the operator sandbox."""
import difflib
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import zipfile

from eligibility_inventory import BATCHES, CACHE, JDKS, RESERVED, ROOT, digest, example, read, upstream_pr, worktree, write
from sealed_io import committed_input


class PreparationStop(ValueError):
    """A missing or unsafe original input. Preserve this case and the reason."""


ARMS = ("cold", "test-assisted", "reviewed")
SOURCE_EXTENSIONS = {".java", ".kt", ".groovy", ".scala"}
TEST_DIR = re.compile(r"(?:^|/)(?:src/(?:[^/]*[Tt]est[^/]*|testFixtures)|[^/]*[-_]tests?|tests?|[^/]*[Tt]estFixtures|acceptance-tests)(?:/|$)")
TEST_CLASS = re.compile(r"(?:^(?:Test[A-Z]\w*)$|(?:Tests?|TestCase|IT)(?:\$.*)?$)")
UNTRUSTED_LISTING = re.compile(r"(?i)@(?:parameterized)?test\b|\b(?:assertThat|assertEquals|assertThrows|assertArrayEquals|assertDoesNotThrow|assertNotNull|assertTrue|assertFalse)\s*\(|org\.junit\.|(?:^|\n)\s*(?:public\s+)?void test[A-Z]|<pre\b|@snippet\b")
HAZARD = re.compile(r"(?i)\b(?:CVE-\d[\d-]*|GHSA-[a-z\d-]+|vulnerabilit\w*|exploits?|ReDoS|denial.of.service|path.traversal|zip.slip|XXE|remote.code.execution|command.injection|SQL.injection|deserialization.attack|security.bypass|cross.site.scripting|server.side.request.forgery)\b")
UNSAFE_MATERIAL = re.compile(r"-----BEGIN (?:[A-Z]+ )*PRIVATE KEY-----|\b(?:AKIA[0-9A-Z]{16}|gh[pousr]_[A-Za-z0-9]{24,})")
CODE_OR_COMMENT = re.compile(r'(?P<string>"""[\s\S]*?"""|"(?:\\.|[^"\\])*"|\x27(?:\\.|[^\x27\\])*\x27)|(?P<comment>//[^\n]*|/\*[\s\S]*?\*/)')


def clean_description(value):
    """Whole prose paragraphs only; omit code, HTML, quoted snippets and test listings."""
    value = re.sub(r"(?ms)^[ \t]*(`{3,}|~{3,})[^\n]*\n.*?(?:^[ \t]*\1[ \t]*(?:\n|$)|\Z)", "\n\n", value)
    value = re.sub(r"(?is)<(?:pre|code|details)\b.*?</(?:pre|code|details)>|<!--.*?-->", "", value)
    kept = []
    for paragraph in re.split(r"\n\s*\n", value.replace("\r", "")):
        if not paragraph.strip():
            continue
        if (UNTRUSTED_LISTING.search(paragraph) or UNSAFE_MATERIAL.search(paragraph)
                or re.search(r"(?m)^\s*(?:[>+`~$]|@@|diff --|import |package |public |class |@)|^ {4}|^\t", paragraph)
                or re.search(r"(?i)\b(?:unified diff|test(?:case| method| class| code| listing)|stack trace)\b", paragraph)):
            continue
        paragraph = re.sub(r"\[([^\]]*)\]\([^)]*\)|https?://\S+", lambda m: m[1] or "", paragraph)
        if any(c in paragraph for c in "{};") or "<" in paragraph or ">" in paragraph:
            continue
        kept.append(paragraph.strip())
    return "\n\n".join(kept)


def is_test(path):
    return bool(TEST_DIR.search(path) or TEST_CLASS.search(PurePosixPath(path).stem))


def is_production(path, *, legacy=False):
    name = PurePosixPath(path)
    lower = {p.lower() for p in name.parts}
    if is_test(path) or lower.intersection({"examples", "example", "samples", "fixtures", "fixture", "benchmarks", "benchmark", "demos", "docs"}):
        return False
    conventional = re.search(r"(?:^|/)src/(?:main/|java/|com/|org/|io/|net/)|(?:^|/)(?:main/)?java/", path)
    if legacy:
        return name.suffix in SOURCE_EXTENSIONS and bool(conventional)
    if lower.intersection({"testdata", "testlib", "testing", "jmh", "test-resources"}) or re.search(r"(?:^|/)src/it/(?:java|resources)/", path):
        return False
    if name.suffix in SOURCE_EXTENSIONS:
        return bool(conventional) or "src" in lower
    return (name.suffix in {".drv", ".jjt", ".jj", ".g4"} or
            "src/main" in path and name.suffix in {".proto", ".properties", ".dtd", ".xsd"})


def clean_production(source):
    def without_comments(match):
        if match["string"] is not None:
            return match[0]
        return "\n" * match[0].count("\n") or " "
    cleaned = CODE_OR_COMMENT.sub(without_comments, source)
    if UNTRUSTED_LISTING.search(cleaned) or UNSAFE_MATERIAL.search(cleaned):
        return None
    return cleaned


def public_documentation(source):
    prose = []
    for match in CODE_OR_COMMENT.finditer(source):
        if not match["comment"] or not match[0].startswith("/**"):
            continue
        body = re.sub(r"(?m)^\s*\* ?", "", match[0][3:-2])
        body = re.sub(r"\{@(?:link|linkplain)\s+([^}\s]+)[^}]*\}", r"\1", body)
        body = re.sub(r"\{@(?:code|literal)\s+([^}\n]{1,80})\}", r"\1", body)
        # Javadoc preformatted blocks or snippets can carry upstream test listings.
        if "@snippet" in body:
            body = body.split("@snippet", 1)[0]
        cleaned = clean_description(body)
        if cleaned:
            prose.append(cleaned)
    return "\n\n".join(prose)


def raw_git(tree, *args, optional=False):
    result = subprocess.run(["git", "-C", str(tree), *args], capture_output=True)
    if result.returncode and not optional:
        raise PreparationStop("git could not read a pinned upstream object")
    return result.stdout if not result.returncode else b""


def source_names(tree, revision):
    return [p.decode("utf-8", "replace") for p in raw_git(tree, "ls-tree", "-r", "--name-only", "-z", revision).split(b"\0") if p]


def related_tests(path, stems, packages):
    folder, name = path.rsplit("/", 1) if "/" in path else ("", path)
    return (any(stem.casefold() in name.casefold() for stem in stems)
            or any(folder.endswith("/" + package) for package in packages))


def source_material(row, destination, metadata, arm, *, tree=None, public_docs=True, approved_tests=None):
    if tree is None:
        tree = worktree(CACHE / BATCHES[row["batch"]][3], row["slot"], "fix")
    old, new = row["pins"]["parent"], row["pins"]["fix"]
    raw = raw_git(tree, "diff", "--no-renames", "--no-ext-diff", "--name-only", "-z", old, new)
    changed = [p.decode("utf-8") for p in raw.split(b"\0") if p]
    counts = {"changedFiles": len(changed), "productionSources": 0, "testFilesVisible": 0,
              "productionListingsWithheld": 0, "testFilesWithheld": 0, "testSourcesOutsideSelection": 0}
    patches, docs, documentation, tests = [], [], [], []
    for path in changed:
        name = PurePosixPath(path)
        if name.is_absolute() or ".." in name.parts:
            raise PreparationStop("upstream source has no safe relative path")
        if not is_production(path, legacy=not public_docs):
            continue
        sources = []
        for side, revision in (("old", old), ("new", new)):
            content = raw_git(tree, "show", f"{revision}:{path}", optional=True)
            source = clean_production(content.decode("utf-8", "replace"))
            sources.append((side, revision, content, source))
        if any(source is None for _, _, _, source in sources):
            counts["productionListingsWithheld"] += 1
            continue
        for side, revision, content, source in sources:
            if content:
                export = destination / "source" / side / path
                export.parent.mkdir(parents=True, exist_ok=True)
                export.write_text(source)
                docs.append({"revision": revision, "side": side, "file": str(export.relative_to(destination)),
                             "upstreamSha256": hashlib.sha256(content).hexdigest(), "visibleSha256": digest(export)})
                api_docs = public_documentation(content.decode("utf-8", "replace")) if public_docs else ""
                if api_docs:
                    doc = destination / "api-docs" / side / (path + ".txt")
                    doc.parent.mkdir(parents=True, exist_ok=True)
                    doc.write_text(api_docs)
                    documentation.append({"revision": revision, "side": side, "file": str(doc.relative_to(destination)),
                                          "sha256": digest(doc)})
        patches.extend(difflib.unified_diff(sources[0][3].splitlines(True), sources[1][3].splitlines(True), f"a/{path}", f"b/{path}"))
        counts["productionSources"] += 1
    (destination / "production.diff").write_text("".join(patches))
    visible = {"productionDiff": "production.diff", "productionSources": docs,
               "title": clean_description(metadata["title"]), "description": clean_description(metadata["body"] or "")}
    if public_docs:
        counts["publicDocumentationFiles"] = len(documentation)
        counts["prDescriptionOriginalBytes"] = len((metadata["body"] or "").encode())
        visible["publicDocumentation"] = documentation
    if arm == "test-assisted":
        if approved_tests is None:
            raise PreparationStop("upstream test sources lack the evaluator's independent functional review")
        production = [p for p in changed if is_production(p, legacy=not public_docs)]
        stems = [PurePosixPath(p).stem for p in production]
        packages = {p.rsplit("/", 1)[0].split(marker)[-1] for p in production
                    for marker in ("/java/", "/kotlin/", "/groovy/", "/scala/") if marker in p}
        for side, revision in (("old", old), ("new", new)):
            for path in source_names(tree, revision):
                name = PurePosixPath(path)
                if not is_test(path) or name.suffix not in SOURCE_EXTENSIONS:
                    continue
                if path not in changed and not related_tests(path, stems, packages):
                    counts["testSourcesOutsideSelection"] += 1
                    continue
                content = raw_git(tree, "show", f"{revision}:{path}")
                letters = content.decode("utf-8", "replace")
                if (hashlib.sha256(content).hexdigest() not in approved_tests[side]
                        or HAZARD.search(letters) or UNSAFE_MATERIAL.search(letters)):
                    counts["testFilesWithheld"] += 1
                    continue
                export = destination / "upstream-tests" / side / path
                export.parent.mkdir(parents=True, exist_ok=True)
                export.write_bytes(content)
                tests.append({"revision": revision, "side": side, "changed": path in changed,
                              "file": str(export.relative_to(destination)), "sha256": digest(export)})
                counts["testFilesVisible"] += 1
        tests.sort(key=lambda t: (not t["changed"], t["file"]))
        visible["upstreamTests"] = tests
        visible["testScope"] = "Only original changed or related test sources affirmatively reviewed for the same ordinary operation and matched byte-for-byte at this pin."
    return visible, counts


def scan_jar(path, against):
    """Refuse an opaque mixed artifact; never rewrite an original deployment to hide tests."""
    if not path.is_file() or not zipfile.is_zipfile(path):
        raise PreparationStop("the declared original classpath needs a verified directory or non-JAR deployment")
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            if name.endswith(".class"):
                binary = re.sub(r"^META-INF/versions/\d+/", "", name.removesuffix(".class").split("$")[0])
                if binary in against:
                    raise PreparationStop("a deployment embeds an original upstream test class")
            if re.search(r"(?:^|/)(?:src/test|testFixtures)/", name):
                raise PreparationStop("a deployment embeds upstream test sources or fixtures")


def upstream_test_classes(tree, pins):
    # Names alone allow the evaluator to deny mixed subject artifacts without exporting tests.
    test_classes = set()
    for revision in pins.values():
        for name in source_names(tree, revision):
            file = PurePosixPath(name)
            if file.suffix in SOURCE_EXTENSIONS and is_test(name) and TEST_CLASS.search(file.stem):
                package_path = re.search(r"(?:^|/)((?:com|org|net|io|edu|dev)/[\w$/]+)\.\w+$", name)
                if package_path:
                    test_classes.add(package_path[1])
    return test_classes


def deployments(row, destination):
    runtime = read(example(row["number"]) / "runtime.json")
    cache = CACHE / BATCHES[row["batch"]][3]
    if cache.name != runtime["cache"]:
        raise PreparationStop("deployment cache does not match the pinned batch")
    jdk = (JDKS / runtime["jdk"]).resolve(strict=True)
    if not jdk.is_relative_to(JDKS.resolve()) or digest(jdk / "release") != runtime["jdkReleaseSha256"]:
        raise PreparationStop("original JDK is unavailable or has changed")
    tree = worktree(cache, row["slot"], "fix")
    test_classes = upstream_test_classes(tree, row["pins"])
    exported, variants = {}, []
    for variant, dep in runtime["deployments"].items():
        if dep.get("service") or dep.get("postgresImage") or dep.get("mysqlImage"):
            raise PreparationStop("original database service is required for this deployment")
        arms = {}
        for side, original in (("old", "parent"), ("new", "fix")):
            cp = []
            for name in dep["classpath"][original]:
                if not isinstance(name, str) or name not in runtime["sha256"]:
                    raise PreparationStop("a classpath input has no registered original artifact digest")
                checksum = runtime["sha256"][name]
                if checksum not in exported:
                    actual = (cache / name).resolve(strict=True)
                    if not actual.is_relative_to(cache.resolve()):
                        raise PreparationStop("classpath references an external cache location")
                    scan_jar(actual, test_classes)
                    rel = f"artifacts/{len(exported):03d}-{checksum[:16]}.jar"
                    target = destination / rel
                    target.parent.mkdir(exist_ok=True)
                    shutil.copyfile(actual, target)
                    if digest(target) != checksum:
                        raise PreparationStop("original artifact SHA-256 differs from the recorded deployment")
                    exported[checksum] = rel
                cp.append({"file": exported[checksum], "sha256": checksum})
            arms[side] = {"classpath": cp, "revision": row["pins"][original]}
        variants.append({"name": variant, **arms})
    if not variants:
        raise PreparationStop("no original ordered deployment")
    return {"jdk": str(jdk), "jdkReleaseSha256": digest(jdk / "release"), "deployments": variants,
            "old": variants[0]["old"], "new": variants[0]["new"]}


def export_packet(row, arm, destination, *, decision, registration=None):
    if arm not in ARMS or row["number"] in RESERVED or not row["eligible"]:
        raise PreparationStop("row or arm outside the declared evaluation")
    if (arm == "reviewed") != (registration is not None):
        raise ValueError("reviewed input belongs only to the reviewed arm")
    from functional_scope import require_decision
    functional_review = require_decision(row, decision)
    metadata = upstream_pr(row)
    if HAZARD.search(" ".join([metadata["title"], metadata["body"] or "", *[label["name"] for label in metadata["labels"]]])):
        raise PreparationStop("scoped abstention for a possible real security vulnerability")
    destination.mkdir()
    contents, visibility = source_material(row, destination, metadata, arm, approved_tests=decision["approvedTests"])
    packet = {"schema": "blind-caller-packet/v1", "arm": arm, "url": row["url"],
              "oldRevision": row["pins"]["parent"], "newRevision": row["pins"]["fix"],
              "functionalReview": functional_review, **contents, **deployments(row, destination)}
    if registration is not None:
        packet["reviewed"] = registration
    write(destination / "packet.json", packet)
    return visibility


def export_product(revision, files, destination):
    if not isinstance(files, dict) or not files:
        raise ValueError("sourceFiles must enumerate file digests at the producer revision")
    for name, checksum in sorted(files.items()):
        path = PurePosixPath(name)
        if (path.is_absolute() or ".." in path.parts or path.parts[:2] != ("examples", "tools")
                or any(p.startswith("test_") or p == "__pycache__" for p in path.parts)):
            raise ValueError("producer source manifest includes an unapproved source path")
        blob = committed_input(revision, name)
        if hashlib.sha256(blob).hexdigest() != checksum:
            raise ValueError("producer source differs from its frozen digest")
        target = destination / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(blob)


def export_checker(checksum, destination):
    name = Path("lib/target/release/jvmcontract")
    if not isinstance(checksum, str) or not re.fullmatch(r"[a-f0-9]{64}", checksum):
        raise PreparationStop("the frozen checker has no SHA-256")
    target = destination / name
    target.parent.mkdir(parents=True, exist_ok=True)
    sources = [CACHE / "blind-caller-pr-verification/checkers" / checksum / "jvmcontract", ROOT / name]
    if os.environ.get("JVMCONTRACT"):
        sources.append(Path(os.environ["JVMCONTRACT"]))
    source = next((p for p in sources if p.is_file() and digest(p) == checksum), None)
    if not source:
        raise PreparationStop("no retained original checker matches the frozen SHA-256")
    shutil.copyfile(source, target)
    if digest(target) != checksum:
        raise PreparationStop("the available native checker differs from the producer freeze")
    target.chmod(0o555)
    return target
