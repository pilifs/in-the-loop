"""Delegated redaction decisions: the watcher of a run as an actor of its own, when a person has said so.

Off unless a person turns it on. Until then every decision in the allow list and the reviewed findings is a
person's, as before (sync.py, "a person's decisions, and a record of them").

  sync.py delegate status            whether it is on, for which watcher, and whether the record verifies
  sync.py delegate request --run R   the watcher asks: its client process is written down, and a code is printed
  sync.py delegate on CODE [--fresh] a person, at their terminal, grants that request (--fresh: earlier watcher
                                     decisions that are not yet on main stop counting)
  sync.py delegate off               anyone: the watcher's decisions that are not yet on main stop counting at once

What the watcher may then do, each recorded with who, which run, the finding's id, the action, its scope, the policy,
the reason and the evidence:

  sync.py delegate approve ID... --evidence KIND:DETAIL --reason TEXT
        approve proposals whose value has a known, benign origin that this command can check: a file `main` already
        publishes, a tracked fixture, an object or digest of this repository, a log's own name. A `long-token`
        needs such evidence: its shape alone establishes nothing. The kinds the redactor removes stay refused.
  sync.py delegate withhold SESSION SHA256 --reason TEXT
        private-only: a log that is not uploaded is sealed in the restricted archive, removed here and marked
        withdrawn in its manifest, so git says truthfully that it was never published.
  sync.py delegate mask ID... --reason TEXT
        an ambiguous value is added to this machine's own redactions, so every later log omits it; logs not yet
        uploaded that hold it are withheld; published ones are escalated.

A person does the last two with `sync.py review withhold` and `sync.py review mask`, from their terminal. And:

  sync.py review escalate ID... --reason TEXT        (anyone)
        one masked record for a person: what is affected, what was contained, what remains to decide.
  sync.py review close ESCALATION --reason TEXT      (a person)

Authority is bound to the watcher's launch: the client process (Claude Code's or Codex's) that asked, by its pid,
start time and this boot. A command counts as the watcher's when the nearest client process above it is that one.
An environment variable or a file in the checkout says nothing, and a watcher that ended has no authority left. The
grant, the record of decisions (one JSON line each, chained by hash and signed with a key kept beside the archive's
tokens) and the escalations are under ~/.local/state/llm-traces, outside every checkout; the record is also sealed
into the restricted archive as it grows. `check`, `land`, `checkpoint` and `promote` count a decision as taken when
it is on `main`, recorded as a person's, or recorded here with the same bytes, under the policy in force, while the
delegation is on. Everything on this machine runs as one user, so this is evidence against a mistake or a careless
edit, and the remote copy is what a forger would also have to change.

The module is given sync.py's own module object (`s`).
"""
from __future__ import annotations

import fcntl
import gzip
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = "itl-delegation/v1"
CLIENTS = ("claude", "codex")
CONFIRM = "delegate"
EVIDENCE = {
    "main-file": "PATH: the value is in that file as `main` already publishes it",
    "tracked-file": "PATH: the value is in that committed file of this line (a fixture)",
    "content-digest": "PATH: the value is the SHA-256, SHA-1, SHA-512 or MD5 of that committed file",
    "git-object": "the value is the id of a commit, tree or blob of this repository",
    "trace-log": "the value is the SHA-256 that names a session's log",
    "public": "URL: where the value is published (not checked here; not enough for a long-token)",
}


class Refused(Exception):
    pass


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def grant_path(s) -> Path:
    return s.STATE / "delegation.json"


def ledger_path(s) -> Path:
    return s.STATE / "watcher-decisions.jsonl"


def escalations_path(s) -> Path:
    return s.STATE / "escalations.jsonl"


def key_path() -> Path:
    return Path(os.environ.get("ITL_DELEGATION_KEY") or Path.home() / ".config" / "in-the-loop" / "delegation-key")


# --------------------------------------------------------------------------- whose command this is

def process(pid: int) -> dict | None:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text()
    except OSError:
        return None
    comm = stat[stat.index("(") + 1:stat.rindex(")")]
    rest = stat[stat.rindex(")") + 2:].split()
    return {"pid": pid, "comm": comm, "ppid": int(rest[1]), "start": int(rest[19])}


def boot() -> str:
    try:
        return Path("/proc/sys/kernel/random/boot_id").read_text().strip()
    except OSError:
        return ""


