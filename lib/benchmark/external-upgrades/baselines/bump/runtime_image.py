"""Materialize the two verified Alpine runtime layers as regular files for an unprivileged, networkless run."""
import hashlib
import os
from pathlib import Path, PurePosixPath
import posixpath
import shutil
import tarfile


ALPINE = "31e352740f534f9ad170f75378a84fe453d6156e40700b882d737a8f4a6988a3"
RUNTIME = "42276f95e61fb8c21e366aa2af910d650d2566ae9f78f39224e88673daeae7ea"
JAVA = "/usr/lib/jvm/java-11-openjdk"
MAVEN = "/usr/share/java/maven-3"


def sha(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def clean(path):
    if path.startswith("./"):
        path = path[2:]
    pieces = path.rstrip("/").split("/")
    if not path or any(p in ("", ".", "..") for p in pieces):
        return None
    return "/".join(pieces)


def allowed(name):
    return name.startswith(("bin/", "lib/", "usr/bin/", "usr/lib/", "usr/share/java/", "usr/share/maven/",
                            "etc/java", "etc/maven", "usr/share/zoneinfo/", "etc/ssl/certs/"))


def rootfs(inputs, out):
    out.mkdir()
    aliases = {}
    directories = set()
    for archive, expected in (("common-alpine.tgz", ALPINE), ("common-jdk-maven.tgz", RUNTIME)):
        layer = inputs / archive
        if sha(layer) != expected:
            raise ValueError("runtime layer digest mismatch")
        prior_files = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} | set(aliases)
        with tarfile.open(layer, "r|gz") as tar:
            for info in tar:
                name = clean(info.name)
                if not name or not allowed(name):
                    continue
                if any(part.startswith(".wh.") for part in name.split("/")):
                    prefix = posixpath.dirname(name) + "/"
                    if name.endswith("/.wh..wh..opq") and not any(old.startswith(prefix) for old in prior_files):
                        continue
                    raise ValueError("unexpected whiteout of selected lower-layer runtime data")
                dest = out / name
                if info.isdir():
                    directories.add(name)
                elif info.isreg():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with dest.open("wb") as file:
                        shutil.copyfileobj(tar.extractfile(info), file, 1024**2)
                    dest.chmod(0o755 if info.mode & 0o111 else 0o644)
                    aliases.pop(name, None)
                elif info.issym() or info.islnk():
                    target = info.linkname
                    if target.startswith("/"):
                        target = target.lstrip("/")
                    elif info.issym():
                        target = posixpath.join(posixpath.dirname(name), target)
                    target = clean(posixpath.normpath(target))
                    if target and allowed(target):
                        aliases[name] = target
    # Resolve only within the selected, digest-verified image data. No archive link is created on the host.
    def resolve(name):
        visited = set()
        while name not in visited:
            visited.add(name)
            pieces = name.split("/")
            for i in range(len(pieces), 0, -1):
                prefix = "/".join(pieces[:i])
                if prefix in aliases:
                    name = "/".join([aliases[prefix], *pieces[i:]])
                    break
            else:
                return name
        return None
    directory_aliases = []
    for name in sorted(aliases):
        resolved = resolve(name)
        if not resolved:
            continue
        real, dest = out / resolved, out / name
        if real.is_file() and not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.link(real, dest)
        elif (real.is_dir() or resolved in directories) and (
                name.startswith(JAVA[1:] + "/") or name.startswith(MAVEN[1:] + "/")):
            directory_aliases.append((dest, real))
    for dest, real in directory_aliases:
        for source in list(real.rglob("*")):
            if source.is_file():
                path = dest / source.relative_to(real)
                if not path.exists():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    os.link(source, path)
    for name in ("work/project", "work/home/.m2", "tmp", "proc", "dev", "etc"):
        (out / name).mkdir(parents=True, exist_ok=True)
    uid, gid = os.getuid(), os.getgid()
    (out / "etc/passwd").write_text(f"research:x:{uid}:{gid}:Local replay:/work/home:/bin/sh\n")
    (out / "etc/group").write_text(f"research:x:{gid}:\n")


def isolate(image, project, repository, scratch, command):
    return ["bwrap", "--unshare-all", "--die-with-parent", "--new-session", "--cap-drop", "ALL",
            "--ro-bind", str(image), "/", "--bind", str(project), "/work/project",
            "--bind", str(repository), "/work/home/.m2", "--bind", str(scratch), "/tmp",
            "--proc", "/proc", "--dev", "/dev", "--chdir", "/work/project", "--", *command]


def environment():
    return {"PATH": f"{JAVA}/bin:{MAVEN}/bin:/usr/bin:/bin", "JAVA_HOME": JAVA,
            "MAVEN_OPTS": "-Duser.home=/work/home", "TZ": "UTC", "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "TMPDIR": "/tmp"}
