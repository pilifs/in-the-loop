"""Draw the blind cohort from signed Java binary and source release indexes. Run behind private_output.py."""
import argparse
from contextlib import closing
import gzip
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import re
import secrets
import struct
import subprocess
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE = "https://archive.ubuntu.com/ubuntu/"
POOL = "https://mirrors.mit.edu/ubuntu/"
SUITES = ("jammy", "noble", "resolute")
KEYRING = "/usr/share/keyrings/ubuntu-archive-keyring.gpg"
STRATA = {
    "wire": r"seriali[sz]|marshall?|codec|compress|file format|binary format|wire format|file reader|file writer|read and write|encod|decod|spreadsheet|\b(pdf|json|yaml|csv|xml|zip|bzip2)\b",
    "history": r"collections?|cach(e|es|ing)\b|data structures?|object pool|connection pool|bitmap|\bgraphs?\b|state machine|event bus|queues?\b|document object model|immutable data|in.memory database|workflow engine",
    "numeric-text": r"numeric|mathemat|arithmetic|numbers|\bmath\b|statistic|parser|parsing|strings?\b|unicode|text process|regular expression|linguistic|tokeniz|date and time",
    "metadata": r"metadata|annotations?|reflecti(on|ve)|introspect|resource bundles?|configur(ation|ing)|dependency injection|classpath|class path|class scanning",
}
UNSUITABLE = re.compile(r"\b(security|cryptograph\w*|vulnerab\w*|exploits?|penetration|malware|authentication|password|security incident)\b", re.I)
MAX_BINARY = 8 * 1024 * 1024


def sha(data):
    return hashlib.sha256(data).hexdigest()


