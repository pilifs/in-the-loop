"""Test transfers between isolated axes, locale profiles and sheet histories, and measure Kryo positions."""
from decimal import Decimal
import os
from pathlib import Path
import subprocess
import tempfile

from register import HERE, jdk, manifests, read, upgrade_replay, write


def require(ok, why):
    if not ok: raise ValueError(why)


def cold(case):
    summary = HERE/"results"/case/"first/summary.json"
    return read(summary)["runs"]["cold"]["claims"]


def windows(value):
    return [tuple(Decimal(x) for x in interval.split(",")) for interval in value.split("/")]


def axes():
    rows = []
    for claim in cold("J03"):
        for child in claim["children"]:
            for side in ("old","new"):
                start = [(Decimal(0), Decimal(10))]*4
                for step, text in enumerate(child[side]["return"].split("|")):
                    end = windows(text)
                    for axis in (0,1):
                        pair, solo = axis, axis+2
                        width = start[pair][1]-start[pair][0]
                        require(all(end[i][1]-end[i][0] == start[i][1]-start[i][0] == width for i in (pair,solo)),"axis width changed")
                        pshift = (end[pair][0]-start[pair][0])/width
                        sshift = (end[solo][0]-start[solo][0])/width
                        same = start[pair] == start[solo] and pshift == sshift
                        matches = end[pair] == end[solo]
                        require(not same or matches, "same axis inputs, different public ranges")
                        rows.append({"args":child["arguments"],"side":side,"step":step+1,"axis":axis,
                                     "sameStartingRange":start[pair] == start[solo],"pairDisplacementInWidths":str(pshift),
                                     "singleDisplacementInWidths":str(sshift),"eligible":same,"sameReturnedRange":matches})
                    start = end
    require(sum(r["eligible"] for r in rows) == 44 and sum(r["sameReturnedRange"] for r in rows) == 46 and len(rows) == 48,
            "unexpected single-axis transfer")
    return rows


def weeks():
    dates = {}
    for node in cold("J04"):
        for c in node["children"]:
            locale,rule = c["arguments"]
            dates[locale,rule] = {s:c[s]["return"].split("/")[-1] for s in ("old","new")}
    for locale in ("en-US","fr-FR","ar-EG"):
        require(dates[locale,"default"]["new"] == dates[locale,"MO"]["new"] == dates["fr-FR","default"]["new"],
                "fixed default no longer agrees with explicit Monday across all three profiles")
        require(dates[locale,"default"]["old"] == dates[locale,"MO" if locale=="fr-FR" else "SU"]["old"], "original default differs")
    return {locale:dates[locale,"default"] for locale in ("en-US","fr-FR","ar-EG")}


def positions():
    folder = HERE/"cases/J10"
    java = jdk(read(folder/"case.json"))/"bin"
    result = {}
    with tempfile.TemporaryDirectory(prefix="kryo-position-") as temp:
        for side,graph in manifests(folder).items():
            classes = Path(temp)/side
            classes.mkdir()
            cp = os.pathsep.join(e["file"] for e in graph["classpath"])
            subprocess.run([java/"javac","-proc:none","-cp",cp,"-d",classes,folder/"StreamPosition.java",folder/"UpgradeProbe.java"],check=True)
            for kind in ("ordinary","abstract"):
                cmd = [java/"java","-Xmx96m","-Djava.io.tmpdir="+temp,"-cp",str(classes)+os.pathsep+cp,"StreamPosition",kind]
                first = subprocess.check_output(cmd,text=True,cwd=classes).splitlines()
                require(subprocess.check_output(cmd,text=True,cwd=classes).splitlines() == first, "byte positions changed on repeat")
                writes = [line.split()[1:] for line in first if line.startswith("write ")]
                reads = [line.split()[1:] for line in first if line.startswith("read ")]
                failure = [line for line in first if line.startswith("failure ")]
                length,complete = map(int,first[-1].split()[1:])
                require(writes == reads and int(reads[-1][1]) == complete and
                        (failure == ["failure java.lang.Enum IllegalArgumentException"] if side=="old" and kind=="abstract" else not failure and length==complete),
                        "inconsistent partial stream or successful cursor")
                result[side+"-"+kind] = {"writes":writes,"reads":reads,"failure":failure,"streamBytes":length,"completeBytes":complete}
    return result


def filtered_block():
    folder = HERE/"cases/J14"
    java = jdk(read(folder/"case.json"))/"bin"
    result = {}
    with tempfile.TemporaryDirectory(prefix="lucene-filter-") as temp:
        for side, graph in manifests(folder).items():
            classes = Path(temp)/side
            classes.mkdir()
            cp = os.pathsep.join(e["file"] for e in graph["classpath"])
            subprocess.run([java/"javac","-proc:none","-cp",cp,"-d",classes,folder/"FilteredBlock.java"],check=True)
            for extra in ("absent","missing","valued"):
                cmd = [java/"java","-Xmx96m","-Djava.io.tmpdir="+temp,"-cp",str(classes)+os.pathsep+cp,"FilteredBlock",extra]
                value = subprocess.check_output(cmd,text=True,cwd=classes).strip()
                key = "30" if side == "old" or extra == "absent" else "null"
                require(value == f"block={1 if extra == 'absent' else 2} selected=1 sort={key}","physical block discriminator failed")
                result[side+"-"+extra] = value
    return result


if __name__ == "__main__":
    poi = read(HERE/"results/J05/first/summary.json")["runs"]
    warm = next(r for r in poi["warm"]["claims"] if r["id"] == "unmoved-object")
    clean = next(r for r in poi["clean"]["claims"] if r["id"] == "unmoved-object")
    require(warm["children"] == clean["children"] and all(a["action"]=="exact reuse" for a in warm["execution"].values()),"different untouched public evidence")
    report = {"axes":axes(),"defaultWeeks":weeks(),"untouchedHyperlinks":{"warm":warm["execution"],"clean":clean["execution"]},
              "kryo":positions(),"filteredBlock":filtered_block(),
              "frozenSummaries":{c:upgrade_replay.sha(HERE/"results"/c/"first/summary.json") for c in ("J03","J04","J05","J10","J14")}}
    write(HERE/"results/transfer-controls.json",report)
    print("48 axis comparisons, three default week profiles, untouched hyperlink reuse, eight Kryo streams and six one-parent index readbacks checked")
