"""Bounded public API search and source emission for reviewed observation shapes.

The input vocabulary describes data and observable fields. Only members found on the
original public API can become source identifiers. Predictions never enter this module.
"""
import hashlib
from pathlib import Path
import re
import zipfile
from string import Template
from textwrap import dedent, indent

from targets import runtime_jar

TEMPLATE = Path(__file__).with_name("java") / "GeneratedObservation.java.template"
IDENTIFIER = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*")
CANDIDATE_BUDGET = 64
NUMBERS = {"Byte", "Short", "Integer", "Long", "Float", "Double", "BigInteger", "BigDecimal"}
NUMBER_ENTRY = "(Ljava/lang/String;Ljava/lang/Class;)Ljava/lang/Number;"
FORMATTED_NUMBER_ENTRY = "(Ljava/lang/String;Ljava/lang/Class;Ljava/text/NumberFormat;)Ljava/lang/Number;"
NUMBER_FIELDS = ["call.outcome", "return.type", "return.value"]
FORMAT_FIELD = "argument.parseBigDecimalAfterReturn"
FORMAT_GETTER = "java.text.DecimalFormat#isParseBigDecimal()Z"


class Unsupported(ValueError):
    """A missing public operation or input meaning. Partial experiments cannot decide a question."""


class API:
    def __init__(self, files, feature):
        self.files = files
        self.feature = feature
        self.classes = {}
        self.used = {}
        self.inspected = set()
        self.rejected = []

    def definition(self, owner):
        if not IDENTIFIER.fullmatch(owner):
            raise Unsupported("invalid public class name")
        if owner not in self.classes:
            name = runtime_jar.internal(owner)
            for file in self.files:
                if file.is_dir():
                    path = file / (name + ".class")
                    data = path.read_bytes() if path.is_file() else None
                else:
                    data = runtime_jar.effective_class(file, name, self.feature)
                if data:
                    self.classes[owner] = data
                    break
            else:
                raise Unsupported("public type missing from the bound deployment: " + owner)
        return self.classes[owner]

    def select(self, owner, names, descriptor, *, static=False):
        """Refuse equally suitable candidates. Do not silently choose a same-name overload."""
        data = self.definition(owner)
        if not runtime_jar.class_flags(data) & 1:
            raise Unsupported("type is inaccessible from a public caller: " + owner)
        methods = runtime_jar.methods(data)
        candidates = []
        for n, d in sorted(methods):
            if n not in names:
                continue
            key = owner + "#" + n + d
            if key not in self.inspected and len(self.inspected) >= CANDIDATE_BUDGET:
                raise Unsupported("public signature candidate budget exhausted at " + key)
            self.inspected.add(key)
            if re.fullmatch(descriptor, d) and runtime_jar.method_flags(data, n, d) & 9 == (9 if static else 1):
                candidates.append((n, d))
            elif key not in self.rejected:
                self.rejected.append(key)
        if len(candidates) != 1:
            raise Unsupported(f"{owner} needs one public {'/'.join(names)} matching {descriptor}, found {candidates}")
        name, desc = candidates[0]
        if name != "<init>" and not IDENTIFIER.fullmatch(name):
            raise Unsupported("unrepresentable public method name")
        entry = owner + "#" + name + desc
        self.used[entry] = hashlib.sha256(data).hexdigest()
        return name, desc

    def require(self, owner, name, descriptor, *, static=False):
        return self.select(owner, [name], re.escape(descriptor), static=static)[0]

    def named(self, simple):
        """Return a unique physical type for an approved grammar or public construction convention."""
        found = set()
        for file in self.files:
            if file.is_dir():
                names = [p.relative_to(file).as_posix() for p in file.rglob(simple + ".class")]
            else:
                with zipfile.ZipFile(file) as jar:
                    names = jar.namelist()
            found.update(n[:-6].replace("/", ".") for n in names if not n.startswith("META-INF/")
                         and n.rsplit("/", 1)[-1] == simple + ".class")
        if len(found) != 1:
            raise Unsupported(f"need one public {simple} declaration, found {sorted(found)}")
        return found.pop()


