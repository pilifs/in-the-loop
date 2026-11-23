"""Exercise a false frame claim at the opt-in issuer boundary and verify consumer isolation."""

from pathlib import Path
import shutil
import tempfile

from prepare import HERE, digest
from replay import contained, fresh_rust


def issuer_frame_case(binary, bundle, observation):
    # This experimental issuer normally declines a frame claim contradicted by the original JVM.
    # The control injects the wrong premise at that boundary. Production records are never consumed here.
    def issue(frame_holds):
        return (bundle / "evidence.cert").read_bytes() if frame_holds else None

    observed = observation["heapAtReturn"] == observation["input"]
    honest = issue(observed)
    faulty = issue(True)
    if honest is not None or faulty is None:
        raise ValueError("the chosen input must distinguish the two issuers")
    with tempfile.TemporaryDirectory() as tmp:
        cert = Path(tmp) / "producer.cert"
        cert.write_bytes(faulty)
        req = bundle / "external.request"
        artifact = bundle / "artifact.bin"
        answer = fresh_rust(binary, req, cert, artifact, [bundle / "support.bin"])
    if answer["exit"] != 2 or "frame changed" not in answer["stdout"]:
        raise ValueError(answer)
    return {
        "route": "Rust",
        "control": "experimental-issuer-false-frame",
        "expected": "rejected",
        "actual": "rejected",
        "requestedClaim": req.read_text(),
        "requestSha256": digest(req.read_bytes()),
        "classSha256": digest(artifact.read_bytes()),
        "checkerVersion": digest(binary.read_bytes()),
        "certificateSha256": digest(faulty),
        "honestIssuer": "declined",
        "faultyIssuer": "issued all return and frame obligations",
        "jvmObservation": observation,
        "consumer": answer,
    }


def isolation(binary):
    with tempfile.TemporaryDirectory() as allowed, tempfile.TemporaryDirectory() as outside:
        folder = Path(allowed)
        shutil.copyfile(binary, folder / "kernel")
        (folder / "kernel").chmod(0o755)
        cache = Path(outside) / "known-cache"
        cache.write_text("outside")
        files = {
            "producer": HERE.parents[1] / "python/jvm_array_induction.py",
            "prior verdict": HERE / "evidence/baseline/336.json",
            "cache": cache,
        }
        results = {}
        for name, p in files.items():
            if not p.is_file():
                raise ValueError("isolation probe needs an existing " + name)
            ck = contained(["./kernel", str(p), "unused.cert", "unused.bin"], folder)
            if ck["exit"] != 2 or "Permission denied" not in ck["stdout"]:
                raise ValueError((name, ck))
            results[name] = ck["stdout"]
    return results
