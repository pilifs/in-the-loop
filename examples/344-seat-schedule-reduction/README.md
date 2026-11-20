# Independent schedules with aliases and an ordered audit

The two-thread corpus covers one or two calls per worker, serial and overlapping invocations, and distinct seats with separate logs, aliased seats with separate logs, or distinct seats with one ordered log. The direct JVM oracle checks each observable history against sequential reservations consistent with its invocation intervals.

[Checked subjects](target.json) · [Sequential oracle](controls/oracle.py)