def keys(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields):
        raise Unsupported("registered input needs exactly " + ", ".join(fields))


def nonempty(value, meaning):
    if not isinstance(value, list) or not value:
        raise Unsupported("missing " + meaning)
    return value


def select(entry, fields, inputs, api):
    owner, method, descriptor = runtime_jar.parse_target(entry)
    if not descriptor:
        raise Unsupported("supply the descriptor of the bound public entry")
    if fields in (NUMBER_FIELDS, [*NUMBER_FIELDS, FORMAT_FIELD]):
        if descriptor not in (NUMBER_ENTRY, FORMATTED_NUMBER_ENTRY):
            raise Unsupported("need a public conversion of text and a numeric class, optionally with NumberFormat")
        api.require(owner, method, descriptor, static=True)
        formatted = descriptor == FORMATTED_NUMBER_ENTRY
        retained = FORMAT_FIELD in fields
        has_read = False
        for item in inputs:
            keys(item, ["conversions"])
            for conv in nonempty(item["conversions"], "texts and requested numeric types"):
                required = ["text", "type", "format"] if formatted else ["text", "type"]
                if retained and isinstance(conv, dict) and "readAfterReturn" in conv:
                    if (not formatted or conv.get("format") is None
                            or conv["readAfterReturn"] != "isParseBigDecimal"):
                        raise Unsupported("the post-return getter needs the configured DecimalFormat passed to this call")
                    required.append("readAfterReturn")
                    has_read = True
                keys(conv, required)
                if not isinstance(conv["type"], str) or conv["type"] not in NUMBERS or not isinstance(conv["text"], str):
                    raise Unsupported("each conversion needs literal text and a supported numeric target type")
                if formatted and conv["format"] is not None:
                    fmt = conv["format"]
                    keys(fmt, ["locale", "pattern", "parseBigDecimal"])
                    if not isinstance(fmt["locale"], str) or not fmt["locale"].strip():
                        raise Unsupported("which explicit language tag supplies the decimal symbols?")
                    if not isinstance(fmt["pattern"], str) or type(fmt["parseBigDecimal"]) is not bool:
                        raise Unsupported("supply a decimal pattern and an explicit BigDecimal parsing flag")
        recipe = {"family": "typed numeric conversions", "owner": owner, "method": method}
        if formatted:
            recipe["formatArgument"] = "java.text.DecimalFormat"
        if retained:
            if not has_read:
                raise Unsupported("specify which conversion retains its formatter for the public getter")
            recipe["argumentRead"] = FORMAT_GETTER
    elif fields == ["result.defined", "fallback.value", "fallback.calls"]:
        _, desc = api.select(owner, [method], r"\(Ljava/util/function/Predicate;\)L[\w/$]+;")
        result = desc.split(")L")[1][:-1].replace("/", ".")
        factory, _ = api.select(owner, ["of", "ofAll", "from"], r"\(\[Ljava/lang/Object;\)L" + re.escape(runtime_jar.internal(owner)) + ";", static=True)
        defined = api.require(result, "isDefined", "()Z")
        fallback = api.require(result, "getOrElse", "(Ljava/util/function/Supplier;)Ljava/lang/Object;")
        for item in inputs:
            keys(item, ["selections", "fallback"])
            if type(item["fallback"]) is not int:
                raise Unsupported("the registered fallback must be an integer")
            for selection in nonempty(item["selections"], "sequences and predicates"):
                keys(selection, ["values", "predicate"])
                if not isinstance(selection["values"], list) or any(v is not None and type(v) is not int for v in selection["values"]):
                    raise Unsupported("selection requires nullable integer values")
                p = selection["predicate"]
                if not isinstance(p, dict) or len(p) != 1 or not (
                        ("oneOf" in p and isinstance(p["oneOf"], list) and all(v is None or type(v) is int for v in p["oneOf"])) or
                        ("greaterThan" in p and type(p["greaterThan"]) is int) or ("odd" in p and p["odd"] is True)):
                    raise Unsupported("missing integer predicate (oneOf, greaterThan or odd)")
        recipe = {"family": "selection and lazy default", "owner": owner, "method": method, "result": result,
                  "factory": factory, "defined": defined, "fallback": fallback}
    else:
        from targets import observer_histories
        recipe = observer_histories.select(entry, fields, inputs, api)
    if not any(target == entry for target in api.used):
        raise Unsupported("selected public overload differs from the reviewed entry: " + entry)
    return recipe


