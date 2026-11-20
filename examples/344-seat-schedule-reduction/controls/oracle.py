from itertools import permutations
import json


def driver_args(): return ["--histories"]


def admissible(row):
    code=row["id"]
    shape=code//12; calls=(1+(code//6)%2,1+(code//3)%2)
    ids=[(worker,j) for worker in range(2) for j in range(calls[worker])]
    before={(a,b) for a in ids for b in ids if row["returned"][a[0]][a[1]]<row["invoked"][b[0]][b[1]]}
    for order in permutations(ids):
        if any(order.index(a)>=order.index(b) for a,b in before):continue
        owner=[0,0];logs=[[],[]];ack=[[0,0],[0,0]]
        for w,j in order:
            seat=0 if shape==1 else w
            won=not owner[seat]
            if won:owner[seat]=w+1
            ack[w][j]=1 if won else -1
            logs[0 if shape==2 else w].append((w+1)*ack[w][j])
        if shape==1:owner[1]=owner[0]
        if shape==2:logs[1]=list(logs[0])
        if (ack,owner,logs)==(row["ack"],row["owners"],row["logs"]):return True
    return False


def problems(lines):
    missing=set(range(36));errors=[]
    for line in lines:
        row=json.loads(line);missing.remove(row["id"])
        if not admissible(row):errors.append([row["id"],"no real-time-consistent reservation and ordered audit"])
    if missing:raise ValueError("missing heap or call pattern")
    return errors
