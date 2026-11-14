"""Hash-pinned acquisition of published artifacts (llm-dlc/loops/example-targets.md, runtime's R2, and the brief's
downloads policy): Maven Central and github.com only, every file by the sha256 its lock records, checked when it is
fetched and again whenever a cached copy is reused. A mutable reference (a range, `+`, LATEST, RELEASE, a SNAPSHOT) and
a missing hash are preparation blockers, never resolved here. The URL says where bytes came from; the sha256 is what
they are. Runtime stream's.

Standard library only and importing nothing of its own, so that its command runs as `python3 -I`, as downloaded data
requires:

    python3 -I examples/tools/targets/runtime_maven.py pin GROUP:ARTIFACT:VERSION

fetches that JAR from Maven Central into a new empty directory, checks it against Central's own .sha1, stores it in
the cache and prints the sidecar entry (`coordinates`, `url`, `sha256`) that records its hash the first time.

    coordinates(text)            (group, artifact, version), or Blocked for a dynamic or malformed version
    central_url(coordinates)     the JAR's URL on Maven Central
    source_url(url, coordinates) the URL to fetch: the recorded one, checked, or Central's
    Cache(root)                  content-addressed by sha256; every restore rechecks the bytes
    acquire(item, dest, ...)     one {coordinates, url, sha256} item's bytes at dest: from the cache or fetched, checked
"""

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CENTRAL = "https://repo.maven.apache.org/maven2/"
HOSTS = ("repo.maven.apache.org", "github.com")
# github.com serves release assets by redirecting to its own content hosts; nothing else is followed.
REDIRECT_HOSTS = HOSTS + ("objects.githubusercontent.com", "release-assets.githubusercontent.com")
CACHE = Path(os.environ.get("TARGETS_CACHE", Path.home() / ".cache/in-the-loop/targets"))
FETCH_TIMEOUT = 60
MAX_BYTES = 256 * 1024 * 1024
USER_AGENT = "in-the-loop-targets/1"  # generic: no user or project details leave the machine

COORDINATES = re.compile(r"^([A-Za-z0-9_.-]+):([A-Za-z0-9_.-]+):([0-9][A-Za-z0-9_.-]*)$")
# Maven's mutable versions: ranges, Gradle's `+`, the LATEST and RELEASE metaversions, and snapshots.
DYNAMIC = re.compile(r"[\[\](),+]|SNAPSHOT|^LATEST$|^RELEASE$", re.I)
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class Blocked(Exception):
    """Acquisition or its lock stops: `stage` (lock or acquire), the diagnostic, and for the handoff the command that
    was run (or would be), the semantics it needs and the next action."""

    def __init__(self, stage, diagnostic, command=None, needs=None, next=None):
        super().__init__(diagnostic)
        self.stage, self.diagnostic, self.command, self.needs, self.next = stage, diagnostic, command, needs, next


def pin_command(coords):
    return f"python3 -I examples/tools/targets/runtime_maven.py pin {coords}"


def coordinates(text):
    """(group, artifact, version) of `group:artifact:version`, refusing a version that can change under the same
    name."""
    match = COORDINATES.match(text or "") if isinstance(text, str) else None
    if not match:
        raise Blocked("lock", f"{text!r} is not group:artifact:version", needs="fixed Maven coordinates",
                      next="record the artifact's exact group:artifact:version in target.json")
    group, artifact, version = match.groups()
    if DYNAMIC.search(version):
        raise Blocked("lock", f"{text}: version {version} is a dynamic or mutable version, which names no fixed bytes",
                      needs="a released, fixed version", next="pin a released version and record its sha256: "
                      + pin_command(f"{group}:{artifact}:<version>"))
    return group, artifact, version


def central_url(coords, extension="jar"):
    group, artifact, version = coordinates(coords)
    return f"{CENTRAL}{group.replace('.', '/')}/{artifact}/{version}/{artifact}-{version}.{extension}"


def allowed(url, hosts=HOSTS):
    parts = urllib.parse.urlsplit(url)
    return parts.scheme == "https" and parts.hostname in hosts and not parts.username and not parts.port


