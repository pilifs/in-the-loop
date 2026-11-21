import errno
import json
from pathlib import Path
import sys

nonce = sys.argv[1]
canary = Path("/case/packet/old/allowed-canary.txt").read_text()
path = Path("/case/work/role-canary.txt")
new = not path.exists()
path.write_text(nonce)
refusals = {}
for name, private in json.loads(Path("/case/packet/old/negative-canaries.json").read_text()).items():
    try:
        Path(private).read_bytes()
    except (FileNotFoundError, PermissionError):
        refusals[name] = True
    else:
        refusals[name] = False
try:
    Path("/case/packet/old/forbidden-write").write_text(nonce)
except OSError as exc:
    readonly = exc.errno in (errno.EROFS, errno.EACCES, errno.EPERM)
else:
    readonly = False
print(
    json.dumps(
        {
            "readCanary": canary,
            "writtenNonce": path.read_text(),
            "startedEmpty": new,
            "deniedOutside": refusals,
            "packetReadOnly": readonly,
        }
    )
)