def client_process(pid: int | None = None) -> dict | None:
    """The nearest client process (Claude Code, Codex) above PID: the session a command was started by."""
    p = process(pid or os.getpid())
    for _ in range(64):
        if p is None or p["pid"] <= 1:
            return None
        if p["comm"] in CLIENTS:
            return {"pid": p["pid"], "start": p["start"], "comm": p["comm"], "boot": boot()}
        p = process(p["ppid"])
    return None


def load_grant(s) -> dict:
    try:
        doc = json.loads(grant_path(s).read_text())
    except (OSError, ValueError):
        doc = {}
    return doc if isinstance(doc, dict) and doc.get("schema") == SCHEMA else {}


def enabled(s) -> bool:
    return bool(load_grant(s).get("enabled"))


def actor(s) -> dict | None:
    """Who this command is, if it is the designated watcher's: None otherwise."""
    grant = load_grant(s)
    watcher, me = grant.get("watcher") or {}, client_process()
    if not grant.get("enabled") or not me or any(me[k] != (watcher.get("process") or {}).get(k) for k in ("pid", "start", "boot")):
        return None
    return {"actor": "watcher", "run": watcher["run"], "session": watcher.get("session"), "grant": watcher["id"],
            "epoch": grant.get("epoch", 0)}


def why_not(s) -> str:
    grant = load_grant(s)
    if not grant.get("enabled"):
        return ("delegation is off: a person turns it on for a watcher with `sync.py delegate on CODE`, after the watcher "
                "ran `sync.py delegate request --run NAME`. Until then the decision is a person's: propose it "
                "(`sync.py allow propose`) and tell them")
    watcher = grant["watcher"]
    return (f"this command was not started by the designated watcher (run {watcher['run']}, client process "
            f"{watcher['process']['pid']}): only that session decides; any other proposes, and asks it or a person")


# --------------------------------------------------------------------------- the record

def key(s, create: bool = False) -> bytes | None:
    path = key_path()
    try:
        return bytes.fromhex(path.read_text().strip())
    except (OSError, ValueError):
        if not create:
            return None
    path.parent.mkdir(parents=True, exist_ok=True)
    s.atomic_write(path, secrets.token_hex(32) + "\n", private=True)
    return bytes.fromhex(path.read_text().strip())


def _line(body: dict) -> str:
    return json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _sign(k: bytes, body: dict) -> str:
    return hmac.new(k, _line(body).encode(), hashlib.sha256).hexdigest()


def append(s, who: dict, **fields) -> dict:
    """Add one decision to the record: after the last line, naming that line's hash, signed."""
    k = key(s)
    if k is None:
        raise Refused(f"the record's key is missing ({key_path().name}): a person turns delegation on again to make one")
    path = ledger_path(s)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        lines = f.read().splitlines()
        body = {"seq": len(lines) + 1, "at": utc(), **who, **fields,
                "prev": hashlib.sha256(lines[-1].encode()).hexdigest() if lines else "0" * 64}
        body["mac"] = _sign(k, body)
        f.write(_line(body) + "\n")
        f.flush()
        os.fsync(f.fileno())
    _seal(s)
    return body


def _seal(s) -> None:
    """The record as an append-only stream in the restricted archive: what a rewrite here would not change there."""
    try:
        import artifacts
        if artifacts.off():
            return
        archive = artifacts.Archive()
        try:
            archive.capture_stream(ledger_path(s), "watcher-decisions", "watcher-record", "delegation/watcher-decisions.jsonl")
        finally:
            archive.close()
        artifacts.kick()
    except Exception as e:
        print(f"note: the decision record was not sealed into the private archive ({type(e).__name__})", file=sys.stderr)


def read(s) -> tuple[list[dict], list[str]]:
    """(the lines that verify, in order; what is wrong). A line that does not verify, and every line after it, is
    left out: nothing later can be shown to follow from what was recorded."""
    try:
        lines = ledger_path(s).read_text().splitlines()
    except OSError:
        return [], []
    k = key(s)
    if k is None:
        return [], [f"the watcher's decision record cannot be verified: its key ({key_path().name}) is missing"]
    out, prev = [], "0" * 64
    for n, line in enumerate(lines, 1):
        try:
            body = json.loads(line)
            mac = body.pop("mac")
            ok = body.get("seq") == n and body.get("prev") == prev and hmac.compare_digest(mac, _sign(k, body)) and line == _line({**body, "mac": mac})
        except (ValueError, KeyError, TypeError, AttributeError):
            ok = False
        if not ok:
            return out, [f"the watcher's decision record does not verify from line {n} of {len(lines)}: that line and those after "
                         "it count for nothing (it was edited, or written by something other than sync.py). The restricted "
                         "archive holds the record as it was sealed"]
        out.append(body)
        prev = hashlib.sha256(line.encode()).hexdigest()
    return out, []


