"""Allocate the matched main and transfer cohorts together from an audited private docket."""

import argparse
from collections import Counter, defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from cryptography.exceptions import InvalidSignature

if __package__:
    from . import screen, seal_reference
else:
    import screen
    import seal_reference


CUTOFF = screen.utc("2026-11-20T23:00:00Z")
TARGET_MAIN = 12
TARGET_TRANSFER = 4
TARGET_RELATION = 2
STRATA = ("change", "preservation")
REVIEW_STATES = {"qualified", "pending", "excluded", "deferred"}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()


def checked_file(root, item, read=None):
    path = screen.evidence(root, item["file"])
    with path.open("rb") as source:
        actual = hashlib.file_digest(source, "sha256").hexdigest()
        screen.require(actual == item["sha256"], "private evidence digest differs")
        if read is not None:
            source.seek(0)
            return read(source)


@dataclass(frozen=True)
class Case:
    stable_id: str
    stratum: str
    client: str
    family: str
    old_version: str
    new_version: str
    trigger: str
    incident: str
    date: datetime
    version_step: str
    build: str

    @property
    def duplicate_key(self):
        return self.client, self.family, self.old_version, self.new_version, self.trigger


@dataclass(frozen=True)
class Pair:
    change: Case
    routine: Case
    tier: int
    distance: timedelta


def match(change, routine):
    distance = abs(routine.date - change.date)
    if routine.date > CUTOFF or distance > timedelta(days=365):
        return None
    if change.family == routine.family:
        tier = 1 if change.client == routine.client else 2
    elif (change.version_step == routine.version_step and change.version_step in {"major", "minor", "patch"}
          and change.build == routine.build and change.build in {"single", "reactor"}):
        tier = 3
    else:
        return None
    return Pair(change, routine, tier, distance)


def ranked_pairs(cases, searches, seed):
    def order(pair):
        c, r = pair.change.stable_id, pair.routine.stable_id
        return (not c.startswith("compsuite:"), screen.rank(seed, c), c,
                pair.tier, pair.distance, screen.rank(seed, r), r)

    result = []
    for anchor, candidates in searches.items():
        if anchor not in cases:
            continue
        for candidate in candidates:
            if candidate in cases:
                pair = match(cases[anchor], cases[candidate])
                if pair:
                    result.append(pair)
    return sorted(result, key=order)


