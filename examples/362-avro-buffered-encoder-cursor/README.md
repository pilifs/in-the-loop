# Avro buffered encoding preserves the caller’s byte window

Avro #198 changes the view passed to a buffered encoder’s output channel. With a 32-byte encoder buffer the bulk path starts at 17 remaining bytes. A caller that retains its input can observe its cursor and the bytes produced by a second write. [Upstream change](https://github.com/apache/avro/commit/c9f2c49241397fb3967bd281225f7cce353c32fc)

The original upstream regression uses a mapped buffer. The public encoder checks here use writable and read-only heap views and include both sides of the bulk threshold. [Inputs and expected bytes](controls/table.json) · [Verification tasks](target.json)

On the parent, selectors 11 and 15 consume all 17 remaining bytes of a read-only view. A second call emits zero bytes. The fix retains the caller’s position and emits both copies. A fresh JVM checked all 16 inputs on each revision. Strict native checking establishes cursor preservation and repeated output for the 14 buffered or array-backed inputs on both revisions. The other two reach interrupt registration in the JDK channel. Setting the interrupt flag before the write causes a real `ClosedByInterruptException` on both versions. [Native partitions and JVM controls](../../verification/domain-foundations/encoder-paths-final)

The shared heap-window producer originally covered backing arrays through six bytes. Eight selectors satisfy that premise. A proof through 20 bytes and a separate read-only-view guarantee cover the full grid. The debugger identified the actual wrap result and the view passed to both packaged encoders. [Call sites and verification costs](../../verification/domain-foundations/encoder-adoption-final/measurement.json)
