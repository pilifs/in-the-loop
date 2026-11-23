# Wide conversions on Commons Lang fractions and mutable doubles

Fraction rounding covers every numerator in [2²⁴, 2²⁵). MutableDouble narrowing covers every binary64 value in [2³¹, 2³²), before and after a sign change.

| Public caller | Frozen observation | Expected |
|---|---|---|
| `WideNumbers#fraction` (numbers) | Widening Fraction.getFraction(n, 2).floatValue() gives the independently rounded even neighbor. | established |
| `WideNumbers#fractionOpcode` (numbers) | The direct i2f, fdiv and f2d sequence agrees with the independently rounded even neighbor. | established |
| `WideNumbers#floorOnly` (numbers) | The widened float value is always the integer floor of n/2. | refuted |
| `WideNumbers#narrow` (numbers) | MutableDouble clamps to MAX_VALUE before setValue(-x) and to MIN_VALUE afterwards for every mantissa. | established |
| `WideNumbers#narrowOpcode` (numbers) | The two direct d2i conversions clamp to the appropriate signed extrema. | established |
| `WideNumbers#wraps` (numbers) | The public intValue result agrees with narrowing through a long. | refuted |

Inspect each strict task with `python3 examples/tools/build.py --plan 377`. The original-JVM controls, paired engine measurements and raw checker outputs use the frozen inputs in the campaign. [Campaign brief](../../llm-dlc/loops/jbmc-java-semantics-gap-brief.md)

```sh
python3 lib/benchmark/java-semantics-gap/campaign.py jvm numbers --output "$TMPDIR/semantics"
```
