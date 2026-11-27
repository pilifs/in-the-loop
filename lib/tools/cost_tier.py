"""The cost tier a Python test runs at: the `@cost` decorator, Python's counterpart of `lib/src/test_tier.rs`.

`lib/tests/costs.json` lists every test's tier, and `lib/README.md`'s Tests section says how to run each:

- **unit**: in process, with no subprocess. Undecorated. Always runs.
- **tool**: spawns a process (`git`, `jj`, `javac`, `java`, the `jvmcontract` binary, another Python) and takes
  seconds. `@cost("tool")`. Runs by default, and is skipped under `TEST_COST=unit`.
- **proof**: JBMC, TLC, or over the tool tier's limits (10 s, 1 GB). `@cost("proof", "WHAT IT RUNS, ~TIME; proxy:
  Class.test")`, the counterpart of Rust's ignore reason, is skipped unless `TEST_COST=proof`, and runs as a pipeline
  job. A proof-tier test that still runs by default (`retier: pending` in
  the inventory) is `@cost("pending")`: it runs like a tool-tier test until a later change moves it.

`python3 lib/tools/test_costs.py tag FILE ...` gives each test of a file the decorator its tier asks for. A test file
reaches this module with
`sys.path.append(str(Path(__file__).resolve().parents[N] / "lib/tools"))`, N being its depth below the repository.
"""
import os
import unittest

# The tests start made-up loops and runs with stand-in clients, from wherever they run, an agent's own loop included.
# The guard against an agent starting a run from inside its loop (watch.nested_run_refusal, feature-loop.sh; VF-045)
# is not for them, and their subprocesses inherit this.
os.environ.setdefault("IN_THE_LOOP_NESTED_RUN", "allow")

VARIABLE = "TEST_COST"
TIERS = ("unit", "tool", "proof")
TAGS = ("tool", "pending", "proof")


def included(tag: str, value: str | None) -> bool:
    """Whether a test tagged TAG runs when the variable is VALUE (None: unset). Unset, empty and `tool` run the
    unit and tool tiers and the pending tests; `unit` the unit tier alone; `proof` everything. Any other value, or
    tag, raises, so that a misspelt tier fails the run instead of running everything."""
    if tag not in TAGS:
        raise ValueError(f"@cost({tag!r}): the tags are {', '.join(map(repr, TAGS))}")
    if value not in (None, "", *TIERS):
        raise ValueError(f"{VARIABLE}={value!r}: the tiers are {', '.join(TIERS)}")
    if value == "unit":
        return False
    return tag != "proof" or value == "proof"


def cost(tag: str, reason: str | None = None):
    """Decorate a test method (or a TestCase) with its cost tier: `"tool"`, `"pending"` or `"proof"`. A proof-tier
    test gives REASON: what it runs and about how long, and its proxy (`"JBMC on X, ~5 min; proxy: Class.test"`),
    which `test_costs.py lint` checks. A test the run's `TEST_COST` leaves out is skipped, saying why."""
    if included(tag, os.environ.get(VARIABLE)):
        return lambda test: test
    value = os.environ.get(VARIABLE) or "unset"
    tier = {"tool": "a tool-tier", "pending": "a proof-tier (retier pending)", "proof": "a proof-tier"}[tag]
    return unittest.skip(f"{tier} test, under {VARIABLE}={value}" + (f": {reason}" if reason else ""))
