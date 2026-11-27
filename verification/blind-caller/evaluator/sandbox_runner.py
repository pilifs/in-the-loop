"""Run one frozen worker with a fresh filesystem view and a disabled network."""
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import resource
import runpy
import signal
import subprocess
import sys


BOOT = Path(__file__).resolve()
READ = "read-file,read-dir"
EXECUTE = "execute,read-file,read-dir"
WRITE = READ + ",write-file,make-dir,make-reg,truncate,remove-file,remove-dir,refer"


def syscall_filter(predict):
    seccomp = ctypes.CDLL("libseccomp.so.2")
    seccomp.seccomp_init.argtypes = [ctypes.c_uint32]
    seccomp.seccomp_init.restype = ctypes.c_void_p
    seccomp.seccomp_rule_add.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint]
    seccomp.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    seccomp.seccomp_load.argtypes = [ctypes.c_void_p]
    seccomp.seccomp_release.argtypes = [ctypes.c_void_p]
    context = seccomp.seccomp_init(0x7fff0000)  # SCMP_ACT_ALLOW
    if not context:
        raise RuntimeError("unable to initialize the syscall boundary")
    deny = 0x00050000 | errno.EPERM  # SCMP_ACT_ERRNO(EPERM)
    names = ["ptrace", "process_vm_readv", "process_vm_writev", "pidfd_getfd", "open_by_handle_at",
             "bpf", "perf_event_open", "io_uring_setup", "mount", "unshare", "setns", "kcmp",
             "kill", "tkill", "pidfd_send_signal"]
    if predict:
        names += ["socket", "connect", "bind", "accept", "accept4", "listen", "socketpair",
                  "clone", "clone3", "fork", "vfork", "execve", "execveat", "memfd_create"]
    try:
        for name in names:
            number = seccomp.seccomp_syscall_resolve_name(name.encode())
            if number >= 0 and seccomp.seccomp_rule_add(context, deny, number, 0) != 0:
                raise RuntimeError("unable to restrict a syscall")
        if predict:
            # The static worker can parse any classfile in its view. Denying executable
            # mappings also prevents starting a JVM in-process through ctypes/JNI.
            class ArgCompare(ctypes.Structure):
                _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_uint),
                            ("a", ctypes.c_uint64), ("b", ctypes.c_uint64)]
            seccomp.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
                                                       ctypes.c_uint, ctypes.POINTER(ArgCompare)]
            protection = ArgCompare(2, 7, 4, 4)  # arg 2 & PROT_EXEC == PROT_EXEC
            for name in ("mmap", "mmap2", "mprotect", "pkey_mprotect"):
                number = seccomp.seccomp_syscall_resolve_name(name.encode())
                if number >= 0 and seccomp.seccomp_rule_add_array(context, deny, number, 1, ctypes.byref(protection)):
                    raise RuntimeError("unable to deny new executable mappings")
        if seccomp.seccomp_load(context) != 0:
            raise RuntimeError("unable to enforce the syscall boundary")
    finally:
        seccomp.seccomp_release(context)


def worker(phase, sentinel, entry, packet, out, limit, host_net_inode, sealed=None):
    """This bootstrap is already inside Landlock when it is entered."""
    # Load standard extension modules used for static classfile/source inspection
    # before the prediction phase disables every new executable mapping.
    import ast, base64, bz2, datetime, decimal, lzma, math, mmap, socket, struct, zipfile, zlib
    import xml.etree.ElementTree
    limit = int(limit)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_CPU, (limit, limit + 1))
    if phase == "predict":
        resource.setrlimit(resource.RLIMIT_AS, (1024 ** 3, 1024 ** 3))
    syscall_filter(phase == "predict")
    try:
        Path(sentinel).read_bytes()
    except PermissionError:
        pass
    else:
        raise RuntimeError("evaluator sentinel read was allowed")
    if phase == "predict":
        try:
            socket.socket()
        except PermissionError:
            pass
        else:
            raise RuntimeError("network socket was allowed")
        try:
            subprocess.run(["/usr/bin/true"], check=False)
        except PermissionError:
            pass
        else:
            raise RuntimeError("prediction could execute a second process")
        try:
            mapping = mmap.mmap(-1, 4096, prot=mmap.PROT_READ | mmap.PROT_EXEC)
        except PermissionError:
            pass
        else:
            mapping.close()
            raise RuntimeError("prediction could load native executable bytes")
    else:
        # Original JDI uses a loopback listening connector and a child JVM. The
        # namespace exposes no host loopback endpoint and has no external interface.
        if Path("/proc/self/ns/net").stat().st_ino == int(host_net_inode):
            raise RuntimeError("measurement shares the host network namespace")
        interfaces = {name for _, name in socket.if_nameindex()}
        if interfaces != {"lo"}:
            raise RuntimeError("measurement has a non-loopback network interface")
        with socket.socket() as check:
            if check.connect_ex(("192.0.2.1", 9)) not in (errno.ENETUNREACH, errno.EHOSTUNREACH):
                raise RuntimeError("measurement has a route outside private loopback")
    # The evaluator records the outcome on a separate captured stream before running the
    # operator. The parent independently requires the exact prelude and successful output.
    print("BOUNDARY fs=denied network=" + ("denied subprocess=denied" if phase == "predict" else "private-loopback subprocess=allowed"), flush=True)
    sys.path.insert(0, str(Path(entry).parent.parent))
    sys.argv = [entry, packet, *([sealed] if sealed else []), out]
    runpy.run_path(entry, run_name="__main__")


