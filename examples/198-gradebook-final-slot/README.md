# Gradebook and the last-slot write

The three fixture revisions return the previous mark. The regression skips the write to the last cell. The repair skips a write only when the cell already contains the requested mark. All three source files come from the restart brief’s starter kit.

| Observation | Inputs per revision | Baseline errors | Regression errors | Repair errors |
|---|---:|---:|---:|---:|
| Previous mark | 306 | 0 | 0 | 0 |
| Complete poststate | 306 | 0 | 78 | 0 |
| Complete poststate, interior slots | 189 | 0 | 0 | 0 |
| Untargeted cells | 306 | 0 | 0 | 0 |

On scores `[0]`, slot 0 and replacement 1, every revision returns zero. The baseline and repair leave `[1]` and the regression leaves `[0]`. This input is outside the interior domain. The JVM driver enumerates each input on a fresh array and the oracle checks the previous mark and each final cell independently.

The five paired obligations cover the regression, repair and preserving refactor. Four additional properties
on each individual revision check the previous value, the full replacement rule, its interior restriction,
and every untargeted cell against its own initial value. [Frozen obligations](milestones.json) · [Public plans](records/recipe-plans.json)

To examine the starter witness under another claim, run
`python3 examples/tools/build.py 198 --task interior-state --replay-witness examples/198-gradebook-final-slot/controls/last-slot-witness.json`.
This creates a JVM replay execution and records the domain rejection. The return-only review admits the
same input and finds equal returns. The full-state review records different final arrays. Each review
points to the original classes, program, input and selected values.