def source(recipe):
    p = recipe
    if p["family"] == "typed numeric conversions":
        formatted = "formatArgument" in p
        setup = '\n                java.text.NumberFormat format = numberFormat((Map<String,Object>)pair.get("format"));'
        capture = '''if (value == null) observations.add(row("return", null, null));
                    else observations.add(row("return", value.getClass().getName(), value.toString()));'''
        if p.get("argumentRead") == FORMAT_GETTER:
            capture = '''List<Object> sample = new ArrayList<>(value == null ? row("return", null, null)
                            : row("return", value.getClass().getName(), value.toString()));
                    if (pair.containsKey("readAfterReturn")) {
                        sample.add(((java.text.DecimalFormat)format).isParseBigDecimal());
                    }
                    observations.add(sample);'''
        body = Template('''
            for (Map<String,$pairType> pair : (List<Map<String,$pairType>>)data.get("conversions")) {
                String type = ${cast}pair.get("type");
                Class<? extends Number> target = Class.forName(
                        (type.startsWith("Big") ? "java.math." : "java.lang.") + type).asSubclass(Number.class);
                String text = ${cast}pair.get("text");$setup
                try {
                    Number value = $owner.$method(text, target$argument);
                    $capture
                } catch (RuntimeException error) {
                    observations.add(row("throws", error.getClass().getName()));
                }
            }''').substitute(owner=p["owner"], method=p["method"], pairType="Object" if formatted else "String",
                            cast="(String)" if formatted else "", setup=setup if formatted else "",
                            argument=", format" if formatted else "", capture=capture)
        support = ""
        if formatted:
            support = '''
                private static java.text.NumberFormat numberFormat(Map<String,Object> spec) {
                    if (spec == null) return null;
                    Locale locale = new Locale.Builder().setLanguageTag((String)spec.get("locale")).build();
                    java.text.DecimalFormat format = new java.text.DecimalFormat((String)spec.get("pattern"),
                            new java.text.DecimalFormatSymbols(locale));
                    format.setParseBigDecimal((Boolean)spec.get("parseBigDecimal"));
                    return format;
                }'''
    elif p["family"] == "selection and lazy default":
        body = '''
            for (Map<String,Object> selection : (List<Map<String,Object>>)data.get("selections")) {
                List<Integer> values = (List<Integer>)selection.get("values");
                Map<String,Object> rule = (Map<String,Object>)selection.get("predicate");
                java.util.function.Predicate<Integer> predicate = x -> {
                    if (rule.containsKey("oneOf")) return ((List<?>)rule.get("oneOf")).contains(x);
                    if (x == null) return false;
                    if (rule.containsKey("greaterThan")) return x > (Integer)rule.get("greaterThan");
                    return (x & 1) != 0;
                };
                OWNER<Integer> receiver = OWNER.FACTORY(values.toArray(new Integer[0]));
                RESULT<Integer> selected = receiver.METHOD(predicate);
                int[] calls = {0};
                boolean defined = selected.DEFINED();
                Integer value = selected.FALLBACK(() -> { calls[0]++; return (Integer)data.get("fallback"); });
                observations.add(row(defined, value, calls[0]));
            }'''
        for key in ["owner", "method", "factory", "result", "defined", "fallback"]:
            body = body.replace(key.upper(), p[key])
        support = ""
    else:
        from targets import observer_histories
        body, support = observer_histories.body(p)
    return TEMPLATE.read_text().replace("        /* MEASURE */", indent(dedent(body).strip(), "        ")).replace(
        "    /* SUPPORT */", indent(dedent(support).strip(), "    "))
