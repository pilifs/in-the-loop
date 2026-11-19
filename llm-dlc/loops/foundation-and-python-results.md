# Java verification restart evidence

The implementation checkout began at f9693c47, the starter brief on top of main at 11413e85. That line includes the previous foundation merge and the subsequent qualification of example 197's receipts. The following inventory was read before changing the proof route.

## Example 105

Run `python3 examples/tools/targets/workflow_handoff.py handoff 105` to navigate from the source claim to its revisions, receipts, verifier records and pipeline steps. The original receipts and their preparation identities are preserved. [Example 105](../../examples/105-commons-numbers-223-pow-of-minus-two-to-the-31)

| Source claim | Task | Prepared claim | Execution | Recorded conclusion |
|---|---|---|---|---|
| 8a4071f6a417d239 | fix-property | 5955760df7c21aec | 20261114T222911Z-a26d0f04 | Established |
| 8a4071f6a417d239 | fix-property-before | bb2955ce1c93a5d7 | 20261114T222911Z-f3a33202 | Refuted |
| 8a4071f6a417d239 | fix-property-before | bb2955ce1c93a5d7 | 20261115T001438Z-b304cfd0 | Refuted |
| 8a4071f6a417d239 | fix-property-before | d1bb93e6fe366579 | 20261115T051521Z-a8b91f86 | Refuted |
| 1d76c0d0c405f392 | regression | 1e8128d965200158 | 20261114T235516Z-061637d0 | Refuted |
| 6bef0dff1140dc6d | confined-change | 13483ab20b3f6b60 | 20261115T011544Z-71dbed5b | Unresolved |

The current handoff accepts the fixed property. Its JVM-replay requirement leaves the before-property and unrestricted comparison open. The historical before-property verifier records carry interpreter evidence, and the separate controls cover the witness. The confined-change attempt stopped at the StringBuilder constructor. The example README’s 1,083-second JBMC run is a historical measurement of that obligation. [Recorded refusal](../../examples/105-commons-numbers-223-pow-of-minus-two-to-the-31/records/refusals/confined-change.json)

## Two array roots

The merged example 197 already binds the three native receipts to the full 71-input heap domain. A fresh run of the starter oracle on Temurin 21.0.13+9 counted zero return differences, three right-root differences, and 21 combined-root differences. The two integrated JBMC experiments distinguish the mutation and replay it. The preserving runs were refused because JBMC stubs the two generated catch handlers. The smaller distinct-root profile has its own digest. [Native receipts](../../examples/197-shared-int-array-poststates/receipts) · [JBMC profile results](../../verification/results/20261119-164549-197-integrated-jbmc-preserving-and-discr/outputs/verification/foundation-jbmc-array-overlap.json)

## Results on the implementation line

| Required work | Outcome | Evidence |
|---|---|---|
| Qualify the checker | The checker preserved both array and immutable-calendar branch outcomes and refuted both collapsed-value controls. Two fresh JVM settings produced different display widths, each qualified under its own setting. The explicit divide-by-zero handler was reached, the fallback and no-escape claims held, and the unwrapped kernel threw the specified class on zero. Strict checking of the exception message stopped at ArithmeticException.getMessage(). | [Checker and JVM observations](../../verification/restart-checker-qualification.json) |
| Bind and recover Gradebook attempts | A fresh job recovered execution `20261119T220012Z-d733295c`, its candidate and missing independent replay. Two simultaneous retries produced two receipts. Redelivering a completion returned the original identity. A later return-only replay rejection left the established sibling eligible. | [Recovery drill](../../examples/198-gradebook-final-slot/records/retry-drill.json) · [Operational limits of the probes](../../examples/198-gradebook-final-slot/records/probe-policy.json) |
| Bounded array inputs and observers | All three full-domain native claims in 197 retain their original results. JBMC established the preserving pair and refuted the alternative on a separately keyed four-heap grid. Its input constructs two distinct, non-null one-cell arrays with independently chosen binary values. The wider nullable/shared JBMC preservation runs remain open at their generated catch handlers. | [Four-heap statement, artifact hashes and JVM replay](../../verification/restart-jbmc-grid.json) |
| Ordered framework observations | Independent receipts establish the return projection and refute the ordered event projection. Both builds return 90 cents at quantities 99 and 100. Both send (90, 99), and only the old build sends (90, 100). The checker runs under recording stubs. | [Amount receipt](../../examples/193-a-bulk-order-s-quote-event-dropped-in-the-refactor-refuted-on-the-route-s-trace-of-sends/receipts/return-amount/20261119T222809Z-7fe6e24d/receipt.json) · [Ordered-send receipt](../../examples/193-a-bulk-order-s-quote-event-dropped-in-the-refactor-refuted-on-the-route-s-trace-of-sends/receipts/ordered-events/20261119T222809Z-af2070a6/receipt.json) |

