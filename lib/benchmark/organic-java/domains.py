"""Regenerate the independent public-observation tables for the six organic Java PRs."""
import argparse
import copy
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
NAMES = {"353": "SumView", "354": "SurrogateCuts", "355": "WritableBuffer",
         "356": "OverflowNumber", "357": "BomReader", "358": "HexWrites"}


def units(text):
    data = text.encode("utf-16-be", "surrogatepass")
    return [int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data), 2)]


def whole_window(tokens, offset, width):
    # A token contributes its original units exactly when its full span lies in the window.
    result, start = [], 0
    for token in tokens:
        encoded = units(token)
        end = start + len(encoded)
        if offset <= start and end <= offset + width:
            result.extend(encoded)
        start = end
    return result


def rows(number):
    if number == "353":
        counts = (0, 1, 3, 2**30 - 1, 2**30, 2**30 + 1, 2**31 - 1)
        for a, b in itertools.product(counts, repeat=2):
            total = min(2**31 - 1, a + b)
            yield {"left": a, "right": b}, {"lookup": total, "size": total, "absent": 0,
                "entries": {"key": "a" if total else None, "count": total, "exhausted": True},
                "live": [[6, 6, 6], [7, 7, 7]]}
    elif number == "354":
        index = 0
        for n in range(5):
            for tokens in itertools.product(("a", "😀"), repeat=n):
                source = units("".join(tokens))
                for offset, width in itertools.product(range(len(source) + 2), repeat=2):
                    start, span = divmod(index % 36, 6)
                    yield {"units": source, "start": offset, "width": width}, {
                        "truncate": whole_window(tokens, offset, width),
                        "fixedCut": whole_window("a😀b", start, span),
                        "abbreviate": units(("😀" if index % 2 else "") + "...")}
                    index += 1
    elif number == "355":
        for capacity in range(6):
            for length in range(capacity + 1):
                first = {"first": "java.lang.IndexOutOfBoundsException", "position": 0}
                yield {"capacity": capacity, "length": length}, {
                    "bounds": [0, length, capacity, length],
                    "prefix": [[i + 1, 0] for i in range(length)], "rejected": first,
                    "directLimit": {"capacity": capacity, "limit": length, **first}}
    elif number == "356":
        for number_text in [str(2**64) + str(i) for i in range(10)] + ["10", "00", "01"]:
            valid = number_text[0] != "0"
            rejection = "peek:MalformedJsonException"
            yield {"text": number_text}, {"token": "NUMBER" if valid else rejection,
                                          "lexeme": number_text if valid else rejection}
    elif number == "357":
        for marks, cap in itertools.product(range(3), (1, 2, 100)):
            result = units("\ufeff" * max(marks - 1, 0) + "foo")
            yield {"marks": marks, "cap": cap}, {"chunked": result, "plain": result}
    elif number == "358":
        for digits in itertools.product("01AF", repeat=4):
            text = "".join(digits)
            expected = list(bytes.fromhex(text))
            for mask in range(8):
                boundaries = [0, *(i for i in (1, 2, 3) if mask & 1 << (i - 1)), 4]
                writes = [b - a for a, b in zip(boundaries, boundaries[1:])]
                yield {"hex": text, "writes": writes}, {"bytes": expected}
        for writes in ([3, 4, 3], [10], [2, 4, 4]):
            yield {"hex": "4142434445", "writes": writes}, {"bytes": list(b"ABCDE")}


def table(number):
    cases = [{"id": i, "input": args, "expected": expected} for i, (args, expected) in enumerate(rows(number))]
    fields = {k: {"entry": f"organic.{NAMES[number]}#{k}(I)I", "encoding": "matches"} for k in cases[0]["expected"]}
    return {"schema": "finite-jvm-observations/v1", "fields": fields, "cases": cases}


def wrong_results(number):
    """Deliberately wrong observations at specific boundary inputs, independent of either implementation."""
    if number == "353":
        return [(32, "lookup", -(2**31)), (32, "size", -(2**31)),
                (32, "entries", "java.lang.IllegalArgumentException"), (0, "absent", 1),
                (0, "live", [[6, 6, 6], [6, 6, 6]])]
    if number == "354":
        values = list(rows(number))
        cut = next(i for i, (a, _) in enumerate(values) if a == {"units": units("a😀a"), "start": 0, "width": 2})
        return [(cut, "truncate", [97, 0xd83d]), (2, "fixedCut", [97, 0xd83d]), (0, "abbreviate", [0xd83d, 46, 46, 46])]
    if number == "355":
        return [(18, "bounds", [0, 5, 5, 5]), (18, "prefix", [[1, 1], [2, 2], [3, 3]]),
                (18, "rejected", {"first": 4, "position": 0}),
                (18, "directLimit", {"capacity": 5, "limit": 5, "first": 4, "position": 0})]
    if number == "356":
        return [(0, "token", "peek:MalformedJsonException"), (0, "lexeme", str(2**64))]
    if number == "357":
        return [(6, "chunked", units("foo")), (8, "plain", units("foo"))]
    return [(2048, "bytes", list(b"ABCD"))]


def check_controls(number, path):
    import sys
    sys.path.insert(0, str(ROOT / "examples/tools"))
    from targets.finite_oracle import Table
    observer = Table(path)
    data = [{"id": i, "input": case["input"], "direct": copy.deepcopy(case["expected"])}
            for i, case in observer.cases.items()]
    if observer.problems(data):
        raise ValueError("the independent correct observations failed")
    for index, field, wrong in wrong_results(number):
        correct = data[index]["direct"][field]
        data[index]["direct"][field] = wrong
        if observer.problems(data) != [[index, field]]:
            raise ValueError(f"{number} field {field} failed to distinguish its wrong-result control")
        data[index]["direct"][field] = correct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for n in NAMES:
        folder, = (ROOT / "examples").glob(n + "-*")
        dest = folder / "controls/table.json"
        spec = table(n)
        # One complete observation per line keeps individual domain points reviewable.
        body = '{\n  "schema": "finite-jvm-observations/v1",\n  "fields": ' + json.dumps(spec["fields"]) + ',\n  "cases": [\n'
        body += ",\n".join("    " + json.dumps(c) for c in spec["cases"]) + "\n  ]\n}\n"
        if args.check:
            if dest.read_text() != body:
                parser.error(f"{dest} differs from its independent input/observation oracle")
        else:
            dest.write_text(body)
        check_controls(n, dest)
        print(n, len(spec["cases"]), "inputs,", len(wrong_results(n)), "wrong-result controls rejected")


if __name__ == "__main__":
    main()
