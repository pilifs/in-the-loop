# Half-byte retention across sliced base16 stream writes

A public decoding stream receives one backing byte array at its actual changing offsets. Closing it yields the mathematically decoded bytes. [Upstream pull request](https://github.com/apache/commons-codec/pull/135)

[Public observations](controls/table.json) · [Verification tasks](target.json)
