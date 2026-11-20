import json
from itertools import product


def driver_args():
    return ["--partitions"]


def domain():
    for length in range(4):
        for chars in product(("A","\u00e9","\U0001f600"),repeat=length):
            word="".join(chars)
            for cuts in range(1 << max(len(word.encode("utf-8"))-1,0)):
                yield word,cuts


def problems(lines):
    bad=0
    first=None
    for i,((word,cuts),line) in enumerate(zip(domain(),lines,strict=True)):
        r=json.loads(line)
        if r["id"] != i:
            raise ValueError("partition order or coverage differs")
        if not r["eof"] or r["units"] != word.encode("utf-16-be").hex():
            bad+=1
            if first is None:first=[i,word,cuts,r]
    return [] if first is None else [[first[0],f"{bad} partitions differ; first {first}"]]


if __name__=="__main__":
    assert sum(1 for _ in domain())==5578
