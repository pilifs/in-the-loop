# Beyond JBMC campaign results

## Lucene fixed-width compatibility

The caller wrote `0x01020304` to a four-byte slice at offset 1. Its two surrounding sentinels stayed intact. Both writers and readers ended at position 5. Each cell ran the same compiled caller in two separate Temurin 21.0.13 processes with one original release JAR on each classpath. [Replay command and source](../../lib/benchmark/beyond-jbmc/wire_campaign.py) · [Physical receipt](../../verification/beyond-jbmc/physical/wire/receipt.json)

| Writer | Frame including sentinels | Reader 8.11.0 | Reader 9.0.0 |
|---|---|---|---|
| 8.11.0 | `33 01 02 03 04 55` | `01020304` | `04030201` |
| 9.0.0 | `33 04 03 02 01 55` | `04030201` | `01020304` |

The separate setup JVM enumeration exercised all 2³² integers. Both mixed reads equaled `Integer.reverseBytes(v)`. Of those, 65,536 values preserved in each direction. For equality, byte 0 must equal byte 3 and byte 1 must equal byte 2, leaving two independent bytes. The ordinary JVM enumeration used contiguous batches at its recorded offsets. [Setup enumeration](beyond-jbmc-java-change-verification-campaign-setup.md)

| Claim and scope | Opening strict native | Successor strict native |
|---|---|---|
| W01, 8.11.0 → 8.11.0, every signed int, six-byte frame | Verified with the complete release classpath | Full matrix queued |
| W01, 8.11.0 → 9.0.0, same domain | Refused the byte-array VarHandle factory during `BitUtil.<clinit>` | Verified reversed value, preservation iff palindrome, both cursors and both sentinels |
| W01, 9.0.0 → 8.11.0 and 9.0.0 → 9.0.0 | Full matrix queued | Full matrix queued |
| W02, arbitrary entry bytes, valid offsets and observed indices within the eight-byte input bound | Full matrix queued | Full matrix queued |
| W04, all int bit patterns with five bytes of VInt capacity | Full matrix queued | Full matrix queued |

The two completed probes quantify over every int. They use native CaDiCaL, unwind 16, complete unwinding and the reported assumption that JDK initialization succeeded. The application initializers run. The new rule binds the Temurin 21.0.13 factory and handles to the image bytes, resolves the order from the real singleton reference, and checks the full width before touching any array cell. Atomic modes, handle identity and floating-point view accesses remain open. [Opening local proof](../../verification/beyond-jbmc/physical/wire/oldOld-native.json.gz) · [Opening mixed refusal](../../verification/beyond-jbmc/physical/wire/oldNew-native.json.gz) · [Mixed proof](../../verification/beyond-jbmc/qualified/wire-probe/oldNew-native.json.gz)

## Transfer to Guava

On Guava 33.4.8-jre, the public `Hashing.farmHashFingerprint64().hashBytes(bytes, 0, 8).asLong()` equals the eight-byte FarmHash formula for every 64-bit word encoded little-endian. The first strict run stopped at the library's `Class.forName("java.lang.invoke.VarHandle")` capability check. Binding that lookup to the same bootstrap image let native prove the public caller with unwind 16. The receipt assumes successful JDK initialization and the stated application class loader. The physical JVM rejected the flipped-byte-order oracle at `0x123456789abcdef0`. Comparator and false-sibling results are queued. [Public caller](../../lib/benchmark/beyond-jbmc/wire-transfer/FarmFrame.java) · [Initial refusal](../../verification/beyond-jbmc/qualified/wire-probe/guava-probe.json.gz) · [Strict result](../../verification/beyond-jbmc/qualified/wire-probe/guava-qualified.json.gz)

## Historical and blind populations

All 187 archived statements match their original source graphs. The comparative refresh uses byte-exact historical inputs, isolated versions on relational claims, strict native, integrated staged JBMC and packaged stock JBMC. The historical 133/24/13/17 classification is retained pending fresh results. The standalone harnesses physically reproduce all seven supplied counterexamples in the real and held-out groups. [Pinned population and profiles](../../lib/benchmark/beyond-jbmc/README.md#historical-comparison)

The 16-pair manifest is sealed. Each of the four strata contains four projects. The draw used distinct projects, distribution-published binaries and original source-package checksums. The automatic evaluation and matched reference-caller comparison are pending the checker freeze. [Manifest commitment](../../lib/benchmark/beyond-jbmc/panel.sha256)