def recorded(s) -> dict[str, dict[str, str]]:
    """{file name: {finding id: digest of the entry}} of the watcher's decisions that count now: the delegation is on,
    the line verifies, it was taken in the current epoch and under the redaction policy in force, and no later
    line took it back."""
    grant = load_grant(s)
    if not grant.get("enabled"):
        return {}
    out: dict[str, dict[str, str]] = {}
    for body in read(s)[0]:
        if body.get("action") not in ("allow", "revoke") or not body.get("file"):
            continue
        entries = out.setdefault(body["file"], {})
        if body["action"] == "revoke" or body.get("epoch") != grant.get("epoch", 0) or body.get("policy") != s.REDACTION_POLICY:
            entries.pop(body["finding"], None)
        else:
            entries[body["finding"]] = body["entry"]
    return out


def fingerprint(s) -> bytes:
    """What the cached answer of `unrecorded_decisions` depends on here: a change clears it."""
    h = hashlib.sha256(str(s.REDACTION_POLICY).encode())
    for path in (grant_path(s), ledger_path(s)):
        try:
            h.update(path.read_bytes())
        except OSError:
            h.update(b"-")
    return h.digest()


def problems(s) -> list[str]:
    return read(s)[1]


# --------------------------------------------------------------------------- on and off

def cmd_delegate(s, args: list[str]) -> int:
    cmd = args[0] if args else "status"
    if cmd == "status" and len(args) <= 1:
        grant = load_grant(s)
        lines, wrong = read(s)
        if not grant.get("enabled"):
            print("delegation is off: redaction decisions are a person's" + (f" (turned off {grant['off_at']})" if grant.get("off_at") else ""))
        else:
            w = grant["watcher"]
            alive = (process(w["process"]["pid"]) or {}).get("start") == w["process"]["start"] and boot() == w["process"]["boot"]
            print(f"delegation is on for the watcher of {w['run']} (session {w.get('session')}, client process {w['process']['pid']}, "
                  f"{'running' if alive else 'ended: it decides nothing more, and what it decided still counts'}), "
                  f"granted by {w['granted_by']} on {w['granted_at']}")
        counts: dict[str, int] = {}
        for body in lines:
            counts[body.get("action", "?")] = counts.get(body.get("action", "?"), 0) + 1
        print(f"the record: {len(lines)} line(s) that verify" + (" (" + ", ".join(f"{n} {a}" for a, n in sorted(counts.items())) + ")" if counts else ""))
        for p in wrong + open_escalations(s):
            print(p)
        return 1 if wrong else 0
    if cmd == "request" and len(args) == 3 and args[1] == "--run":
        me = client_process()
        if me is None:
            print("refused: no client session (Claude Code, Codex) started this command, so there is no watcher to name", file=sys.stderr)
            return 1
        code = secrets.token_hex(3)
        folder = s.STATE / "delegation-requests"
        folder.mkdir(parents=True, exist_ok=True)
        s.atomic_write(folder / f"{code}.json", json.dumps({"code": code, "run": args[2], "session": s.running_session(), "process": me,
                                                           "repo": str(s.REPO), "at": utc()}, indent=1) + "\n")
        print(f"request {code}: the watcher of {args[2]} (client process {me['pid']}) asks to take routine redaction decisions.\n"
              f"A person grants it from their own terminal with: python3 llm-dlc/tools/sync.py delegate on {code}")
        return 0
    if cmd == "off" and len(args) == 1:
        grant = load_grant(s)
        if not grant.get("enabled"):
            print("delegation is already off")
            return 0
        grant.update(enabled=False, off_at=utc())
        s.atomic_write(grant_path(s), json.dumps(grant, indent=1) + "\n")
        print("delegation is off. The watcher's decisions that are on main stand; those that are not stop counting now: `check` "
              "names them, and a person approves or vouches for them (`sync.py allow vouch`) or they are dropped.")
        return 0
    if cmd == "on" and len(args) in (2, 3) and (len(args) == 2 or args[2] == "--fresh"):
        if not s.person_at_terminal():
            print("refused: a person turns delegation on, from their own terminal. Ask them to run this command.", file=sys.stderr)
            return 1
        try:
            request = json.loads((s.STATE / "delegation-requests" / f"{args[1]}.json").read_text())
        except (OSError, ValueError):
            print(f"no request {args[1]}: the watcher makes one with `sync.py delegate request --run NAME`", file=sys.stderr)
            return 1
        p = request["process"]
        now = process(p["pid"])
        if now is None or now["start"] != p["start"] or boot() != p["boot"]:
            print(f"request {args[1]} names a client process ({p['pid']}) that has ended: the watcher asks again", file=sys.stderr)
            return 1
        print(f"The watcher of {request['run']} asks to take routine redaction decisions without you:\n"
              f"  session {request['session']}, client process {p['pid']} ({p['comm']}), in {request['repo']}, asked {request['at']}\n"
              "It could then approve allow-list proposals that have checkable evidence, withhold a log from publication and\n"
              "mask a value. It could not waive what the redactor removes, publish a withheld log, or act once that session ends.")
        if input(f'Type "{CONFIRM}" to grant it: ').strip() != CONFIRM:
            print("nothing granted")
            return 1
        key(s, create=True)
        grant = load_grant(s)
        who = s._cmd("git", "config", "--get", "user.name") or "maintainer"
        watcher = {"id": secrets.token_hex(8), "run": request["run"], "session": request["session"], "process": p,
                   "granted_by": who, "granted_at": utc()}
        doc = {"schema": SCHEMA, "enabled": True, "watcher": watcher, "epoch": grant.get("epoch", 0) + (1 if len(args) == 3 else 0),
               "grants": (grant.get("grants") or [])[-50:] + [{k: watcher[k] for k in ("id", "run", "session", "granted_by", "granted_at")}]}
        s.atomic_write(grant_path(s), json.dumps(doc, indent=1) + "\n")
        print(f"delegation is on for the watcher of {request['run']}. Turn it off with: python3 llm-dlc/tools/sync.py delegate off")
        return 0
    if cmd in ("approve", "withhold", "mask"):
        who = actor(s)
        if who is None:
            print(f"refused: {why_not(s)}", file=sys.stderr)
            return 1
        try:
            if cmd == "approve":
                return approve(s, who, args[1:])
            words, options = _options(args[1:], ("--reason",))
            if not options.get("--reason") or (cmd == "withhold" and len(words) != 2):
                raise Refused(f"usage: sync.py delegate {cmd} {'SESSION SHA256' if cmd == 'withhold' else 'ID...'} --reason TEXT")
            by = f"the watcher of {who['run']}"
            if cmd == "withhold":
                print(_withhold(s, who, by, words[0], words[1], options["--reason"]))
                return 0
            return mask(s, who, by, words, options["--reason"])
        except Refused as r:
            print(str(r) if str(r).startswith("usage:") else f"refused: {r}", file=sys.stderr)
            return 2 if str(r).startswith("usage:") else 1
    print("usage: sync.py delegate [status | request --run NAME | on CODE [--fresh] | off | approve ID... --evidence KIND:DETAIL "
          "--reason TEXT | withhold SESSION SHA256 --reason TEXT | mask ID... --reason TEXT]", file=sys.stderr)
    return 2


