"""Resolve data fixtures by digest into the reviewed input, keeping their original bytes for offline replay."""
import hashlib
import json
from pathlib import Path
import re


def resolve(packet, directory, *, from_source=None):
    if "fixtures" not in packet:
        return packet, []
    values, records, used = {}, [], set()
    directory = Path(directory)
    for item in packet["fixtures"]:
        if (set(item) != {"id","file","sha256","encoding"} or not isinstance(item["id"],str)
                or not item["id"] or item["id"] in values or not re.fullmatch(r"[0-9a-f]{64}",item["sha256"])):
            raise ValueError("invalid or duplicate registered fixture")
        saved = directory / "fixtures" / item["sha256"]
        if from_source is not None:
            root = Path(from_source).resolve()
            source = (root/item["file"]).resolve()
            if Path(item["file"]).is_absolute() or not source.is_relative_to(root):
                raise ValueError("registered fixture lies outside the reviewed packet")
        else:
            source = saved
        data = source.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("registered fixture digest differs: " + item["id"])
        if item["encoding"] == "text":
            value = data.decode("utf-8")
        elif item["encoding"] == "hex":
            value = data.hex()
        elif item["encoding"] == "json":
            value = json.loads(data)
        else:
            raise ValueError("unknown registered fixture encoding")
        if from_source is not None:
            saved.parent.mkdir(exist_ok=True)
            saved.write_bytes(data)
        values[item["id"]] = value
        records.append({**item, "bytes":len(data)})

    def substitute(value):
        if isinstance(value,list):
            return [substitute(x) for x in value]
        if isinstance(value,dict):
            if value.keys() == {"fixture"}:
                name = value["fixture"]
                if name not in values:
                    raise ValueError("unregistered fixture reference: " + str(name))
                used.add(name)
                return values[name]
            return {k:substitute(v) for k,v in value.items()}
        return value

    expanded = {k:v for k,v in packet.items() if k!="fixtures"}
    expanded["questions"] = [{**q,"inputs":substitute(q["inputs"])} for q in packet["questions"]]
    if used != values.keys():
        raise ValueError("a registered fixture is disconnected from the public inputs")
    return expanded, records
