# A fast Avro reader materializes the array member of a union default

The binary inputs include an empty writer record and three records carrying markers −1, 0 and 1. The public fast reader receives the expected and writer schemas in the upstream order. Direct-array defaults preserve the same observations. JSON, the standard reader and the missing-default control are separately reproducible. [Upstream change](https://github.com/apache/avro/pull/3730)

The fast binary reader returns a record with an empty array for its reader-only union field and retains each writer marker when present. With a direct array field and the same empty default the fast binary reader returns the empty array and preserves each writer marker. [Public observations](controls/table.json) · [Verification tasks](target.json)

Run `python3 examples/tools/build.py --plan 367` to inspect the frozen tasks.