# --------------------------------------------------------------------------- what the watcher decides

def _options(args: list[str], names: tuple[str, ...]) -> tuple[list[str], dict[str, str]]:
    """Leading words, and the text after each option up to the next one."""
    words, options, i = [], {}, 0
    while i < len(args):
        if args[i] in names:
            j = i + 1
            while j < len(args) and args[j] not in names:
                j += 1
            options[args[i]] = " ".join(args[i + 1:j]).strip()
            i = j
        else:
            words.append(args[i])
            i += 1
    return words, options


def evidence_of(s, kind: str, value: str, spec: str) -> dict:
    """Check the origin claimed for a value, and return what the record keeps of it. Raises Refused."""
    how, _, detail = spec.partition(":")
    if how not in EVIDENCE:
        raise Refused("evidence is one of: " + "; ".join(f"{k}{':' if 'PATH' in v or 'URL' in v else ''}{v}" for k, v in EVIDENCE.items()))

    def shown(rev: str) -> bytes:
        r = s.jj("file", "show", "-r", rev, detail)
        if r.returncode:
            raise Refused(f"{detail} is not a file at {rev}")
        return r.stdout.encode() if isinstance(r.stdout, str) else r.stdout
    bound, verified = "", True
    if how in ("main-file", "tracked-file"):
        data = shown("trunk()" if how == "main-file" else "@-")
        if value.encode() not in data:
            raise Refused(f"the value is not in {detail} " + ("as main publishes it" if how == "main-file" else "as committed"))
        bound = hashlib.sha256(data).hexdigest()
    elif how == "content-digest":
        data = shown("@-")
        if value.lower() not in {hashlib.new(a, data).hexdigest() for a in ("sha256", "sha1", "sha512", "md5")}:
            raise Refused(f"the value is not a digest of {detail} as committed")
        bound = hashlib.sha256(data).hexdigest()
    elif how == "git-object":
        import subprocess
        if not (7 <= len(value) <= 64 and all(c in "0123456789abcdef" for c in value)) or subprocess.run(
                ["git", "-C", str(s.REPO), "cat-file", "-e", value], capture_output=True).returncode:
            raise Refused("the value is not the id of an object of this repository")
    elif how == "trace-log":
        if not any(value in (m.get("logs") or {}) for m in s.all_manifests().values()):
            raise Refused("the value does not name a log of any session here")
    elif how == "public":
        if not detail.startswith("https://") or kind == "long-token":
            raise Refused("`public:` takes an https URL, and is not enough for a long-token: its shape alone establishes "
                          "nothing, so its origin has to be one this command can check")
        verified = False
    return {"kind": how, "detail": detail, "verified": verified,
            "sha256": hashlib.sha256(f"{how}\0{detail}\0{bound}\0{s.finding_id(kind, value)}".encode()).hexdigest()}


