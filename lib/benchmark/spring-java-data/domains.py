"""Independent finite observations for the Spring and Java data callers."""
import json
from itertools import permutations, product
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
TOKENS = ("-2", "bad", None, "2147483648", "+7")


def binding():
    for shared in (False, True):
        for order in permutations(range(3)):
            primary = ["initial", 1]
            backup = primary if shared else list(primary)
            beans, ledger = [], []
            errors = []
            for edit in order:
                if edit == 0:
                    primary[0] = "Kim"
                elif edit == 1:
                    errors.append(("backup.count", "oops"))
                else:
                    primary[1] = 7
                beans.append([*primary, *backup, shared, True])
                ledger.append([len(errors), *(errors[0] if errors else (None, None)), primary[1], backup[1]])
            yield {"shared": shared, "order": list(order)}, {"beans": beans, "ledger": ledger}


def decimal(text):
    if not text:
        return 0
    digits = text.lstrip("+-") if text[0] in "+-" else text
    if len(text) - len(digits) > 1 or not digits or any(ch not in "0123456789" for ch in digits):
        return 0
    number = int(text, 10)
    return number if -(1 << 31) <= number < 1 << 31 else 0


def boxed():
    words = [list(chars) for width in range(3) for chars in product(TOKENS, repeat=width)]
    def row(rows, aliases):
        return {"rows": rows, "aliases": aliases}, {
            "values": [[decimal(s) for s in word] for word in rows],
            "fresh": [len(rows) * (len(rows) - 1) // 2, True, True, True]}
    yield row([], [])
    for indices, aliases in [((0,), [0]), ((0, 0), [0, 0]), ((0, 0), [0, 1]),
                             ((0, 5, 0), [0, 1, 0]), ((0, 0, 5), [0, 1, 2]), ((0, 5, 6), [0, 1, 2])]:
        for first in range(len(words)):
            yield row([words[(first + step) % len(words)] for step in indices], aliases)


def table(folder, entry, rows, check=False):
    data = [dict(id=i, input=inp, expected=expected) for i, (inp, expected) in enumerate(rows)]
    fields = {key: {"entry": f"{entry}#{key}(I)I", "encoding": "matches"} for key in data[0]["expected"]}
    text = '{"schema":"finite-jvm-observations/v1","fields":' + json.dumps(fields) + ',"cases":[\n'
    text += ",\n".join(json.dumps(row, separators=(",", ":")) for row in data) + "\n]}\n"
    path = folder / "controls/table.json"
    if check:
        if path.read_text() != text:
            raise ValueError(f"{folder.name}: independent oracle differs")
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return len(data)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    for number, cls, grid in [(368, "springwork.BindingChecks", binding), (369, "datawork.RowChecks", boxed)]:
        folder, = (ROOT / "examples").glob(f"{number}-*")
        print(folder.name, table(folder, cls, grid(), args.check))
