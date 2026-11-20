from itertools import permutations
import json


def driver_args(): return ["--histories"]


def problems(lines):
    missing={(distinct,mode) for distinct in (False,True) for mode in range(3)}
    failures=[]
    for line in lines:
        r=json.loads(line)
        distinct,mode=r["distinct"],r["mode"]
        missing.remove((distinct,mode))
        c,e=r["invoked"],r["returned"]
        if sorted(c+e)!=[1,2,3,4] or any(a>=b for a,b in zip(c,e)) or (mode<2 and e[mode]>=c[1-mode]):
            raise ValueError("malformed invocation intervals")
        for first,second in permutations(range(2)):
            if e[second]<c[first]:continue
            table={}; success=[False,False]
            for who in (first,second):
                key=(who if distinct else 0)
                if key not in table:
                    success[who]=True;table[key]="AB"[who]
            if success==r["success"] and r["size"]==len(table) and r["owners"]==[table.get(0),table.get(1)]:break
        else:failures.append([int(distinct)*3+mode,"no allowed sequential reservation order"])
    if missing:raise ValueError("omitted invocation modes")
    return failures
