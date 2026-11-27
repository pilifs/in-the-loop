"""Wire positions refer to the ordered JSON value returned by the measured caller."""
def mapping(fields, recipe, entry):
    family = recipe["family"]
    fields_by_family = {
        "typed numeric conversions": [
            ("[call][0]", entry, "return or throws at each public call"),
            ("[call][1]", "Object.getClass().getName()", "runtime class or exception type; null is distinct"),
            ("[call][2]", "Number.toString()", "numeric spelling after normal return")],
        "selection and lazy default": [
            ("[selection][0]", "selected.isDefined()", "boolean"),
            ("[selection][1]", "selected.getOrElse(Supplier)", "nullable integer"),
            ("[selection][2]", "counter increment in the actual supplied callback", "integer")],
        "weight view and backing graph": [
            ("[write][0]", entry, "normal return or thrown type"),
            ("[write][1]", "view.getEdgeWeight(same edge)", "double"),
            ("[write][2]", "backing.getEdgeWeight(same edge)", "double")],
        "commands on one listener-backed state machine": [
            ("[command][0]", "actual public interface command", "normal return or thrown type"),
            ("[command][1]", "receiver.getState().name()", "state after command"),
            ("[command][2]", "registered listener's event list size", "cumulative integer"),
            ("[last]", "event.getStateTransition().name() in callback order", "ordered sequence")],
        "marked stream and retained destination": [
            ("[0][1]", "stream.read()", "integer prefix"),
            ("[read][1]", entry, "integer byte count, including EOF"),
            ("[read][2]", "all bytes of the same caller-owned array after read", "hex octets in array order"),
            ("[reset][0]", "stream.reset() completed", "reset boundary")],
        "persistent archive rename and reopen": [
            ("[rename][entry][0]", "fresh JDK ZipFile enumeration, ZipEntry.getName()", "name"),
            ("[rename][entry][1]", "ZipEntry.isDirectory()", "boolean"),
            ("[rename][entry][2]", "fresh entry input stream read to EOF", "hex octets, sorted by name")],
        "class-token write and read": [
            ("[0][0]", "active encoder or independent decoder call", "write or read"),
            ("[failure][1]", "index of the call that threw", "integer"),
            ("[success][1]", "decoder.readObject and reference equality with each input Class", "ordered names and identities"),
            ("[failure][3] or [success][2]", "encoder/decoder position() at observation", "integer cursor"),
            ("[success][3:5]", "output.toBytes().length and comparison with decoder position()", "length and fully-consumed flag"),
            ("[failure][last]", "exception.getClass().getName() at failed operation", "type")],
        "collision subsets on a live map view": [
            ("[subset][2][step][0]", entry, "boolean for each removal"),
            ("[subset][2][step][1,3]", "map.containsKey/get/size after each removal", "mapping and size"),
            ("[subset][2][step][2]", "one retained keySet().contains", "keys in canonical order"),
            ("[subset][2][step][4,5]", "retained.contains(null) and map.get(null)", "presence and value")],
        "peek on a retained stack": [
            ("[0][0]",entry,"return or throws"),
            ("[0][1]",entry,"nullable value or exception type")],
        "CSS grammar with typed dimension readback": [
            ("[0][0]","CSS value spelling read after parsing","string"),
            ("[0][1]","getPrimitiveType or getLexicalUnitType","integer type"),
            ("[0][2]","getFloatValue","numeric magnitude")],
        "paired mutable-property samples": [
            ("[mutation][0,1]","message and constructed copy getters after each mutation","nullable milliseconds"),
            ("[0][0]","original public getter","nullable milliseconds"),
            ("[0][1]","constructed copy's public getter","nullable milliseconds"),
            ("[0][2]","Date captured by recording public copy target","nullable milliseconds")],
        "consume an event-stream response": [
            ("[stream][0]","subscribed event.data and event.retry","ordered payloads and nullable milliseconds"),
            ("[stream][1]","doOnComplete/doOnError","terminal signal"),
            ("[stream][2]","public terminal error.getClass().getName()","nullable type"),
            ("[stream][3]","public terminal error.getCause()","nullable type")],
        "reopened block index and sorted hits": [
            ("[query][1][hit][0]","reopened searcher.storedFields().document(hit.doc)","parent identifier in hit order"),
            ("[query][1][hit][1]","FieldDoc.fields[0] from public search","nullable sort-key spelling"),
            ("[query][0]","TopFieldDocs.totalHits.value()","integer")],
        "mutable Date property and copies": [
            ("[0][0]","message getter after input-date mutation","nullable milliseconds"),
            ("[0][1]","message getter after returned-date mutation","nullable milliseconds"),
            ("[0][2]","copy constructor and getter","nullable milliseconds"),
            ("[0][3,4]","Date forwarded to recording target and subsequent original getter","nullable milliseconds")],
    }
    sources = fields_by_family[family]
    if family == "typed numeric conversions" and "argumentRead" in recipe:
        sources.append(("[call][3]", recipe["argumentRead"], "boolean returned on the retained formatter after normal return"))
    if family == "peek on a retained stack" and recipe.get("subsequentPop"):
        sources.append(("[1][1]", "subsequent pop on the same receiver", "retained top or exception type"))
    return [{"field":field,"position":position,"source":source,"type":kind}
            for field,(position,source,kind) in zip(fields,sources,strict=True)]