def source_url(url, coords):
    """Where `coords` is fetched from: `url` if the lock records one (on Maven Central, it must be that coordinates'
    own file), else Central's. Any host but Maven Central and github.com is refused."""
    expected = central_url(coords)
    if url is None:
        return expected
    if not isinstance(url, str) or not allowed(url):
        raise Blocked("lock", f"{coords}: {url!r} is not an https URL on Maven Central or github.com",
                      needs="an artifact from Maven Central or github.com", next="record Maven Central's URL, or none")
    if urllib.parse.urlsplit(url).hostname == "repo.maven.apache.org" and url != expected:
        raise Blocked("lock", f"{coords}: {url} is not that artifact's file on Maven Central ({expected})",
                      needs="the URL to name the same artifact as the coordinates", next=f"record {expected}")
    return url


def check_item(item, role):
    """One lock item, {coordinates, url, sha256}, checked offline: fixed coordinates, an allowed URL, a recorded
    sha256. The checked item, with its URL resolved."""
    if not isinstance(item, dict):
        raise Blocked("lock", f"a {role} is not a {{coordinates, url, sha256}} entry: {item!r}")
    coords = item.get("coordinates")
    coordinates(coords)
    url = source_url(item.get("url"), coords)
    digest = item.get("sha256")
    if not isinstance(digest, str) or not SHA256.match(digest):
        raise Blocked("lock", f"{coords} has no recorded sha256" if digest is None
                      else f"{coords}: {digest!r} is not a sha256", command=pin_command(coords),
                      needs="every published file's sha256, recorded the first time it is fetched",
                      next=f"record its sha256 in target.json: run {pin_command(coords)} (it fetches the JAR, checks "
                           f"Maven Central's .sha1 and prints the entry)")
    return {"coordinates": coords, "url": url, "sha256": digest, "role": role}


def sha256_of(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


class Cache:
    """Files by content, under root/sha256/<first two hex>/<sha256>. Reuse is preparation reuse, never proof evidence:
    a restore rechecks the bytes, and an entry that fails is moved aside (root/corrupt/) and reported, never used."""

    def __init__(self, root=None):
        self.root = Path(root or CACHE)

    def path(self, digest):
        return self.root / "sha256" / digest[:2] / digest

    def restore(self, digest, dest):
        """(True, note) with the bytes copied to `dest` if the cache holds `digest`'s and they still hash to it;
        (False, note) otherwise."""
        path = self.path(digest)
        if not path.is_file():
            return False, "not cached"
        found = sha256_of(path)
        if found != digest:
            aside = self.root / "corrupt" / f"{digest}-{time.strftime('%Y%m%dT%H%M%S')}-{found[:12]}"
            aside.parent.mkdir(parents=True, exist_ok=True)
            os.replace(path, aside)
            return False, f"the cached copy hashed to {found}, not {digest}: moved aside to {aside}, not used"
        shutil.copyfile(path, dest)
        if sha256_of(dest) != digest:  # the copy, too, is checked
            Path(dest).unlink()
            return False, f"the copy from the cache did not hash to {digest}"
        return True, f"cache hit {path}, rechecked"

    def store(self, source, digest):
        path = self.path(digest)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f".{digest}.{os.getpid()}.tmp")
        shutil.copyfile(source, tmp)
        if sha256_of(tmp) != digest:
            tmp.unlink()
            raise Blocked("acquire", f"the copy into the cache did not hash to {digest}")
        os.replace(tmp, path)
        return path


class _Redirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed(newurl, REDIRECT_HOSTS):
            raise urllib.error.URLError(f"redirected to {newurl}, outside Maven Central and github.com")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url, dest):
    """`url`'s bytes into `dest` (a file in a new empty directory), over https from an allowed host only, at most
    MAX_BYTES."""
    if not allowed(url):
        raise Blocked("acquire", f"{url} is not on Maven Central or github.com")
    opener = urllib.request.build_opener(_Redirects)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with opener.open(request, timeout=FETCH_TIMEOUT) as response, open(dest, "wb") as out:
            total = 0
            for block in iter(lambda: response.read(1 << 20), b""):
                total += len(block)
                if total > MAX_BYTES:
                    raise Blocked("acquire", f"{url} is larger than {MAX_BYTES} bytes")
                out.write(block)
    except (urllib.error.URLError, OSError) as e:
        raise Blocked("acquire", f"GET {url} failed: {e}", command=f"GET {url}",
                      needs="the recorded bytes from Maven Central or github.com",
                      next="retry once the network is back (an infrastructure failure, not a finding)") from None


