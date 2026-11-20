# A four-byte character crosses reads in the unchanged importer

The first CSV row is `abc,😀`. With one-byte reads, the decoder receives the four UTF-8 bytes of the second field across read boundaries. The literal oracle expects the UTF-16 pair D83D DE00 in one field. The two historical upgrades, application class and record-number checks are the ones from example 345.

[Input and expected records](controls/table.json) · [Four configurations](records/matrix/matrix.json) · [Decoder transfer](records/decoder-transfer.json)