def read_docket(root, doc, commitment):
    """Keep screening status separate from the independently signed reference."""
    audit = doc["audit"]
    checked_file(root, audit["ledger"])
    reasons = Counter()
    for field in ("before_v0_scoring", "ranked_review_complete"):
        screen.require(type(audit[field]) is bool, "invalid frontier audit")
        if not audit[field]:
            reasons[field] += 1
    rows, qualified, receipts = {}, {}, {}
    labels = set()
    for stratum, section in zip(STRATA, ("changes", "routines")):
        for row in doc[section]:
            sid = row["stable_id"]
            pattern = (r"compsuite:i-[0-9]+|bump:[0-9a-f]{40}" if stratum == "change"
                       else r"github:[a-z0-9_.-]+/[a-z0-9_.-]+#[1-9][0-9]*")
            screen.require(re.fullmatch(pattern, sid) and sid not in rows, "invalid or duplicate stable ID")
            state = row["review"]
            screen.require(state in REVIEW_STATES, "invalid candidate review")
            rows[sid] = (stratum, state)
            if state == "pending":
                reasons["pending_ranked_reviews"] += 1
            audited = row.get("reference_audited", False)
            screen.require(type(audited) is bool, "invalid reference review")
            needs_decision = state == "qualified" and audited and row.get("reference") is not None
            decision = checked_file(root, row["evidence"], json.load if needs_decision else None)
            if row.get("reference") is not None:
                receipt, *_ = checked_file(root, row["reference"],
                                           lambda handle: seal_reference.verify_packet(handle, commitment))
                screen.require(receipt["packet_id"] not in labels, "reused signed packet")
                labels.add(receipt["packet_id"])
                receipts[sid] = {**receipt, "file_sha256": row["reference"]["sha256"]}
            if state != "qualified":
                continue
            if sid not in receipts or not audited:
                reasons["qualified_without_audited_signed_reference"] += 1
                continue
            screen.require(decision["stable_id"] == sid and decision["stratum"] == stratum
                           and decision["packet_id"] == receipts[sid]["packet_id"]
                           and decision["signed_envelope_sha256"] == receipts[sid]["signed_envelope_sha256"],
                           "signed reference differs from its independent eligibility decision")
            fields = {k: row[k] for k in ("client", "family", "old_version", "new_version", "trigger",
                                           "incident", "version_step", "build")}
            screen.require(all(screen.nonempty_text(v) and v == v.strip() for v in fields.values()),
                           "incomplete case identity")
            for identity in ("client", "family"):
                fields[identity] = fields[identity].casefold()
            screen.require(fields["old_version"] != fields["new_version"], "identical dependency versions")
            if stratum == "preservation":
                screen.require(sid[7:].rsplit("#", 1)[0] == fields["client"], "PR client differs")
            date = screen.utc(row["changed_at" if stratum == "change" else "merged_at"])
            qualified[sid] = Case(sid, stratum, date=date, **fields)
    searches = {}
    for row in doc["searches"]:
        anchor = row["anchor"]
        screen.require(anchor in rows and rows[anchor][0] == "change" and anchor not in searches,
                       "invalid or repeated matching anchor")
        candidates = row["routine_ids"]
        screen.require(isinstance(candidates, list) and len(set(candidates)) == len(candidates)
                       and all(r in rows and rows[r][0] == "preservation" for r in candidates),
                       "invalid routine search results")
        screen.require(type(row["complete"]) is bool, "invalid search completeness")
        checked_file(root, row["evidence"])
        if not row["complete"] and rows[anchor][1] in {"qualified", "pending"}:
            reasons["incomplete_searches"] += 1
        searches[anchor] = candidates
    reasons["missing_anchor_searches"] += sum(
        state == ("change", "qualified") and sid not in searches for sid, state in rows.items()
    )
    return rows, qualified, receipts, searches, +reasons


def any_of(terms):
    return "(or " + " ".join(terms) + ")" if terms else "false"


def bound(terms, count, *, at_least=False):
    if at_least:
        if count <= 0:
            return "true"
        if count > len(terms):
            return "false"
    elif count >= len(terms):
        return "true"
    name = "at-least" if at_least else "at-most"
    return f"((_ {name} {count}) " + " ".join(terms) + ")"


class Solver:
    """Incremental local Boolean feasibility oracle. Only numbered symbols reach Z3."""

    def __init__(self, process):
        self.process = process

    def command(self, text):
        self.process.stdin.write(text + "\n")

    def constrain(self, term):
        self.command("(assert " + term + ")")

    def symbol(self, name, definition=None):
        self.command(f"(declare-const {name} Bool)")
        if definition is not None:
            self.constrain(f"(= {name} {definition})")
        return name

    def feasible(self, *terms):
        self.command("(push 1)")
        for term in terms:
            self.constrain(term)
        self.command("(check-sat)")
        self.command("(pop 1)")
        self.process.stdin.flush()
        response = self.process.stdout.readline().strip()
        if response not in {"sat", "unsat"}:
            raise RuntimeError("local allocation solver returned no decision")
        return response == "sat"

    def maximum(self, terms, limit):
        low, high = 0, min(limit, len(terms))
        while low < high:
            middle = (low + high + 1) // 2
            if self.feasible(bound(terms, middle, at_least=True)):
                low = middle
            else:
                high = middle - 1
        self.constrain(bound(terms, low, at_least=True))
        return low

    def earliest(self, terms, count):
        # Binary search for the first index that can extend the fixed prefix to a full solution.
        fixed, start = [], 0
        for _ in range(count):
            left, right = start, len(terms) - 1
            while left < right:
                mid = (left + right) // 2
                if self.feasible(any_of(terms[left:mid + 1])):
                    right = mid
                else:
                    left = mid + 1
            self.constrain("(not " + any_of(terms[start:left]) + ")")
            self.constrain(terms[left])
            fixed.append(left)
            start = left + 1
        return fixed


