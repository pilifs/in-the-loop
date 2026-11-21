# Example 348 claim history

## generated-keys

Source claim `8a3ffbec57461471` on old, new. Eligible conclusion: open.

Latest execution [20261120T232346Z-e35e180a](receipts/generated-keys/executions/20261120T232346Z-e35e180a/attempt.json) reached receipt-published.
First blocker: the tool's own checker met 1 gap, a construct it does not implement as the JVM does, and refused it (--gaps strict): jdk-static-method:java.sql.DriverManager.getConnection(Ljava/lang/String;)Ljava/sql/Connection;@jdk-21.0.13 (java.sql.DriverManager.getConnection(java.lang.String) at before.calibration.GeneratedKeys.keys:13). It has no approximation under --gaps assume, since its value could only be made up: only a contract closes it (--gaps advised)
Missing evidence: eligible conclusion.


