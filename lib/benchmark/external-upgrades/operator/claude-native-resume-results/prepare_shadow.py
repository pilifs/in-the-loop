"""Create the amended meter from the exact frozen product-free native-resume meter."""

import argparse
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / "claude-native-resume"
sys.path.insert(0, str(BASE))
import runner_core as core  # noqa: E402
import isolation  # noqa: E402


def edit(source, old, new):
    if source.count(old) != 1:
        raise ValueError("the pinned meter extension point changed")
    return source.replace(old, new)


def build(base, output):
    conf = core.json_file(BASE / "claude-native-resume.json")
    if (
        isolation.digest(base / "manifest.json") != conf["shadow"]["toolRootSha256"]
        or isolation.canonical(isolation.tree(base / "root")) != (base / "manifest.json").read_bytes()
    ):
        raise ValueError("the base context meter differs from the frozen qualification")
    output.mkdir(parents=True, mode=0o700, exist_ok=False)

    def clone(src, out):
        try:
            os.link(src, out)
        except OSError:
            shutil.copy2(src, out)

    shutil.copytree(base / "root", output / "root", copy_function=clone, symlinks=True)
    area = output / "root/opt/operator-shadow"
    f = area / "measure.py"
    if isolation.digest(f) != conf["runnerSha256"]["shadow_guest.py"]:
        raise ValueError("the base meter implementation differs")
    source = edit(
        f.read_text(),
        "from signals import contained",
        "from signals import contained\nfrom native_result import from_case",
    )
    source = edit(
        source,
        '            need = spec.get("expectedBlockSha256")',
        "            native_result = from_case(msgs, spec, signals)",
    )
    source = edit(
        source,
        '"priorSignalRestored": not need or need in signals,',
        '"nativeRestore": native_result["mode"],\n                    "priorSignalRestored": native_result["accepted"],',
    )
    f.unlink()
    f.write_text(source)
    shutil.copy2(HERE / "native_result.py", area / "native_result.py")
    (output / "manifest.json").write_bytes(isolation.canonical(isolation.tree(output / "root")))
    return isolation.digest(output / "manifest.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-shadow", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(build(args.base_shadow, args.output))
