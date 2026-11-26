"""Composite public observations for copied mutable properties, reactive bodies, and persisted block indexes."""
import re
from targets import runtime_jar
from targets.observer_recipes import keys, nonempty, Unsupported

COPIES = ["date.afterEachMutation.messageAndCopy", "date.publicGetter", "date.constructedCopy", "date.target"]
EVENTS = ["events.envelopes", "terminal.signal", "terminal.outer", "terminal.cause"]
SEARCH = ["hits.orderedParentIds", "hits.sortKeys", "hits.total"]


def select(entry, fields, inputs, api):
    owner, method, desc = runtime_jar.parse_target(entry)
    if fields == COPIES:
        from targets import observer_public_data
        base = {"seed":0, "mutateInput":0, "mutateReturn":0, "mutateTarget":0, "preexisting":0, "overridden":False}
        recipe = observer_public_data.select(entry,observer_public_data.DATES,[base],api)
        for item in inputs:
            mode = item.get("mode")
            if mode == "paired mutations":
                keys(item, ["mode","seed","mutateInput","mutateReturn","mutateTarget","preexisting"])
            elif mode in {"unset","overridden getter"}:
                keys(item, ["mode","seed","preexisting"])
            else:
                raise Unsupported("specify the alias history, explicit null input, or getter-only override")
            if (mode == "unset" and item["seed"] is not None or
                    any(type(v) != int for k,v in item.items() if k != "mode" and (mode != "unset" or k != "seed"))):
                raise Unsupported("the mutation boundaries need milliseconds or an explicit unset date")
        return {**recipe, "family":"paired mutable-property samples"}
    if fields == EVENTS:
        # The private implementation is reached through its published response interface.
        interface = api.named("WebClient") + "$ResponseSpec"
        api.require(interface,method,desc)
        if ((method,desc) not in runtime_jar.methods(api.definition(owner)) or
                runtime_jar.internal(interface) not in runtime_jar.interfaces(api.definition(owner))):
            raise Unsupported("the bound public response interface lacks a concrete implementation")
        import hashlib
        api.used[entry] = hashlib.sha256(api.definition(owner)).hexdigest()
        response = api.named("ClientResponse")
        event = api.named("ServerSentEvent")
        api.require(event,"data","()Ljava/lang/Object;")
        api.require(event,"retry","()Ljava/time/Duration;")
        api.require(response+"$Builder","body","(Ljava/lang/String;)L"+runtime_jar.internal(response)+"$Builder;")
        for item in inputs:
            keys(item,["streams"])
            if any(not isinstance(body,str) for body in nonempty(item["streams"],"finite event-stream bodies")):
                raise Unsupported("a stream needs the original encoded response body")
        return {"family":"consume an event-stream response", "method":method,"client":interface.split("$")[0],
                "response":response,"event":event,"type":api.named("ParameterizedTypeReference"),"status":api.named("HttpStatus"),
                "bindingEntry":interface+"#"+method+desc, "requiredDispatch":entry}
    if fields == SEARCH:
        api.require(owner,method,desc)
        if method != "<init>" or not re.fullmatch(r"\(Ljava/lang/String;L[\w/$]+\$Type;ZL[\w/$]+;L[\w/$]+;\)V",desc):
            raise Unsupported("need the parent sort constructor over the parent and child filter producers")
        for item in inputs:
            keys(item,["blocks","order","excludeMissingChild","childMissing","parentMissing"])
            if item["order"] not in {"ascending","descending"} or type(item["excludeMissingChild"]) != bool:
                raise Unsupported("need a child inclusion rule and sort direction")
            for block in nonempty(item["blocks"],"parent/child blocks"):
                keys(block,["parent","children"])
                if not isinstance(block["parent"],str) or any(c is not None and type(c)!=int for c in block["children"]):
                    raise Unsupported("each parent requires its identifier and nullable integer child field values")
        lib = {}
        for name in ["ByteBuffersDirectory","IndexWriter","IndexWriterConfig","DirectoryReader","IndexSearcher",
                     "Document","StringField","Field","StoredField","SortedDocValuesField","SortedNumericDocValuesField",
                     "BytesRef","QueryBitSetProducer","BitSetProducer","TermQuery","Term","SortField","Sort","FieldDoc"]:
            lib[name] = api.named(name)
        return {"family":"reopened block index and sorted hits","owner":owner,"types":lib}
    raise Unsupported("no combined public observation for those fields")