@contextmanager
def local_solver():
    proc = subprocess.Popen(["z3", "-in", "-smt2"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, text=True)
    try:
        yield Solver(proc)
    finally:
        proc.kill()
        proc.communicate()


def grouped(cases, key):
    result = defaultdict(list)
    for i, case in enumerate(cases):
        result[key(case)].append(i)
    return result


def allocate(cases, pairs):
    if not pairs:
        return {"main_pairs": 0, "reserve_pairs": 0,
                "reserve": {stratum: {"same": 0, "new": 0} for stratum in STRATA}}, None
    ordered = sorted(cases.values(), key=lambda c: c.stable_id)
    touching = defaultdict(list)
    for i, pair in enumerate(pairs):
        touching[pair.change.stable_id].append(i)
        touching[pair.routine.stable_id].append(i)
    with local_solver() as solver:
        main = [solver.symbol(f"m{i}") for i in range(len(pairs))]
        transfer = [solver.symbol(f"t{i}") for i in range(len(pairs))]
        members, reserves, used = [], [], []
        for i, case in enumerate(ordered):
            positions = touching[case.stable_id]
            in_main, in_transfer = [main[j] for j in positions], [transfer[j] for j in positions]
            solver.constrain(bound(in_main + in_transfer, 1))
            members.append(solver.symbol(f"a{i}", any_of(in_main)))
            reserves.append(solver.symbol(f"b{i}", any_of(in_transfer)))
            used.append(solver.symbol(f"u{i}", any_of([members[i], reserves[i]])))
        for key in (lambda c: c.duplicate_key, lambda c: c.incident):
            for ids in grouped(ordered, key).values():
                solver.constrain(bound([used[i] for i in ids], 1))
        membership = {}
        for prop in ("client", "family"):
            by_identity = {}
            for j, (name, ids) in enumerate(grouped(ordered, lambda c: getattr(c, prop)).items()):
                by_identity[name] = solver.symbol(f"{prop}{j}", any_of([members[i] for i in ids]))
                for stratum in STRATA:
                    solver.constrain(bound([members[i] for i in ids if ordered[i].stratum == stratum], 2))
            membership[prop] = by_identity
        relations = {s: {"same": [], "new": []} for s in STRATA}
        for i, case in enumerate(ordered):
            family = membership["family"][case.family]
            same = solver.symbol(f"s{i}", f"(and {reserves[i]} {family})")
            new = solver.symbol(f"n{i}", f"(and {reserves[i]} (not {family}))")
            solver.constrain(f"(=> {same} (not {membership['client'][case.client]}))")
            relations[case.stratum]["same"].append(same)
            relations[case.stratum]["new"].append(new)
        for groups in relations.values():
            for terms in groups.values():
                solver.constrain(bound(terms, TARGET_RELATION))
        solver.constrain(bound(main, TARGET_MAIN))
        solver.constrain(bound(transfer, TARGET_TRANSFER))
        # The shortfall is one jointly attainable count vector, prioritizing the 24 main cases.
        n_main = solver.maximum(main, TARGET_MAIN)
        n_transfer = solver.maximum(transfer, TARGET_TRANSFER)
        if (n_main, n_transfer) != (TARGET_MAIN, TARGET_TRANSFER):
            counts = {}
            for stratum, groups in relations.items():
                same = solver.maximum(groups["same"], TARGET_RELATION)
                counts[stratum] = {"same": same, "new": n_transfer - same}
            return {"main_pairs": n_main, "reserve_pairs": n_transfer, "reserve": counts}, None
        main_ids = solver.earliest(main, n_main)
        transfer_ids = solver.earliest(transfer, n_transfer)
        screen.require(solver.feasible(), "ranked selection failed independent feasibility check")
        chosen = [pairs[i] for i in main_ids], [pairs[i] for i in transfer_ids]
    return {"main_pairs": n_main, "reserve_pairs": n_transfer,
            "reserve": {s: {"same": 2, "new": 2} for s in STRATA}}, chosen


def validate_selection(chosen):
    main, transfer = chosen
    screen.require(len(main) == TARGET_MAIN and len(transfer) == TARGET_TRANSFER, "incorrect pair count")
    main_cases = [c for pair in main for c in (pair.change, pair.routine)]
    transfer_cases = [c for pair in transfer for c in (pair.change, pair.routine)]
    all_cases = main_cases + transfer_cases
    for key in (lambda c: c.stable_id, lambda c: c.duplicate_key, lambda c: c.incident):
        screen.require(len({key(c) for c in all_cases}) == len(all_cases), "duplicate selected case")
    for pair in main + transfer:
        screen.require(pair.change.stratum == "change" and pair.routine.stratum == "preservation"
                       and match(pair.change, pair.routine) == pair, "invalid selected pair")
    clients, families = {c.client for c in main_cases}, {c.family for c in main_cases}
    for stratum in STRATA:
        group = [c for c in main_cases if c.stratum == stratum]
        for prop in ("client", "family"):
            screen.require(max(Counter(getattr(c, prop) for c in group).values()) <= 2, "main diversity cap")
        subset = [c for c in transfer_cases if c.stratum == stratum and c.family in families]
        screen.require(len(subset) == 2 and all(c.client not in clients for c in subset),
                       "invalid transfer family or client")
    return families


def run(docket, seed_path, commitment, output):
    root = screen.private_path(docket).parent
    source = screen.private_path(docket).read_bytes()
    seed = screen.private_path(seed_path).read_bytes()
    seed_hash = digest(seed)
    screen.require(len(seed) == 32 and json.loads(commitment.read_bytes())["seed_sha256"] == seed_hash,
                   "seed does not match commitment")
    rows, cases, receipts, searches, reasons = read_docket(root, json.loads(source), commitment)
    pairs = ranked_pairs(cases, searches, seed)
    counts, chosen = allocate(cases, pairs)
    anchors = {p.change.stable_id for p in pairs}
    summary = {"status": "shortfall" if chosen is None else "audit-pending" if reasons else "ready-to-seal",
               "required": {"main_pairs": TARGET_MAIN, "reserve_per_stratum_per_relationship": TARGET_RELATION},
               "shortfall": {"main_pairs": TARGET_MAIN - counts["main_pairs"],
                             "reserve": {s: {k: TARGET_RELATION - n for k, n in counts["reserve"][s].items()}
                                         for s in STRATA}},
               "attainable": counts, "audited_signed_candidates": {
                   s: sum(c.stratum == s for c in cases.values()) for s in STRATA},
               "reviewed": {s: dict(Counter(state for stratum, state in rows.values() if stratum == s))
                            for s in STRATA},
               "qualified_changes_without_eligible_match": sum(
                   c.stratum == "change" and c.stable_id not in anchors for c in cases.values()),
               "audit_outstanding": dict(reasons)}
    result = {"summary": summary, "docket_sha256": digest(source), "seed_sha256": seed_hash,
              "commitment_sha256": digest(commitment.read_bytes())}
    if chosen is not None and not reasons:
        families = validate_selection(chosen)
        clients = {c.client for p in chosen[0] for c in (p.change, p.routine)}
        for phase, group in zip(("main", "transfer"), chosen):
            records = []
            for pair in group:
                record = {"match_tier": pair.tier, "distance_microseconds": pair.distance // timedelta(microseconds=1)}
                for case in (pair.change, pair.routine):
                    data = {"stable_id": case.stable_id, "reference": receipts[case.stable_id]}
                    if phase == "transfer":
                        data["family_relationship"] = "same" if case.family in families else "new"
                        data["client_in_main"] = case.client in clients
                    record[case.stratum] = data
                records.append(record)
            result[phase] = records
            result[phase + "_sha256"] = digest(canonical(records))
    with seal_reference.publish_once(screen.private_path(output)) as staged:
        staged.write(canonical(result))
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docket", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", required=True, type=Path)
    parser.add_argument("--commitment", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary = run(args.docket, args.seed, args.commitment, args.output)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, InvalidSignature):
        parser.exit(1, "Allocation failed. Inspect the inputs and solver in the private curator workspace.\n")
    print(json.dumps(summary, sort_keys=True))
    return 0 if summary["status"] == "ready-to-seal" else 2


if __name__ == "__main__":
    sys.exit(main())
