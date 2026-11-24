"""Independently check the complete decision table in both original DateUtil class files."""
import hashlib
import json
from pathlib import Path
import struct
import sys

CASE = Path(__file__).resolve().parent
ROOT = CASE.parents[3]
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import runtime_jar


def prove_switch(code):
    if code[:4] != bytes.fromhex("1aaa0000"):
        raise ValueError("expected iload_0 and a table switch at offset one")
    default,low,high = struct.unpack_from(">iii",code,4)
    if (low,high)!=(14,47):
        raise ValueError("unexpected selector interval")
    offsets = struct.unpack_from(">34i",code,16)
    base=16+4*len(offsets)
    # iconst_1; goto ireturn; iconst_0; ireturn. All offsets below are
    # relative to tableswitch at BCI one. The default covers all other ints.
    if code[base:]!=bytes.fromhex("04a7000403ac") or default+1!=base+4:
        raise ValueError("unexpected return or default path")
    if not all(off+1 in (base,base+4) for off in offsets):
        raise ValueError("unknown switch target")
    true_keys=[low+i for i,off in enumerate(offsets) if off+1==base]
    if true_keys!=[*range(14,23),*range(45,48)]:
        raise ValueError("incorrect internal-date classification")
    return true_keys


def main():
    sides={}
    for side in ("old","new"):
        doc=json.loads((CASE/side/"prepared.json").read_bytes())
        jar=Path(doc["classpath"][0]["file"])
        if hashlib.sha256(jar.read_bytes()).hexdigest()!=doc["classpath"][0]["sha256"]:
            raise ValueError("incorrect production artifact")
        body=runtime_jar.read_class(jar,"org/apache/poi/ss/usermodel/DateUtil")
        flags,code,handlers=runtime_jar._declarations(body,with_code=True)[1]["isInternalDateFormat","(I)Z"]
        if flags!=9 or handlers:
            raise ValueError("unexpected helper access or exception handlers")
        yes=prove_switch(code)
        altered=bytearray(code)
        altered[16+4*(23-14):20+4*(23-14)]=code[16:20]
        try:
            prove_switch(bytes(altered))
        except ValueError as e:
            if "incorrect internal-date" not in str(e):
                raise
        else:
            raise ValueError("wrong classification at 23 was accepted")
        sides[side]={"commit":doc["commit"],"jar":doc["classpath"][0]["sha256"],
                     "class":hashlib.sha256(body).hexdigest(),"code":code.hex(),"trueIndices":yes,
                     "falseIndices":2**32-len(yes),"frame":"only the argument local, switch and constant returns",
                     "substitutedTarget23Rejected":True}
    p=ROOT/"verification/organic-composition/poi/all-int-classification.json"
    p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(sides,indent=2)+"\n")

if __name__=="__main__":
    main()
