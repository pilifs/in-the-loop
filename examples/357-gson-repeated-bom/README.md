# A byte-order mark across short JsonReader reads

A lenient reader consumes exactly the initial mark for zero, one or two marks across three distinct short-read schedules. [Upstream pull request](https://github.com/google/gson/pull/3137)

[Public observations](controls/table.json) · [Verification tasks](target.json)
