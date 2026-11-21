import sys
import json

import errno
import os
import pathlib
import socket

EXPECTED = sys.argv[1]
OUTSIDE = json.loads(sys.argv[2])

p = pathlib.Path
positive = p("/case/packet/old/allowed-canary.txt").read_text() == EXPECTED
negative = {}
for name, candidate in OUTSIDE.items():
    try:
        p(candidate).read_bytes()
    except (FileNotFoundError, PermissionError, IsADirectoryError):
        negative[name] = True
    else:
        negative[name] = False
writes = {}
for name, path in {
    "packet": "/case/packet/new/changed",
    "product": "/opt/product/pin-changed",
}.items():
    try:
        p(path).write_text("canary")
    except OSError as e:
        writes[name] = e.errno in (errno.EROFS, errno.EACCES, errno.EPERM)
    else:
        writes[name] = False
p("/case/work/positive-write").write_text("ok")
with socket.socket() as sock:
    sock.settimeout(1)
    code = sock.connect_ex(("192.0.2.1", 9))
interfaces = {r.split(":")[0].strip() for r in p("/proc/net/dev").read_text().splitlines()[2:]}
status = p("/proc/self/status").read_text().splitlines()
check = {
    "positiveRead": positive,
    "positiveWrite": p("/case/work/positive-write").read_text() == "ok",
    "outsideBlocked": negative,
    "readOnly": writes,
    "networkUnavailable": code in (errno.ENETUNREACH, errno.EHOSTUNREACH)
    and interfaces.issubset({"lo"}),
    "noEffectiveCapabilities": int(next(x.split()[1] for x in status if x.startswith("CapEff:")), 16)
    == 0,
    "noNewPrivileges": next(x.split()[1] for x in status if x.startswith("NoNewPrivs:")) == "1",
    "privatePidNamespace": {q.name for q in p("/proc").iterdir() if q.name.isdigit()}.issubset(
        {"1", "2", "3"}
    ),
    "environmentAllowlisted": set(os.environ)
    <= set(
        [
            "PATH",
            "HOME",
            "LANG",
            "TZ",
            "JAVA_HOME",
            "JVMCONTRACT_VERIFIER_JDK",
            "TARGETS_JDK_CANDIDATES",
            "JVMCONTRACT",
            "JVMCONTRACT_BITWUZLA",
            "JVMCONTRACT_SOLVER",
            "LD_LIBRARY_PATH",
            "TMPDIR",
            "TARGETS_CACHE",
            "PYTHONDONTWRITEBYTECODE",
            "PWD",
        ]
    ),
}
print(json.dumps(check))
