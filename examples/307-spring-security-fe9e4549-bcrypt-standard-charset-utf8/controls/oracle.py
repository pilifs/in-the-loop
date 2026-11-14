"""307's independent oracle: written from the bcrypt scheme's definition and Java's String.getBytes specification, not
from either revision's code. It computes no cipher.

What it states, for BCrypt.hashpw(String password, String salt), on the probes of replay/probes.json:

1. The password's bytes are its UTF-8 encoding, as java.lang.String.getBytes(UTF-8) specifies it: each well-formed
   surrogate pair is one 4-byte sequence, and each isolated surrogate is malformed input, replaced by the charset's
   default replacement byte, '?' (0x3F). The oracle encodes the UTF-16 code units itself.
2. A null password is a NullPointerException, whatever the salt: the conversion is the method's first step at both
   revisions, and Java throws on a call on null. Only the exception's class is observed: since JDK 14 the message names
   the method called on null, which is exactly what the patch changes (getBytes(String) against getBytes(Charset)).
3. A salt in bcrypt's format, "$2" [a b x y]? "$" cost "$" 22 characters of bcrypt's base64, with cost 04..31, is
   valid; a stored hash (the same followed by 31 more characters) is a valid salt and only its first part is read.
   Every other salt of the probes (null, empty, cost 03, too short) is an IllegalArgumentException, the class
   upstream's BCryptTests expect of the unchanged callee hashpw(byte[],String).
4. With a valid salt the result is the salt's own prefix ("$2a$06$" and the 22 salt characters, or "$2$05$" and 22)
   followed by 31 characters of bcrypt's base64 alphabet: 60 characters, or 59 with no minor revision.
5. The key: the password's bytes, with a NUL appended when the salt has a minor revision ('a' here), read cyclically:
   bcrypt's key schedule consumes 72 bytes of that cycle (18 words of 4 bytes) and nothing else. So the result is a
   function of the salt and those 72 key bytes: two probes with the same salt and the same 72 key bytes give the same
   result (a 72-byte password and its 73-byte extension; 'a'*71 and 'a'*71 + NUL; 'ab' and 'ab' NUL 'ab'). With no
   minor revision an empty password is an empty key, which the cyclic read can't take: an
   ArrayIndexOutOfBoundsException (a prediction from the scheme, checked by the replay).
6. Assumed, not derived: different 72-byte keys under one salt give different results on these probes (bcrypt has no
   known collision; upstream's testInternationalChars makes the same assumption for 'ππππππππ' and '????????').
7. Known answers: upstream's test vectors, at both commits (replay/probes.json's known_answers).

Each revision's driver output (replay/driver, one JSON line per probe) is checked against these, and the revisions'
lines against each other. Rules 5 and 6 are what make the UTF-8 encoding observable without a cipher: the US-ASCII
mutant (controls/us-ascii.patch) encodes 'é' as '?', so it gives 'é' and '?' one result (rule 6 fails), and it moves
the 72-byte cut in 'a'*70 + 'é' (rule 5 fails between it and its 73-byte extension). The oracle never calls the
implementation under test; it reads replay/probes.json, parses nothing else and downloads nothing.

    python3 -I oracle.py argv            the driver's argument vector, one argument per line
    python3 -I oracle.py table           each probe's code units, UTF-8 bytes, key class and expected outcome
    python3 -I oracle.py check FILE...   each file one revision's driver stdout; exit 1 if any disagrees
"""

import json
import re
import sys
from pathlib import Path

PROBES_FILE = Path(__file__).resolve().parent.parent / "replay" / "probes.json"
BASE64 = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
SALT = re.compile(r"\$2([abxy]?)\$(\d\d)\$([./A-Za-z0-9]{22})")
NPE = "java.lang.NullPointerException"
IAE = "java.lang.IllegalArgumentException"
AIOOBE = "java.lang.ArrayIndexOutOfBoundsException"
KEY_BYTES = 72


def units(s):
    """The UTF-16 code units of a Python string (isolated surrogates kept)."""
    raw = s.encode("utf-16-le", "surrogatepass")
    return tuple(int.from_bytes(raw[i:i + 2], "little") for i in range(0, len(raw), 2))


def password_units(spec):
    """A probe's password, as code units: None, or the [text, count] segments concatenated."""
    if spec is None:
        return None
    return tuple(u for text, count in spec for _ in range(count) for u in units(text))


