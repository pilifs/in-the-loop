"""Resolve the five public URLs using only cached GitHub, upstream Git and original build outputs."""
import argparse
import os
from pathlib import Path
import re
import shutil
import tempfile
import zipfile

from eligibility_inventory import CACHE, HERE, JDKS, PR, ROOT, digest, git, pr_key, read, worktree, write
from packet_view import HAZARD, PreparationStop, scan_jar, source_material, upstream_test_classes


AREA = CACHE / "merged-pr-links-n01-n05"
URLS = ROOT / "llm-dlc/loops/organic-java-merged-pr-links-n01-n05.md"
SQL_IMAGE = "mysql@sha256:0255b469f0135a0236d672d60e3154ae2f4538b146744966d96440318cc822c6"
JD_REPLAY = {"1.8": "8.0.512.0+9-tem", "17": "17.0.21.0+9-tem", "25": "17.0.21.0+9-tem"}


def urls():
    return [f"https://github.com/{project}/pull/{number}" for project, number in PR.findall(URLS.read_text())]


def resolve(url):
    match = PR.fullmatch(url)
    if not match:
        raise PreparationStop("expected a canonical GitHub pull request URL")
    (metadata_path,) = (AREA / "upstream/prs").glob(f"*-{match[1].replace('/', '_')}-{match[2]}.json")
    data = read(metadata_path)
    if not data.get("merged_at") or pr_key(data["base"]["repo"]["full_name"], data["number"]) != pr_key(*match.groups()):
        raise PreparationStop("public metadata does not establish a merged PR at the requested repository")
    if HAZARD.search(data["title"] + "\n" + (data["body"] or "")):
        raise PreparationStop("scoped abstention for a possible real security vulnerability")
    slot = metadata_path.name.split("-", 1)[0]
    fix = data["merge_commit_sha"]
    tree = worktree(AREA, slot, "fix")
    header = git(tree, "cat-file", "-p", fix).split("\n\n", 1)[0]
    parents = [ln[7:] for ln in header.splitlines() if ln.startswith("parent ")]
    if not parents or git(tree, "rev-parse", "--verify", "HEAD") != fix:
        raise PreparationStop("cached production landing differs from the public merged commit")
    if git(worktree(AREA, slot, "parent"), "rev-parse", "--verify", "HEAD") != parents[0]:
        raise PreparationStop("cached production parent differs from the merged commit's first parent")
    return slot, tree, data, {"parent": parents[0], "fix": fix}


def original_build(slot, role):
    folder = AREA / "artifacts" / f"{slot}-{role}"
    (subject,) = folder.glob("*.jar")
    with zipfile.ZipFile(subject) as archive:
        manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8", "replace")
    build = re.search(r"(?im)^Build-Jdk(?:-Spec)?: (1\.8|\d+)\b", manifest)
    if not build or build[1] not in JD_REPLAY:
        raise PreparationStop("original build has no supported JDK provenance")
    recorded = [line.split(maxsplit=1)[0] for line in (folder / "SHA256SUMS").read_text().splitlines()
                if line.split() and Path(line.split()[-1]).name == subject.name]
    if set(recorded) != {digest(subject)}:
        raise PreparationStop("cached subject jar differs from the original upstream build record")
    cp = next((p for p in (folder / "runtime-classpath.txt", folder / "runtimeClasspath.txt") if p.is_file()), None)
    if cp is None:
        raise PreparationStop("upstream build has no original runtime classpath")
    deps = [Path(name) for name in cp.read_text().strip().split(os.pathsep) if name]
    service = None
    if cp.name == "runtimeClasspath.txt" and subject.name.startswith("spring-jdbc-"):
        # The benchmark specifies the original MySQL 9.1.0 deployment in addition
        # to spring-jdbc's own Gradle runtime graph. No case-specific caller is used.
        deps.append(AREA / "releases/mysql-connector-j-9.1.0/mysql-connector-j-9.1.0.jar")
        service = {"kind": "mysql", "image": SQL_IMAGE, "driver": "com.mysql:mysql-connector-j:9.1.0",
                   "state": "requires a newly provisioned isolated service and independent connection"}
    if not all(p.resolve().is_relative_to(AREA.resolve()) and p.is_file() for p in deps):
        raise PreparationStop("a runtime-classpath export references unavailable production bytes")
    return [subject, *deps], JDKS / JD_REPLAY[build[1]], service, {
        "buildJdkSpec": build[1], "upstreamSubjectSha256": digest(subject),
        "buildDigestRecordSha256": digest(folder / "SHA256SUMS"), "upstreamClasspathExportSha256": digest(cp)}


