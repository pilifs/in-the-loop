"""A V0 operator tool process gets one verified packet, one private work area and a frozen toolchain."""

import argparse
import hashlib
import gzip
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import sysconfig

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
PIN = HERE.parent / "v0.json"
GUEST_JDK = Path("/opt/jdks/21-tem")
PRODUCT = Path("/opt/product")
EXAMPLE = PRODUCT / "examples/001-case"


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode()


def hashed(value):
    return hashlib.sha256(value).hexdigest()


def git(*args):
    return subprocess.check_output(["git", "-C", str(REPO), *args])


def inside(root, absolute):
    return root / Path(absolute).relative_to("/")


def install(root, target, source):
    target = inside(root, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    return target


def system_runtime(root):
    # Every host source here is a named program, the system Python standard library or its dynamic linker dependencies.
    # No host filesystem tree is mounted in the guest.
    python = Path(sys.executable).resolve()
    stdlib = Path(sysconfig.get_path("stdlib")).resolve()
    system = [
        python,
        *[
            Path(shutil.which(name)).resolve()
            for name in (
                "bash",
                "dash",
                "cat",
                "cp",
                "find",
                "git",
                "ls",
                "mkdir",
                "mv",
                "printf",
                "rm",
                "sha256sum",
                "stat",
            )
        ],
    ]
    for executable in system:
        install(root, "/usr/bin/" + executable.name, executable)
    bin_dir = inside(root, "/usr/bin")
    (bin_dir / "sh").symlink_to("dash")
    (bin_dir / "python3").symlink_to(python.name)
    inside(root, "/bin").symlink_to("usr/bin")
    std_dest = inside(root, stdlib)
    shutil.copytree(
        stdlib,
        std_dest,
        ignore=shutil.ignore_patterns(
            "dist-packages",
            "site-packages",
            "__pycache__",
            "test",
            "tests",
            "idlelib",
            "tkinter",
            "ensurepip",
        ),
    )
    native = list((stdlib / "lib-dynload").glob("*.so"))
    for module in (
        "jsonschema",
        "jsonschema_specifications",
        "referencing",
        "rpds",
        "attr",
        "attrs",
        "typing_extensions",
    ):
        spec = importlib.util.find_spec(module)
        origin = Path(spec.origin).resolve()
        if not origin.is_relative_to("/usr/lib/python3/dist-packages"):
            raise ValueError("expected a system schema-validation package")
        if spec.submodule_search_locations:
            src = origin.parent
            shutil.copytree(
                src, inside(root, src), ignore=shutil.ignore_patterns("__pycache__", "tests", "test")
            )
            native.extend(src.rglob("*.so"))
        else:
            install(root, origin, origin)
    for package in (
        "jsonschema",
        "jsonschema-specifications",
        "referencing",
        "rpds-py",
        "attrs",
        "typing-extensions",
    ):
        distribution = importlib.metadata.distribution(package)
        dirname = (
            distribution.metadata["Name"].replace("-", "_")
            + "-"
            + distribution.version
            + ".dist-info"
        )
        where = Path(distribution.locate_file(dirname)).resolve()
        shutil.copytree(where, inside(root, where))
    return system + native


def libraries(root, programs, jdk, bitwuzla):
    lib = jdk / "lib"
    env = {
        "PATH": "/usr/bin:/bin",
        "LC_ALL": "C",
        "LD_LIBRARY_PATH": os.pathsep.join(map(str, [lib, lib / "server", bitwuzla])),
    }
    ldd = subprocess.run(
        ["/usr/bin/ldd", *map(str, programs)], env=env, capture_output=True, text=True, check=True
    )
    for line in ldd.stdout.splitlines():
        match = re.search(r"^\s*(?:[^ ]+ => )?(/[^ ]+) \(0x[0-9a-f]+\)", line)
        if not match:
            continue
        path = Path(match[1])
        real = path.resolve()
        if real.is_relative_to(jdk) or real.is_relative_to(bitwuzla) or inside(root, path).exists():
            continue
        if not (real.is_relative_to("/usr/lib") or real.is_relative_to("/lib")):
            raise ValueError(f"unexpected shared library origin {path.name}")
        install(root, path, real)


def workflow_file(name):
    path = Path(name)
    if name in {
        "examples/tools/targets/fixtures/build_fixtures.py",
        "verification/pipeline.py",
        "verification/pipeline.toml",
        "lib/tools/process_usage.py",
        "plugins/in-the-loop/skills/prove-java-change/SKILL.md",
        "examples/tags.json",
        "llm-dlc/runtime.md",
        "llm-dlc/prove-plan-template.md",
        "llm-dlc/prove-plan.schema.json",
    }:
        return True
    if path.parts[:2] in {("examples", "schema"), ("verification", "schema")}:
        return path.suffix == ".json"
    return (
        path.parts[:-1] in {("examples", "tools"), ("examples", "tools", "targets")}
        and path.suffix == ".py"
        and not path.name.startswith("test_")
        and path.name not in {"runtime_calibrate.py", "runtime_slice.py"}
    )


def stage_product(dest, checker, jdk, bitwuzla):
    pin = json.loads(PIN.read_bytes())
    revision = pin["revision"]
    file_lock = gzip.decompress((PIN.parent / "v0-files.json.gz").read_bytes())
    if hashed(file_lock) != pin["sourceManifestSha256"]:
        raise ValueError("V0 source manifest hash differs")
    locked_files = json.loads(file_lock)["files"]
    for name, expected in pin["gitObjects"].items():
        if git("rev-parse", f"{revision}:{name}").decode().strip() != expected:
            raise ValueError("wrong product tree " + name)
    hashes = pin["sha256"]
    bitwuzla = bitwuzla.resolve()
    jdk = jdk.resolve()
    tools = {
        "jvmcontract": checker,
        "jbmc": Path(shutil.which("jbmc")),
        "z3": Path(shutil.which("z3")),
    }
    sources = {
        **tools,
        **{
            name: jdk / name
            for name in ("release", "bin/java", "bin/javac", "lib/server/libjvm.so", "lib/modules")
        },
        **{name: bitwuzla / name for name in hashes if name.startswith("libbitwuzla")},
    }
    if set(sources) != set(hashes) or any(
        digest(source) != hashes[k] for k, source in sources.items()
    ):
        raise ValueError("V0 executable, JDK or solver hash differs")
    dest.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = dest / "root"
    root.mkdir()
    for path in [
        "dev",
        "proc",
        "case/packet",
        "case/dependencies",
        "case/work",
        "home/operator",
        "tmp",
        "etc",
        "opt/product/examples/001-case",
    ]:
        (root / path).mkdir(parents=True, exist_ok=True)
    (root / "etc/passwd").write_text(
        f"operator:x:{os.getuid()}:{os.getgid()}::/home/operator:/bin/sh\n"
    )
    (root / "etc/group").write_text(f"operator:x:{os.getgid()}:\n")
    programs = system_runtime(root)
    for name, source in tools.items():
        install(root, "/usr/bin/" + name, source)
        programs.append(source)
    for child in [
        jdk / "release",
        *[jdk / "bin" / name for name in ("java", "javac", "jar", "javap")],
        *[
            f
            for f in (jdk / "lib").glob("*")
            if f.is_file()
            and (
                f.suffix in {".so", ".jar", ".sym", ".dat", ".cfg"}
                or f.name in {"modules", "jexec", "jspawnhelper"}
            )
        ],
        jdk / "lib/server/libjvm.so",
        jdk / "lib/jvm.cfg",
    ]:
        install(root, GUEST_JDK / child.relative_to(jdk), child)
    shutil.copytree(jdk / "conf", inside(root, GUEST_JDK / "conf"))
    for name in ("security/default.policy", "security/public_suffix_list.dat"):
        if (jdk / "lib" / name).is_file():
            install(root, GUEST_JDK / "lib" / name, jdk / "lib" / name)
    for name in sources:
        if name.startswith("libbitwuzla"):
            install(root, "/opt/solver/" + name, sources[name])
            # The pinned workflow clears LD_LIBRARY_PATH on the checker child; its loader still needs the sibling libraries.
            install(root, "/lib/x86_64-linux-gnu/" + name, sources[name])
            programs.append(sources[name])
    programs += [
        jdk / "bin/java",
        jdk / "bin/javac",
        jdk / "lib/server/libjvm.so",
        jdk / "lib/libjava.so",
        jdk / "lib/libzip.so",
        jdk / "lib/libnet.so",
        jdk / "lib/libnio.so",
    ]
    libraries(root, programs, jdk, bitwuzla)
    names = (
        git(
            "ls-tree",
            "-r",
            "--name-only",
            revision,
            "--",
            "examples/tools",
            "examples/schema",
            "examples/tags.json",
            "verification/pipeline.py",
            "verification/pipeline.toml",
            "lib/tools/process_usage.py",
            "plugins/in-the-loop/skills/prove-java-change/SKILL.md",
            "verification/schema",
            "llm-dlc/runtime.md",
            "llm-dlc/prove-plan-template.md",
            "llm-dlc/prove-plan.schema.json",
        )
        .decode()
        .splitlines()
    )
    selected = [n for n in names if workflow_file(n)]
    for name in selected:
        target = inside(root, PRODUCT / name)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = git("show", f"{revision}:{name}")
        if name in locked_files:
            blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
            if blob != locked_files[name][1]:
                raise ValueError("V0 source blob differs: " + name)
        target.write_bytes(data)
    (inside(root, PRODUCT) / ".in-the-loop-runtime.json").write_text("{}\n")
    (root / "opt/product-pin.json").write_bytes(PIN.read_bytes())
    # Hash the assembled filesystem, including interpreter and workflow, for each host-side launch.
    manifest = tree(root)
    (dest / "manifest.json").write_bytes(canonical(manifest))
    return {
        "revision": revision,
        "checkerSha256": hashes["jvmcontract"],
        "rootSha256": hashed(canonical(manifest)),
        "workflowFiles": len(selected),
        "rootFiles": len(manifest),
    }


def tree(directory):
    files = {}
    for path in sorted(directory.rglob("*")):
        mode = path.lstat().st_mode
        if stat.S_ISDIR(mode):
            continue
        name = path.relative_to(directory).as_posix()
        if stat.S_ISLNK(mode):
            link = os.readlink(path)
            if Path(link).is_absolute() or not path.resolve(strict=True).is_relative_to(
                directory.resolve()
            ):
                raise ValueError("symlink escapes clean tree")
            files[name] = {"mode": "120000", "sha256": hashed(os.fsencode(link))}
        elif stat.S_ISREG(mode):
            files[name] = {"mode": "100755" if mode & 0o111 else "100644", "sha256": digest(path)}
        else:
            raise ValueError("unreleased special file")
    return files


def check_packet(pair, manifest_sha):
    if pair.is_symlink() or {p.name for p in pair.iterdir()} != {"pair.json", "old", "new"}:
        raise ValueError("expected exactly the released neutral pair")
    manifest = pair / "pair.json"
    if manifest.is_symlink() or not manifest.is_file() or digest(manifest) != manifest_sha:
        raise ValueError("operator packet hash differs from trusted release")
    d = json.loads(manifest.read_bytes())
    if set(d) != {"case_id", "old", "new"} or not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", d["case_id"]):
        raise ValueError("invalid neutral receipt")
    for side in ("old", "new"):
        directory = pair / side
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError("invalid side")
        files = tree(directory)
        if not files or d[side] != {"tree_sha256": hashed(canonical(files))}:
            raise ValueError("neutral source tree differs")
    return d


def copy_dependencies(case, source, expected, case_id):
    """Only the release's named, ordered files enter the guest. The source directory is never mounted."""
    released = source.read_bytes()
    if hashed(released) != expected:
        raise ValueError("dependency release differs from the trusted digest")
    manifest = json.loads(released)
    if (
        manifest.get("case_id") != case_id
        or set(manifest) != {"case_id", "artifacts"}
        or not isinstance(manifest["artifacts"], list)
    ):
        raise ValueError("dependency release belongs to another case or is malformed")
    dest = case / "dependencies"
    dest.mkdir()
    copied = set()
    for item in manifest["artifacts"]:
        if (
            set(item) != {"side", "path", "sha256"}
            or item["side"] not in ("old", "new", "both")
            or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])
        ):
            raise ValueError("invalid released dependency row")
        name = Path(item["path"])
        if (
            name.is_absolute()
            or not name.parts
            or ".." in name.parts
            or name.as_posix() == "manifest.json"
        ):
            raise ValueError("invalid released dependency path")
        origin = (source.parent / name).resolve(strict=True)
        if not origin.is_relative_to(source.parent.resolve()) or not origin.is_file():
            raise ValueError("dependency outside its released directory")
        output = dest / name
        if name not in copied:
            output.parent.mkdir(parents=True, exist_ok=True)
            with output.open("xb") as out, origin.open("rb") as inp:
                shutil.copyfileobj(inp, out)
            copied.add(name)
        if digest(output) != item["sha256"]:
            raise ValueError("released dependency bytes differ")
    (dest / "manifest.json").write_bytes(released)
    (case / "dependency-tree.sha256").write_text(hashed(canonical(tree(dest))) + "\n")


