"""Generate the independent observations for the five original public callers."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "examples/tools"))
from targets.finite_oracle import Table

ADAPTERS = {363: "NestedBinary", 364: "EnumReader", 365: "AsyncTokens", 366: "DelimitedFields", 367: "DefaultReader"}


def csv_record(fields, delimiter):
    return delimiter.join('"' + s.replace('"', '""') + '"' if delimiter in s or '"' in s else s for s in fields)


def cases(number):
    if number == 363:
        def window(index, length):
            return dict(bytes=list(range(10 + 10 * index, 10 + 10 * index + length)),
                        remaining=length, exhausted=True)
        for pad in (0, 25):
            for index in (0, 1):
                for right in range(4):
                    for left in range(4):
                        yield dict(left=left, right=right, index=index, padding=pad), dict(
                            extent=window(index, (left, right)[index]), fresh=dict(sameStart=True, value=window(1, right)))
    elif number == 364:
        for reverse in (False, True):
            for wire, symbol in [(0, "A"), (2, "B")]:
                yield dict(wire=wire, reversed=reverse), dict(renamed=symbol, preserved=[symbol, "org.apache.avro.AvroTypeException"])
    elif number == 365:
        for pad in range(4):
            for mask in range(32):
                yield dict(cuts=mask, padding=pad), dict(
                    offsets=dict(trace=[3,1,1,9,2,5,4,5,6,3,1], matchesUnpadded=True), tokens=[3,9,4,3,1])
    elif number == 366:
        shapes = []
        for delimiter in ("||", "|||", "|~|"):
            for fields in (["a","b","c"], ["a","","b"], ["a","b"+delimiter+"c","d"], ["a","b",""]):
                shapes.append((delimiter, fields))
        shapes.extend([("||", ["a","b","c","d","","f"]), ("||", ["a","b||c","d","","f"])])
        controls = [("||", ["a|b"]), ("|||", ["a|b"]), ("|||", ["a||b"]), ("|~|", ["a|b"]),
                    ("|~|", ["a|~b"]), (",", ["a","b",""]), (",", ["a","b,c"])]
        for i, (d, fields) in enumerate(shapes):
            cd, control = controls[i % len(controls)]
            yield dict(delimiter=d, source=csv_record(fields, d), controlDelimiter=cd, controlSource=csv_record(control, cd)), dict(
                fields=[fields], prefixes=[control])
    elif number == 367:
        for marker in (None, -1, 0, 1):
            value = dict(size=0, marker=marker)
            yield dict(marker=marker), dict(union=value, direct=value)


WRONG = {
    363: [(36, "extent", dict(bytes=[16,1,0,0,0,20], remaining=6, exhausted=True)),
          (36, "fresh", dict(sameStart=False, value=dict(bytes=[20], remaining=1, exhausted=True)))],
    364: [(2, "renamed", "B"), (0, "preserved", ["A","A"])],
    365: [(32, "offsets", dict(trace=[3,1,1,9,2,5,4,6,6,3,1], matchesUnpadded=False)),
          (31, "tokens", [3,9,4,3,0])],
    366: [(3, "fields", [["a","b"]]), (2, "fields", [["a","bc","d"]]), (2, "prefixes", [["ab"]])],
    367: [(1, "union", dict(size=0, marker=None)), (3, "direct", dict(size=0, marker=0))]
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for number, adapter in ADAPTERS.items():
        folder, = (ROOT / "examples").glob(f"{number}-*")
        dest = folder / "controls/table.json"
        rows = [dict(id=i, input=inp, expected=expected) for i, (inp, expected) in enumerate(cases(number))]
        fields = {key: dict(entry=f"campaign.{adapter}#{key}(I)I", encoding="matches") for key in rows[0]["expected"]}
        body = '{\n  "schema": "finite-jvm-observations/v1",\n  "fields": ' + json.dumps(fields)
        body += ',\n  "cases": [\n' + ',\n'.join('    ' + json.dumps(r) for r in rows) + '\n  ]\n}\n'
        if args.check:
            if dest.read_text() != body:
                raise ValueError(f"{number}: frozen oracle differs")
        else:
            dest.write_text(body)
        table = Table(dest)
        truth = [dict(id=r["id"], input=r["input"], direct=dict(r["expected"])) for r in rows]
        if table.problems(truth):
            raise ValueError(f"{number}: correct observations rejected")
        for i, field, wrong in WRONG[number]:
            truth[i]["direct"][field] = wrong
            if table.problems(truth) != [[i, field]]:
                raise ValueError(f"{number}: wrong {field} accepted at {i}")
            truth[i]["direct"][field] = rows[i]["expected"][field]
        print(f"{number}: {len(rows)} inputs and {len(WRONG[number])} negative controls")


if __name__ == "__main__":
    main()
