"""Prove the temporary-file setting still holds when a caller clears the JVM environment, and exercise V0 normally."""

import argparse
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import control  # noqa: E402
import isolation  # noqa: E402
import probe  # noqa: E402

GUEST = """import json,os,pathlib,re,subprocess
from pathlib import Path
base=Path('/opt/jdks/21-tem/bin');root=Path('/case/work/tmp');data={}
for command in ['java','javac','jar','javap']:
 option='-XshowSettings:properties' if command=='java' else '-J-XshowSettings:properties'
 version='-version' if command in ('java','javac','javap') else '--version'
 p=subprocess.run([str(base/command),option,version],env={},stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
 m=re.search(r'^\\s*java\\.io\\.tmpdir\\s*=\\s*(.+?)\\s*$',p.stdout,re.M);data[command]={'exit':p.returncode,'tmpdir':m[1] if m else None}
code=Path('/case/work/T.java');code.write_text('import java.nio.file.*; public class T {public static void main(String[] a) throws Exception {System.out.println(Files.createTempFile("actual-case-file", ".txt").toRealPath());System.out.println(System.getProperty("java.home"));}}');subprocess.run([str(base/'javac'),'-d','/case/work',str(code)],env={},check=True);rows=subprocess.check_output([str(base/'java'),'-cp','/case/work','T'],env={},text=True).splitlines();data['physicalFileUnderCase']=Path(rows[0]).is_relative_to(root) and Path(rows[0]).is_file();data['javaHomeLeadsToCanonicalWrapper']=str(Path(rows[1])/'bin/java')==str(base/'java');print(json.dumps(data))"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--product", required=True, type=Path)
    p.add_argument("--scratch", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--native", action="store_true")
    a = p.parse_args()
    root = a.scratch.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    pair, _ = probe.packet(root)
    case = root / "jdk-case"
    isolation.fresh_case(case, pair, isolation.digest(pair / "pair.json"))
    r = control.execute(
        a.product,
        case,
        {
            "type": "function_call",
            "name": "case_command",
            "arguments": json.dumps({"argv": ["python3", "-c", GUEST]}),
        },
    )
    assert not r["exit"], r["output"][-500:]
    data = json.loads(r["output"])
    assert all(
        data[n] == {"exit": 0, "tmpdir": "/case/work/tmp"} for n in ("java", "javac", "jar", "javap")
    ), data
    assert data["physicalFileUnderCase"] and data["javaHomeLeadsToCanonicalWrapper"]
    data["caseRootSha256"] = isolation.digest(a.product / "manifest.json")
    data["pinnedLaunchers"] = json.loads((a.product / "java-launchers.json").read_bytes())[
        "launchers"
    ]
    pin = json.loads((HERE.parents[1] / "v0.json").read_bytes())
    assert all(
        data["pinnedLaunchers"][name]["temurinBinarySha256"] == pin["sha256"]["bin/" + name]
        for name in ("java", "javac")
    )
    if a.native:
        output = root / "native.json"
        subprocess.run(
            [
                sys.executable,
                HERE.parent / "probe.py",
                "--native",
                "--product",
                a.product,
                "--scratch",
                root / "native",
                "--output",
                output,
            ],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        native = json.loads(output.read_bytes())
        data["v0Native"] = native["nativeVerification"]
        data["nativeReceiptSha256"] = isolation.digest(
            next((root / "native/case/example/receipts/preserve").glob("*/result.json"))
        )
    a.output.write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps({name: data[name] for name in ("java", "javac", "physicalFileUnderCase")}))


if __name__ == "__main__":
    main()
