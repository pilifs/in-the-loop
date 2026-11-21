"""Stage a read-only, credentialless loopback control image from the common case runtime with all tested product and solver bytes omitted."""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import isolation  # noqa: E402
from identity import product_owned  # noqa: E402


def build(product, dest, cli):
    base = product / "root"
    manifest = json.loads((product / "manifest.json").read_bytes())
    if isolation.tree(base) != manifest:
        raise ValueError("base tool root differs from its own manifest")
    dest.mkdir(mode=0o700, parents=True, exist_ok=False)
    root = dest / "root"

    def clone(src, out):
        try:
            os.link(src, out)
        except OSError:
            shutil.copy2(src, out)

    def omit_product(directory, names):
        rel = Path(directory).relative_to(base)
        return [name for name in names if product_owned((rel / name).as_posix())]

    shutil.copytree(base, root, symlinks=True, copy_function=clone, ignore=omit_product)
    # The common namespace expects one empty private example mount point.
    (root / "opt/product/examples/001-case").mkdir(parents=True, exist_ok=True)
    (root / "srv").mkdir(exist_ok=True)
    area = root / "opt/operator-shadow"
    area.mkdir()
    (area / "lib").mkdir()
    shutil.copy2(cli, area / "claude")
    shutil.copyfile(HERE / "shadow_guest.py", area / "measure.py")
    shutil.copyfile(HERE / "signals.py", area / "signals.py")
    for name in ("librt.so.1", "libpthread.so.0", "libdl.so.2"):
        shutil.copy2(Path("/usr/lib/x86_64-linux-gnu") / name, area / "lib" / name)
    code = area / "public/lib/benchmark/external-upgrades/operator"
    code.mkdir(parents=True)
    for f in ("control.py", "mcp_server.py", "isolation.py"):
        shutil.copy2(HERE.parent / f, code / f)
    (area / "mcp.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "neutral_case": {
                        "type": "stdio",
                        "command": "/usr/bin/python3",
                        "args": [
                            "/opt/operator-shadow/public/lib/benchmark/external-upgrades/operator/mcp_server.py",
                            "--product",
                            "/absent",
                            "--case",
                            "/absent",
                        ],
                    }
                }
            }
        )
    )
    (dest / "manifest.json").write_bytes(isolation.canonical(isolation.tree(root)))
    return isolation.digest(dest / "manifest.json")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--product", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--claude", type=Path, default=Path(shutil.which("claude")))
    a = p.parse_args()
    print(build(a.product.resolve(), a.output.resolve(), a.claude.resolve()))
