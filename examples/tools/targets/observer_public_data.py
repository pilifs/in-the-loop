"""Generate public collection, grammar-reader and mutable-property experiments from their inputs."""
import re
from targets import runtime_jar
from targets.observer_recipes import keys, nonempty, Unsupported

STACK = ["peek.outcome", "peek.value"]
STACK_RETAINED = [*STACK, "pop.afterPeek"]
CSS = ["dimension.spelling", "dimension.type", "dimension.magnitude"]
DATES = ["date.inputAlias", "date.returnAlias", "date.copy", "date.target"]


def select(entry, fields, inputs, api):
    owner, method, desc = runtime_jar.parse_target(entry)
    recipe = {"owner":owner,"method":method}
    if fields in (STACK,STACK_RETAINED):
        api.require(owner, method, "()Ljava/lang/Object;")
        api.select(owner, ["push"], r"\(Ljava/lang/Object;\)(?:V|Z|Ljava/lang/Object;)")
        api.require(owner, "pop", "()Ljava/lang/Object;")
        cls = owner
        if runtime_jar.class_flags(api.definition(owner)) & 0x600:
            raise Unsupported("need a public concrete stack implementation for the bound interface")
        constructors = runtime_jar.methods(api.definition(cls))
        with_capacity = ("<init>", "(I)V") in constructors
        api.require(cls, "<init>", "(I)V" if with_capacity else "()V")
        for item in inputs:
            keys(item, ["capacity","values","drain"])
            if (type(item["capacity"]) != int or not 0 < item["capacity"] <= 1024 or type(item["drain"]) != bool
                    or not isinstance(item["values"], list) or len(item["values"]) > item["capacity"]):
                raise Unsupported("stack observation needs its capacity, sequence of pushes and drain boundary")
        return {**recipe,"family":"peek on a retained stack","constructor":cls,"capacity":with_capacity,
                "subsequentPop":fields == STACK_RETAINED}
    if fields == CSS:
        api.require(owner, method, desc)
        match = re.fullmatch(r"\(L([\w/$]+/InputSource);\)L([\w/$]+);",desc)
        if not match:
            raise Unsupported("need a CSS 2.1 grammar reader taking an InputSource and returning a typed value")
        input_type,result = [v.replace("/",".") for v in match.groups()]
        api.require(input_type, "<init>", "(Ljava/io/Reader;)V")
        package = owner.rpartition(".")[0]
        concrete = api.named("SACParserCSS21")
        grammar = concrete
        ctor = "(Lorg/w3c/css/sac/Parser;)V"
        if ("<init>", ctor) in runtime_jar.methods(api.definition(owner)):
            api.require(owner, "<init>", ctor)
            constructor = f"new {owner}(new {concrete}())"
        elif owner == concrete or runtime_jar.class_flags(api.definition(owner)) & 0x600:
            constructor = f"new {concrete}()"
        else:
            raise Unsupported("missing CSS 2.1 parser construction on the bound public API")
        api.require(grammar, "<init>", "()V")
        if result.endswith(".LexicalUnit"):
            projection = "lexical"
        elif result.endswith((".CSSValue",".CSSStyleDeclaration")):
            projection = "declaration" if result.endswith(".CSSStyleDeclaration") else "primitive"
        else:
            raise Unsupported("missing typed CSS property lookup on " + result)
        for item in inputs:
            keys(item, ["text","property"])
            if not isinstance(item["text"],str) or not isinstance(item["property"],str):
                raise Unsupported("registered CSS grammar input and property name are required")
        return {**recipe,"family":"CSS grammar with typed dimension readback","constructor":constructor,
                "inputType":input_type,"result":result,"projection":projection}
    if fields == DATES:
        date = "Ljava/util/Date;"
        data = api.definition(owner)
        getters = [(name,d) for name,d in runtime_jar.methods(data) if name.startswith("get") and d=="()"+date
                   and ("set"+name[3:],"("+date+")V") in runtime_jar.methods(data)]
        if len(getters)!=1:
            raise Unsupported("choose the mutable Date property with its public getter and setter")
        getter,gd = getters[0]
        setter = "set"+getter[3:]
        api.require(owner,getter,gd)
        api.require(owner,setter,"("+date+")V")
        api.require(owner,"<init>","()V")
        api.require(owner,"<init>","(L"+runtime_jar.internal(owner)+";)V")
        copy,cd=api.select(owner,["copyTo"],r"\(L[\w/$]+;\)V")
        target=cd[2:-3].replace("/",".")
        if not runtime_jar.class_flags(api.definition(target)) & 0x200:
            raise Unsupported("copy target requires a public recording interface")
        api.require(target,setter,"("+date+")V")
        for item in inputs:
            keys(item, ["seed","mutateInput","mutateReturn","mutateTarget","preexisting","overridden"])
            if type(item["overridden"])!=bool or any(type(v)!=int for k,v in item.items() if k!="overridden"):
                raise Unsupported("date history requires concrete initial, mutation and target times")
        return {**recipe,"family":"mutable Date property and copies","getter":getter,"setter":setter,"copy":copy,"target":target}
    raise Unsupported("unresolved public data projection")


