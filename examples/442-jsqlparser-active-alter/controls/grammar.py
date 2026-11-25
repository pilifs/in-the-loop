"""Check the two deparser outputs against the PostgreSQL dialect and a real PostgreSQL server."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[1]
sys.path.insert(0, str(EXAMPLES / "tools"))
from targets import public_comparison as replay
from targets.public_postgres import postgres


def run():
    runtime = replay.read(HERE.parent / "runtime.json")
    quartz = replay.read((next(EXAMPLES.glob("434-*"))) / "runtime.json")
    database = quartz["deployments"]["postgres16"]
    cache = Path(os.environ.get("PUBLIC_COMPARISON_CACHE", Path.home()/".cache/in-the-loop"/runtime["cache"]))
    jdk = Path(os.environ.get("PUBLIC_COMPARISON_JDK", Path.home()/".sdkman/candidates/java"/runtime["jdk"]))
    sha = replay.upgrade_replay.sha
    parser, = runtime["deployments"]["pins"]["classpath"]["fix"]
    driver, = (p for p in database["classpath"]["fix"] if Path(p).name.startswith("postgresql-"))
    if (sha(jdk/"release") != runtime["jdkReleaseSha256"] or sha(cache/parser) != runtime["sha256"][parser]
            or sha(cache/driver) != quartz["sha256"][driver]):
        raise ValueError("registered JDK, parser, or JDBC driver changed")
    with tempfile.TemporaryDirectory(prefix="pg-grammar-") as t, postgres(database["postgresImage"]) as env:
        work = Path(t)
        cp = os.pathsep.join(str(cache/p) for p in (parser,driver))
        source = HERE/"Grammar.java"
        launch = replay.upgrade_replay.LAUNCHER
        subprocess.run([jdk/"bin/javac","-g","-proc:none","-cp",cp,"-d",work,launch,source],check=True)
        observed = replay.observe(jdk,str(work)+os.pathsep+cp,work,"Grammar",[],
                                  {"net.sf.jsqlparser.parser.CCJSqlParserUtil":cache/parser,
                                   "org.postgresql.Driver":cache/driver},label="PostgreSQL grammar",service_env=env)
        expected = ("with tail=JSQLParserException/42601 without tail=ALTER TABLE t ALTER COLUMN id TYPE INT "
                    "USING id + 102/id=103 exhausted=true")
        if observed != {"return":expected}: raise ValueError(observed)
        return {"postgresVersion":env["PUBLIC_COMPARISON_PG_VERSION"],"image":database["postgresImage"],
                "sourceSha256":sha(source),"callerClassSha256":sha(work/"Grammar.class"),
                "parserSha256":sha(cache/parser),"driverSha256":sha(cache/driver),"outcome":observed}


if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--record",action="store_true")
    args=ap.parse_args()
    result=run()
    receipt=HERE/"postgres.json"
    if args.record: receipt.write_text(json.dumps(result,indent=2)+"\n")
    elif replay.read(receipt)!=result: raise SystemExit("fresh SQL observations differ")
    print(result["outcome"]["return"])
