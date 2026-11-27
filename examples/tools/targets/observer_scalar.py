"""Construct and independently read one scalar public operation over an explicit finite domain."""
import re

from targets import observer_actions, runtime_jar
from targets.observer_recipes import Unsupported

FIELDS = ["call.outcome", "return.scalar"]
TYPES = {"I": "Integer", "J": "Long", "S": "Short", "B": "Byte", "Z": "Boolean", "C": "Character",
         "Ljava/lang/String;": "String"}
PARAMETER = re.compile(r"\[*(?:[ZBCSIJFD]|L[\w/$]+;)")


def parts(descriptor):
    args, result = descriptor[1:].split(")",1)
    params = PARAMETER.findall(args)
    if "".join(params) != args:
        raise Unsupported("invalid JVM parameter declaration")
    return params, result


def accepts(typ, value):
    if typ == "Ljava/lang/String;":
        return value is None or isinstance(value,str)
    if typ == "Z":
        return type(value) is bool
    if typ == "C":
        return isinstance(value,str) and len(value.encode("utf-16-be","surrogatepass")) == 2
    bounds = {"I": 32, "J": 32, "S": 16, "B": 8}
    return type(value) is int and -(2**(bounds[typ]-1)) <= value < 2**(bounds[typ]-1)


def select(entry, inputs, api):
    owner, name, desc = runtime_jar.parse_target(entry)
    params, result = parts(desc)
    if result not in TYPES or any(p not in TYPES for p in params) or name in ("<init>","<clinit>"):
        raise Unsupported("the selected declaration needs a public object construction or a richer return projection")
    flags = runtime_jar.method_flags(api.definition(owner), name, desc)
    if flags is None:
        raise Unsupported("the selected public scalar overload is absent from this revision")
    static = bool(flags & 8)
    api.require(owner,name,desc,static=static)
    if not static:
        if runtime_jar.class_flags(api.definition(owner)) & 0x0600:
            raise Unsupported("which concrete public receiver implements " + owner + "?")
        api.require(owner,"<init>","()V")
    for item in inputs:
        args = item.get("arguments") if isinstance(item,dict) and set(item) == {"arguments"} else None
        if not isinstance(args,list) or len(args) != len(params) or any(not accepts(p,v) for p,v in zip(params,args)):
            raise Unsupported("the scalar history needs one compatible argument per declared JVM parameter")
    return {"family":"public scalar method","owner":owner,"method":name,"entry":entry,
            "parameters":params,"result":result,"static":static}


def body(recipe):
    owner = recipe["owner"].replace("$",".")
    receiver = owner if recipe["static"] else "new " + owner + "()"
    expressions = []
    for index, kind in enumerate(recipe["parameters"]):
        arg = f"arguments.get({index})"
        if kind == "Ljava/lang/String;":
            expressions.append("(String)" + arg)
        elif kind == "C":
            expressions.append("((String)" + arg + ").charAt(0)")
        elif kind == "Z":
            expressions.append("((Boolean)" + arg + ").booleanValue()")
        else:
            conversion = {"I":"intValue", "J":"longValue", "S":"shortValue", "B":"byteValue"}[kind]
            expressions.append("((Number)" + arg + ")." + conversion + "()")
    return f'''List<?> arguments = (List<?>)data.get("arguments");
            try {{
                Object returned = {receiver}.{recipe["method"]}({", ".join(expressions)});
                observations.add(returned == null ? row("return", null, null)
                        : row("return", returned.getClass().getName(), returned.toString()));
            }} catch (Exception error) {{
                observations.add(row("throws", error.getClass().getName()));
            }}''', ""


def value(typ, atom):
    if typ == "Ljava/lang/String;" and atom["type"] in ("null","java.lang.String"):
        return atom["value"]
    if typ == "Z" and atom["type"] == "boolean" and atom["value"] in ("true","false"):
        return atom["value"] == "true"
    if typ == "C" and atom["type"] == "char":
        return chr(int(atom["value"]))
    primitive = {"I":"int","J":"long","S":"short","B":"byte"}
    if typ in primitive and atom["type"] == primitive[typ]:
        return int(atom["value"])
    raise ValueError("actual public scalar type differs from the selected descriptor")


def qualify(recipe, inputs, marks, values):
    entries = [observer_actions.decode(m.split(" ",1)[1]).decode().splitlines() for m in marks if m.startswith("UPGRADE-SCALAR-ENTRY ")]
    if len(entries) != 1:
        raise ValueError("expected exactly one original scalar invocation")
    args = [value(p,observer_actions.atom(a)) for p,a in zip(recipe["parameters"], entries[0], strict=True)]
    if args != inputs["arguments"]:
        raise ValueError("original scalar arguments differ from the frozen input")
    throws = [m.partition(" ")[2] for m in marks if m.startswith("UPGRADE-SCALAR-THROW ")]
    actions = []
    if throws:
        if len(throws) != 1 or any(m.startswith("UPGRADE-ACTION ") for m in marks):
            raise ValueError("ambiguous original scalar exception")
        actual = ["throws",throws[0]]
    else:
        actions = observer_actions.events({"return":recipe["entry"]},marks)
        if len(actions) != 1:
            raise ValueError("expected one direct public return")
        result = value(recipe["result"],actions[0]["return"])
        spelling = str(result).lower() if type(result) is bool else str(result)
        actual = ["return", None, None] if result is None else ["return","java.lang."+TYPES[recipe["result"]],spelling]
    if values != [actual]:
        raise ValueError("reported scalar differs from the original return or escaping exception")
    return {"scalarArguments":args, "scalarOutcome":actual, "publicActions":actions}
