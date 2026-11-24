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
| W01, 8.11.0 → 8.11.0, every signed int, six-byte frame | Verified with the complete release classpath | Verified |
| W01, 8.11.0 → 9.0.0, same domain | Refused the byte-array VarHandle factory during `BitUtil.<clinit>` | Verified reversed value, preservation iff palindrome, both cursors and both sentinels |
| W01, 9.0.0 → 8.11.0 and 9.0.0 → 9.0.0 | Both refused the VarHandle factory | Both verified |
| W02, arbitrary entry bytes, valid offsets and observed indices within the eight-byte input bound | Both claims refused | Both verified, including writes through an alias and reads on arbitrary entry bytes |
| W04, all int bit patterns with five bytes of VInt capacity | Verified both mixed directions, including length and next byte | Both verified |

All four W01 strict successor proofs quantify over every int. The intentionally false mixed identity claim produced a witness that reproduced on both original JVM assertion profiles. [Three-engine wire report](../../verification/beyond-jbmc/qualified/wire/results.json.gz)

The two initial diagnostic probes use the same six-byte allocation. They use native CaDiCaL, unwind 16, complete unwinding and the reported assumption that JDK initialization succeeded. The application initializers run. The new rule binds the Temurin 21.0.13 factory and handles to the image bytes, resolves the order from the real singleton reference, and checks the full width before touching any array cell. Atomic modes, handle identity and floating-point view accesses remain open. [Opening local proof](../../verification/beyond-jbmc/physical/wire/oldOld-native.json.gz) · [Opening mixed refusal](../../verification/beyond-jbmc/physical/wire/oldNew-native.json.gz) · [Mixed proof](../../verification/beyond-jbmc/qualified/wire-probe/oldNew-native.json.gz)

Opening stock JBMC proved the local 8.11.0 round trip and both VInt claims. It reported violations for three fixed-width compositions involving 9.0.0 and both slice claims. Each of those five inputs satisfied the property in two fresh unmodified JVMs under both assertion modes. Its witness for the deliberately false mixed identity claim reproduced, as did the integrated witness. [Seven original witness replays](../../verification/beyond-jbmc/opening/wire-witnesses.json)

## Transfer to Guava

On Guava 33.4.8-jre, the public `Hashing.farmHashFingerprint64().hashBytes(bytes, 0, 8).asLong()` equals the eight-byte FarmHash formula for every 64-bit word encoded little-endian. The first strict run stopped at the library's `Class.forName("java.lang.invoke.VarHandle")` capability check. Binding that lookup to the same bootstrap image let native prove the public caller with unwind 16. The receipt assumes successful JDK initialization and the stated application class loader. The physical JVM rejected the flipped-byte-order oracle at `0x123456789abcdef0`. Native refuted that false sibling on the original JVM. Stock reported success on the false sibling and its post-call false control, so its result is ineligible. [Transfer measurement](../../verification/beyond-jbmc/qualified/W02-transfer/results.json.gz) [Public caller](../../lib/benchmark/beyond-jbmc/wire-transfer/FarmFrame.java) · [Initial refusal](../../verification/beyond-jbmc/qualified/wire-probe/guava-probe.json.gz) · [Strict result](../../verification/beyond-jbmc/qualified/wire-probe/guava-qualified.json.gz)

## Rounded multiplication

Strict native proved N01 on the public vecmath `Tuple2f.scale(float)` caller. Its two independent binary32 factors cover 2⁴⁶ pairs. Every rounded product lies in [2, 8) and the companion component equals its negation. The same implementation proved N10 on Commons Math's `Vector2D.scalarMultiply(double)` over 2¹⁰⁴ binary64 pairs. The result is zero exactly at the two lower endpoints. The only other possible values are the first two positive subnormals. The queued original-class run also verified N02 at binary32 underflow and refuted strict positivity and the unrounded binary64 formula with original-JVM witnesses. All five final numeric outcomes matched both the integrated and packaged stock comparators. Both probes use the original classes and retain their initialization assumptions. [Vecmath proof](../../verification/beyond-jbmc/qualified/numeric-probe/range-native.json.gz) · [Commons Math transfer proof](../../verification/beyond-jbmc/qualified/numeric-probe/commons-math-native.json.gz) · [Vecmath comparisons](../../verification/beyond-jbmc/qualified/N01-N02/results.json.gz) · [Binary64 comparisons](../../verification/beyond-jbmc/qualified/N10/results.json.gz)

## Reflection

S01 was chosen after a released caller needed reflective lookup to select the byte-array implementation. On the expanded local fixture, the first native refusal identifies the nested `Convert<Enum<?>, String>` signature. S02 reaches a different first refusal at the original `Class.getMethod("get")` in the public Spring caller. The released-path fixture also checks the unaffected `ResolvableType.forMethodReturnType` observation and the S09 mutation/clear-cache history. All 13 opening physical controls passed. The successor proved the expanded S01 defensive-copy and owner predicate and transferred the nested wildcard to the real Spring Converter interface. On S02, the original resolution call reached the Spring framework and the JDK List generic-interface hierarchy after binding the original public no-argument method and reifying its nested List return. This is an observed advance within S02. Its original resolution vector still needs a complete proof. [S01 proof](../../verification/beyond-jbmc/qualified/reflection-probes/reified.json.gz) · [Spring Converter proof](../../verification/beyond-jbmc/qualified/reflection-probes/converter.json.gz) · [First framework refusal](../../verification/beyond-jbmc/qualified/reflection-probes/s02-after-return.json.gz) [Local fixture](../../lib/benchmark/beyond-jbmc/reflection/InterfaceClaims.java) · [Release callers](../../lib/benchmark/beyond-jbmc/reflection/SpringTypes.java)

## Historical and blind populations

All 187 archived statements match their original source graphs. The comparative refresh uses byte-exact historical inputs, isolated versions on relational claims, strict native, integrated staged JBMC and packaged stock JBMC. The opening refresh found 147 decisions in common, 32 native only, zero integrated JBMC only and eight neither. Strict native gained 22 decisions overall versus its historical 157/187. Against the union of qualified integrated and packaged-stock decisions the partition is 153/26/1/7. Stock produced 12 universal assertions contradicted on their own caller, 26 refutations that failed physical replay and one proof whose post-call trace input could not be reconstructed. The matrices retain the full 187 and the original 133/24/13/17 classification. [Opening matrix, costs and dispositions](../../verification/beyond-jbmc/opening/comparison/RESULTS.md) [Pinned population and profiles](../../lib/benchmark/beyond-jbmc/README.md#historical-comparison)

The 16-pair manifest is sealed. Each of the four strata contains four projects. The draw used distinct projects, distribution-published binaries and original source-package checksums. The automatic evaluation and matched reference-caller comparison are pending the checker freeze. [Manifest commitment](../../lib/benchmark/beyond-jbmc/panel.sha256)
