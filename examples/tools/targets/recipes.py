"""Compile a frozen target claim to checker arguments, then bind its ordered classpaths."""

from dataclasses import dataclass
import hashlib
import json
from typing import Optional

from targets.interfaces import RUNTIME, TaskPlan, Unsupported


@dataclass(frozen=True)
class Argument:
    field: str
    flag: str
    value: str
    file: bool = False


@dataclass(frozen=True)
class Invocation:
    argv: tuple[str, ...]
    entry: str
    classpaths: dict
    entries: dict
    timeout: int


@dataclass(frozen=True)
class ProofRecipe:
    kind: str
    command: str
    subject: str
    entry: str
    arguments: tuple[Argument, ...]
    defaults: dict
    correspondence: Optional[dict] = None
    observed_initializers: Optional[dict] = None

    def describe(self):
        return {"kind": self.kind, "command": self.command, "subject": self.subject, "checkedEntry": self.entry,
                "arguments": [dict(field=a.field, flag=a.flag, value=a.value,
                                   **({"bindSha256AtPreparation": True} if a.file else {})) for a in self.arguments],
                "checkerDefaults": self.defaults,
                "preparation": "Bind each original class and the ordered classpath of its revision by digest.",
                **({"observedInitializerStates": self.observed_initializers} if self.observed_initializers else {}),
                **({"correspondence": self.correspondence} if self.correspondence else {})}

    def bind(self, plan, exe, sides, work, timeout):
        from targets import runtime, runtime_jar
        entry = runtime.java_target(self.entry)
        paths, entries, originals, dependencies = {}, {}, {}, {}
        for revision, (_, prepared, artifacts) in sides.items():
            upstream = prepared.source["target"]
            original = upstream["loadedFrom"]
            digest = upstream.get("classSha256")
            selected = [a for a in artifacts if a.path == original or a.role in ("dependency", "stub")]
            if self.correspondence:
                adapter = next((a for a in artifacts if a.role == "adapter"), None)
                if adapter is None or not prepared.source["target"].get("adapterCallsTarget"):
                    raise runtime.Refused("claim", "the prepared adapter has no reference to the declared upstream method")
                owner, method, desc = runtime_jar.parse_target(self.entry)
                data = runtime_jar.read_class(sides[revision][0] / adapter.path, runtime_jar.internal(owner))
                if not data or (method, desc) not in runtime_jar.methods(data):
                    raise runtime.Refused("claim", "the prepared adapter has no declared checked entry")
                digest = hashlib.sha256(data).hexdigest()
                original = adapter.path
                selected.insert(0, adapter)
            entries[revision] = {"entry": self.entry, "classSha256": digest, "loadedFrom": original,
                                 "subject": self.subject, "subjectClassSha256": upstream.get("classSha256")}
            originals[revision] = original
            dependencies[revision] = [a for a in selected if a.path != original]
            paths[revision] = [dict(path=a.path, sha256=a.sha256, role=a.role) for a in selected]
            if self.observed_initializers:
                entries[revision]["initializerClasses"] = initializer_classes(self.observed_initializers, sides[revision][0], paths[revision])

        def classpath(revision, flag):
            return [word for a in dependencies[revision] for word in (flag, f"prepare/{revision}/{a.path}")]

        if self.command == "prove":
            [rev] = plan.revisions
            argv = [exe, self.command, entry, "--classes", f"prepare/{rev}/{originals[rev]}", *classpath(rev, "--classpath")]
        else:
            before, after = plan.revisions
            argv = [exe, self.command, "--before", f"{work}/classes/{before}", "--after", f"{work}/classes/{after}",
                    "--target", entry, *classpath(after, "--classpath")]
            if [a.sha256 for a in dependencies[before]] != [a.sha256 for a in dependencies[after]]:
                argv += classpath(before, "--before-classpath") or ["--before-classpath", ""]
        for arg in self.arguments:
            value = str(runtime._claim_file(plan, arg.field)) if arg.file else arg.value
            argv.extend([arg.flag, value])
        argv.extend(["--timeout", str(timeout), "--work", f"{work}/work", "--report", f"{work}/report", "--json"])
        return Invocation(tuple(argv), self.entry, paths, entries, timeout)


