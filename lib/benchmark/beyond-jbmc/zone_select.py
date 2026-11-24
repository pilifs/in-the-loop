"""Choose the second zone by seed and bind the portion of the release provider map used by lookup."""
import hashlib
import json
import struct
import zipfile

from history import HERE, encoded
from release_cases import jars_for

PREFIX="org/joda/time/tz/data/"
SEED=hashlib.sha256(b"Beyond JBMC C07 unaffected zone; casebook v1; frozen before checking time zones").digest()
PIN=HERE/"zone-choice.json"


def zone_map(raw):
    at=0
    def short():
        nonlocal at
        n=struct.unpack_from(">H",raw,at)[0];at+=2;return n
    names=[]
    for _ in range(short()):
        size=short();names.append(raw[at:at+size].decode("ascii"));at+=size
    mapping={names[key]:names[value] for key,value in ((short(),short()) for _ in range(short()))}
    if at!=len(raw):raise ValueError("incomplete Joda zone map")
    return mapping


def selection():
    jars=[jars_for("joda-time-"+v)[0] for v in ("2.12.0","2.12.1")]
    with zipfile.ZipFile(jars[0]) as old,zipfile.ZipFile(jars[1]) as new:
        common=set(old.namelist())&set(new.namelist())
        pool=sorted(n[len(PREFIX):] for n in common if n.startswith(PREFIX) and '/' in n[len(PREFIX):] and not n.endswith('/') and old.read(n)==new.read(n))
        name=min(pool,key=lambda n:hashlib.sha256(SEED+b"\0"+n.encode()).digest())
        payloads={}
        for z,jar in zip((old,new),jars):
            data=z.read(PREFIX+"ZoneInfoMap")
            mapping=zone_map(data)
            def chain(key):
                path=[]
                while key not in path:
                    path.append(key)
                    key=mapping[key]
                if path[-1]!=key:raise ValueError("unexpected provider alias cycle")
                return path
            payloads[jar.name]={"map":hashlib.sha256(data).hexdigest(),"zones":{k:{"chain":chain(k),
                "resource":hashlib.sha256(z.read(PREFIX+chain(k)[-1])).hexdigest()} for k in (name,"America/Mexico_City")}}
        changed_classes=[n for n in common if n.endswith(".class") and old.read(n)!=new.read(n)]
        return {"seedHex":SEED.hex(),"population":len(pool),"populationSha256":hashlib.sha256(encoded(pool)).hexdigest(),
            "selected":name,"payloads":payloads,"commonClasses":sum(n.endswith(".class") for n in common),"changedClasses":changed_classes}


if __name__=="__main__":
    selected=selection()
    if PIN.exists() and json.loads(PIN.read_bytes())!=selected:raise ValueError("C07 draw changed")
    if not PIN.exists():PIN.write_bytes(encoded(selected))
    print(selected["selected"],selected["population"],selected["commonClasses"],"unchanged module classes")
