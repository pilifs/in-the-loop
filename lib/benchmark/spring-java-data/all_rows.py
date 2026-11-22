"""Check the complete bounded row family on the original JVM, including every feasible input alias pattern."""
import argparse
import gzip
from itertools import product
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

from domains import decimal, TOKENS
from measure import HERE, ROOT, SETUP, digest, read, run_cmd, write
from targets import runtime_jdk

FOLDER = ROOT / "examples/369-boxed-ragged-rows"

def partitions(height, pattern=()):
    if len(pattern) == height:
        yield pattern
        return
    for label in range(max(pattern, default=-1) + 2):
        yield from partitions(height, pattern + (label,))

def check(lines):
    words = [tuple(decimal(s) for s in row) for width in range(3) for row in product(TOKENS, repeat=width)]
    count = 0
    groups = {}
    iterator = iter(lines)
    for height in range(4):
        for pattern in partitions(height):
            unique = len(set(pattern))
            group = 0
            for ids in product(range(31),repeat=unique):
                record = json.loads(next(iterator))
                values = [list(words[ids[i]]) for i in pattern]
                expected = {"values":values,"aliases":[pattern.index(i) for i in pattern],
                            "fresh":[height*(height-1)//2,True,True,True]}
                if (record["id"] != count or record["input"] != {"partition":list(pattern),"words":list(ids)}
                        or record["direct"] != expected):
                    raise ValueError(f"wrong alias, output value or mutation at {pattern}/{ids}")
                group += 1
                count += 1
            groups[str(pattern)] = group
    if next(iterator,None) is not None or count != 33729:
        raise ValueError("different bounded row population")
    return groups

def run(out):
    out.mkdir(parents=True, exist_ok=True)
    jdk = Path(runtime_jdk.home("21"))
    jar = SETUP / "artifacts/commons-lang-1635-landed.jar"
    catalog = read(FOLDER / "controls/libraries.json")
    if digest(jar) != catalog["commons-lang-1635-landed"]["sha256"]:
        raise ValueError("different Commons Lang artifact")
    with tempfile.TemporaryDirectory(prefix="all-boxed-rows-") as tmp:
        classes = Path(tmp)
        sources = [*sorted((FOLDER / "application").rglob("*.java")), *sorted((FOLDER / "adapter").rglob("*.java")),
                   *sorted((FOLDER / "driver").rglob("*.java")), HERE / "AllRows.java",
                   ROOT / "examples/tools/targets/java/org/intheloop/controls/Grid.java"]
        subprocess.run([jdk/"bin/javac","--release","21","-parameters","-proc:none","-cp",jar,"-d",classes,*sources],check=True)
        producer = classes / "datawork/RowMapper.class"
        javap = subprocess.check_output([jdk/"bin/javap","-v","-p",producer],text=True)
        sites = javap.split("BootstrapMethods:\n",1)[1].split("InnerClasses:",1)[0].strip()
        methods = re.findall(r"(?m)^\s*#\d+ REF_invokeStatic (\S+)",sites)
        if len(methods) != 4 or not any("NumberUtils.toInt:(Ljava/lang/String;)I" in m for m in methods):
            raise ValueError("expected the four original SAM implementation handles")
        if not all(desc in sites for desc in ["(Ljava/lang/String;)Ljava/lang/Integer;","(I)[Ljava/lang/Integer;","(I)[[Ljava/lang/Integer;"]):
            raise ValueError("wrong instantiated mapper or array factories")
        (out/"bootstrap.txt").write_text(sites+"\n")
        raw = classes / "observations.jsonl"
        cost = run_cmd([jdk/"bin/java","-Xmx256m","-cp",os.pathsep.join(map(str,[classes,jar])),"datawork.AllRows"],raw)
        if cost["exit"]: raise ValueError("row client failed")
        with raw.open() as lines: groups = check(lines)
        packed=out/"observations.jsonl.gz"
        packed.write_bytes(gzip.compress(raw.read_bytes(), mtime=0))
        write(out/"measurement.json",dict(cases=sum(groups.values()),partitions=groups,
              java=runtime_jdk.release(jdk),classSha256=digest(producer),jarSha256=digest(jar),
              bootstrapSha256=digest(out/"bootstrap.txt"),sources={p.name:digest(p) for p in sources},
              observationsSha256=digest(packed),cost={k:v for k,v in cost.items() if k!="log"}))

if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",type=Path,required=True)
    run(parser.parse_args().output)
