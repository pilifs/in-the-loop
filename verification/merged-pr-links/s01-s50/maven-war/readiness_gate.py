#!/usr/bin/env python3
"""Replay S48's delayed setup through the jobs pipeline: the third gate of the generic-jobs-pipeline brief.

On 2026-11-27 the domain investigation of Spring Boot S48 (example 635, PR #51551) needed the Maven plugin's
integration harness, which setup had never exercised. It took five rounds and six jobs (VF-076). This replays it
as one request, from the same cache made insufficient (readiness-operation.json: `base.without` lists what is
left out, and `base.why` says how that differs from the state those rounds began in):

  1. A consumer job that needs the operation, and an unrelated job, are committed to a throwaway repository with
     this checkout's pipeline in it, and a runner is started there. The consumer waits; the unrelated job finishes.
  2. The request is admitted (`pipeline.py resolve`, then a commit), as the watcher admits one.
  3. The resolution job fetches what the task asks for and proves it offline; the receipt wakes the consumer,
     which reads the four WARs offline on the prepared inputs. Its readbacks are compared with parent.json and
     fix.json beside this file.
  4. Three controls, each a resolution of its own that must be withheld at the fetch stage with nothing
     published: the BOM withheld from every authorised source, a wrong digest for the Maven distribution, and a
     repository that does not answer on a cold cache.

It runs inside one job of the first format, because the default checkout's runner is the pipeline of before this
line (it would not run a job of the second format); the scheduler under test is the one in the throwaway
repository. It fetches the Maven 3.9.13 distribution and one POM from Maven Central, twice each at most.

  python3 verification/merged-pr-links/s01-s50/maven-war/readiness_gate.py --output FILE [--no-controls] [--operation FILE]

Exit 0 when every check passed; the record (FILE) has each check with what was seen.
"""
import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REL = HERE.relative_to(ROOT).as_posix()
CENTRAL = "https://repo.maven.apache.org/maven2/"
NOWHERE = "http://127.0.0.1:9/"          # the discard port: nothing listens there


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class Gate:
    def __init__(self, work: Path, operation: dict, consumer_steps: list, expected: dict, settings: dict) -> None:
        self.work, self.operation, self.consumer_steps, self.expected = work, operation, consumer_steps, expected
        self.repo, self.store = work / "repository", work / "store"
        self.settings = {**settings, "readiness_dir": str(self.store)}   # the gate's own store: never the machine's
        self.checks, self.timeline, self.runner = [], [], None
        self.env = {**os.environ, "VERIFY_REPO": str(self.repo), "VERIFY_MACHINE_CONFIG": "", "ITL_ORIGINALS_OFF": "1"}
        self.env.pop("VERIFY_CONFIG", None)

    # ----- the throwaway repository

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True, text=True).stdout.strip()

    def commit(self, message):
        env = dict(os.environ, GIT_AUTHOR_NAME="gate", GIT_AUTHOR_EMAIL="gate@example.invalid", GIT_COMMITTER_NAME="gate",
                   GIT_COMMITTER_EMAIL="gate@example.invalid")
        self.git("add", "-A")
        tree = self.git("write-tree")
        parent = subprocess.run(["git", "rev-parse", "-q", "--verify", "HEAD"], cwd=self.repo, capture_output=True, text=True).stdout.strip()
        made = subprocess.run(["git", "commit-tree", tree, *(["-p", parent] if parent else []), "-m", message], cwd=self.repo, env=env,
                              check=True, capture_output=True, text=True).stdout.strip()
        self.git("update-ref", "HEAD", made)

    def build_repository(self, copies: list) -> None:
        self.repo.mkdir(parents=True)
        skip = shutil.ignore_patterns("test_*", "fixtures", "__pycache__", "*.pyc", ".state")
        shutil.copytree(ROOT / "jobs", self.repo / "jobs", ignore=skip)
        (self.repo / "verification").mkdir()
        for name in ("pipeline.py", "layout.py", "capture.py"):
            shutil.copy(ROOT / "verification" / name, self.repo / "verification" / name)
        shutil.copytree(ROOT / "verification/schema", self.repo / "verification/schema")
        for rel in copies:   # what the task itself reads from the checkout
            (self.repo / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(ROOT / rel, self.repo / rel, ignore=skip) if (ROOT / rel).is_dir() else shutil.copy(ROOT / rel, self.repo / rel)
        (self.repo / "verification/pipeline.toml").write_text(
            "[runner]\n" + "".join(f"{k} = {json.dumps(v)}\n" for k, v in self.settings.items()) + '[defaults]\nmemory = "256M"\nduration = "1m"\n')
        (self.repo / ".gitignore").write_text("verification/.state/\n__pycache__/\n")
        self.git("init", "-q", "-b", "main")
        self.commit("the pipeline of this checkout, and what the task reads")

    def pipeline(self, *args, check=True):
        proc = subprocess.run([sys.executable, "jobs/pipeline.py", *args], cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=600)
        if check and proc.returncode != 0:
            raise RuntimeError(f"pipeline.py {' '.join(args)} exited {proc.returncode}:\n{proc.stdout}\n{proc.stderr}")
        return proc

    def view(self):
        return json.loads(self.pipeline("view", check=False).stdout)

    def job(self, job_id):
        return next((j for j in self.view()["jobs"] if j["id"] == job_id), None)

    def staged(self, job_id):
        return json.loads((self.repo / "verification/.state/results" / job_id / "result.json").read_text())

    # ----- the record

    def check(self, name: str, passed: bool, detail) -> bool:
        self.checks.append({"check": name, "passed": bool(passed), "detail": detail})
        print(f"{'ok  ' if passed else 'FAIL'}  {name}" + ("" if passed else f": {json.dumps(detail)[:600]}"), flush=True)
        return bool(passed)

    def note(self, what: str) -> None:
        self.timeline.append({"at": now(), "what": what})
        print(f"      {what}", flush=True)

    def until(self, condition, what: str, seconds: float) -> bool:
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if condition():
                return True
            if self.runner and self.runner.poll() is not None:
                break
            time.sleep(3)
        self.check(what, False, {"waited": seconds, "runnerExited": self.runner.poll() if self.runner else None})
        return False

    def start_runner(self) -> None:
        self.log = open(self.work / "runner.log", "w")
        self.runner = subprocess.Popen([sys.executable, "jobs/pipeline.py", "run", "--watch"], cwd=self.repo, env=self.env,
                                       stdout=self.log, stderr=subprocess.STDOUT, start_new_session=True)

    def stop_runner(self) -> None:
        if self.runner and self.runner.poll() is None:
            os.killpg(self.runner.pid, signal.SIGTERM)
            try:
                self.runner.wait(timeout=120)
            except subprocess.TimeoutExpired:
                os.killpg(self.runner.pid, signal.SIGKILL)
        if self.runner:
            self.log.close()
        self.runner = None

    # ----- the request, the wait, the admission, the handover

    def one_request(self, wait_seconds: float) -> dict:
        (self.repo / "operation.json").write_text(json.dumps(self.operation, indent=2) + "\n")
        steps = [arg for name, run in self.consumer_steps for arg in ("--step", name, run)]
        outputs = [arg for path in self.expected for arg in ("--output", path)]
        resources = self.operation.get("resources") or {}
        submit = self.pipeline("submit", "--purpose", "test", "--case", str(self.operation.get("consumer") or "case"),
                               "--title", "Read the task's outputs offline on the prepared inputs",
                               "--description", "The consumer of the gate's one request: it needs the operation ready, runs the original task "
                                                "with no network on the view the receipt hands over, and brings its readbacks back.",
                               "--needs-readiness", "operation.json", "--network", "none", "--phase", "test",
                               "--cpus", str(resources.get("cpus", 1)), "--memory", str(resources.get("memory", "256M")),
                               "--duration", str(resources.get("duration", "5m")), *steps, *outputs)
        consumer = submit.stdout.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]
        unrelated = self.pipeline("submit", "--purpose", "maintenance", "--title", "An unrelated job, to finish while the consumer waits",
                                  "--description", "Has nothing to do with the request: it must not be held up by it.",
                                  "--run", "python3 -c 'print(6 * 7)'").stdout.split("verification/jobs/")[1].split(".json")[0].rsplit("/", 1)[-1]
        requests = sorted(p.name for p in (self.repo / "verification/readiness").glob("*.json"))
        self.check("the request is one file, the operation under its key", len(requests) == 1, requests)
        key = requests[0][:-5]
        self.commit("the case that needs more setup, and an unrelated job")
        self.start_runner()
        self.note("the runner is at work; the consumer needs a readiness nobody has resolved")
        if not self.until(lambda: (self.job(unrelated) or {}).get("state") == "finished", "the unrelated job finished during the wait", 300):
            return {}
        view = self.view()
        waiting = next(j for j in view["jobs"] if j["id"] == consumer)
        request = next((r for r in view["readiness"] if r["key"] == key), {})
        self.check("the unrelated job finished during the wait", True, {"job": unrelated})
        self.check("only the consumer waits, and the view says for what", waiting["state"] == "waiting" and request.get("unanswered") is True
                   and request.get("wantedBy") == [consumer], {"state": waiting["state"], "why": waiting["why"], "request": request})
        self.check("nothing was fetched or published before the admission", not (self.store / "bundles").exists() and not (self.store / "receipts").exists(),
                   sorted(p.name for p in self.store.iterdir()) if self.store.exists() else [])
        said = json.loads(self.pipeline("resolve", "--json", "--by", "the gate, as the watcher", "--run-phase", "watcher").stdout)
        self.check("one resolution job is written for the one request", len(said["written"]) == 1 and not said["skipped"], said)
        if not said["written"]:
            return {}
        resolver = said["written"][0]["job"]
        self.commit("admit the resolution")
        self.pipeline("nudge", check=False)
        self.note(f"admitted {resolver}")
        done = lambda: all((self.job(j) or {}).get("state") == "finished" for j in (resolver, consumer)) or \
            (self.job(consumer) or {}).get("state") == "blocked"
        self.until(done, "the resolution and the consumer finished", wait_seconds)
        self.stop_runner()
        out = {"key": key, "consumer": consumer, "resolver": resolver, "unrelated": unrelated}
        try:
            resolved = self.staged(resolver)
        except (OSError, ValueError) as e:
            self.check("the resolution job left a result", False, str(e))
            return out
        concluded = (resolved.get("conclusion") or {}).get("readiness") or [{}]
        receipt = json.loads((self.store / "receipts" / f"{key}.json").read_text()) if (self.store / "receipts" / f"{key}.json").exists() else {}
        out["receipt"] = {k: receipt.get(k) for k in ("state", "stage", "outcome", "why", "level", "rounds", "fetch", "base", "offline", "at")}
        out["receipt"]["bundle"] = {k: (receipt.get("bundle") or {}).get(k) for k in ("digest", "files")}
        self.check("readiness is established by one resolution job", resolved["status"] == "passed" and concluded[0].get("verdict") == "ready",
                   {"status": resolved["status"], "summary": resolved["summary"], "conclusion": concluded[0], "tail": resolved["steps"][-1].get("tail", [])[-12:]})
        self.check("the resolution's offline run saw no network", ((receipt.get("offline") or {}).get("network") or {}).get("enforced") is True,
                   (receipt.get("offline") or {}).get("network"))
        self.check("what was fetched is what the task asked for, each verified",
                   bool(receipt.get("bundle")) and all(f.get("verifiedBy") for f in receipt["bundle"]["files"] if not f["path"].endswith(".sha1")),
                   [{k: f.get(k) for k in ("path", "bytes", "source", "verifiedBy")} for f in (receipt.get("bundle") or {}).get("files") or []])
        self.check("the base was laid without what the task has to ask for, and the receipt says so", (receipt.get("base") or {}).get("reconstructed") is True,
                   receipt.get("base"))
        try:
            consumed = self.staged(consumer)
        except (OSError, ValueError) as e:
            self.check("the consumer ran", False, {"error": str(e), "job": self.job(consumer)})
            return out
        out["consumerResult"] = {k: consumed.get(k) for k in ("status", "summary", "attention", "readiness", "timing", "startedAt", "finishedAt")}
        self.check("the consumer passed, once, after the resolution", consumed["status"] == "passed" and not consumed["attempt"]["previous"]
                   and consumed["startedAt"] >= resolved["finishedAt"],
                   {"status": consumed["status"], "summary": consumed["summary"], "attention": consumed["attention"],
                    "previous": consumed["attempt"]["previous"], "tail": consumed["steps"][-1].get("tail", [])[-12:]})
        self.check("every step of the consumer ran with no network, shown by a probe",
                   all((s.get("network") or {}).get("enforced") is True for s in consumed["steps"] if s.get("index", 0) > 0 and s["status"] != "skipped"),
                   [(s.get("name"), s.get("network")) for s in consumed["steps"]])
        self.check("the consumer ran on the bundle the receipt names",
                   [(r["key"], r["bundleDigest"]) for r in consumed.get("readiness") or []] == [(key, (receipt.get("bundle") or {}).get("digest"))],
                   consumed.get("readiness"))
        readbacks = {}
        for path, committed in self.expected.items():
            got = self.repo / "verification/.state/results" / consumer / "outputs" / path
            if committed is None:   # no committed copy: byte for byte what the resolution's own offline run wrote, by its receipt
                wrote = {row["path"]: row.get("sha256") for row in (receipt.get("offline") or {}).get("outputs") or []}
                try:
                    readbacks[path] = json.loads(got.read_text())
                    same = hashlib.sha256(got.read_bytes()).hexdigest() == wrote.get(Path(path).name)
                except (OSError, ValueError) as e:
                    readbacks[path], same = f"not read: {e}", False
                self.check(f"the consumer's {path} is byte for byte what the resolution's offline run wrote", same, readbacks[path])
                continue
            try:
                readbacks[path] = json.loads(got.read_text())
                same = readbacks[path] == json.loads((ROOT / committed).read_text())
            except (OSError, ValueError) as e:
                readbacks[path], same = f"not read: {e}", False
            self.check(f"the consumer's {path} is what {committed} records", same, readbacks[path])
        out["readbacks"] = readbacks
        return out

    # ----- the controls: a resolution that must be withheld, with nothing published

    def control(self, name: str, change, stage: str, outcome: str, allow: list) -> dict:
        operation = copy.deepcopy(self.operation)
        change(operation)
        path = self.work / f"control-{name}.json"
        path.write_text(json.dumps(operation, indent=2) + "\n")
        self.note(f"control {name}: a resolution that must be withheld ({outcome})")
        proc = subprocess.run([sys.executable, str(self.repo / "jobs/readiness.py"), "resolve", str(path), "--store", str(self.store),
                               "--work", str(self.work / f"control-{name}-work")], cwd=self.repo,
                              env={**self.env, "ITL_FETCH_ALLOW": json.dumps(allow)}, capture_output=True, text=True)
        key = subprocess.run([sys.executable, str(self.repo / "jobs/readiness.py"), "key", str(path)], cwd=self.repo, capture_output=True, text=True).stdout.strip()
        try:
            receipt = json.loads((self.store / "receipts" / f"{key}.json").read_text())
        except (OSError, ValueError):
            receipt = {}
        seen = {"exit": proc.returncode, "state": receipt.get("state"), "stage": receipt.get("stage"), "outcome": receipt.get("outcome"),
                "why": receipt.get("why"), "rounds": [{k: r.get(k) for k in ("n", "missing", "result", "offlineSeconds")} for r in receipt.get("rounds") or []],
                "said": proc.stdout.strip()[-600:]}
        self.check(f"control {name}: readiness is withheld at the {stage} stage ({outcome}), and nothing is published",
                   proc.returncode == 1 and (receipt.get("state"), receipt.get("stage"), receipt.get("outcome")) == ("failed", stage, outcome)
                   and not (self.store / "bundles" / key).exists(), seen)
        return {"control": name, "key": key, **seen}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--output", type=Path, required=True, help="where the gate's record is written")
    parser.add_argument("--operation", type=Path, default=HERE / "readiness-operation.json")
    parser.add_argument("--work", type=Path, help="a folder for the throwaway repository and the store (default: a new one under ~/.cache/in-the-loop/readiness-gates)")
    parser.add_argument("--no-controls", action="store_true")
    parser.add_argument("--wait", type=float, default=3600, help="seconds to wait for the resolution and the consumer (default 3600)")
    args = parser.parse_args(argv)
    operation = json.loads(args.operation.read_text())
    work = args.work or Path.home() / ".cache/in-the-loop/readiness-gates" / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    work.mkdir(parents=True, exist_ok=True)
    resources = operation.get("resources") or {}
    settings = {"isolation": "none", "workers": 2, "cpus": float(resources.get("cpus", 1)) + 1, "memory": "9G", "job_memory_max": "8G",
                "memory_floor": "0", "keep_workdirs": "never", "poll_seconds": 2, "link": [], "after_collect": [],
                "fetch_allow": [CENTRAL], "fetch_slots": 10}
    replay = f"python3 {REL}/replay.py"
    gate = Gate(work, operation,
                consumer_steps=[(side, f'mkdir -p readbacks tmp && TMPDIR="$PWD/tmp" {replay} {side} --output readbacks/{side}.json') for side in ("parent", "fix")],
                expected={"readbacks/parent.json": f"{REL}/parent.json", "readbacks/fix.json": f"{REL}/fix.json"}, settings=settings)
    record = {"schema": "itl-s48-readiness-gate/v1", "startedAt": now(), "operation": args.operation.name, "work": str(work)}
    try:
        gate.build_repository([REL])
        record["request"] = gate.one_request(args.wait)
        if not args.no_controls:
            def withheld(op):      # the BOM is in no authorised source: one that answers, and does not have it
                op["repositories"] = [CENTRAL + "withheld-by-the-readiness-gate/"]

            def wrong_digest(op):  # the Maven distribution is not the one the operation pins
                op["pinned"][0]["sha512"] = "0" * 128

            def unavailable(op):   # a cold cache, and a repository that does not answer
                op["repositories"] = [NOWHERE]
            record["controls"] = [gate.control("withheld-bom", withheld, "fetch", "absent", [CENTRAL]),
                                  gate.control("wrong-maven-digest", wrong_digest, "fetch", "digest-mismatch", [CENTRAL]),
                                  gate.control("unavailable-repository", unavailable, "fetch", "repository-unavailable", [CENTRAL, NOWHERE])]
    except Exception as e:  # noqa: BLE001  (the record says what stopped it)
        gate.check("the gate ran to its end", False, f"{type(e).__name__}: {e}")
    finally:
        gate.stop_runner()
    return conclude(gate, record, work, args.output)


def conclude(gate: Gate, record: dict, work: Path, output: Path) -> int:
    """Write the gate's record (every check, the timeline, the runner's last lines) and say how it ended."""
    record.update(finishedAt=now(), checks=gate.checks, timeline=gate.timeline,
                  passed=bool(gate.checks) and all(c["passed"] for c in gate.checks))
    try:
        record["runnerLog"] = (work / "runner.log").read_text()[-6000:].splitlines()
    except OSError:
        pass
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n")
    failed = [c["check"] for c in gate.checks if not c["passed"]]
    print(f"\n{len(gate.checks) - len(failed)} of {len(gate.checks)} checks passed" + (f"; failed: {'; '.join(failed)}" if failed else ""))
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