def body(p):
    if p["family"]=="paired mutable-property samples":
        body='''
            String mode = (String)data.get("mode");
            final Number seed = (Number)data.get("seed");
            OWNER message;
            if (mode.equals("overridden getter")) {
                message = new OWNER() {
                    @Override public java.util.Date GETTER() { return new java.util.Date(seed.longValue()); }
                };
            } else message = new OWNER();
            java.util.Date supplied = seed == null ? null : new java.util.Date(seed.longValue());
            if (!mode.equals("overridden getter")) message.SETTER(supplied);
            OWNER copy = new OWNER(message);
            final java.util.Date[] target = {new java.util.Date(((Number)data.get("preexisting")).longValue())};
            TARGET recording = (TARGET)java.lang.reflect.Proxy.newProxyInstance(TARGET.class.getClassLoader(),
                    new Class<?>[]{TARGET.class}, (proxy, member, arguments) -> {
                        if (member.getName().equals("SETTER") && arguments.length == 1) target[0]=(java.util.Date)arguments[0];
                        return null;
                    });
            message.COPY(recording);
            if (mode.equals("paired mutations")) {
                supplied.setTime(((Number)data.get("mutateInput")).longValue());
                observations.add(row(millis(message.GETTER()), millis(copy.GETTER())));
                message.GETTER().setTime(((Number)data.get("mutateReturn")).longValue());
                observations.add(row(millis(message.GETTER()), millis(copy.GETTER())));
                target[0].setTime(((Number)data.get("mutateTarget")).longValue());
                observations.add(row(millis(message.GETTER()), millis(copy.GETTER())));
            } else observations.add(row(millis(message.GETTER()), millis(copy.GETTER()), millis(target[0])));
        '''
        for key in ("owner","getter","setter","target","copy"):
            body=body.replace(key.upper(),p[key].replace("$","."))
        return body,"private static Long millis(java.util.Date d) { return d == null ? null : d.getTime(); }"
    if p["family"]=="consume an event-stream response":
        body='''
            for (String text : (List<String>)data.get("streams")) {
                List<Object> events = new ArrayList<>();
                String[] terminal = new String[3];
                CLIENT client = CLIENT.builder().exchangeFunction(request ->
                        reactor.core.publisher.Mono.just(RESPONSE.create(STATUS.OK)
                            .header("Content-Type", "text/event-stream").body(text).build())).build();
                CLIENT.ResponseSpec response = client.get().uri("http://localhost/observed").retrieve();
                reactor.core.publisher.Flux<EVENT<String>> stream = response.METHOD(new TYPE<EVENT<String>>() {});
                stream.doOnNext(event -> events.add(row(event.data(), event.retry()==null ? null : event.retry().toMillis())))
                      .doOnComplete(() -> terminal[0]="complete")
                      .doOnError(error -> {
                          terminal[0]="error";
                          terminal[1]=error.getClass().getName();
                          terminal[2]=error.getCause()==null ? null : error.getCause().getClass().getName();
                      }).onErrorResume(error -> reactor.core.publisher.Flux.empty()).blockLast(java.time.Duration.ofSeconds(10));
                observations.add(row(events, terminal[0], terminal[1], terminal[2]));
            }
        '''
        for key in ("client","response","status","event","method","type"):
            body=body.replace(key.upper(),p[key])
        return body,""
    body='''
        try (ByteBuffersDirectory directory = new ByteBuffersDirectory()) {
            try (IndexWriter writer = new IndexWriter(directory, new IndexWriterConfig())) {
                for (Map<String,Object> block : (List<Map<String,Object>>)data.get("blocks")) {
                    List<Document> docs = new ArrayList<>();
                    for (Integer value : (List<Integer>)block.get("children")) {
                        Document child = new Document();
                        child.add(new StringField("role","child", Field.Store.NO));
                        if (value != null) {
                            child.add(new StringField("valued","yes",Field.Store.NO));
                            child.add(new SortedDocValuesField("spelling",new BytesRef(value.toString())));
                            child.add(new SortedNumericDocValuesField("number",value));
                        }
                        docs.add(child);
                    }
                    Document parent = new Document();
                    parent.add(new StringField("role","parent",Field.Store.NO));
                    parent.add(new StoredField("identity",(String)block.get("parent")));
                    docs.add(parent);
                    writer.addDocuments(docs);
                }
            }
            try (DirectoryReader reader = DirectoryReader.open(directory)) {
                IndexSearcher searcher = new IndexSearcher(reader);
                TermQuery parents = new TermQuery(new Term("role","parent"));
                boolean filtered = (Boolean)data.get("excludeMissingChild");
                BitSetProducer parentFilter = new QueryBitSetProducer(parents);
                BitSetProducer childFilter = new QueryBitSetProducer(new TermQuery(
                        new Term(filtered ? "valued" : "role",filtered ? "yes" : "child")));
                boolean reverse = data.get("order").equals("descending");
                SortField ordering = new OWNER("spelling",SortField.Type.STRING,reverse,parentFilter,childFilter);
                observations.add(hits(searcher,parents,ordering));
                List<Integer> missing = (List<Integer>)data.get("childMissing");
                if (!missing.isEmpty()) {
                    try {
                        java.lang.reflect.Constructor<?> withMissing = OWNER.class.getConstructor(String.class,
                                SortField.Type.class,boolean.class,Object.class,Object.class,BitSetProducer.class,BitSetProducer.class);
                        for (Integer replacement : missing) {
                            SortField numeric = (SortField)withMissing.newInstance("number",SortField.Type.INT,reverse,
                                    data.get("parentMissing"),replacement,parentFilter,childFilter);
                            observations.add(hits(searcher,parents,numeric));
                        }
                    } catch (NoSuchMethodException absent) { observations.add(row("overload-absent")); }
                }
            }
        }'''
    support='''
        private static List<Object> hits(IndexSearcher searcher, TermQuery parents, SortField ordering) throws IOException {
            org.apache.lucene.search.TopFieldDocs found = searcher.search(parents,100,new Sort(ordering));
            List<Object> values = new ArrayList<>();
            for (org.apache.lucene.search.ScoreDoc doc : found.scoreDocs) {
                Object sortKey = ((FieldDoc)doc).fields[0];
                String spelling = sortKey == null ? null : sortKey instanceof BytesRef ? ((BytesRef)sortKey).utf8ToString() : sortKey.toString();
                values.add(row(searcher.storedFields().document(doc.doc).get("identity"),spelling));
            }
            return row(found.totalHits.value(), values);
        }'''
    def types(java):
        identifiers={**p["types"],"OWNER":p["owner"]}
        return re.sub(r"\b(?:"+"|".join(identifiers)+r")\b",lambda m: identifiers[m[0]],java)
    return types(body),types(support)
