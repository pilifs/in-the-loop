"""Build the blind caller eligibility inventory from identity records, independently of the draw."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import re
import subprocess
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CACHE = Path.home() / ".cache/in-the-loop"
JDKS = Path.home() / ".sdkman/candidates/java"
RESERVED = {539, 551}
BATCHES = {
    "P": (478, 30, "spring-framework-merged-pr-links-p01-p30.md", "spring-pr-links-p01-p30"),
    "Q": (508, 30, "spring-framework-merged-pr-links-q01-q30.md", "spring-pr-links-q01-q30"),
    "R": (538, 50, "organic-java-merged-pr-links-r01-r50.md", "merged-pr-links-r01-r50"),
}
PR = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+)\b", re.I)
COMMIT = re.compile(r"\b[0-9a-f]{40}\b")
REPO_ALIASES = {"junit-team/junit5": "junit-team/junit-framework",
                "vavr-io/javaslang": "vavr-io/vavr", "javaslang/javaslang": "vavr-io/vavr",
                "apache/parquet-mr": "apache/parquet-java"}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=True, indent=2) + "\n")


def relative(path):
    return str(path.relative_to(ROOT))


def repo(value):
    short = re.sub(r"^(?:https?://|git@)?(?:www\.)?github\.com[/:]", "", value.lower())
    short = short.rstrip("/").removesuffix(".git")
    return REPO_ALIASES.get(short, short)


def pr_key(project, number):
    return f"{repo(project)}#{number}"


def git(tree, *args):
    return subprocess.check_output(["git", "-C", str(tree), *args], text=True).strip()


def worktree(cache, slot, side):
    matches = list((cache / "worktrees").glob(f"{slot}-*-{side}"))
    direct = cache / "worktrees" / f"{slot}-{side}"
    if direct.is_dir():
        matches.append(direct)
    if len(matches) != 1:
        raise ValueError(f"expected one pinned worktree for {slot}/{side}")
    return matches[0]


def example(number):
    if int(number) in RESERVED:
        raise ValueError("reserved example materials are unavailable")
    (folder,) = (ROOT / "examples").glob(f"{number}-*")
    return folder


def family(owner):
    package = owner.split("#", 1)[0].rsplit(".", 1)[0]
    return package if "." in package else None


def packages(runtime):
    return sorted({p for dep in runtime["deployments"].values() for owner in dep.get("providers", {})
                   if (p := family(owner))})


def upstream_pr(row):
    cache = CACHE / BATCHES[row["batch"]][3] / "upstream/prs"
    if row["batch"] == "R":
        (path,) = cache.glob(f"{row['slot']}-*.json")
    else:
        path = cache / f"{row['pr']}.json"
    data = read(path)
    if pr_key(data["base"]["repo"]["full_name"], data["number"]) != row["canonicalPR"]:
        raise ValueError("upstream PR metadata identifies a different case")
    return data


def identity_rows():
    rows = []
    for batch, (first, count, filename, area) in BATCHES.items():
        source = ROOT / "llm-dlc/loops" / filename
        urls = PR.findall(source.read_text())
        if len(urls) != count:
            raise ValueError(f"incomplete URL roster for {batch}")
        for index, (project, number) in enumerate(urls):
            n, slot = first + index, f"{batch}{index + 1:02d}"
            trees = {s: worktree(CACHE / area, slot, s) for s in ("parent", "fix")}
            pins = {s: git(tree, "rev-parse", "--verify", "HEAD^{commit}") for s, tree in trees.items()}
            row = {"number": n, "batch": batch, "slot": slot, "repository": repo(project),
                   "pr": int(number), "canonicalPR": pr_key(project, number),
                   "url": f"https://github.com/{project}/pull/{number}", "pins": pins,
                   "source": relative(source), "aliases": [], "landingAliases": [], "apiPackages": []}
            if n not in RESERVED:
                metadata = upstream_pr(row)
                # A merge and the submitted head can identify the same reviewed change. A base
                # SHA alone is never a change identity: many unrelated PRs share one.
                row["landingAliases"] = sorted({metadata["head"]["sha"], metadata["merge_commit_sha"]} - {pins["fix"], None})
                message = git(trees["fix"], "show", "--no-patch", "--format=%B", pins["fix"])
                for match in re.finditer(r"(?i)cherry[- ]picked from commit ([0-9a-f]{40})", message):
                    row["landingAliases"].append(match[1].lower())
                for match in re.finditer(r"(?i)\bbackport of (?:PR\s*)?(?:#(\d+)|https://github\.com/([\w.-]+/[\w.-]+)/pull/(\d+))", message + "\n" + (metadata["body"] or "")):
                    row["aliases"].append(pr_key(match[2] or project, match[3] or match[1]))
                row["landingAliases"] = sorted(set(row["landingAliases"]))
                row["aliases"] = sorted(set(row["aliases"]) - {row["canonicalPR"]})
                row["apiPackages"] = packages(read(example(n) / "runtime.json"))
            rows.append(row)
    return rows


def prior_catalog(rows):
    """No P/Q/R answer archive or reserved example is inspected to assemble this ledger."""
    prior = []

    def add(source, category, project, keys=(), pairs=(), landings=(), api=(), alias=None):
        if project in ("", "pilifs/in-the-loop"):
            return
        prior.append({"source": str(source), "category": category, "repository": repo(project),
                      "prs": sorted(set(keys)), "pairs": sorted(set(tuple(p) for p in pairs)),
                      "landings": sorted(set(landings)), "apiPackages": sorted(set(api)),
                      **({"alias": alias} if alias else {})})

    for path in sorted((ROOT / "examples").glob("[0-9][0-9][0-9]-*")):
        number = int(path.name[:3])
        if number >= BATCHES["P"][0]:
            continue
        comparison, target = path / "comparison.json", path / "target.json"
        if comparison.is_file():
            data = read(comparison)
            match = PR.search(data["source"]) if isinstance(data["source"], str) else None
            if match:
                project, pr = match.groups()
                pins = data["revisions"]
                add(relative(comparison), "previous numbered PR", project, [pr_key(project, pr)],
                    [(pins["parent"], pins["fix"])], [pins["fix"]], packages(read(path / "runtime.json")),
                    f"example {number}")
        elif target.is_file():
            data = read(target)
            history = data.get("history", {})
            project = history.get("repository", "")
            if not isinstance(project, str) or "github.com/" not in project:
                continue
            revisions = history.get("revisions", {})
            pairs = []
            for pair in history.get("pairs", []):
                a = revisions.get(pair["before"], {}).get("commit")
                b = revisions.get(pair["after"], {}).get("commit")
                if a and b and COMMIT.fullmatch(a) and COMMIT.fullmatch(b):
                    pairs.append((a, b))
            urls = PR.findall((path / "example.json").read_text())
            add(relative(target), "previous numbered development", project,
                [pr_key(p, n) for p, n in urls if repo(p) == repo(project)], pairs,
                [b for _, b in pairs], alias=f"example {number}")

    organic = ROOT / "lib/benchmark/organic-java/cases.json"
    for group in ("cases", "reserves", "adoptions"):
        for number, item in read(organic)[group].items():
            if not item.get("pullRequest") or not item.get("parent") or not item.get("fix"):
                continue
            project = item["repository"]
            add(relative(organic), "organic development", project, [pr_key(project, item["pullRequest"])],
                [(item["parent"], item["fix"])], [item["fix"]], alias=f"{group}/{number}")

    jbrief = ROOT / "llm-dlc/loops/organic-java-pr-product-behaviour-20-additional-cases.md"
    jurls = [PR.search(line).groups() for line in jbrief.read_text().splitlines()
             if " · [Compare " in line and PR.search(line)]
    if len(jurls) != 20:
        raise ValueError("incomplete J01–J20 crosswalk")
    for index, (project, pr) in enumerate(jurls, 1):
        alias = f"J{index:02d}"
        path = ROOT / f"verification/product-behaviour/cases/{alias}/case.json"
        item = read(path)
        old, new = (item["commits"][side] for side in ("old", "new"))
        pkg = family(item["entry"])
        add(relative(path), "public behavior development", project, [pr_key(project, pr)],
            [(old, new)], [new], [pkg] if pkg else [], alias)

    exposure = ROOT / "lib/benchmark/organic-composition/exposure.json"
    names = {"phone": "google/libphonenumber#2272", "threeten": "ThreeTen/threetenbp#77",
             "collections-628": "apache/commons-collections#628", "collections-755": "apache/commons-collections#755",
             "log4j": "apache/logging-log4j2#1173", "io": "apache/commons-io#520",
             "gson": "google/gson#3098", "lang": "apache/commons-lang#1839", "poi": "apache/poi#1420",
             "icu": "unicode-org/icu#3249", "url-only": "stleary/JSON-java#552"}
    if set(read(exposure)["projectOverlap"]) != set(names.values()) - {names["url-only"]}:
        raise ValueError("organic composition identities changed")
    for name, key in names.items():
        project, number = key.split("#")
        folder = exposure.parent / name
        old, new = (read(folder / side / "prepared.json")["commit"] for side in ("old", "new"))
        add(relative(folder), "composition development", project, [pr_key(project, number)], [(old, new)], [new], alias=name)

    for path in (ROOT / "lib/benchmark/beyond-jbmc/blind/draw/roster.json",
                 ROOT / "verification/beyond-jbmc/successor/draw/sealed.json.gz"):
        data = json.loads(gzip.decompress(path.read_bytes())) if path.suffix == ".gz" else read(path)
        for index, item in enumerate(data["pairs"], 1):
            add(relative(path), "frozen distribution transfer", item["project"],
                alias=f"{index:02d}/{item['artifact']}/{'..'.join(item['versions'])}")

    numbered = {r["number"]: r for r in rows}
    for name in ("p01-p30", "q01-q30", "r01-r50"):
        for path in sorted((ROOT / f"verification/merged-pr-links/{name}/qualified").glob("*-pins.json.gz")):
            row = numbered[int(path.name.partition("-")[0])]
            add(relative(path), "shared change-plan qualification", row["repository"], [row["canonicalPR"]],
                [(row["pins"]["parent"], row["pins"]["fix"])], [row["pins"]["fix"]], row["apiPackages"])

    # Extend the same underlying identity with its producer-facing uses. Directory and
    # archive entry names suffice for the numbered handoffs; historical callers stay closed.
    shared = ROOT / "verification/generated-observers"
    freeze = read(shared / "freeze.json")
    aliases = {record["alias"].removeprefix("example "): record for record in prior if "alias" in record}
    for row in rows:
        if row["number"] not in RESERVED:
            aliases[str(row["number"])] = {"repository": row["repository"], "prs": [row["canonicalPR"]],
                "pairs": [(row["pins"]["parent"], row["pins"]["fix"])], "landings": [row["pins"]["fix"]],
                "apiPackages": row["apiPackages"]}
    def use(case, category, evidence, api=()):
        record = aliases[case]
        add(relative(evidence), category, record["repository"], record["prs"], record["pairs"],
            record["landings"], api or record["apiPackages"], case)

    for category, cases in (("generator development", freeze["development"]), ("frozen generator transfer", freeze["transfer"])):
        for case in cases:
            if case in ("06", "09"):
                record = next(r for r in prior if r.get("alias", "").startswith(case + "/")
                              and r["source"].startswith("verification/beyond-jbmc/successor"))
                aliases[case] = record
            use(case, category, shared / "freeze.json")
    for path in sorted((shared / "registrations").glob("*.json")):
        case = path.stem.split("-", 1)[0]
        pkg = family(read(path)["entry"])
        use(case, "shared caller recipe", path, [pkg] if pkg else [])
    for path in sorted((shared / "receipts").glob("numbered*.zip")):
        with zipfile.ZipFile(path) as archive:
            ids = {m[1] for name in archive.namelist() if (m := re.search(r"(?:^|/)examples/(\d{3})-", name))}
        for case in ids:
            use(case, "numbered handoff", path)
    use("480", "frozen startup-fact transfer", ROOT / "verification/startup-facts/spring_declaration.py")
    brief = ROOT / "llm-dlc/loops/in-the-loop-blind-caller-and-pr-verification-brief.md"
    for case in ("458", "466", "484", "J08", "J14"):
        use(case, "current disclosed development", brief)
    return sorted(prior, key=lambda r: (r["source"], r["category"], r.get("alias", ""), r["repository"]))


def join(rows, prior):
    for row in rows:
        project = row["repository"]
        sources = [s for s in prior if s["repository"] == project]
        reasons = []
        pins = (row["pins"]["parent"], row["pins"]["fix"])
        siblings = [s for s in rows if s["number"] < row["number"] and s["repository"] == project]
        for earlier in siblings:
            if (earlier["canonicalPR"] == row["canonicalPR"] or earlier["pins"] == row["pins"]
                or set([earlier["canonicalPR"], *earlier["aliases"]]) & set([row["canonicalPR"], *row["aliases"]])
                or set([earlier["pins"]["fix"], *earlier["landingAliases"]]) & set([pins[1], *row["landingAliases"]])):
                reasons.append({"category": "duplicate roster identity", "source": earlier["slot"]})
        for entry in sources:
            how = []
            if set(entry["prs"]) & {row["canonicalPR"], *row["aliases"]}:
                how.append("PR or explicit PR alias")
            if list(pins) in [list(p) for p in entry["pairs"]]:
                how.append("ordered revision pair")
            if set(entry["landings"]) & {pins[1], *row["landingAliases"]}:
                how.append("landing or submitted/cherry-picked commit")
            if how:
                reasons.append({"category": entry["category"], "source": entry["source"], "match": how})
        if row["number"] in RESERVED:
            reasons.append({"category": "reserved by preservation brief", "source": "user decision 2026-11-27"})
        row["exclusions"] = reasons
        row["eligible"] = not reasons
        row["priorProjectSeen"] = bool(sources)
        row["sharedApiPackages"] = sorted(set(row["apiPackages"]) & {pkg for s in sources for pkg in s["apiPackages"]})


def build():
    rows = identity_rows()
    prior = prior_catalog(rows)
    join(rows, prior)
    result = {}
    for batch in BATCHES:
        subset = [r for r in rows if r["batch"] == batch]
        eligible = [r for r in subset if r["eligible"]]
        result[batch] = {"inventory": len(subset), "eligible": len(eligible), "excluded": len(subset) - len(eligible),
                         "eligibleProjects": len({r["repository"] for r in eligible}),
                         "eligibleFamiliarProject": sum(r["priorProjectSeen"] for r in eligible),
                         "eligibleSharedPackage": sum(bool(r["sharedApiPackages"]) for r in eligible),
                         "exclusionReasons": dict(sorted(Counter(k for r in subset for k in {e["category"] for e in r["exclusions"]}).items()))}
    return {"schema": "blind-caller-eligibility/v1", "counts": result,
            "repositoryAliases": REPO_ALIASES, "prior": prior, "rows": rows}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    manifest = build()
    path = HERE / "eligibility.json"
    if args.check:
        if read(path) != json.loads(json.dumps(manifest)):
            raise SystemExit("eligibility manifest changed")
    else:
        write(path, manifest)
    print(json.dumps(manifest["counts"], indent=2))