def approve(s, who: dict, args: list[str]) -> int:
    """`delegate approve ID... --evidence KIND:DETAIL --reason TEXT`. Prints no value: the watcher's own transcript
    is published."""
    no_commit = "--no-commit" in args
    ids, options = _options([a for a in args if a != "--no-commit"], ("--evidence", "--reason"))
    if not ids or not options.get("--evidence") or not options.get("--reason"):
        raise Refused("usage: sync.py delegate approve ID... --evidence KIND:DETAIL --reason TEXT")
    entries = s.load_allowlist()
    proposed = {fid: e for fid, e in entries.items() if e["status"] == "proposed"}
    done, missing = s._resolve(ids, proposed)
    if missing:
        print(f"no single proposal for {', '.join(missing)}: the watcher approves what was proposed, by id", file=sys.stderr)
        return 1
    redact, cache = s.Redactor(), s.load_findings_cache()
    if any(fid not in cache for fid in done.values()):
        cache |= {fid: {**f, "where": sorted(f["where"])} for fid, f in s.open_findings(redact, values=True).items()}
    chosen, today = {}, time.strftime("%Y-%m-%d")
    for fid in done.values():
        e, f = proposed[fid], cache.get(fid)
        try:
            if f is None or s.finding_id(e["kind"], f["value"]) != fid:
                raise Refused("its value is not known from a scan here")
            if problem := s._value_problem(e["kind"], f["value"], redact):
                raise Refused(problem)
            evidence = evidence_of(s, e["kind"], f["value"], options["--evidence"])
        except Refused as r:
            print(f"refused {fid[:8]} ({e['kind']}, {e.get('masked', '')}): {r}", file=sys.stderr)
            return 1
        chosen[fid] = {**e, "value": f["value"], "status": "approved", "reason": options["--reason"], "actor": "watcher",
                       "authorized_by": f"the watcher of {who['run']}", "approved_on": today, "evidence": evidence}
    for fid, e in chosen.items():  # the record first: an entry with no line is the error, a line with no entry is nothing
        append(s, who, file=s.ALLOWLIST.name, finding=fid, entry=s._decision_digest(e), action="allow", kind=e["kind"],
               destination="git and the published logs", scope="this value, wherever the rules find it as this kind",
               policy=s.REDACTION_POLICY, rationale=options["--reason"], evidence=e["evidence"])
    entries.update(chosen)
    s.save_allowlist(entries)
    for fid, e in chosen.items():
        print(f"allowed {fid[:8]}  {e['kind']}  {e.get('masked', '')}  ({e['evidence']['kind']}"
              f"{'' if e['evidence']['verified'] else ', not checked here'})")
    print(f"the watcher of {who['run']} allowed {len(chosen)} value(s) in {s.ALLOWLIST.relative_to(s.REPO)}, each in the record")
    if no_commit or not s.has_jj():
        return 0
    return s.commit_allowlist(chosen, f"The watcher of {who['run']}", how="under the delegation a person granted, each with evidence in the record")


