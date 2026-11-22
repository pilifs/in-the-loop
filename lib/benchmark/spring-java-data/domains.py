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


def roles():
    edges = {"A": ("B",), "B": ("C", "D")}
    for prefix in ("ROLE_", "CUSTOM_PREFIX_"):
        for mask in range(16):
            reached = {name for i, name in enumerate("ABCD") if mask & (1 << i)}
            work = list(reached)
            while work:
                for dest in edges.get(work.pop(), ()):
                    if dest not in reached:
                        work.append(dest)
                        reached.add(dest)
            names = sorted(prefix + name for name in reached)
            grant = "D" in reached
            yield {"prefix": prefix, "subset": mask}, {
                "legacyNames": names, "legacyDecision": grant,
                "fluentNames": {"present": names, "absent": None},
                "fluentDecision": {"present": grant, "absent": None}}


def matrices():
    words = [list(row) for width in range(3) for row in product(range(2), repeat=width)]
    for height in range(4):
        for words_in_matrix in product(words, repeat=height):
            rows = list(words_in_matrix)
            rectangle = len({len(row) for row in rows}) <= 1
            if not rectangle:
                yield rows, {"contract": "java.lang.IllegalArgumentException", "rectangle": None}
                continue
            # The singleton empty row is an identity fast path on both original revisions.
            transposed = [[]] if rows == [[]] else [list(column) for column in zip(*rows)]
            yield rows, {"contract": transposed, "rectangle": [transposed, True]}


def accessors():
    controls = [("Budget", "budget", "Plain", "name", "name"),
                ("Issue", "issue", "Bean", "getName", "name"),
                ("Widget", "getWidget", "Extra", "getWidget", "widget")]
    for component, method, other, getter, expected in controls:
        yield [component, method, other, getter], {"components": method, "getters": expected}


def searches():
    alphabet = (0x7ff8000000000001, 0xfff8000000000011, 1 << 63, 0, 0x3ff0000000000000)
    def inputs():
        for start in (-1, 0, 1):
            yield None, start
        for width in range(4):
            for word in product(alphabet, repeat=width):
                for start in range(-1, width + 2):
                    yield word, start
        yield (0xfff0000000000000, alphabet[0], 0x7ff0000000000000, alphabet[2], 0), 0

    def nan(bits):
        return (bits >> 52) & 0x7ff == 0x7ff and bits & ((1 << 52) - 1) != 0

    def equal(left, right):
        return left == right or nan(left) and nan(right) or (left | right) & ((1 << 63) - 1) == 0

    for word, start in inputs():
        signed = None if word is None else [v - (1 << 64) if v >> 63 else v for v in word]
        indices = [next((i for i in range(max(0, start), len(word or ())) if equal(word[i], value)), -1)
                   for value in alphabet]
        yield {"bits": signed, "start": start}, {"nans": [indices[:2], signed], "numbers": [indices[2:], signed]}


def dates():
    from datetime import datetime, timezone
    instant = int(datetime(2009, 10, 31, 1, 5, tzinfo=timezone.utc).timestamp()) * 1000
    local, invalid, iso = "10/31/09 1:05", "bad-date", "2009-10-31T01:05:00.000Z"
    error = [None, 1, "local", invalid, invalid]
    yield {"history": 0}, {"annotated": [[instant, 0, None, None, local]],
                           "preservation": [[instant, 0, None, None, iso]]}
    yield {"history": 1}, {"annotated": [error, [instant, 1, "local", invalid, invalid]], "preservation": [error]}


def precision():
    from decimal import Decimal
    cases = [("0.100000001490116121", "0.1", ["Float", 0x3dcccccd]),
             ("0.100000001490116122", "0.5", ["Float", 0x3f000000]),
             ("-0.100000001490116121", "17", ["Integer", 17])]
    for text, control, expected in cases:
        sign, digits, exponent = Decimal(text).as_tuple()
        coefficient = ("-" if sign else "") + "".join(map(str, digits))
        yield [text, control, "1eE"], {"precise": ["BigDecimal", coefficient, -exponent],
                                       "preserved": [expected, "java.lang.NumberFormatException"]}


GRIDS = {368: ("springwork.BindingChecks", binding), 369: ("datawork.RowChecks", boxed),
         370: ("springwork.RoleChecks", roles), 371: ("datawork.Matrices", matrices),
         372: ("springwork.Accessors", accessors), 373: ("datawork.NanSearch", searches),
         374: ("springwork.DateEdits", dates), 375: ("datawork.Decimals", precision)}


def table(folder, entry, rows, check=False):
    data = [dict(id=i, input=inp, expected=expected) for i, (inp, expected) in enumerate(rows)]
    fields = {key: {"entry": f"{entry}#{key}(I)I", "encoding": "matches"} for key in data[0]["expected"]}
    if entry == "springwork.RoleChecks":
        for key in ("fluentNames", "fluentDecision"):
            fields[key]["selection"] = "api"
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
    for number, (cls, grid) in GRIDS.items():
        folder, = (ROOT / "examples").glob(f"{number}-*")
        print(folder.name, table(folder, cls, grid(), args.check))
