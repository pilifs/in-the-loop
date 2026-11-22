# Avro buffered encoding preserves the caller’s byte window

Avro #198 changes the view passed to a buffered encoder’s output channel. With a 32-byte encoder buffer the bulk path starts at 17 remaining bytes. A caller that retains its input can observe its cursor and the bytes produced by a second write. [Upstream change](https://github.com/apache/avro/commit/c9f2c49241397fb3967bd281225f7cce353c32fc)

The original upstream regression uses a mapped buffer. The public encoder checks here use writable and read-only heap views and include both sides of the bulk threshold. [Inputs and expected bytes](controls/table.json) · [Verification tasks](target.json)
