"""Public byte-stream, archive and class-token observation recipes."""
import re
from targets import runtime_jar
from targets.observer_recipes import keys, nonempty, Unsupported

STREAM = ["prefix", "read.count", "destination.bytes", "rewind"]
ARCHIVE = ["archive.name", "archive.directory", "archive.payload"]
TOKENS = ["phase", "token.index", "class.identity", "stream.cursor", "stream.length", "exception"]


def select(entry, fields, inputs, api):
    owner, method, desc = runtime_jar.parse_target(entry)
    recipe = {"owner": owner, "method": method}
    if fields == STREAM:
        api.require(owner, method, "([BII)I")
        api.require(owner, "<init>", "(Ljava/lang/CharSequence;Ljava/nio/charset/Charset;I)V")
        for name, signature in (("mark", "(I)V"), ("reset", "()V"), ("read", "()I")):
            api.require(owner, name, signature)
        for item in inputs:
            keys(item, ["text", "charset", "encoderBuffer", "destination", "markLimit", "readWindowsByEpoch"])
            if (not isinstance(item["text"], str) or not isinstance(item["charset"], str) or
                    not re.fullmatch(r"(?:[0-9a-f]{2})+", item["destination"]) or type(item["encoderBuffer"]) != int or
                    type(item["markLimit"]) != int):
                raise Unsupported("stream needs registered text, charset, encoder size and initial destination bytes")
            for epoch in nonempty(item["readWindowsByEpoch"], "read windows between mark/reset boundaries"):
                for window in nonempty(epoch, "a registered read window"):
                    if len(window) != 2 or any(type(x) != int or x < 0 for x in window) or sum(window) > len(item["destination"])//2:
                        raise Unsupported("read window outside the caller's destination")
        return {**recipe, "family": "marked stream and retained destination"}
    if fields == ARCHIVE:
        api.require(owner, method, "(Ljava/lang/String;Ljava/lang/String;)V")
        api.require(owner, "<init>", "(Ljava/io/File;)V")
        for item in inputs:
            keys(item, ["entries", "names"])
            if len(nonempty(item["names"], "successive names of the registered entry")) < 2:
                raise Unsupported("a rename needs an original and a new name")
            for e in nonempty(item["entries"], "original archive entries"):
                keys(e, ["name", "payload"])
                if not isinstance(e["name"], str) or not re.fullmatch(r"(?:[0-9a-f]{2})*", e["payload"]):
                    raise Unsupported("archive entries require names and their payload bytes")
        return {**recipe, "family": "persistent archive rename and reopen"}
    if fields == TOKENS:
        api.require(owner, method, desc)
        match = re.fullmatch(r"\(L([\w/$]+);Ljava/lang/Object;\)V", desc)
        if not match:
            raise Unsupported("expected a writer accepting an output and an object")
        writer = match[1].replace("/", ".")
        name, rdesc = api.select(owner, ["readObject", "decode"], r"\(L[\w/$]+;Ljava/lang/Class;\)Ljava/lang/Object;")
        reader = rdesc.split(";")[0][2:].replace("/", ".")
        for typ, signature in ((owner, "()V"), (writer, "(II)V"), (reader, "([B)V")):
            api.require(typ, "<init>", signature)
        api.require(owner, "setRegistrationRequired", "(Z)V")
        api.require(writer, "toBytes", "()[B")
        for typ in (reader, writer):
            api.require(typ, "position", "()I")
        for item in inputs:
            keys(item, ["classTokens"])
            for token in nonempty(item["classTokens"], "class identity sequence"):
                if token not in ("void", "fixture enum") and not re.fullmatch(r"java\.[a-z]+\.[A-Za-z]+", token):
                    raise Unsupported("missing public class-token fixture: " + str(token))
        return {**recipe, "family": "class-token write and read", "writer": writer, "reader": reader, "read": name}
    raise Unsupported("unsupported byte or archive observation")


BYTES = '''
private static byte[] bytes(String text) {
    byte[] bytes = new byte[text.length()/2];
    for (int i=0; i<bytes.length; i++) bytes[i]=(byte)Integer.parseInt(text.substring(2*i, 2*i+2), 16);
    return bytes;
}
private static String hex(byte[] bytes) {
    StringBuilder value = new StringBuilder();
    for (byte b : bytes) value.append(String.format(Locale.ROOT, "%02x", b & 255));
    return value.toString();
}'''


