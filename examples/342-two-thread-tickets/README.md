# Two real threads request the next ticket

Two platform threads call once each on the same allocated counter, including both serial orders. The JVM witness pauses both workers after their reads outside the monitor. Erasing those waits leaves a legal execution of the original empty between method.

[Public claims](target.json) · [Sequential history oracle](controls/oracle.py)
