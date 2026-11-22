# Nested binary values have independent byte windows

The builder serializes two binary children. Their independent widths are zero through three and their initial bytes are 10 and 20. Both selection indices are exercised after rewrapping the exact logical lengths with zero or 25 leading bytes. The upstream test additionally nests the array inside an object. [Upstream change](https://github.com/apache/parquet-java/pull/3333)

The selected child exposes exactly its own unsigned bytes and length and rejects the next relative read, including the first read of an empty child. After the last child view is consumed, a fresh lookup starts at the original position, contains exactly the last payload, and exhausts there. [Public observations](controls/table.json) · [Verification tasks](target.json)

Run `python3 examples/tools/build.py --plan 363` to inspect the frozen tasks.