def utf8(code_units):
    """Rule 1: UTF-8 bytes of a sequence of UTF-16 code units, an isolated surrogate replaced by '?'."""
    out, i = bytearray(), 0
    while i < len(code_units):
        u = code_units[i]
        if 0xD800 <= u <= 0xDBFF and i + 1 < len(code_units) and 0xDC00 <= code_units[i + 1] <= 0xDFFF:
            cp = 0x10000 + ((u - 0xD800) << 10) + (code_units[i + 1] - 0xDC00)
            i += 2
        elif 0xD800 <= u <= 0xDFFF:
            out.append(0x3F)
            i += 1
            continue
        else:
            cp = u
            i += 1
        if cp < 0x80:
            out.append(cp)
        elif cp < 0x800:
            out += bytes([0xC0 | cp >> 6, 0x80 | cp & 0x3F])
        elif cp < 0x10000:
            out += bytes([0xE0 | cp >> 12, 0x80 | cp >> 6 & 0x3F, 0x80 | cp & 0x3F])
        else:
            out += bytes([0xF0 | cp >> 18, 0x80 | cp >> 12 & 0x3F, 0x80 | cp >> 6 & 0x3F, 0x80 | cp & 0x3F])
    return bytes(out)


def characters(code_units):
    """The password's characters as code-unit tuples: a well-formed surrogate pair is one character."""
    out, i = [], 0
    while i < len(code_units):
        pair = 0xD800 <= code_units[i] <= 0xDBFF and i + 1 < len(code_units) and 0xDC00 <= code_units[i + 1] <= 0xDFFF
        out.append(tuple(code_units[i:i + 2 if pair else 1]))
        i += 2 if pair else 1
    return out


def parse_salt(salt):
    """Rule 3: (minor, cost, salt characters, the result's prefix) of a valid salt, or None."""
    if salt is None:
        return None
    m = SALT.match(salt)
    if not m or not 4 <= int(m.group(2)) <= 31:
        return None
    return m.group(1), int(m.group(2)), m.group(3), m.group(0)


def key72(password_bytes, minor):
    """Rule 5: the 72 key bytes bcrypt reads, or None for an empty key."""
    key = password_bytes + (b"\0" if minor else b"")
    if not key:
        return None
    return bytes(key[i % len(key)] for i in range(KEY_BYTES))


def expected(password, salt):
    """('threw', class) or ('returned', (prefix, key class)) by rules 2, 3 and 5."""
    if password is None:
        return ("threw", NPE)
    parsed = parse_salt(salt)
    if parsed is None:
        return ("threw", IAE)
    minor, cost, chars, prefix = parsed
    key = key72(utf8(password), minor)
    if key is None:
        return ("threw", AIOOBE)
    return ("returned", (prefix, (minor, cost, chars, key)))


def token(u):
    """The driver's spelling of one argument: `null`, or `u` and the code units in hex, comma-separated."""
    return "null" if u is None else "u" + ",".join(f"{c:04x}" for c in u)


def load(path=PROBES_FILE):
    """(probes, known answers): probes as (password units, salt), known answers as {(token, token): value}."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    salts = data["salts"]
    probes = [(password_units(p["password"]), salts[p["salt"]]) for p in data["probes"]]
    if len(set(probes)) != len(probes):
        raise SystemExit("a probe is listed twice")
    known = {}
    for k in data["known_answers"]:
        probe = (password_units(k["password"]), salts[k["salt"]])
        if probe not in probes:
            raise SystemExit(f"a known answer is not a probe: {k}")
        known[key(probe)] = k["value"]
    return probes, known


def key(probe):
    password, salt = probe
    return (token(password), token(None if salt is None else units(salt)))


def argv(probes):
    return [t for probe in probes for t in key(probe)]


def read(lines, probes):
    """{(password token, salt token): record} from one revision's driver lines. An unreadable line or a missing probe
    is a replay problem: it raises, never counts as a disagreement."""
    seen = {}
    for line in lines:
        if line.strip():
            record = json.loads(line)
            seen[(record["password"], record["salt"])] = record
    missing = [key(p) for p in probes if key(p) not in seen]
    if missing:
        raise ValueError(f"no observation for {missing}: an incomplete replay")
    return seen


def check(lines, probes, known):
    """[(probe, problem)] for each observation of one revision the statement disagrees with."""
    seen = read(lines, probes)
    problems = []
    by_class = {}
    for probe in probes:
        k, record = key(probe), seen[key(probe)]
        kind, what = expected(*probe)
        if kind == "threw":
            if record["outcome"] != "threw" or record["exception"] != what:
                problems.append((k, f"{record['outcome']} {record.get('exception', record.get('value'))}, the statement says {what}"))
            continue
        if record["outcome"] != "returned":
            problems.append((k, f"threw {record.get('exception')}, the statement says a result"))
            continue
        prefix, cls = what
        value = record["value"]
        tail = value[len(prefix):] if isinstance(value, str) else ""
        if not (isinstance(value, str) and value.startswith(prefix) and len(tail) == 31 and all(c in BASE64 for c in tail)):
            problems.append((k, f"returned {value!r}, not {prefix!r} and 31 characters of bcrypt's base64 (rule 4)"))
        if k in known and value != known[k]:
            problems.append((k, f"returned {value!r}, upstream's test vector is {known[k]!r} (rule 7)"))
        by_class.setdefault(cls, []).append((k, value))
    for members in by_class.values():
        if len({v for _, v in members}) > 1:
            problems.append(([m[0] for m in members], "the same salt and 72 key bytes, different results (rule 5)"))
    firsts = {}
    for cls, members in by_class.items():
        value = members[0][1]
        if value in firsts and firsts[value] != cls:
            problems.append(([members[0][0]], f"one result for two different 72-byte keys under one salt (rule 6): {value!r}"))
        firsts.setdefault(value, cls)
    return problems


def differences(before_lines, after_lines, probes):
    """[(probe, before record, after record)] where two revisions' observations differ: the preservation side."""
    before, after = read(before_lines, probes), read(after_lines, probes)
    observed = lambda r: (r["outcome"], r.get("value"), r.get("exception"))
    return [(key(p), before[key(p)], after[key(p)]) for p in probes if observed(before[key(p)]) != observed(after[key(p)])]


