"""Requalify the motivating original histories after changing the shared debugger boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from zipfile import ZipFile, ZIP_DEFLATED

from freeze import files
from charset import compile_to, command, ENV, OBSERVER, startup_facts
from first_use import control
from transfer_avro import avro

HERE = Path(__file__).resolve().parent
CASES = {
    "charset-small": ["charset.py", "small"],
    "charset-io": ["charset.py", "io"],
    "threeten-members": ["members.py"],
    "poi-tables": ["tables.py"],
    "batik-resource": ["files.py", "batik"],
    "properties-file": ["files.py", "file"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--qualify-first-use", action="store_true")
    args = parser.parse_args()
    scratch = Path(os.environ.get("TMPDIR") or Path.home()/".cache/in-the-loop/agent-tmp")
    if scratch == Path("/tmp") or Path("/tmp") in scratch.parents:
        scratch = Path.home()/".cache/in-the-loop/agent-tmp"
    scratch.mkdir(parents=True, exist_ok=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    source = hashlib.sha256(json.dumps(files(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="final-startup-originals-", dir=scratch) as tmp:
        work = Path(tmp)
        extra = {}
        if args.qualify_first_use:
            prestate = work / "first-use"
            prestate.mkdir()
            extra["firstUseControls"] = control(prestate)
            large = work / "ordered-avro"
            large.mkdir()
            row, = avro(large, fixed_bounds_only=True)["rows"]
            observed = row["record"]
            if not (row["verdict"]=="verified" and row["sameRegisteredState"] and observed["classes"]==220 and
                    observed["objects"]==1079 and observed["startupBoundary"]==extra["firstUseControls"]["cold"]["record"]["startupBoundary"]):
                raise ValueError("the fixed Avro bounds claim did not reproduce its registered fresh four-root state")
            extra["orderedAvroFirstUse"] = row
        tools, subject = work/"tools", work/"subject"
        compile_to(tools, sorted(OBSERVER.glob("*.java")))
        compile_to(subject, [HERE/"TableControls.java"], str(tools))
        failure = startup_facts.recover(command("TableControls$Failing#count()I","result == 0",subject,tools),
                                       work/"failed-startup",env=ENV,properties={"startup.fixture.fail":"yes"})
        if (failure.get("receiptId") or failure.get("retry") or failure["consumed"] or
                not any(e["type"]=="java.lang.IllegalArgumentException" for e in failure.get("failure",{}).get("exceptions",[]))):
            raise ValueError("failed startup did not remain a diagnostic: " + str(failure))
        rows = []
        for case, (script, *mode) in CASES.items():
            result = work/(case+".zip")
            subprocess.run([sys.executable, HERE/script, *mode, "--output", result], check=True, env=dict(os.environ, TMPDIR=tmp))
            data = result.read_bytes()
            with ZipFile(result) as archive:
                if archive.testzip() is not None:
                    raise ValueError("incomplete release qualification " + case)
                doc = json.loads(archive.read("scorecard.json"))
            cases = doc.get("rows", doc.get("cases"))
            rows.append({"case":case, "profiles":len(cases), "archive":result.name, "sha256":hashlib.sha256(data).hexdigest()})
        with ZipFile(args.output,"w",compression=ZIP_DEFLATED) as archive:
            archive.writestr("scorecard.json", json.dumps({"producer":source,"rows":rows,"failedStartup":failure,**extra},indent=2)+"\n")
            for row in rows:
                archive.write(work/row["archive"],row["archive"])
    print("all six original qualification matrices passed on the follow-up producer")


if __name__ == "__main__":
    main()
