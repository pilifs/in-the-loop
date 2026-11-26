# Decimal holders read the signed value at the selected buffer position

Both Arrow widths and both holder readers recovered the negative decimal regardless of its neighbors. On this little-endian host the parent holder and vector reads disagreed.

The measured host is little-endian. The parent prediction depends on byte order.

| Registered history | Parent JVM | Merged JVM | Merged prediction |
|---|---|---|---|
| Intent | `289800550213539428966876423680520355.84=1234567.89/-276508270255690270237838353077716910.09=-1234567.89` | `1234567.89=1234567.89/-1234567.89=-1234567.89` | matched |
| Control | `0.00=0.00` | `0.00=0.00` | matched |
| Challenge | `-276508270255690270237838353077716910.09=-276508270255690270237838353077716910.09/-94090888675820811663901943169086139152349395172391494149580801793128377876.49=-94090888675820811663901943169086139152349395172391494149580801793128377876.49 / -276508270255690270237838353077716910.09=-276508270255690270237838353077716910.09/-94090888675820811663901943169086139152349395172391494149580801793128377876.49=-94090888675820811663901943169086139152349395172391494149580801793128377876.49` | `-1234567.89=-1234567.89/-1234567.89=-1234567.89 / -1234567.89=-1234567.89/-1234567.89=-1234567.89` | matched |

With the prepared R-series cache, run `python3 examples/tools/build.py 572`. [Questions and falsifiers](comparison.json) · [Caller](caller/PublicCaller.java) · [Runtime inputs](runtime.json) · [Recorded outcomes](observations.json) · [Upstream pull request](https://github.com/apache/arrow-java/pull/1518)
