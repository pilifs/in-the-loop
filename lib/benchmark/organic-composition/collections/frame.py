"""List the exact iterator-field accesses and calls that an unrestricted heap proof would need."""
import hashlib
import json
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from plan_run import ROOT, OUTPUT
sys.path.insert(0,str(ROOT/"examples/tools"))
from targets import change_inventory, runtime_jar
OWNER="org/apache/commons/collections4/iterators/IteratorChain"


def inspect(data, root):
    pool,methods,_=runtime_jar._declarations(data,with_code=True)
    pending=[root];seen=set();fields=[];calls=[];array_writes=[]
    while pending:
        method,desc=pending.pop()
        if (method,desc) in seen:continue
        seen.add((method,desc))
        _,code,_=methods[method,desc]
        for pc,op in change_inventory.instructions(code or b""):
            if 0x4f<=op<=0x56:
                array_writes.append({"method":method+desc,"bci":pc,"opcode":op})
            if not 0xb2<=op<=0xb9:continue
            index=int.from_bytes(code[pc+1:pc+3],"big")
            owner,name,sig=runtime_jar._member_ref(pool,pool[index][1])
            entry={"source":method+desc,"bci":pc,"owner":owner,"member":name+sig}
            if op<=0xb5:
                entry["instruction"]=("getstatic","putstatic","getfield","putfield")[op-0xb2]
                fields.append(entry)
            else:
                entry["dispatch"]=("virtual","special","static","interface")[op-0xb6]
                entry["declaredLocal"]=owner==OWNER and (name,sig) in methods
                calls.append(entry)
                if entry["declaredLocal"]:pending.append((name,sig))
    return {"declarations":sorted(name+desc for name,desc in seen),"fields":fields,"calls":calls,
            "arrayStores":array_writes,"scope":"Static declared-class closure only. External iterator calls and virtual overrides may read or write arbitrary reachable state."}


def depth_source(worktree):
    rel=Path("src/test/java/org/apache/commons/collections4/iterators/IteratorChainTest.java")
    source=(worktree/rel).read_text()
    marker="public void testChainingPerformsWell()"
    if marker not in source:
        return {"file":str(rel),"methodPresent":False}
    start=source.index(marker); body=source[source.index("{",start):]
    level=0
    for i,ch in enumerate(body):
        if ch=="{":level+=1
        if ch=="}":level-=1
        if not level:break
    method=source[start:source.index("{",start)]+body[:i+1]
    if not all(text in method for text in ("i < 150","Duration.ofSeconds(1)","iterFinal.next()","iterFinal.remove()","iterFinal.hasNext()")):
        raise ValueError("published upstream depth control differs")
    return {"file":str(rel),"methodPresent":True,"methodSha256":hashlib.sha256(method.encode()).hexdigest(),
            "nestedLayers":150,"traversalSeconds":1,"testFileSha256":hashlib.sha256(source.encode()).hexdigest()}


def main():
    result={}
    for n in ("628","755"):
        for side in ("old","new"):
            manifest=json.loads((HERE.parent/("collections-"+n)/side/"prepared.json").read_bytes())
            p=Path(manifest["classpath"][0]["file"])
            if hashlib.sha256(p.read_bytes()).hexdigest()!=manifest["classpath"][0]["sha256"]:raise ValueError("unexpected production JAR")
            data=runtime_jar.read_class(p,OWNER)
            upstream=json.loads((HERE.parent/("collections-"+n)/"upstream.json").read_bytes())
            worktree=Path.home()/".cache/in-the-loop/organic-composition-ff/worktrees"/upstream[side]["worktree"]
            result[n+"-"+side]={"upstreamDepthTest":depth_source(worktree),"classSha256":hashlib.sha256(data).hexdigest(),
                                "update":inspect(data,("updateCurrentIterator","()V")),"remove":inspect(data,("remove","()V"))}
    dest=ROOT/OUTPUT/"collections/bytecode-frames.json";dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(result,indent=2)+"\n")
if __name__=="__main__":main()