def _withhold(s, who: dict | None, by: str, sid: str, sha: str, reason: str) -> str:
    m = s.load_manifest(sid)
    info = (m.get("logs") or {}).get(sha)
    if info is None:
        raise Refused(f"session {sid} lists no log {sha[:12]}")
    if info.get("url"):
        raise Refused(f"log {sha[:12]} is published: taking it down is a person's (`sync.py unpublish {sid} {sha} --reason ...`). "
                      "Escalate it (`sync.py review escalate`)")
    if info.get("withdrawn"):
        return f"log {sha[:12]} of {sid[:8]} was already withdrawn"
    path = s.log_path(sid, sha)
    if path.exists():
        import artifacts
        if not artifacts.off():
            archive = artifacts.Archive()
            try:  # unclassified, so restricted: the bytes git will only name
                archive.capture(path, "withheld-log", str(path.relative_to(s.REPO)), session=sid, notes={"reason": reason, "by": by})
            finally:
                archive.close()
            artifacts.kick()
        path.unlink()
    info["withdrawn"] = f"withheld before publication by {by}: {reason}"
    s.save_manifest(sid, m)
    if who:
        append(s, who, file="manifest.json", finding=f"{sid}/{sha}", action="private-only", destination="the restricted archive only",
               scope="this log; later logs of the session are separate", policy=s.REDACTION_POLICY, rationale=reason)
    return f"withheld log {sha[:12]} of {sid[:8]}: never published, marked withdrawn in its manifest"


def cmd_review(s, args: list[str]) -> int | None:
    """The forms of `sync.py review` this module adds; None when the arguments are another form."""
    if not args or args[0] not in ("withhold", "mask", "escalate", "close"):
        return None
    cmd = args[0]
    try:
        if cmd == "escalate":
            ids, options = _options(args[1:], ("--reason", "--contained"))
            if not ids or not options.get("--reason"):
                raise Refused("usage: sync.py review escalate ID... --reason WHAT REMAINS TO DECIDE [--contained WHAT WAS DONE]")
            return escalate(s, ids, options["--reason"], options.get("--contained", ""))
        if cmd == "close":
            words, options = _options(args[1:], ("--reason",))
            if len(words) != 1 or not options.get("--reason"):
                raise Refused("usage: sync.py review close ESCALATION --reason TEXT")
            if not s.person_at_terminal():
                raise Refused("a person closes an escalation, from their own terminal")
            return close(s, words[0], options["--reason"])
        if not s.person_at_terminal():
            raise Refused(f"a person decides this from their own terminal (the designated watcher has `sync.py delegate {cmd}`)")
        by = s._cmd("git", "config", "--get", "user.name") or "maintainer"
        words, options = _options(args[1:], ("--reason",))
        if not options.get("--reason") or (cmd == "withhold" and len(words) != 2):
            raise Refused(f"usage: sync.py review {cmd} {'SESSION SHA256' if cmd == 'withhold' else 'ID...'} --reason TEXT")
        if cmd == "withhold":
            print(_withhold(s, None, by, words[0], words[1], options["--reason"]))
            return 0
        return mask(s, None, by, words, options["--reason"])
    except Refused as r:
        print(f"refused: {r}" if not str(r).startswith("usage:") else str(r), file=sys.stderr)
        return 2 if str(r).startswith("usage:") else 1