def coverage(probes, known):
    """What the brief and the acceptance contract ask the probes to reach; a list of what is missing."""
    lengths = {len(utf8(p)) for p, s in probes if p is not None and parse_salt(s)}
    widths = {len(utf8(c)) for p, _ in probes if p for c in characters(p) if not (len(c) == 1 and 0xD800 <= c[0] <= 0xDFFF)}
    pairs = any(0xD800 <= u <= 0xDBFF for p, _ in probes if p for u in p)
    lone = any(utf8(p).count(b"?") > sum(1 for u in p if u == 0x3F) for p, _ in probes if p)
    classes = {}
    for probe in probes:
        kind, what = expected(*probe)
        if kind == "returned":
            classes.setdefault(what[1], set()).add(probe[0])
    shared = any(len(v) > 1 for v in classes.values())
    stored = [s for _, s in probes if s and len(s) == 60]
    ascii_short = [p for p, _ in probes if p and len(p) <= 2 and any(u >= 0x80 for u in p)]
    missing = []
    for want, have in [("empty password", 0 in lengths), ("71, 72 and 73 UTF-8 bytes", {71, 72, 73} <= lengths),
                       ("1-, 2-, 3- and 4-byte characters", {1, 2, 3, 4} <= widths), ("a surrogate pair", pairs),
                       ("an isolated surrogate", lone), ("two passwords with one key", shared),
                       ("a stored hash as the salt", bool(stored)), ("a short non-ASCII password", bool(ascii_short)),
                       ("a known answer", bool(known)), ("a null password", any(p is None for p, _ in probes)),
                       ("an invalid salt", any(s is not None and parse_salt(s) is None for _, s in probes))]:
        if not have:
            missing.append(want)
    return missing


def table(probes):
    names = {}
    for probe in probes:
        kind, what = expected(*probe)
        if kind == "returned":
            names.setdefault(what[1], f"K{len(names) + 1}")
        p, s = probe
        row = {"salt": s, "units": None if p is None else len(p), "utf8": None if p is None else len(utf8(p))}
        row["expected"] = what if kind == "threw" else f"{what[0]}… key class {names[what[1]]}"
        print(json.dumps(row, ensure_ascii=False))


# The runner's interface (examples/tools/targets/runtime.py's docstring, "the oracle convention"): what
# runtime.run_controls passes the driver, and how workflow_ingest reads one revision's lines. An exception is a replay
# that can't be judged, never a violation.

def _checked_probes():
    probes, known = load()
    missing = coverage(probes, known)
    if missing:
        raise ValueError(f"the probes don't reach: {', '.join(missing)}")
    return probes, known


def driver_args():
    """The driver's whole argument vector: a password and a salt per probe."""
    return argv(_checked_probes()[0])


def problems(lines):
    """[(probe, problem)] where one revision's lines disagree with the statement (rules 1-7)."""
    probes, known = _checked_probes()
    return check(lines, probes, known)


def main(args):
    probes, known = load()
    missing = coverage(probes, known)
    if missing:
        raise SystemExit(f"the probes don't reach: {', '.join(missing)}")
    if args[:1] == ["argv"]:
        print("\n".join(argv(probes)))
        return 0
    if args[:1] == ["table"]:
        table(probes)
        return 0
    if args[:1] == ["check"] and len(args) > 1:
        outputs = [Path(f).read_text(encoding="utf-8").splitlines() for f in args[1:]]
        failed = False
        for name, lines in zip(args[1:], outputs):
            problems = check(lines, probes, known)
            failed = failed or bool(problems)
            print(json.dumps({"file": name, "probes": len(probes), "problems": problems}, ensure_ascii=False))
        for name, lines in zip(args[2:], outputs[1:]):
            diff = differences(outputs[0], lines, probes)
            failed = failed or bool(diff)
            print(json.dumps({"file": name, "against": args[1], "differences": [d[0] for d in diff]}))
        return 1 if failed else 0
    raise SystemExit(__doc__)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
