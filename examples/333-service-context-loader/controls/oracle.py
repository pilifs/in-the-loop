import json


def driver_args():
    return ["--two-lookups"]


def problems(lines):
    missing=set(range(16))
    problems=[]
    for line in lines:
        row=json.loads(line); code=row["id"];missing.remove(code)
        for p,call in zip(divmod(code,4),row["calls"],strict=True):
            order=("","C","CW","WC")[p]
            if call != [order,order[:1],"","",order[:1],order]:
                problems.append([code,"provider selection, descriptor order or construction timing differs"])
    if missing: raise ValueError("missing loader pairs")
    return problems
