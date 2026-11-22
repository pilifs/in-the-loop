# CSV lookahead preserves complete fields and delimiter prefixes

The fixtures cross three delimiters with four shapes and include both literal upstream witnesses. Each observation keeps the record and field boundaries and checks terminal exhaustion. Prefix controls exercise every proper length as well as comma and quoted-field cases. [Upstream change](https://github.com/apache/commons-csv/pull/218)

Each multicharacter fixture parses as exactly one record with the independent field vector, including empty and quoted fields. Iterator exhaustion follows. Every proper delimiter prefix followed by a mismatch remains literal. The single-character and ordinary quoted controls preserve all fields and exhaust. [Public observations](controls/table.json) · [Verification tasks](target.json)

Run `python3 examples/tools/build.py --plan 366` to inspect the frozen tasks.
