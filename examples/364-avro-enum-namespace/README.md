# Enum decoding across two schema namespaces

The wire inputs are the literal bytes 0 and 2. The writer orders symbols A then B. The reader uses both original and reversed order. The landed regression additionally writes and reads an Avro container file. [Upstream change](https://github.com/apache/avro/pull/1381)

Reading wire byte 0 or 2 through the original record reader returns the writer symbol A or B when reader.E replaces writer.E, including reversed reader symbol order. Matching enum names and namespaces decode each symbol and a different short name without an alias raises AvroTypeException in the original read. [Public observations](controls/table.json) · [Verification tasks](target.json)

Run `python3 examples/tools/build.py --plan 364` to inspect the frozen tasks.