def launch(phase, product, packet, scratch, jdk, sentinel, *, sealed=None, seconds=50, worker_path=None,
           diagnostic_path=None):
    if phase not in ("predict", "measure", "trace") or (phase == "measure") != bool(sealed):
        raise ValueError("unknown evaluation phase or missing sealed prediction")
    if not sentinel.is_file() or not sentinel.stat().st_size:
        raise ValueError("a real evaluator-only sentinel is required")
    if not (1 <= seconds <= 300):
        raise ValueError("worker time cap outside the supported range")
    scratch.mkdir()
    out = scratch / "out"
    out.mkdir()
    entry = worker_path or product / "examples/tools/targets" / {
        "predict": "blind_prediction.py", "measure": "blind_measure.py", "trace": "approved_test_trace.py"}[phase]
    if not entry.resolve().is_relative_to(product.resolve()) or not entry.is_file():
        raise ValueError("worker missing from the frozen producer export")
    rules = ["setpriv", "--no-new-privs", "--landlock-access", "fs"]
    def grant(access, paths):
        for p in paths:
            path = Path(p)
            if path.exists():
                value = access if path.is_dir() else access.replace(",read-dir", "").replace("read-dir,", "")
                rules.extend(["--landlock-rule", f"path-beneath:{value}:{path.resolve()}"])
    # No general grant for the repository, home, /etc, /proc or /sys. Worker inputs,
    # original JDK and standard runtime are read-only; the output area alone is writable.
    grant(EXECUTE, ["/usr", jdk])
    grant(READ, [product, packet, BOOT, "/etc/ld.so.cache", "/etc/localtime", "/proc/meminfo",
                 "/proc/cpuinfo", "/proc/stat", "/proc/sys/kernel/osrelease", "/sys/devices/system/cpu",
                 "/dev/urandom", "/dev/random"])
    if sealed:
        grant(READ, [sealed])
    checker = product / "lib/target/release/jvmcontract"
    if phase != "predict" and checker.is_file():
        grant("execute,read-file", [checker])
    grant("read-file,write-file", ["/dev/null"])
    grant(WRITE, [scratch])
    env = {"HOME": str(scratch), "TMPDIR": str(scratch), "PATH": "/usr/bin:/bin", "LANG": "C.UTF-8",
           "JAVA_TOOL_OPTIONS": f"-XX:-UsePerfData -XX:ActiveProcessorCount=2 -Djava.io.tmpdir={scratch}",
           "PYTHONDONTWRITEBYTECODE": "1"}
    if phase != "predict" and checker.is_file():
        env["JVMCONTRACT"] = str(checker)
    host_net_inode = str(Path("/proc/self/ns/net").stat().st_ino)
    command = [*rules, "--", "/usr/bin/python3", "-I", "-B", BOOT, phase, sentinel, entry, packet, out, str(seconds), host_net_inode]
    if sealed:
        command.append(sealed)
    if phase != "predict":
        box = ["bwrap", "--unshare-user", "--unshare-net", "--unshare-pid", "--unshare-uts", "--hostname", "caller",
               "--die-with-parent", "--cap-drop", "ALL",
               "--ro-bind", "/usr", "/usr", "--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64",
               "--symlink", "usr/bin", "/bin", "--dev", "/dev", "--proc", "/proc"]
        for mount in (jdk.resolve(), product, packet, sealed, BOOT, sentinel, Path("/etc/ld.so.cache"),
                      Path("/etc/localtime"), Path("/sys/devices/system/cpu")):
            if mount is not None and mount.exists():
                box += ["--ro-bind", str(mount.resolve()), str(mount)]
        hosts = scratch.parent / "private-loopback-hosts"
        hosts.write_text("127.0.0.1 localhost caller\n::1 localhost caller\n")
        command[command.index("--"):command.index("--")] = ["--landlock-rule", "path-beneath:read-file:/etc/hosts"]
        box += ["--ro-bind", str(hosts), "/etc/hosts"]
        box += ["--bind", str(scratch), str(scratch), "--chdir", str(scratch), "--"]
        command = box + command
    with subprocess.Popen(list(map(str, command)), stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=scratch, env=env, close_fds=True, start_new_session=True) as child:
        try:
            stdout, stderr = child.communicate(timeout=seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            stdout, stderr = child.communicate()
            timed_out = True
    expected = b"BOUNDARY fs=denied network=" + (b"denied subprocess=denied\n" if phase == "predict" else b"private-loopback subprocess=allowed\n")
    boundary = stdout.startswith(expected)
    if diagnostic_path is not None:
        diagnostic_path.write_bytes(stderr)
    policy = {"phase": phase, "landlockSentinelDenied": boundary, "networkDenied": boundary,
              "network": "socket creation denied" if phase == "predict" else "dedicated loopback-only namespace",
              "predictionSubprocessDenied": boundary if phase == "predict" else None,
              "predictionExecutableMappingDenied": boundary if phase == "predict" else None, "freshProcess": True,
              "secondsLimit": seconds, "timedOut": timed_out, "exitCode": child.returncode,
              "stdoutSha256": hashlib.sha256(stdout).hexdigest(), "stderrSha256": hashlib.sha256(stderr).hexdigest(),
              "stdoutBytes": len(stdout), "stderrBytes": len(stderr)}
    return out, policy


if __name__ == "__main__":
    worker(*sys.argv[1:])
