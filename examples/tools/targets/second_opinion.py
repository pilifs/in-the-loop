"""Check a registered array-induction request on the original classpath with a frozen independent checker."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

from targets import array_induction, interfaces, route, runtime, runtime_jar, runtime_jdk, sidecar, workflow

ROOT = Path(__file__).resolve().parents[3]
KERNEL = ROOT / "lib/benchmark/trusted-kernel"
PIN = "635cc9433ada216c0f065c10d823c2b4d3f1cc67f5e9354de9151995f9604da1"
ENVIRONMENT = "initialized-verified-jvm-v1"
REQUESTS = {
    ("336", "first-any-length"): "requests/Ints.request",
    ("346", "first-any-length"): "requests/Longs.request",
    **{("337", name): f"evidence/range-proof/{name}.request"
       for name in ("fill-any-length", "caller-any-length", "caller-extra-any-length")},
}


class BindingError(ValueError):
    """The selected deployment and the registered external request describe different subjects."""


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def consumer(work, supplied):
    from frozen_range import int_kernel

    default = Path.home() / ".cache/in-the-loop/trusted-kernel-receiver-recovery/kernel/kernel-at-head"
    candidate = supplied or (default if default.is_file() else None)
    if candidate is None:
        binary = int_kernel(work / "build")
        mode = "rebuilt from pinned sources"
    else:
        binary = work / "consumer"
        shutil.copy2(candidate, binary)
        mode = "prebuilt"
    if digest(binary) != PIN:
        raise ValueError("independent checker differs from the registered binary")
    return binary, mode


def extract(owner, home, jars, destination):
    if owner.startswith("java/"):
        with zipfile.ZipFile(home / "jmods/java.base.jmod") as image:
            data = image.read("classes/" + owner + ".class")
    else:
        definitions = [data for jar in jars if (data := runtime_jar.read_class(jar, owner)) is not None]
        if len(definitions) != 1:
            raise ValueError(f"expected one deployable definition of {owner}, found {len(definitions)}")
        data = definitions[0]
    if runtime_jar.this_class(data) != owner:
        raise ValueError(f"selected class has a different name from {owner}")
    destination.write_bytes(data)
    return destination


def bind(folder, target, spec, request, work):
    plan, source_key = array_induction.record_key(folder, target, spec)
    prepared = route.prepare_revision(plan, spec["revision"], work / "prepared", {})
    if isinstance(prepared, interfaces.Unsupported) or prepared.stage != "artifacts-ready":
        raise ValueError(f"original preparation failed: {prepared}")
    entries = [a for a in runtime._checked(work / "prepared", prepared) if a.role in ("original", "dependency")]
    jars = [work / "prepared" / a.path for a in entries]
    artifact_plan, = [a for a in plan.artifacts if a["revision"] == spec["revision"]]
    feature, = artifact_plan["jdks"]
    home = Path(runtime_jdk.home(feature))
    lines = request.read_text().splitlines()
    fields = dict(line.split(" ", 1) for line in lines)
    owner, name, desc = runtime_jar.parse_target(spec.get("caller", spec["entry"]))
    owner = owner.replace(".", "/")
    theorem = ("least-index-frame-total-v1" if spec["rule"] == "first-index" else
               "range-fill-caller-frame-observation-v1" if "caller" in spec else "range-fill-frame-v1")
    if (len(lines) != len(fields) or fields["request"] != "1" or
            (fields["environment"], fields["theorem"], fields["entry"]) != (ENVIRONMENT, theorem, f"{name} {desc}")):
        raise BindingError("external request disagrees with the selected contract")
    artifact = extract(owner, home, jars, work / "class.bin")
    if fields["class"] != f"{owner} {digest(artifact)}":
        raise BindingError("original class does not match the external request")
    dependencies = []
    if "caller" in spec:
        called, method, signature = runtime_jar.parse_target(spec["entry"])
        dependency = called.replace(".", "/")
        role = "callee"
        if fields["companion"] != f"{method} {signature}":
            raise BindingError("caller request selects a different callee method")
    else:
        dependency = runtime_jar.super_class(artifact.read_bytes())
        role = "support"
    if dependency and dependency != "java/lang/Object":
        bound = extract(dependency, home, jars, work / "dependency.bin")
        if fields.get(role) != f"{dependency} {digest(bound)}":
            raise BindingError(f"external {role} differs from the deployed class")
        dependencies.append(bound)
    elif "support" in fields or "callee" in fields:
        raise BindingError("external request adds an unbound dependency")
    classes = {owner: digest(artifact)}
    if dependencies:
        classes[dependency] = digest(dependencies[0])
    deployment = {"sourceKey": source_key, "revision": spec["revision"], "preparation": prepared.commit,
                  "classes": classes, "classpath": [{"path": a.path, "role": a.role, "sha256": a.sha256} for a in entries],
                  "jdk": runtime_jdk.identity(home), "javaModuleImageSha256": digest(home / "lib/modules")}
    return fields, artifact, dependencies, deployment


def classify(run, request_sha, fields):
    code, output = run["exit"], run["stdout"]
    if len(output.splitlines()) != 1:
        return "checker unavailable"
    if code == 0:
        owner, class_sha = fields["class"].split()
        entry = fields["entry"].replace(" ", "")
        companion = fields["companion"].replace(" ", "")
        expected = (f"accepted {fields['theorem']} {owner}#{entry} companion {companion} environment {ENVIRONMENT} "
                    f"class {class_sha} request {request_sha} obligations ")
        count = output.removeprefix(expected)
        return "independently established" if count != output and count.isdecimal() and int(count) > 0 else "checker unavailable"
    if code == 2 and output.startswith("rejected checked witness "):
        return "checked counterexample"
    if code == 3 and output in ("unsupported cut point or cursor local", "unsupported range cut point or cursor"):
        return "invalid evidence"
    if code == 3 and output.startswith("unsupported "):
        return "unsupported scope"
    if code == 2 and output.startswith("rejected "):
        reason = output.removeprefix("rejected ")
        if reason.startswith(("certificate", "missing obligation", "unexpected obligation", "duplicate obligation",
                              "missing hints", "external ", "support class", "superclass resolution",
                              "missing external", "invalid witness", "bad support", "missing prefix invariant",
                              "missing written-prefix cut", "invalid cut PC", "invalid cursor slot",
                              "invalid range cut PC", "invalid range cursor slot", "witness outside int domain")):
            return "invalid evidence"
        return "unsupported scope"
    return "checker unavailable"


def conclusion(primary, independent):
    if ((primary == "established" and independent == "checked counterexample") or
            (primary == "refuted" and independent == "independently established")):
        return "contradicted"
    return independent


def evaluate(folder, target, spec, work, supplied_kernel=None, supplied_evidence=None, seconds=60):
    # Benchmark modules also serve the command-line experiment. Import them only for this opt-in route.
    if str(KERNEL) not in sys.path:
        sys.path.insert(0, str(KERNEL))
    start = time.monotonic()
    array_induction.run(folder, target, spec, seconds, records=work / "ordinary")
    record, = (work / "ordinary" / spec["id"]).glob("*/result.json")
    primary = json.loads(record.read_bytes())
    result = {"schema": "array-second-opinion/v1", "example": folder.name[:3], "contract": spec["id"],
              "ordinary": primary, "ordinaryRecordSha256": digest(record), "times": {"ordinary": time.monotonic() - start}}
    selection = REQUESTS.get((folder.name[:3], spec["id"]))
    if selection is None:
        return {**result, "assurance": "unsupported scope", "reason": "no independently registered request for this contract"}
    try:
        check_bound(folder, target, spec, work, selection, supplied_kernel, supplied_evidence, result)
    except BindingError as exc:
        result.update(assurance="invalid evidence", reason=str(exc))
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        result.update(assurance="checker unavailable", reason=str(exc))
    result["times"]["wholeRun"] = time.monotonic() - start
    return result


def check_bound(folder, target, spec, work, selection, supplied_kernel, supplied_evidence, result):
    from certificate import issue as issue_search
    from range_certificate import issue as issue_range
    from replay import fresh_rust

    primary = result["ordinary"]
    request = work / "external.request"
    shutil.copyfile(KERNEL / selection, request)
    clock = time.monotonic()
    fields, artifact, dependencies, deployment = bind(folder, target, spec, request, work)
    if (primary["sourceKey"] != deployment["sourceKey"] or primary["classpath"] != deployment["classpath"] or
            {k: v["sha256"] for k, v in primary["classes"].items()} != deployment["classes"] or
            primary["jdk"] != deployment["jdk"] or primary["preparation"] != deployment["preparation"]):
        raise BindingError("the two preparations select different inputs")
    result.update(request=request.read_text(), requestSha256=digest(request), deployment=deployment)
    result["times"]["independentPreparation"] = time.monotonic() - clock
    clock = time.monotonic()
    binary, mode = consumer(work, supplied_kernel)
    result["times"]["checkerPreparation"] = time.monotonic() - clock
    clock = time.monotonic()
    cert = work / "evidence.cert"
    if supplied_evidence:
        shutil.copyfile(supplied_evidence, cert)
    elif spec["rule"] == "first-index":
        cert.write_text(issue_search(request, artifact))
    else:
        cert.write_text(issue_range(request, artifact, dependencies[0] if dependencies else None))
    result["times"]["certificatePreparation"] = time.monotonic() - clock
    clock = time.monotonic()
    checked = fresh_rust(binary, request, cert, artifact, dependencies)
    elapsed = time.monotonic() - clock
    independent = classify(checked, result["requestSha256"], fields)
    result.update(independent={"disposition": independent, "checkerSha256": PIN, "checkerPreparation": mode,
                               "certificateSha256": digest(cert), "certificateBytes": cert.stat().st_size,
                               "suppliedEvidence": supplied_evidence is not None, **checked},
                  assurance=conclusion(primary["status"], independent))
    result["times"].update(isolatedProcess=checked["wallSeconds"], stagingAndProcess=elapsed)


def main(argv):
    import build

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("example")
    parser.add_argument("contract")
    parser.add_argument("--second-opinion", required=True, action="store_true")
    parser.add_argument("--kernel", type=Path, help="prebuilt binary with the registered checker digest")
    parser.add_argument("--certificate", type=Path, help="untrusted hints to check against the registered request")
    parser.add_argument("--checker-seconds", type=int, default=60)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    if args.checker_seconds < 1:
        parser.error("positive checker deadline required")
    try:
        folder, = build.EXAMPLES.glob(args.example + "-*")
        target = sidecar.load(folder, build.load_example(folder))
        spec, = [s for s in target.get("arrayContracts", []) if s["id"] == args.contract]
        with tempfile.TemporaryDirectory() as tmp:
            result = evaluate(folder, target, spec, Path(tmp), args.kernel, args.certificate, args.checker_seconds)
        output = args.output or (folder / "records/second-opinion" / args.contract /
                                 workflow.canonical_digest(result)[:20] / "result.json")
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=output.parent, delete=False) as handle:
            json.dump(result, handle, indent=2)
            handle.write("\n")
        Path(handle.name).replace(output)
        print(f"{args.example}/{args.contract}: ordinary {result['ordinary']['status']}, {result['assurance']}, {output}")
        return 0 if result["assurance"] == "independently established" else 1
    except (ValueError, OSError, KeyError, subprocess.SubprocessError) as exc:
        print(f"Second opinion unavailable: {exc}", file=sys.stderr)
        return 2