def fresh_case(dest, packet, manifest_sha, dependencies=None, dependency_digest=None):
    dest.mkdir(parents=True, mode=0o700, exist_ok=False)
    pair = dest / "packet"
    if packet.is_symlink():
        raise ValueError("expected a regular packet directory")
    check_packet(packet, manifest_sha)
    shutil.copytree(packet, pair, symlinks=True)
    release = check_packet(pair, manifest_sha)
    if (dependencies is None) != (dependency_digest is None):
        raise ValueError("both the dependency release and its trusted digest are required")
    if dependencies is not None:
        copy_dependencies(dest, dependencies, dependency_digest, release["case_id"])
    work = dest / "work"
    work.mkdir()
    (dest / "example").mkdir()
    (work / "tmp").mkdir()
    (work / "cache").mkdir()
    (dest / "release.sha256").write_text(manifest_sha + "\n")
    return release


def environment(product, case):
    root = product / "root"
    pair = case / "packet"
    work = case / "work"
    # Compare the publication to the frozen packet after the copy; either tree may have changed between invocations.
    check_packet(pair, (case / "release.sha256").read_text().strip())
    if canonical(tree(root)) != (product / "manifest.json").read_bytes():
        raise ValueError("tool root changed after staging")
    mounts = []
    if (case / "dependency-tree.sha256").is_file():
        if (
            hashed(canonical(tree(case / "dependencies")))
            != (case / "dependency-tree.sha256").read_text().strip()
        ):
            raise ValueError("released dependency tree changed")
        mounts = ["--ro-bind", str(case / "dependencies"), "/case/dependencies"]
    return [
        "bwrap",
        "--unshare-user",
        "--unshare-pid",
        "--unshare-net",
        "--unshare-ipc",
        "--unshare-uts",
        "--unshare-cgroup-try",
        "--disable-userns",
        "--cap-drop",
        "ALL",
        "--die-with-parent",
        "--new-session",
        "--clearenv",
        "--ro-bind",
        str(root),
        "/",
        "--ro-bind",
        str(pair),
        "/case/packet",
        *mounts,
        "--bind",
        str(work),
        "/case/work",
        "--bind",
        str(case / "example"),
        str(EXAMPLE),
        "--dev",
        "/dev",
        "--proc",
        "/proc",
        "--remount-ro",
        "/proc",
        "--tmpfs",
        "/tmp",
        "--chdir",
        "/case/work",
        "--setenv",
        "PATH",
        f"{GUEST_JDK}/bin:/usr/bin:/bin",
        "--setenv",
        "HOME",
        "/home/operator",
        "--setenv",
        "LANG",
        "C.UTF-8",
        "--setenv",
        "TZ",
        "UTC",
        "--setenv",
        "JAVA_HOME",
        str(GUEST_JDK),
        "--setenv",
        "JVMCONTRACT_VERIFIER_JDK",
        str(GUEST_JDK),
        "--setenv",
        "TARGETS_JDK_CANDIDATES",
        "/opt/jdks",
        "--setenv",
        "JVMCONTRACT",
        "/usr/bin/jvmcontract",
        "--setenv",
        "JVMCONTRACT_SOLVER",
        "bitwuzla-words",
        "--setenv",
        "JVMCONTRACT_BITWUZLA",
        "/opt/solver/libbitwuzla.so.0",
        "--setenv",
        "LD_LIBRARY_PATH",
        "/opt/solver",
        "--setenv",
        "TMPDIR",
        "/case/work/tmp",
        "--setenv",
        "TARGETS_CACHE",
        "/case/work/cache",
        "--setenv",
        "PYTHONDONTWRITEBYTECODE",
        "1",
        "--",
    ]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="action", required=True)
    s = sub.add_parser("product")
    s.add_argument("dest", type=Path)
    s.add_argument(
        "--checker",
        type=Path,
        default=Path.home()
        / ".cache/in-the-loop/external-upgrades"
        / json.loads(PIN.read_bytes())["sha256"]["jvmcontract"]
        / "jvmcontract",
    )
    s.add_argument("--jdk", type=Path, required=True)
    s.add_argument("--bitwuzla", type=Path, required=True)
    s = sub.add_parser("case")
    s.add_argument("dest", type=Path)
    s.add_argument("packet", type=Path)
    s.add_argument("packet_digest")
    s.add_argument("--dependencies", type=Path)
    s.add_argument("--dependency-digest")
    a = parser.parse_args()
    print(
        json.dumps(
            stage_product(a.dest, a.checker, a.jdk, a.bitwuzla)
            if a.action == "product"
            else fresh_case(a.dest, a.packet, a.packet_digest, a.dependencies, a.dependency_digest),
            indent=2,
        )
    )
