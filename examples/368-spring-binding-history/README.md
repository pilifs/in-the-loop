# Successive Spring edits preserve bean identity and binding errors

One Spring Framework 6.2.3 DataBinder receives three edits on a fresh bean. The primary and backup references begin shared or distinct. Each of the six edit orders records both children's names and counts, reference identity, and the field error after each call. The error carries the rejected text `oops` even after a successful write. A fresh binder over the same bean starts with an empty ledger. [Application](application/springwork/BindingHistory.java) · [Independent observations](controls/table.json)

Run `python3 examples/tools/build.py 368 --task replay` for the 12 histories and their controls. The `beans-release` and `ledger-release` tasks check the two properties independently.
