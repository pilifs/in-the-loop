"""The JDKs a preparation or a control runs on, each by its full path and identified by its `release` file and
`java -version` (llm-dlc/loops/example-targets.md, the JDK rule): a different JDK is a different identity. Runtime
stream's (R1, R4). Nothing here changes sdkman's default; a JDK is chosen by its home, never through `current`.

    homes()               {feature: home} of the installed JDKs under ~/.sdkman/candidates/java/, Temurin preferred
    home(feature)         one feature's home, or None
    identity(home)        {feature, version, home, release}: what a record names the JDK by
    build_home()          the JDK the fixture route builds with: build_fixtures.py's (JAVA_HOME, else javac on PATH)
"""

import functools
import os
import shutil
import subprocess
from pathlib import Path

CANDIDATES = Path(os.environ.get("TARGETS_JDK_CANDIDATES", Path.home() / ".sdkman/candidates/java"))
# The release-file keys a record keeps: enough to tell two builds of one feature apart.
RELEASE_KEYS = ("JAVA_VERSION", "JAVA_RUNTIME_VERSION", "IMPLEMENTOR", "IMPLEMENTOR_VERSION", "OS_ARCH")


def release(home):
    """The JDK's `release` file as a dict, or {} when it has none."""
    path = Path(home) / "release"
    if not path.is_file():
        return {}
    out = {}
    for line in path.read_text(errors="replace").splitlines():
        key, sep, value = line.partition("=")
        if sep:
            out[key.strip()] = value.strip().strip('"')
    return out


def feature(version):
    """The feature release of a JAVA_VERSION: 1.8.0_512 -> 8, 21.0.13 -> 21."""
    parts = version.split(".")
    return parts[1] if parts[0] == "1" and len(parts) > 1 else parts[0]


@functools.lru_cache(maxsize=None)
def homes():
    """{feature: home} for each JDK installed under CANDIDATES (not the `current` link), a Temurin build preferred
    over another vendor's of the same feature, then the highest version."""
    found = {}
    if not CANDIDATES.is_dir():
        return {}
    for entry in sorted(CANDIDATES.iterdir()):
        if entry.name == "current" or entry.is_symlink() or not (entry / "bin/java").is_file():
            continue
        info = release(entry)
        if not info.get("JAVA_VERSION"):
            continue
        key = (entry.name.endswith("-tem"), tuple(int(p) for p in _digits(info["JAVA_VERSION"])))
        f = feature(info["JAVA_VERSION"])
        if f not in found or key > found[f][0]:
            found[f] = (key, entry.resolve())
    return {f: str(home) for f, (_, home) in sorted(found.items())}


def _digits(version):
    out = []
    for part in version.replace("_", ".").replace("+", ".").split("."):
        digits = "".join(c for c in part if c.isdigit())
        out.append(digits or "0")
    return out


def home(feature_):
    return homes().get(str(feature_))


@functools.lru_cache(maxsize=None)
def identity(home_):
    """What a record names the JDK by: its feature, `java -version`'s first line, its real home and release keys."""
    home_ = Path(home_).resolve()
    info = release(home_)
    proc = subprocess.run([str(home_ / "bin/java"), "-version"], capture_output=True, text=True, timeout=60)
    lines = (proc.stderr + proc.stdout).strip().splitlines()
    return {"feature": feature(info.get("JAVA_VERSION", "0")), "version": lines[0] if lines else "",
            "home": str(home_), "release": {k: info[k] for k in RELEASE_KEYS if k in info}}


def build_home():
    """The JDK build_fixtures.py compiles with (JAVA_HOME when set, else the javac on PATH), resolved to its real
    home, so the fixture route's bytes are build_fixtures.py's and its JDK is named by path. None when there is none."""
    if os.environ.get("JAVA_HOME"):
        candidate = Path(os.environ["JAVA_HOME"]).resolve()
    else:
        javac = shutil.which("javac")
        if not javac:
            return None
        candidate = Path(javac).resolve().parent.parent
    return str(candidate) if (candidate / "bin/javac").is_file() else None