### Gradebook

All 17 required claim/subject pairs are decided. Twelve compare a single revision with its own previous-value, poststate, interior or frame rule. Only the regression violates the full poststate rule. Five compare revisions. The complete poststate changes at introduction and repair, and is preserved between baseline and repair. The regression preserves the returned mark and the interior poststate. The three revisions respectively have 0, 78 and 0 whole-array discrepancies on the independent 306-input JVM grid, with zero interior discrepancies on 189 inputs. [Frozen requirements](../../examples/198-gradebook-final-slot/milestones.json) · [Checkpoint plans](../../examples/198-gradebook-final-slot/records/checkpoint-plans.json) · [Translated public plans](../../examples/198-gradebook-final-slot/records/recipe-plans.json)

| Same baseline/regression bytes | Eligible result | Review of scores [0], slot 0, replacement 1 |
|---|---|---|
| Previous mark | Established | Admitted. Both return zero. [Replay](../../examples/198-gradebook-final-slot/receipts/return-only/executions/20261119T223631Z-bda778e4/replay.json) |
| Complete final array | Refuted | Admitted. The two final arrays are [1] and [0]. [Replay](../../examples/198-gradebook-final-slot/receipts/full-state/executions/20261119T223634Z-a29e8521/replay.json) |
| Complete final array on interior slots | Established | The frozen precondition rejects slot 0 on a length-one array. [Replay](../../examples/198-gradebook-final-slot/receipts/interior-state/executions/20261119T223637Z-86af1128/replay.json) |

### Direct and adapter recipes

| Pilot | JVM calibration | Checker disposition |
|---|---|---|
| Apache Commons Math GCD | 45 of 441 incorrect power-pair results on the parent, zero on the fix. Both satisfy the 256 zero cases. At (65536, 65536) the parent returns 131072 and the fix returns 65536. | All four obligations decided on the compiled upstream classes. The checkpoint and the new recipe have identical prepared claims and effective statements. The recipe independently replayed the refutation on the JVM. [Direct comparison](../../examples/309-commons-math-238-gcd/records/route-comparison.json) |
| ThreeTenBP complete hours | The adapter agrees with all 36,864 direct calls per revision. Recompiling it with MINUTES yields 36,672 correspondence discrepancies on each. The parent has 6,912 clock errors, the fix zero. Same-day and sign reversal pass on both. | Five strict claims remain open. Their first blocker is BigInteger.valueOf(long) during Duration class initialization. The finite correspondence applies to June 15–16, 2012 on the quarter-hour grid with HOURS and local civil time. [Adapter report](../../examples/310-threeten-complete-hours/records/adapter-correspondence.json) · [Collected attempts](../../verification/results/20261119-215957-threetenbp-hours-adapter-on-the-qualifie/result.json) |
| Apache Commons Lang UTF-16 search | A second instance of the same adapter recipe uses a StringBuilder. All 160 adapter calls agree with direct calls on each revision. The parent missed 25 last matches and the fix missed zero. Both pass the 85 absent and 120 single-unit cases. | Five strict claims remain open. The checker reports StringBuilder.appendCodePoint and Pattern.compile. [Calibration](../../examples/311-commons-lang-utf16-search/records/calibration.json) · [Collected attempts](../../verification/results/20261119-222214-check-the-supplementary-character-search/result.json) |

On the same fixed GCD claim and artifact binding, a one-second native checker deadline expired after 1.076 seconds. Its linked retry completed in 202.756 seconds at a 600-second deadline. Both ran on the same host with fresh verifier work directories and a shared preparation. Their measured maximum process RSS was 120,905,728 and 943,595,520 bytes. The separate checkpoint comparison preserves its cgroup measurements. The recipe comparison job shares one cgroup step across four claims, so its peak applies to that batch. [Linked attempts, resources and stages](../../examples/309-commons-math-238-gcd/records/budget-comparison.json)

### Handoff

The original 105 and 197 work was already merged at the restart checkpoint. The new checker qualifications, source packets, direct and adapter translation, version-aware result reader, witness qualification and durable history are on the implementation line with the collector’s results. The native scalar/array and bounded framework checks are ready for follow-on examples at their recorded scopes. Further work on exception messages, wide JBMC array preservation, civil time or UTF-16 can start from the named blockers above.

From the repository root, `python3 examples/tools/targets/workflow_handoff.py handoff 198 --markdown` shows latest executions next to eligible results with evidence links. Omitting `--markdown` includes machine-readable bindings and qualifications. Each example’s milestone enumerates its required subject pairs independently of execution count.