FETCH = fetch  # tests replace it with a local repository


def acquire(item, dest, cache=None, network=True, fetcher=None):
    """The bytes of one checked lock item at `dest`: restored from the cache if it holds them (rechecked), else
    fetched into a new empty directory, checked against the recorded sha256 and only then cached. A mismatch is a
    preparation failure: the wrong bytes are neither cached nor used, and nothing is rebuilt in their place. Returns
    the log lines."""
    cache = cache or Cache()
    digest, url = item["sha256"], item["url"]
    hit, note = cache.restore(digest, dest)
    log = [f"{item['coordinates']} sha256 {digest}: {note}"]
    if hit:
        return log
    if not network:
        raise Blocked("acquire", f"{item['coordinates']} is not in the cache and the task's plan allows no "
                      f"acquisition (network: false)", command=f"GET {url}", needs="the recorded bytes",
                      next="plan the task with acquisition (TaskPlan.network), or pin it into the cache: "
                           + pin_command(item["coordinates"]))
    scratch = Path(tempfile.mkdtemp(prefix="fetch-", dir=_scratch(cache)))
    try:
        fetched = scratch / Path(urllib.parse.urlsplit(url).path).name
        (fetcher or FETCH)(url, fetched)
        found = sha256_of(fetched)
        log.append(f"GET {url}: {fetched.stat().st_size} bytes, sha256 {found}")
        if found != digest:
            raise Blocked("acquire", f"{url} has sha256 {found}, not the recorded {digest}: refused, not cached and "
                          f"not rebuilt", command=f"GET {url}", needs="the bytes the lock records",
                          next="find out which bytes are right before changing anything; a lock is never updated to "
                               "whatever was fetched")
        cache.store(fetched, digest)
        shutil.copyfile(fetched, dest)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if sha256_of(dest) != digest:
        raise Blocked("acquire", f"the copy of {url} at {dest} did not hash to {digest}")
    return log


def _scratch(cache):
    path = cache.root / "tmp"
    path.mkdir(parents=True, exist_ok=True)
    return path


def pin_file(url, cache=None, fetcher=None):
    """The first fetch of a file on Maven Central: (sha256, sha1), after checking the bytes against Central's own
    .sha1. The bytes go into the cache; nothing is written anywhere else."""
    cache = cache or Cache()
    if urllib.parse.urlsplit(url).hostname != "repo.maven.apache.org" or not allowed(url):
        raise Blocked("acquire", f"{url} is not on Maven Central, whose .sha1 files this checks against")
    scratch = Path(tempfile.mkdtemp(prefix="pin-", dir=_scratch(cache)))
    try:
        data, sha1 = scratch / "artifact", scratch / "artifact.sha1"
        (fetcher or FETCH)(url, data)
        (fetcher or FETCH)(url + ".sha1", sha1)
        published = sha1.read_text(errors="replace").split()[0].lower() if sha1.stat().st_size else ""
        actual = hashlib.sha1(data.read_bytes()).hexdigest()
        if published != actual:
            raise Blocked("acquire", f"{url} has sha1 {actual}, but Maven Central's .sha1 says {published!r}")
        digest = sha256_of(data)
        cache.store(data, digest)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return digest, actual


def pin(coords, cache=None, fetcher=None):
    """The first fetch of a published JAR, from Maven Central: its sha256 and Central's .sha1, which must agree with
    the bytes. Returns the sidecar entry. Its bytes go into the cache; nothing is written anywhere else."""
    url = central_url(coords)
    digest, actual = pin_file(url, cache, fetcher)
    return {"coordinates": coords, "url": url, "sha256": digest,
            "checked": f"sha1 {actual} matches Maven Central's .sha1, {time.strftime('%Y-%m-%d')}"}


def main(argv):
    if len(argv) != 2 or argv[0] != "pin":
        print("usage: python3 -I examples/tools/targets/runtime_maven.py pin GROUP:ARTIFACT:VERSION", file=sys.stderr)
        return 2
    try:
        print(json.dumps(pin(argv[1]), indent=2))
    except Blocked as e:
        print(f"runtime_maven: {e.stage}: {e.diagnostic}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
