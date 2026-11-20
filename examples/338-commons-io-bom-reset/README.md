# A BOM stream rewinds its prefetched bytes

The wrapper and its delegate can have different positions after a one-byte preview. Reset must restore the correct remaining bytes and EOF.

[Input table and independent expectations](controls/table.json) · [Public verification tasks](target.json) · [Required outcomes](milestones.json)
