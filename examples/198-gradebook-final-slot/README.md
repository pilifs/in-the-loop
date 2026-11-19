# Gradebook and the last-slot write

The three fixture revisions return the previous mark. The regression skips the write to the last cell. The repair skips a write only when the cell already contains the requested mark. All three source files come from the restart brief’s starter kit.

| Observation | Inputs per revision | Baseline errors | Regression errors | Repair errors |
|---|---:|---:|---:|---:|
| Previous mark | 306 | 0 | 0 | 0 |
| Complete poststate | 306 | 0 | 78 | 0 |
| Complete poststate, interior slots | 189 | 0 | 0 | 0 |
| Untargeted cells | 306 | 0 | 0 | 0 |

On scores `[0]`, slot 0 and replacement 1, every revision returns zero. The baseline and repair leave `[1]` and the regression leaves `[0]`. This input is outside the interior domain. The JVM driver enumerates each input on a fresh array and the oracle checks the previous mark and each final cell independently.