def mask(s, who: dict | None, by: str, ids: list[str], reason: str) -> int:
    cache = s.load_findings_cache()
    done, missing = s._resolve(ids, cache)
    if not ids or missing:
        raise Refused(f"no single finding for {', '.join(missing) or 'no id'} in the last scan (`sync.py review` lists them)")
    values = {fid: cache[fid] for fid in done.values()}
    for fid, f in values.items():
        if len(f["value"]) < 4 or "\n" in f["value"] or "=>" in f["value"] or f["value"] != f["value"].strip():
            raise Refused(f"{fid[:8]} cannot be masked as a literal (too short, or it holds a line break or `=>`): withhold the logs that hold it")
    path = s.EXTRA_REDACTIONS
    path.parent.mkdir(parents=True, exist_ok=True)
    known = path.read_text() if path.exists() else ""
    s.atomic_write(path, known + ("" if not known or known.endswith("\n") else "\n")
                   + "".join(f"{f['value']} => [REDACTED:masked]\n" for f in values.values()), private=True)
    withheld, published = [], []
    sessions = {w for f in values.values() for w in f.get("where", [])}
    needles = [f["value"].encode() for f in values.values()]
    for sid, m in s.all_manifests().items():
        if not any(sid.startswith(w) for w in sessions):
            continue
        for sha, info in sorted((m.get("logs") or {}).items()):
            log = s.log_path(sid, sha)
            if info.get("withdrawn") or not log.exists():
                continue
            data = gzip.decompress(log.read_bytes())
            if not any(n in data for n in needles):
                continue
            if info.get("url"):
                published.append(f"{sid[:8]}/{sha[:12]}")
            else:
                withheld.append(_withhold(s, who, by, sid, sha, f"it holds a value masked since: {reason}"))
    for fid, f in values.items():
        if who:
            append(s, who, file="redact.txt", finding=fid, action="mask", kind=f["kind"], destination="every later log",
                   scope="this machine's redactions", policy=s.REDACTION_POLICY, rationale=reason)
        print(f"masked {fid[:8]}  {f['kind']}  {s._mask(f['value'])}: every log made from now on omits it")
    for line in withheld:
        print(line)
    if published:
        escalate(s, list(done.values()), f"{len(published)} published log(s) hold a value that was masked ({reason}): withdraw them "
                 "(`sync.py unpublish SESSION SHA256 --reason ...`) or leave them", "masked for later logs; unpublished logs that held it withheld",
                 where=published, by=by)
    print("The redactions changed, so the next check scans every stored log again (minutes, once).")
    return 0


def escalate(s, ids: list[str], reason: str, contained: str, where: list[str] | None = None, by: str | None = None) -> int:
    """One masked record for a person: what is affected, what was contained, what remains to decide."""
    cache = s.load_findings_cache()
    done, _ = s._resolve(ids, cache)
    found = [{"id": fid[:8], "kind": cache[fid]["kind"], "masked": s._mask(cache[fid]["value"]), "where": cache[fid].get("where", [])}
             for fid in done.values()] or [{"id": i[:8]} for i in ids]
    who = actor(s)
    record = {"id": secrets.token_hex(3), "at": utc(), "by": by or (f"the watcher of {who['run']}" if who else "an agent" if s.in_agent_session() else "a person"),
              "findings": found, "where": where or [], "contained": contained, "choice": reason, "open": True}
    path = escalations_path(s)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"escalated as {record['id']}: `check` warns of it until a person closes it (`sync.py review close {record['id']} --reason ...`)")
    return 0


def _escalations(s) -> list[dict]:
    try:
        return [json.loads(line) for line in escalations_path(s).read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def open_escalations(s) -> list[str]:
    closed = {e["closes"] for e in _escalations(s) if e.get("closes")}
    return [f"escalation {e['id']} ({e['at']}, {e['by']}) awaits a person: {e['choice']}"
            + (f"; contained: {e['contained']}" if e.get("contained") else "")
            + ("; findings " + ", ".join(f"{f['id']} {f.get('kind', '')} {f.get('masked', '')}".strip() for f in e["findings"]))
            + (f"; in {', '.join(e['where'][:6])}" if e.get("where") else "")
            + f". Close it with: python3 llm-dlc/tools/sync.py review close {e['id']} --reason ..."
            for e in _escalations(s) if e.get("open") and e["id"] not in closed]


def close(s, ident: str, reason: str) -> int:
    if not any(e.get("open") and e["id"] == ident for e in _escalations(s)):
        print(f"no open escalation {ident}", file=sys.stderr)
        return 1
    with open(escalations_path(s), "a") as f:
        f.write(json.dumps({"closes": ident, "at": utc(), "by": s._cmd("git", "config", "--get", "user.name") or "maintainer",
                            "reason": reason}, sort_keys=True) + "\n")
    print(f"closed escalation {ident}")
    return 0
