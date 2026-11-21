# UTF-16 cuts through Commons Lang's public string operations

Truncation copies exactly the complete UTF-16 tokens inside the original window. Abbreviation also keeps surrogate pairs intact. [Upstream pull request](https://github.com/apache/commons-lang/pull/1719)

[Public observations](controls/table.json) · [Verification tasks](target.json)
