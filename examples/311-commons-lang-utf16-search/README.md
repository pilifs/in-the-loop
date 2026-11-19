# Last-match offsets on a StringBuilder

The pin selects Apache’s public StringUtils.lastIndexOf(CharSequence, int) overload. The runtime sequence is a StringBuilder. The adapter covers all forty sequences of up to three tokens drawn from a, b and U+2070E, and searches each for those three code points and z. The Python oracle enumerates tokens and counts UTF-16 code units preceding the last match. [Apache fix](https://github.com/apache/commons-lang/commit/bdd674f7c64dbc2c8ff043ee995fcd9f6f59a13b)

The adapter agreed with the independent direct call on all 160 inputs on both revisions. The parent missed 25 last matches and the fix missed zero. Both passed all 85 absent-character and 120 single-code-unit checks. [JVM calibration](records/calibration.json)