def export(url, destination):
    slot, tree, metadata, pins = resolve(url)
    target = Path(destination)
    target.mkdir()
    fields, visibility = source_material({"pins": pins}, target, metadata, "cold", tree=tree, public_docs=False)
    test_classes = upstream_test_classes(tree, pins)
    exported = {}
    variants = {"name": "pins"}
    provenance = {"url": url, "landingFromMergedPublicMetadata": True, "parentFromOriginalCommitHeader": True,
                  "pins": pins, "newBuilds": 0, "stage": "original intact build cache", "sides": {}, "view": visibility}
    jdk, service = None, None
    for key, role in (("old", "parent"), ("new", "fix")):
        jars, jdk_home, required, source = original_build(slot, role)
        if jdk is not None and (jdk != jdk_home or required != service):
            raise PreparationStop("original deployment policies differ by side")
        jdk, service = jdk_home, required
        cp = []
        for jar in jars:
            checksum = digest(jar)
            if checksum not in exported:
                scan_jar(jar, test_classes)
                rel = f"artifacts/{len(exported):03d}-{checksum[:16]}.jar"
                dest = target / rel
                dest.parent.mkdir(exist_ok=True)
                shutil.copyfile(jar, dest)
                if digest(dest) != checksum:
                    raise PreparationStop("original public build changed during export")
                exported[checksum] = rel
            cp.append({"file": exported[checksum], "sha256": checksum})
        variants[key] = {"revision": pins[role], "classpath": cp}
        provenance["sides"][key] = {**source, "orderedClasspathSha256": [j["sha256"] for j in cp]}
    packet = {"schema": "blind-caller-packet/v1", "arm": "cold", "url": url, "oldRevision": pins["parent"],
              "newRevision": pins["fix"], "old": variants["old"], "new": variants["new"], "deployments": [variants],
              "jdk": str(jdk), "jdkReleaseSha256": digest(jdk / "release"), **fields}
    if service:
        packet["service"] = service
    write(target / "packet.json", packet)
    return {**provenance, "jdkReleaseSha256": packet["jdkReleaseSha256"], "service": service,
            "publicDescription": packet["description"], "packetSha256": digest(target / "packet.json")}


def export_batch(destination, receipt):
    if destination.exists():
        raise ValueError("URL-only intake needs a fresh packet directory")
    with tempfile.TemporaryDirectory(prefix="public-url-export-") as temporary:
        stage = Path(temporary) / "packets"
        stage.mkdir()
        cases = [export(url, stage / f"{index:02d}") for index, url in enumerate(urls(), 1)]
        stage.rename(destination)
    write(receipt, {"schema": "url-only-upstream-intake/v1", "inputListSha256": digest(URLS), "input": "public URLs only",
                    "rebuilds": 0, "originalBuildCacheHits": sum(len(case["sides"]) for case in cases),
                    "sources": ["cached merged GitHub PR metadata", "original Git commit headers and production source",
                                "Maven or Gradle production runtime classpath and SHA-256 build records",
                                "original JDBC deployment specified by the brief"], "cases": cases})
    print(f"{len(cases)} URLs resolved; both original build graphs exported for every URL")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="one public PR URL, or all for the committed five-link file")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    if args.url == "all":
        export_batch(args.packet, args.receipt)
    else:
        write(args.receipt, export(args.url, args.packet))
        print("one URL resolved and both original build graphs identified")