def body(p):
    if p["family"]=="peek on a retained stack":
        body='''
            OWNER receiver = new CONSTRUCT(CAPACITY);
            List<Object> values = (List<Object>)data.get("values");
            for (Object value : values) receiver.push(value);
            if ((Boolean)data.get("drain")) for (int i=0; i<values.size(); i++) receiver.pop();
            try {
                Object value = receiver.METHOD();
                observations.add(row("return", value));
            } catch (RuntimeException error) { observations.add(row("throws",error.getClass().getName())); }
            FOLLOWING
        '''
        following = ('try { observations.add(row("pop",receiver.pop())); } '
                'catch (RuntimeException error) { observations.add(row("throws",error.getClass().getName())); }'
                if p.get("subsequentPop") else "")
        return body.replace("FOLLOWING",following).replace("OWNER",p["owner"]).replace("CONSTRUCT",p["constructor"]).replace(
            "CAPACITY",'(Integer)data.get("capacity")' if p["capacity"] else "").replace("METHOD",p["method"]), ""
    if p["family"]=="CSS grammar with typed dimension readback":
        body='''
            OWNER parser = CONSTRUCTOR;
            INPUT source = new INPUT(new StringReader((String)data.get("text")));
            RESULT value = parser.METHOD(source);
            PROJECTION
        '''
        if p["projection"]=="lexical":
            projection='observations.add(row(value.toString(), (int)value.getLexicalUnitType(), (double)value.getFloatValue(), value.getDimensionUnitText()));'
        else:
            value = 'value.getPropertyCSSValue((String)data.get("property"))' if p["projection"]=="declaration" else "value"
            projection=('org.w3c.dom.css.CSSPrimitiveValue primitive = (org.w3c.dom.css.CSSPrimitiveValue)'+value+';\n'
                        'short type = primitive.getPrimitiveType();\n'
                        'observations.add(row(primitive.getCssText(), (int)type, (double)primitive.getFloatValue(type)));')
        return body.replace("OWNER",p["owner"]).replace("CONSTRUCTOR",p["constructor"]).replace("INPUT",p["inputType"]).replace(
            "RESULT",p["result"]).replace("METHOD",p["method"]).replace("PROJECTION",projection),""
    body='''
        final long seed = ((Number)data.get("seed")).longValue();
        OWNER message;
        if ((Boolean)data.get("overridden")) {
            message = new OWNER() {
                @Override public java.util.Date GETTER() { return new java.util.Date(seed); }
            };
        } else message = new OWNER();
        java.util.Date inputDate = new java.util.Date(seed);
        if (!(Boolean)data.get("overridden")) message.SETTER(inputDate);
        inputDate.setTime(((Number)data.get("mutateInput")).longValue());
        Long afterInput = millis(message.GETTER());
        java.util.Date returned = message.GETTER();
        if (returned != null) returned.setTime(((Number)data.get("mutateReturn")).longValue());
        Long afterReturn = millis(message.GETTER());
        OWNER copy = new OWNER(message);
        final java.util.Date[] received = {new java.util.Date(((Number)data.get("preexisting")).longValue())};
        TARGET recording = (TARGET)java.lang.reflect.Proxy.newProxyInstance(TARGET.class.getClassLoader(),
                new Class<?>[]{TARGET.class}, (proxy, member, arguments) -> {
                    if (member.getName().equals("SETTER") && arguments.length == 1) received[0]=(java.util.Date)arguments[0];
                    return null;
                });
        message.COPY(recording);
        Long forwarded = millis(received[0]);
        if (received[0] != null) received[0].setTime(((Number)data.get("mutateTarget")).longValue());
        observations.add(row(afterInput, afterReturn, millis(copy.GETTER()), forwarded, millis(message.GETTER())));
    '''
    for name in ("owner","getter","setter","copy","target"):
        body=body.replace(name.upper(),p[name])
    return body, "private static Long millis(java.util.Date date) { return date == null ? null : date.getTime(); }"