def initializer_classes(names, root, classpath):
    from targets import runtime, runtime_jar
    hashes = {}
    for name in names:
        internal = runtime_jar.internal(name)
        for artifact in classpath:
            data = runtime_jar.read_class(root / artifact["path"], internal)
            if data is not None:
                hashes[name] = hashlib.sha256(data).hexdigest()
                break
        else:
            raise runtime.Refused("claim", f"observed initializer {name} is absent from this revision's prepared classpath")
    return hashes


def translate(plan: TaskPlan) -> ProofRecipe | Unsupported:
    claim = plan.claim
    def refused(field, reason):
        return Unsupported("run-verifier", RUNTIME, f"{field}: {reason}", stage="claim")
    if plan.kind not in ("prove", "equivalence"):
        return refused("kind", f"the direct method recipe has no {plan.kind} invocation")
    bounds = claim.get("bounds") or {}
    unknown = sorted(set(bounds) - {"unwind", "maxArrayLength"})
    if unknown:
        return refused("bounds", f"the claim's bounds {', '.join(unknown)} have no jvmcontract option here")
    if claim.get("models"):
        return refused("models", "the claim states models by file digest, and no route passes these files to the verifier")
    if (claim.get("namedModels") or claim.get("observedInitializers")) and plan.engine != "native":
        return refused("engine", "named models and JVM-observed initializer states require the native checker")
    arguments = []
    def add(field, flag, values):
        arguments.extend(Argument(field, flag, str(value)) for value in values)

    if plan.kind == "equivalence" and claim.get("allowedChange"):
        add("allowedChange", "--unchanged-unless", [claim["allowedChange"]])
    if claim.get("assume"):
        add("assume", "--assume", [claim["assume"]])
    if plan.kind == "prove":
        if claim.get("assert"):
            add("assert", "--assert", [claim["assert"]])
        add("throws", "--throws", claim.get("throws") or [])
    observations = claim.get("observations") or ["result", "exception"]
    defaults = {}
    if all(isinstance(o, dict) for o in observations):
        if plan.kind != "equivalence":
            return refused("observations", "typed observation selection currently requires a paired equivalence task")
        add("observations", "--observe", [json.dumps(o, sort_keys=True) for o in observations])
    elif set(o for o in observations if isinstance(o, str)) == {"result", "exception"} and len(observations) == 2:
        defaults["observations"] = {"values": observations, "evidence": "stated.observations"}
    else:
        return refused("observations", f"the {plan.kind} default covers result and exception; selection {observations!r} has no lowering")
    for field, flag in (("nullable", "--nullable"), ("mayAlias", "--may-alias")):
        add(field, flag, claim.get(field) or [])
        if not claim.get(field):
            defaults[field] = {"values": [], "evidence": "stated.domain"}
    if not claim.get("assume"):
        defaults["assume"] = {"value": True, "evidence": "absence of a precondition in stated.assumptions"}
    if claim.get("assumptions"):
        defaults["authoredQualifications"] = claim["assumptions"]
    if claim.get("boundEnvironment"):
        defaults["requiredStatementEvidence"] = claim["boundEnvironment"]
    for field, flag in (("plan", "--plan"), ("contracts", "--contracts")):
        if claim.get(field):
            arguments.append(Argument(field, flag, claim[field]["path"], file=True))
    if plan.checkedLemmas:
        arguments.append(Argument("checkedLemmas", "--lemmas", plan.checkedLemmas["path"], file=True))
    add("engine", "--engine", [plan.engine])
    add("gaps", "--gaps", [plan.gaps])
    add("namedModels", "--model", claim.get("namedModels") or [])
    add("observedInitializers", "--observed-initializer", sorted(claim.get("observedInitializers") or {}))
    for field, flag in (("unwind", "--unwind"), ("maxArrayLength", "--max-array-length")):
        if field in bounds:
            add("bounds." + field, flag, [bounds[field]])
    adapter = claim.get("adapter")
    if adapter and not any(c["kind"] == "oracle" and c["id"] == adapter["correspondence"] for c in claim.get("controls", [])):
        return refused("adapter.correspondence", "the correspondence oracle is not frozen in the claim")
    return ProofRecipe("adapter" if adapter else "direct-method", plan.kind, plan.target,
                       adapter["entry"] if adapter else plan.target, tuple(arguments), defaults, adapter, claim.get("observedInitializers"))
