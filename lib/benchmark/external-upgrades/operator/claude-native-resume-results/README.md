# Native Claude tool-result restoration

The frozen history-preserving operator stopped before its third model request on the disclosed Commons Text upgrade. Its first report recorded two planner requests, two tool calls in each, 2,080 charged tokens and $0.0721872. The sealed record identifies a failed shadow check. It did not retain the failed predicate. [Original first report](../claude-native-resume/opening-reports/V0/u-d8e01af4/operator.json)

A separate, unscored run on the same public source pair also stopped at the third shadow. Its two Fable requests cost $0.0521056 and the diagnostic took 16.541 seconds. The tool ID, role session, catalogue, prompt, high effort and output cap matched. The broker had returned a 36-byte error from a command that exited 127. The stock client preserved the entire JSON result and appended a 174-character system reminder. The old parser looked for a complete JSON document and missed the intact prefix. The third shadow made no model request. [Bounded diagnostic and offline recheck](evidence/commons-text-diagnostic.json)

A separate generated case produced a second legitimate stock representation. Two tools per native response each returned 12,054 bytes of control-heavy text. The client wrote each result to its own session file and placed a 2,217-byte preview in the next request. Ordinary generated XML, JSON, text, Unicode and empty results remained directly visible. [Generated message checks](evidence/generated-results.json)

## Acceptance

The launcher loads the existing frozen scheduler, roles, prompts, resource limits and token reservation. After a payable request, the extension joins the actual native tool-use ID and its argument vector to the broker’s recorded exit and output. Ambiguous matches stop the run. The previous role transcript SHA, current session UUID and original case tool checks all still apply. [Controller extension](observation.py)

The meter accepts a complete matching broker object, optionally followed by the stock system-reminder wrapper. For a preview, it also verifies the hash of the exact original absolute reference, the owning session and tool ID, and the contained regular sidecar’s complete byte digest. The sidecar must decode to the expected exit and normalized output. A symlink, a replacement with a freshly recomputed digest, a foreign role, an unrelated tool ID and arbitrary trailing text all fail. When the client supplies a preview, the model sees the preview. The private meter checks the retained bytes without adding them to the conversation. The shadow records its restoration mode. The scorecard seals its final sanitized predicate flags as a separately hashed evidence file. [Result validation](native_result.py) · [Negative controls](evidence/semantic-controls.json) · [Stock-client checks for both roles](evidence/native-client-checks.json) · [Retained failed-shadow receipt](evidence/sealed-shadow-failure.json)

## Reproduce the controls

~~~sh
op=lib/benchmark/external-upgrades/operator/claude-native-resume-results
python3 "$op/prepare_shadow.py" --base-shadow "$FROZEN_NATIVE_SHADOW" --output "$NEW_SHADOW"
python3 "$op/check_restoration.py" --scratch "$TMPDIR"
python3 "$op/qualification/check_stock.py" --base-shadow "$FROZEN_NATIVE_SHADOW" \
  --amended-shadow "$NEW_SHADOW" --scratch "$NEW_SYNTHETIC_DIRECTORY" --model claude-fable-5-2
python3 "$op/qualification/check_stock.py" --base-shadow "$FROZEN_NATIVE_SHADOW" \
  --amended-shadow "$NEW_SHADOW" --scratch "$NEW_SYNTHETIC_DIRECTORY" --model claude-opus-5-5
~~~

The generated checks run the installed client against a private loopback endpoint with a fabricated key and produce aggregate results. For a separately admitted case, use `python3 "$op/launch.py"` with the usual native-resume arguments, this amendment’s `--shadow-product` and `--launch-sha256`, and fresh case and first-report directories. The V0 subject tree and measured environment are the same as the original history-preserving operator. Transfer builds can use `launch.py freeze-launch` with their own build locks. The signed study roster must name this new shared profile for a scored run. [Amendment identity](profile.json) · [V0 launch](v0-launch.json)

The offline recheck accepted the diagnostic transcript and both synthetic stock formats. The paid diagnostic used the published earlier profile. It did not produce a new Commons Text proof or establish the cause of the older first report.
