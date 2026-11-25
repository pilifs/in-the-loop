# jOOQ preserves row identity across static JDBC batches

The parent reported three stored rows but wrote Alice three times. H2, PostgreSQL 16.16 and the reported PostgreSQL 18.1 returned the three original ID/name pairs on the fix, including across a two-row batch and its one-row tail. Prepared statements preserved all rows on both pins.

Each history starts in a fresh JVM on each measured deployment and uses the same compiled caller on both revisions. Each pin runs on H2 2.4.240 and on disposable PostgreSQL 16.16 and 18.1 servers. Both PostgreSQL versions are read back from the server. Every trial reads both result columns over JDBC.

Run `python3 examples/tools/build.py 418` with the prepared deployments. [Predictions and independent bases](comparison.json) · [Ordered classpaths and digests](runtime.json) · [Public caller](caller/PublicCaller.java) · [Measured observations](observations.json) · [Upstream change](https://github.com/jOOQ/jOOQ/pull/19875)

The original setup supplies PostgreSQL 16. To prepare the additional reporter-version fixture, run `docker pull postgres@sha256:1090bc3a8ccfb0b55f78a494d76f8d603434f7e4553543d6e807bc7bd6bbd17f`. Each replay starts and removes its own loopback-only server.