def body(p):
    family = p["family"]
    if family == "marked stream and retained destination":
        return '''
            byte[] destination = bytes((String)data.get("destination"));
            try (OWNER stream = new OWNER((String)data.get("text"),
                    java.nio.charset.Charset.forName((String)data.get("charset")), (Integer)data.get("encoderBuffer"))) {
                observations.add(row("prefix", stream.read()));
                stream.mark((Integer)data.get("markLimit"));
                boolean first = true;
                for (List<List<Integer>> epoch : (List<List<List<Integer>>>)data.get("readWindowsByEpoch")) {
                    if (!first) {
                        stream.reset();
                        observations.add(row("reset"));
                    }
                    first = false;
                    for (List<Integer> window : epoch) {
                        int count = stream.METHOD(destination, window.get(0), window.get(1));
                        observations.add(row("read", count, hex(destination)));
                    }
                }
            }'''.replace("OWNER", p["owner"]).replace("METHOD", p["method"]), BYTES
    if family == "persistent archive rename and reopen":
        return '''
            File file = new File("fixture.zip");
            try (java.util.zip.ZipOutputStream out = new java.util.zip.ZipOutputStream(new FileOutputStream(file))) {
                for (Map<String,String> item : (List<Map<String,String>>)data.get("entries")) {
                    java.util.zip.ZipEntry entry = new java.util.zip.ZipEntry(item.get("name"));
                    entry.setTime(946684800000L);
                    out.putNextEntry(entry);
                    out.write(bytes(item.get("payload")));
                    out.closeEntry();
                }
            }
            List<String> names = (List<String>)data.get("names");
            for (int i=1; i<names.size(); i++) {
                new OWNER(file).METHOD(names.get(i-1), names.get(i));
                try (java.util.zip.ZipFile archive = new java.util.zip.ZipFile(file)) {
                    TreeMap<String,List<Object>> entries = new TreeMap<>();
                    for (java.util.zip.ZipEntry entry : Collections.list(archive.entries())) {
                        ByteArrayOutputStream contents = new ByteArrayOutputStream();
                        try (InputStream in = archive.getInputStream(entry)) {
                            byte[] buf = new byte[256];
                            for (int n; (n=in.read(buf)) != -1;) contents.write(buf, 0, n);
                        }
                        if (entries.put(entry.getName(), row(entry.getName(), entry.isDirectory(), hex(contents.toByteArray()))) != null)
                            throw new IllegalStateException("ambiguous duplicated archive name");
                    }
                    observations.add(new ArrayList<>(entries.values()));
                }
            }'''.replace("OWNER", p["owner"]).replace("METHOD", p["method"]), BYTES
    body = '''
        OWNER encoder = new OWNER();
        encoder.setRegistrationRequired(false);
        WRITER writer = new WRITER(256, -1);
        List<String> tokens = (List<String>)data.get("classTokens");
        List<Class<?>> types = new ArrayList<>();
        for (String name : tokens) types.add(name.equals("void") ? Void.TYPE :
                name.equals("fixture enum") ? Color.class : Class.forName(name));
        boolean complete = true;
        for (int i=0; i<types.size(); i++) {
            Class<?> token = types.get(i);
            try { encoder.METHOD(writer, token); }
            catch (RuntimeException error) {
                observations.add(row("write", i, token.getName(), writer.position(), error.getClass().getName()));
                complete = false;
                break;
            }
        }
        if (complete) {
            byte[] bytes = writer.toBytes();
            OWNER decoder = new OWNER();
            decoder.setRegistrationRequired(false);
            READER reader = new READER(bytes);
            List<Object> identities = new ArrayList<>();
            for (int i=0; i<types.size(); i++) {
                try {
                    Class<?> read = decoder.READ(reader, Class.class);
                    identities.add(row(read.getName(), read == types.get(i)));
                } catch (RuntimeException error) {
                    observations.add(row("read", i, reader.position(), error.getClass().getName()));
                    complete = false;
                    break;
                }
            }
            if (complete) observations.add(row("read", identities, reader.position(), bytes.length, reader.position() == bytes.length));
        }'''
    for key in ("owner", "method", "writer", "reader", "read"):
        body = body.replace(key.upper(), p[key])
    return body, "public enum Color { SAMPLE }"
