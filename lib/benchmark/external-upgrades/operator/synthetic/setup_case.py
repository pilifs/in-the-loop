"""Write the public toy target and import the released source through the same restricted command tool."""

import json
from pathlib import Path
import shutil
import sys

example = Path("/opt/product/examples/001-case")
for side in ("old", "new"):
    shutil.copytree(Path("/case/packet") / side / "src/main/java", example / side)
for name, content in json.loads(sys.argv[1]).items():
    path = example / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
