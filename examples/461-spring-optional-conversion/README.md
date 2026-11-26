# Optional conversion eligibility reflects its known element type

Spring stopped offering an Optional<Integer> to LocalDate conversion when its default converters could not supply it.

| History | Observation |
|---|---|
| Intent | The parent offered the path and then threw ConversionFailedException. The merge reported ineligible and threw ConverterNotFoundException on a direct attempt. |
| Control | Both services converted the typed 42 to the String 42 and kept raw Optional eligible. |
| Challenge | Adding an integer-to-date converter made the typed path eligible on both revisions. Both returned 12 February 1970. |

The same TypeDescriptor is passed to the eligibility query and the conversion.

With the prepared Spring cache, run `python3 examples/tools/build.py 461` to repeat all histories on both revisions. [Predictions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime lock](runtime.json) · [Observed returns](observations.json) · [Spring PR #36913](https://github.com/spring-projects/spring-framework/pull/36913)
