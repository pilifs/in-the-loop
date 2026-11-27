# Mongo health reports all visible databases with one explicit hello

Counts commands issued by each health indicator using recording clients, while independently checking the complete returned set of database names.

| History | Parent | Merge | Merged prediction |
|---|---|---|---|
| Intent | `UP:complete:10:test,admin/UP:complete:10:test,admin` | `UP:complete:10:admin/UP:complete:10:admin` | matched |
| Control | `UP:complete:10:test/UP:complete:10:test` | `UP:complete:10:test/UP:complete:10:test` | matched |
| Challenge | `UP:complete:10:fixture0,fixture1,fixture2,fixture3,fixture4,fixture5,fixture6,fixture7,admin/UP:complete:10:fixture0,fixture1,fixture2,fixture3,fixture4,fixture5,fixture6,fixture7,admin;UP:complete:10:admin,fixture0,fixture1,fixture2,fixture3,fixture4,fixture5,fixture6,fixture7/UP:complete:10:admin,fixture0,fixture1,fixture2,fixture3,fixture4,fixture5,fixture6,fixture7` | `UP:complete:10:admin/UP:complete:10:admin;UP:complete:10:admin/UP:complete:10:admin` | matched |

Replay with `python3 examples/tools/build.py 622` using the prepared Spring Boot cache. [Registered questions](comparison.json) · [Public caller](caller/PublicCaller.java) · [Runtime and class digests](runtime.json) · [Observed results](observations.json) · [Merged PR](https://github.com/spring-projects/spring-boot/pull/50734)
