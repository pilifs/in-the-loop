"""Replay the qualified stock client's generated multiple results and mutate only its copied synthetic sidecar."""

import argparse
import json
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
BASE = (HERE.parent.parent / "claude-native-resume").resolve()
sys.path[:0] = [str(HERE.parent), str(BASE)]
import runner_core as core  # noqa: E402
import control  # noqa: E402
import isolation  # noqa: E402
import probe  # noqa: E402
import resume_meter as meter  # noqa: E402
import native_result  # noqa: E402


def check(args, model):
    out = args.scratch / model / args.shape
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    pair, _ = probe.packet(out)
    generated = out / "fixture"
    isolation.fresh_case(generated, pair, isolation.digest(pair / "pair.json"))
    work = generated / "work"
    profile = core.json_file(BASE / "claude-native-resume.json")
    core.atomic(
        work / "synthetic.json",
        {"shape": args.shape, "model": model, "options": profile["explicitSettings"]},
    )
    shutil.copy2(HERE / "stock_guest.py", work / "stock_guest.py")
    response = control.execute(
        args.base_shadow,
        generated,
        {
            "type": "function_call",
            "name": "case_command",
            "arguments": json.dumps({"argv": ["python3", "/case/work/stock_guest.py"]}),
        },
        timeout=35,
    )
    if response["exit"]:
        raise ValueError("the offline native synthetic sequence failed")
    generated_result = json.loads(response["output"])
    assert len(generated_result["wire"]) == 3 and generated_result["brokerCompleted"] == [
        [1, 1],
        [1, 2],
        [2, 1],
        [2, 2],
    ]
    terminal = generated_result["wire"][-1]["previous"]
    if args.shape != "control":
        return {
            "fixtureThirdRequest": terminal,
            "copiedResultFiles": generated_result["copiedResultFiles"],
        }
    assert len(terminal) == 2 and all(
        p["idPresent"] and p["hasPersistenceMarker"] and not p["directVisiblePresent"]
        for p in terminal
    )
    state = work / "state"
    old = next((state / "projects").glob("*/*.jsonl"))
    session = old.stem
    ident = "toolu_public_2_2"
    raw = "synthetic-2-2\n" + "\x01" * 13000 + "\n"
    shown = raw.encode()[:12000].decode() + "\n[Output truncated. Rerun with a narrower projection.]"
    ident_sha = native_result.digest(ident.encode())
    previous = {
        "transcriptSha256": isolation.digest(old),
        "lastVisibleBlockSha256": native_result.signal(shown),
        "lastToolResultIdSha256": ident_sha,
    }
    base_copy = meter.copy_current
    result = {}
    positive = 0
    try:
        for mutation in ("original", "substituted", "foreign-path", "wrong-id"):

            def copy(source, state, session, target):
                base_copy(source, state, session, target)
                known = {}
                directory = source.parent / session / "tool-results"
                for entry in directory.iterdir():
                    relative = entry.relative_to(state)
                    guest = Path("/case/work/state") / relative
                    saved = target / relative
                    if entry.stem == ident and mutation == "substituted":
                        saved.write_text(
                            json.dumps(
                                [
                                    {
                                        "type": "text",
                                        "text": json.dumps(
                                            {"exit": 0, "output": "changed public synthetic bytes"}
                                        ),
                                    }
                                ]
                            )
                        )
                    if mutation == "foreign-path" and entry.stem == ident:
                        guest = Path("/other-role") / relative
                    known[native_result.digest(str(guest).encode())] = {
                        "relative": relative.as_posix(),
                        "sha256": isolation.digest(saved),
                    }
                core.atomic(
                    target.parent / "native-result-bindings.json",
                    {
                        "files": known,
                        "outcomeSha256": native_result.outcome({"exit": 0, "output": shown}),
                        "trustedToolIdSha256": ident_sha,
                    },
                )

            meter.copy_current = copy
            scratch = out / mutation
            scratch.mkdir()
            control_budget = SimpleNamespace(
                root=scratch,
                shadow_product=args.amended_shadow,
                profile=profile,
                require_time=lambda: None,
                left=lambda: 20,
            )
            sample = (
                {**previous, "lastToolResultIdSha256": "0" * 64}
                if mutation == "wrong-id"
                else previous
            )
            try:
                outcome = meter.measure(
                    control_budget,
                    model,
                    state,
                    session,
                    sample,
                    "Continue the same public synthetic role.",
                )
            except core.Stopped as exc:
                assert exc.code == "shadow-meter" and mutation != "original"
                outcome = core.json_file(scratch / "last-shadow-observation.json")
            else:
                assert (
                    mutation == "original" and outcome["nativeRestore"] == "verified-native-preview"
                )
                positive += 1
            assert isolation.digest(old) == previous["transcriptSha256"]
            result[mutation] = {
                k: outcome[k]
                for k in (
                    "nativeRestore",
                    "priorSignalRestored",
                    "priorToolResultIdRestored",
                    "model",
                    "effort",
                    "sessionMatched",
                    "identityEncoding",
                    "fakeKeyOnly",
                    "maxOutputTokens",
                    "tools",
                )
            }
    finally:
        meter.copy_current = base_copy
    assert positive == 1
    return {
        "fixtureThirdRequest": terminal,
        "copiedResultFiles": generated_result["copiedResultFiles"],
        "checks": result,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-shadow", type=Path, required=True)
    parser.add_argument("--amended-shadow", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--model", choices=("claude-fable-5-2", "claude-opus-5-5"), required=True)
    parser.add_argument(
        "--shape",
        choices=(
            "control",
            "short",
            "empty",
            "plain",
            "xml",
            "json",
            "dense",
            "unicode",
            "escapes",
            "escaped-unicode",
            "error",
        ),
        default="control",
    )
    args = parser.parse_args()
    print(json.dumps(check(args, args.model), indent=2))
