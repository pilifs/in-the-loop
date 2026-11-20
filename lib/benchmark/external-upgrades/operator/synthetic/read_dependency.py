import errno
import json
from pathlib import Path

root = Path("/case/dependencies")
listed = (root / "sample.txt").read_text() == "synthetic allowed dependency"
try:
    (root / "sample.txt").write_text("changed")
except OSError as error:
    protected = error.errno in (errno.EROFS, errno.EACCES, errno.EPERM)
else:
    protected = False
print(
    json.dumps(
        {
            "listedFileAvailable": listed,
            "unlistedFileAbsent": not (root / "withheld.txt").exists(),
            "readOnly": protected,
        }
    )
)