def encode(obj):
    return (json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n").encode()


def save(path, data):
    # The lock serializes writers; atomic replacement preserves the last complete receipt across interruption.
    tmp = path.with_suffix(path.suffix + ".partial")
    tmp.write_bytes(data)
    tmp.replace(path)


def fetch(area, relative, dest, expected=None):
    if dest.exists():
        if expected and sha(dest.read_bytes()) != expected:
            raise ValueError("cached input lost its signed digest")
        return
    base = POOL if relative.startswith("pool/") else BASE
    url = urllib.parse.urljoin(base, relative)
    if not url.startswith(base) or ".." in relative.split("/"):
        raise ValueError("unexpected archive path")
    timer = area / "last-request"
    def wait():
        last = float(timer.read_text()) if timer.exists() else 0
        time.sleep(max(0, 1.1 - (time.time() - last)))
        save(timer, str(time.time()).encode())
    for attempt in range(2):
        wait()
        try:
            with closing(urllib.request.urlopen(url, timeout=35)) as r:
                data = r.read(32 * 1024 * 1024 + 1)
            break
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt:
                raise
            delay = exc.headers.get("Retry-After")
            if delay and not delay.isdigit():
                from email.utils import parsedate_to_datetime
                seconds = max(0, parsedate_to_datetime(delay).timestamp() - time.time())
            else:
                seconds = int(delay or 60)
            time.sleep(seconds)
    if len(data) > 32 * 1024 * 1024 or expected and sha(data) != expected:
        raise ValueError("archive bytes exceed the limit or differ from the signed digest")
    save(dest, data)


def paragraphs(stream):
    block = {}
    key = None
    for line in stream:
        line = line.rstrip("\r\n")
        if not line:
            if block:
                yield block
            block, key = {}, None
        elif line[0].isspace():
            if key:
                block[key] += "\n" + line.strip()
        else:
            key, _, value = line.partition(":")
            block[key] = value.strip()
    if block:
        yield block


def index(area, suite):
    folder = area / suite
    folder.mkdir(exist_ok=True)
    signed = folder / "InRelease"
    local = Path("/var/lib/apt/lists") / f"archive.ubuntu.com_ubuntu_dists_{suite}_InRelease"
    if not signed.exists() and local.is_file():
        save(signed, local.read_bytes())
    fetch(area, f"dists/{suite}/InRelease", signed)
    verified = subprocess.check_output(["gpgv", "--keyring", KEYRING, "--output", "-", signed], stderr=subprocess.DEVNULL)
    release = next(paragraphs(io.StringIO(verified.decode())))
    if release["Suite"] != suite or release["Codename"] != suite:
        raise ValueError("not the base release")
    hashes = {name: h for h, _, name in (line.split() for line in release["SHA256"].splitlines() if line)}
    paths = {}
    for section in ("binary-amd64/Packages", "source/Sources"):
        key = "universe/" + section
        name = key.split("/")[-1]
        apt = local.with_name(f"archive.ubuntu.com_ubuntu_dists_{suite}_universe_" + section.replace("/", "_"))
        if apt.is_file() and sha(apt.read_bytes()) == hashes[key]:
            paths[name] = apt
        else:
            path = folder / (name + ".xz")
            fetch(area, f"dists/{suite}/{key}.xz", path, hashes[key + ".xz"])
            paths[name] = path
    return {"date": release["Date"], "signedSha256": sha(signed.read_bytes()),
            "indexes": {k: {"path": str(v), "sha256": sha(v.read_bytes())} for k, v in paths.items()}}


def records(path):
    with (lzma.open(path, "rt", encoding="utf-8") if path.suffix == ".xz" else path.open(encoding="utf-8")) as stream:
        yield from paragraphs(stream)


def exposure_text():
    paths = set((ROOT / "examples").glob("*/*.json"))
    paths.update((ROOT / "llm-dlc/loops").glob("*.md"))
    paths.add(ROOT / "verification/findings.md")
    for path in (ROOT / "lib/benchmark").rglob("*"):
        if HERE not in path.parents and path.suffix in (".json", ".md", ".py") and path.stat().st_size <= 7_000_000:
            paths.add(path)
    # Contents are public. Include the known source repository and dependency names of prior external panels.
    return "\n".join(p.read_text(errors="replace").lower() for p in sorted(paths))


def upstream(version):
    value = version.split(":")[-1].rsplit("-", 1)[0]
    return re.split(r"(?:[+.~](?:ds|dfsg|repack|orig))", value, flags=re.I)[0]


def adjacent(a, b):
    if not all(re.fullmatch(r"\d+(?:\.\d+)+", v) for v in (a, b)):
        return False
    old, new = ([int(i) for i in v.split(".")] for v in (a, b))
    return len(old) == len(new) and old[:-1] == new[:-1] and old[-1] + 1 == new[-1]


def project(home):
    u = urllib.parse.urlparse(home.lower())
    host = (u.hostname or "").removeprefix("www.")
    parts = [p.removesuffix(".git") for p in u.path.split("/") if p]
    if host in ("github.com", "gitlab.com", "bitbucket.org", "salsa.debian.org"):
        return "/".join([host, *parts[:2]]) if len(parts) >= 2 else None
    if not host:
        return None
    if host in ("code.google.com", "sourceforge.net"):
        return "/".join([host, *parts[:2]]) if len(parts) >= 2 else None
    return host


def pool(area):
    text = exposure_text()
    inventory = {s: index(area, s) for s in SUITES}
    populations = {}
    for suite, release in inventory.items():
        indexes = release["indexes"]
        binaries = {}
        for r in records(Path(indexes["Packages"]["path"])):
            name = r["Package"]
            if not (name.startswith("lib") and name.endswith("-java") and r["Architecture"] == "all"):
                continue
            if int(r["Size"]) > MAX_BINARY or r.get("Section", "").split("/")[-1] not in ("java", "libs"):
                continue
            source = r.get("Source", name).split()[0]
            source_version = r.get("Source", "").partition("(")[2].rstrip(")") or r["Version"]
            fields = {k: r[k] for k in ("Version", "Filename", "SHA256", "Description", "Homepage") if k in r}
            binaries[name] = {**fields, "source": source, "sourceVersion": source_version}
        wanted = {(b["source"], b["sourceVersion"]) for b in binaries.values()}
        sources = {}
        for r in records(Path(indexes["Sources"]["path"])):
            key = r["Package"], r["Version"]
            if key not in wanted:
                continue
            files = [l.split() for l in r["Checksums-Sha256"].splitlines() if l]
            if any(".orig" in name for _, _, name in files):
                sources[key] = {"directory": r["Directory"], "files": files}
        populations[suite] = {name: dict(b, sourceEntry=sources[b["source"], b["sourceVersion"]])
                              for name, b in binaries.items() if (b["source"], b["sourceVersion"]) in sources}
    eligible, excluded = [], []
    for first, second in zip(SUITES, SUITES[1:]):
        old, new = populations[first], populations[second]
        for name in sorted(old.keys() & new.keys()):
            a, b = old[name], new[name]
            av, bv = upstream(a["Version"]), upstream(b["Version"])
            if a["source"] != b["source"] or av == bv:
                continue
            key = [name, av, bv]
            site = project(b.get("Homepage", ""))
            identity = {name[3:-5], b["source"].removeprefix("lib").removesuffix("-java")}
            category = next((k for k, p in STRATA.items() if re.search(p, b["Description"], re.I)), None)
            reason = None
            if not category or not site or not re.fullmatch(r"\d+(?:\.\d+)+", av) or not re.fullmatch(r"\d+(?:\.\d+)+", bv):
                reason = "missing stratum, project or numeric release"
            elif UNSUITABLE.search(name + " " + b["Description"]):
                reason = "outside ordinary functional scope"
            elif site in text or any(len(s) < 3 or (s in text and re.search(r"(?<![a-z0-9])" + re.escape(s) + r"(?![a-z0-9])", text)) for s in identity):
                reason = "prior project exposure or ambiguous identity"
            if reason:
                excluded.append([key, reason])
                continue
            eligible.append({"artifact": name, "versions": [av, bv], "project": site, "source": b["source"],
                             "stratum": category, "adjacentNumeric": adjacent(av, bv), "suites": [first, second],
                             "before": a, "after": b})
    ordered = sorted(eligible, key=lambda r: (r["artifact"], r["versions"], r["suites"]))
    save(area / "population.json", encode({"releases": inventory, "eligible": ordered, "excluded": excluded}))


def public_api(data):
    """A shared named public method with Code on a public class, excluding constructors, bridges and synthetics."""
    buf = io.BytesIO(data)
    def u1():
        return struct.unpack(">B", buf.read(1))[0]
    def u2():
        return struct.unpack(">H", buf.read(2))[0]
    def u4():
        return struct.unpack(">I", buf.read(4))[0]
    if u4() != 0xcafebabe:
        raise ValueError("invalid Java class")
    u2()
    if u2() > 65:  # Temurin 21
        return set()
    size = u2()
    strings = {}
    widths = {3: 4, 4: 4, 5: 8, 6: 8, 7: 2, 8: 2, 9: 4, 10: 4, 11: 4, 12: 4,
              15: 3, 16: 2, 17: 4, 18: 4, 19: 2, 20: 2}
    i = 1
    while i < size:
        tag = u1()
        if tag == 1:
            strings[i] = buf.read(u2()).decode("utf-8", "replace")
        else:
            buf.seek(widths[tag], 1)
        i += 2 if tag in (5, 6) else 1
    if not u2() & 1:
        return set()
    u2()
    u2()
    buf.seek(2 * u2(), 1)
    methods = set()
    for members in ("fields", "methods"):
        for _ in range(u2()):
            flags, name, descriptor = u2(), strings[u2()], strings[u2()]
            has_code = False
            for _ in range(u2()):
                attribute, length = strings[u2()], u4()
                has_code |= attribute == "Code"
                buf.seek(length, 1)
            if members == "methods" and has_code and flags & 1 and not flags & 0x1040 and not name.startswith("<"):
                methods.add(name + descriptor)
    return methods


def inspect_deb(path):
    jars, changelogs = {}, []
    proc = subprocess.Popen(["dpkg-deb", "--fsys-tarfile", path], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for m in tar:
                if not m.isfile() or m.size > 24 * 1024 * 1024:
                    continue
                name = m.name.removeprefix("./")
                if name.startswith(("usr/share/java/", "usr/share/maven-repo/")) and name.endswith(".jar"):
                    jar = tar.extractfile(m).read()
                    api = set()
                    with zipfile.ZipFile(io.BytesIO(jar)) as z:
                        for member in z.infolist():
                            if (member.filename.endswith(".class") and not member.filename.startswith("META-INF/")
                                    and member.file_size < 2 * 1024 * 1024):
                                owner = member.filename[:-6]
                                api.update(owner + "#" + f for f in public_api(z.read(member)))
                    jars[name] = (sha(jar), api)
                elif (name.startswith("usr/share/doc/") and re.fullmatch(r"(ChangeLog|changes|news)(\.txt|\.md|\.html)?(\.gz)?",
                                                                         name.split("/")[-1], re.I)):
                    content = tar.extractfile(m).read()
                    if name.endswith(".gz"):
                        with gzip.GzipFile(fileobj=io.BytesIO(content)) as gz:
                            content = gz.read(2 * 1024 * 1024)
                    changelogs.append((name, content.decode("utf-8", "replace")))
    finally:
        proc.stdout.close()
        if proc.wait():
            raise ValueError("package extraction failed")
    return jars, changelogs


def change_entries(notes, row):
    # Require an upstream change entry within the new release's own version block.
    documented = []
    old_version, new_version = row["versions"]
    version = re.compile(r"(?<![\w.])v?(\d+(?:\.\d+)+)(?![\w.])", re.I)
    for name, log in notes:
        lines = log.splitlines()
        for i, line in enumerate(lines):
            if new_version not in version.findall(line) or len(line) > 145:
                continue
            block = []
            for next_line in lines[i + 1:i + 36]:
                if old_version in version.findall(next_line) or re.match(r"^#{1,3}\s+.*\d+\.\d+", next_line):
                    break
                block.append(next_line)
            hits = [s.strip() for s in block if re.search(r"\b(fix(?:ed|es)?|return(?:s|ed)?|preserv\w*|accept\w*|reject\w*|support\w*)\b", s, re.I)
                    and not re.search(r"\b(build|ci|test|document\w*|typo|dependency|dependencies)\b", s, re.I)]
            if hits and not UNSUITABLE.search(" ".join(hits)):
                documented.append({"file": name, "versionHeading": line, "entry": hits[0]})
                break
    return documented


def source_notes(area, row):
    entry = row["after"]["sourceEntry"]
    notes = []
    for digest, size, filename in entry["files"]:
        if not re.search(r"\.orig\.tar\.(gz|xz|bz2)$", filename) or int(size) > 12 * 1024 * 1024:
            continue
        path = area / (digest + ".orig")
        fetch(area, entry["directory"] + "/" + filename, path, digest)
        with tarfile.open(path, "r|*") as tar:
            for m in tar:
                title = m.name.split("/")[-1]
                if (m.isfile() and m.size <= 2 * 1024 * 1024 and
                        re.fullmatch(r"(changes|changelog|news|history|releases?|release[-_ ]notes)(\.\w+)?", title, re.I)):
                    notes.append((m.name, tar.extractfile(m).read().decode("utf-8", "replace")))
    return change_entries(notes, row)


def validate(area, row):
    sides, notes = [], []
    for side in ("before", "after"):
        rec = row[side]
        path = area / (rec["SHA256"] + ".deb")
        fetch(area, rec["Filename"], path, rec["SHA256"])
        jars, notes = inspect_deb(path)
        sides.append(jars)
    pairs = [(pa, pb, a[0], b[0], a[1] & b[1]) for pa, a in sides[0].items() for pb, b in sides[1].items()
             if a[0] != b[0] and a[1] & b[1]]
    if not pairs:
        return None
    pa, pb, da, db, api = min(pairs, key=lambda p: (-len(p[4]), p[0], p[1]))
    return {"oldJar": pa, "newJar": pb, "oldSha256": da, "newSha256": db, "commonPublicMethods": len(api),
            "methodInventorySha256": sha(encode(sorted(api))), "eligibilityExample": min(api), "changeNotes": change_entries(notes, row)}


def draw(area, limit):
    population = json.loads((area / "population.json").read_bytes())
    seedfile = area / "seed"
    if not seedfile.exists():
        with seedfile.open("xb") as f:
            f.write(secrets.token_bytes(32))
    seed = seedfile.read_bytes()
    if len(seed) != 32:
        raise ValueError("incomplete seed")
    def rank(*parts):
        return hashlib.sha256(seed + encode(parts)).hexdigest()
    journal = area / "screening.json"
    screened = json.loads(journal.read_bytes()) if journal.exists() else {}
    chosen, used_projects, used_sources = [], set(), set()
    strata = sorted(STRATA, key=lambda s: len({r["project"] for r in population["eligible"] if r["stratum"] == s}))
    remaining = limit
    for slot in range(4):
        for stratum in strata:
            candidates = [r for r in population["eligible"] if r["stratum"] == stratum and
                          r["project"] not in used_projects and r["source"] not in used_sources]
            candidates.sort(key=lambda r: (slot == 0 and not r["adjacentNumeric"],
                                            rank("project", r["project"]), rank("pair", r["artifact"], r["versions"])))
            for r in candidates:
                key = rank("record", r["artifact"], r["versions"], r["suites"])
                if key not in screened:
                    if remaining == 0:
                        return None
                    remaining -= 1
                    try:
                        screened[key] = validate(area, r)
                    except urllib.error.HTTPError as exc:
                        if exc.code not in (404, 410):
                            raise
                        screened[key] = {"excluded": "published binary unavailable", "status": exc.code}
                    save(journal, encode(screened))
                evidence = screened[key]
                if not evidence or evidence.get("excluded"):
                    continue
                if not any(c["eligibility"]["changeNotes"] for c in chosen) and not evidence["changeNotes"] and not evidence.get("sourceNotesChecked"):
                    evidence["changeNotes"] = source_notes(area, r)
                    evidence["sourceNotesChecked"] = True
                    save(journal, encode(screened))
                if len(chosen) == 15 and not any(c["eligibility"]["changeNotes"] for c in chosen) and not evidence["changeNotes"]:
                    continue
                chosen.append(dict(r, eligibility=evidence))
                used_projects.add(r["project"])
                used_sources.add(r["source"])
                break
            else:
                raise ValueError("insufficient eligible projects for " + stratum)
    if len(chosen) != 16 or len(used_projects) != 16 or not any(c["adjacentNumeric"] for c in chosen):
        raise ValueError("incomplete draw")
    manifest = {"schema": "beyond-jbmc-blind-16/v1", "seed": seed.hex(), "populationSha256": sha((area / "population.json").read_bytes()),
                "screeningSha256": sha(journal.read_bytes()), "selectionProgramSha256": sha(Path(__file__).read_bytes()),
                "pairs": chosen}
    target = area / "sealed.json"
    data = encode(manifest)
    if target.exists() and target.read_bytes() != data:
        raise ValueError("the frozen manifest would change")
    if not target.exists():
        with target.open("xb") as f:
            f.write(data)
    return sha(data)


def main():
    import fcntl
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("action", choices=("population", "draw"))
    ap.add_argument("private_directory", type=Path)
    ap.add_argument("--limit", type=int, default=4, help="maximum new eligibility inspections this invocation")
    args = ap.parse_args()
    p = args.private_directory.resolve()
    if any((a / "llm-dlc/tools/sync.py").is_file() for a in (p, *p.parents)):
        raise ValueError("the cohort belongs outside the checkout")
    os.umask(0o077)
    p.mkdir(exist_ok=True, mode=0o700)
    if p.stat().st_mode & 0o077 or p.stat().st_uid != os.getuid():
        raise ValueError("private directory must be owner-only")
    with (p / "lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if args.action == "population":
            if not (p / "population.json").exists():
                pool(p)
            data = json.loads((p / "population.json").read_bytes())
            counts = [len({r["project"] for r in data["eligible"] if r["stratum"] == k}) for k in STRATA]
            digest = None
        else:
            digest = draw(p, args.limit)
            counts = []
    print(json.dumps({"schema": "external-upgrade-private-progress/v1", "status": "ok" if digest or counts else "partial",
                      "counts": counts, "flags": [], "digests": [digest] if digest else []}))


if __name__ == "__main__":
    main()
