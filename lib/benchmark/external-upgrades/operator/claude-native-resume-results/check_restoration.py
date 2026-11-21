"""Small fail-closed result-binding checks with fabricated role, tool IDs and sidecars."""

import argparse
import json
from pathlib import Path
import sys
import tempfile
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "claude-native-resume"))
import native_result as nr  # noqa: E402
import observation  # noqa: E402
import isolation  # noqa: E402


def check(root):
    state = root / "state"
    session = str(uuid.uuid4())
    ident = "toolu_synthetic_2"
    other = "toolu_synthetic_foreign"
    expected = {"exit": 127, "output": "missing synthetic executable\n"}
    received = json.dumps(expected)
    spec = {
        "session": session,
        "expectedToolResultIdSha256": nr.digest(ident.encode()),
        "expectedBlockSha256": "1" * 64,
    }
    rel = Path("projects/-srv") / session / "tool-results" / (ident + ".json")
    path = state / rel
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"type": "text", "text": received}]))
    pointer = "/qualified/private-role/" + rel.as_posix()
    bound = {
        "outcomeSha256": nr.outcome(expected),
        "trustedToolIdSha256": spec["expectedToolResultIdSha256"],
        "files": {
            nr.digest(pointer.encode()): {
                "relative": rel.as_posix(),
                "sha256": nr.digest(path.read_bytes()),
            }
        },
    }

    def preview(reference):
        return (
            "<persisted-output>\nOutput too large (81.1KB). Full output saved to: "
            + reference
            + "\n\nPreview (first 2KB):\n{...}\n</persisted-output>"
        )

    def mode(value, tool=ident, cfg=spec, release=bound):
        messages = [
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": tool, "content": value}],
            }
        ]
        return nr.restore(messages, cfg, release, state, set())

    scenarios = {}

    def expect(name, observed, accepted):
        assert observed["accepted"] is accepted, (name, observed)
        scenarios[name] = observed["mode"]

    expect("wholeResult", mode([{"type": "text", "text": received}]), True)
    expect(
        "stockReminder",
        mode(received + "\n<system-reminder>Fresh stock status.</system-reminder>"),
        True,
    )
    expect("arbitraryTail", mode(received + " trailing unknown data"), False)
    expect("changedExit", mode(json.dumps({**expected, "exit": 0})), False)
    expect("changedOutput", mode(json.dumps({**expected, "output": "other"})), False)
    expect("verifiedPreview", mode(preview(pointer)), True)
    expect("unregisteredPointer", mode(preview("/another/account/" + rel.as_posix())), False)
    expect("foreignToolId", mode(preview(pointer), other), False)
    expect(
        "wrongRoleSession", mode(preview(pointer), cfg={**spec, "session": str(uuid.uuid4())}), False
    )
    broken = {
        "relative": str(
            Path("projects/-srv") / str(uuid.uuid4()) / "tool-results" / (ident + ".json")
        ),
        "sha256": nr.digest(path.read_bytes()),
    }
    expect(
        "foreignSidecar",
        mode(preview(pointer), release={**bound, "files": {nr.digest(pointer.encode()): broken}}),
        False,
    )
    path.write_text(
        json.dumps([{"type": "text", "text": json.dumps({"exit": 127, "output": "changed result"})}])
    )
    expect("substitutedSidecar", mode(preview(pointer)), False)
    copied = {"relative": rel.as_posix(), "sha256": nr.digest(path.read_bytes())}
    expect(
        "rehashedSubstitutedOutcome",
        mode(preview(pointer), release={**bound, "files": {nr.digest(pointer.encode()): copied}}),
        False,
    )
    path.unlink()
    outside = root / "other-role.json"
    outside.write_text(json.dumps([{"type": "text", "text": received}]))
    path.symlink_to(outside)
    expect("symlinkedSidecar", mode(preview(pointer)), False)
    # Native message order and completion order need not agree. Bind the correct actual argv.
    transcript = state / "projects/-srv" / (session + ".jsonl")
    blocks = [
        {
            "type": "tool_use",
            "id": key,
            "name": "mcp__neutral_case__case_command",
            "input": {"argv": ["cmd", name]},
        }
        for key, name in [(other, "left"), (ident, "right")]
    ]
    transcript.write_text(json.dumps({"type": "assistant", "message": {"content": blocks}}) + "\n")
    prior = {
        "lastToolResultIdSha256": spec["expectedToolResultIdSha256"],
        "transcriptSha256": isolation.digest(transcript),
    }
    journal = root / "real-shaped-broker.jsonl"
    rows = [
        {"argv": ["cmd", "right"], **expected},
        {"argv": ["cmd", "left"], "exit": 0, "output": "different sibling result"},
    ]
    journal.write_text("".join(json.dumps(row) + "\n" for row in rows))
    bound = observation.recorded_outcome(state, session, prior, journal)
    assert bound["outcomeSha256"] == nr.outcome(expected)
    scenarios["reversedCompletionOrder"] = "bound-actual-argv"
    with journal.open("a") as out:
        out.write(
            json.dumps({"argv": ["cmd", "right"], "exit": 0, "output": "different second completion"})
            + "\n"
        )
    assert observation.recorded_outcome(state, session, prior, journal) == {}
    scenarios["ambiguousRepeatedCommand"] = "refused"
    return scenarios


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", required=True, type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(dir=args.scratch) as temp:
        print(json.dumps(check(Path(temp)), indent=2))
