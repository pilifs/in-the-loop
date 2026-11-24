"""Join every frozen minimum substitution to the original bulk copy and its caller's entire destination."""
import hashlib
import json
from pathlib import Path
import zipfile

from bytecode import Body, OWNER, require, runtime_jar
from register import CASE, ENTRY, reference, sha
from plan_run import JDK, ROOT, OUTPUT
from targets import change_helpers


def instruction_sites(stream):
    read = Body(stream, "read", "([BII)I")
    buffer = "getfield " + OWNER + ".bBuf:Ljava/nio/ByteBuffer;"
    block = ["aload_0", buffer, "invokevirtual java/nio/ByteBuffer.remaining:()I", "iload_3",
             "invokestatic java/lang/Math.min:(II)I", "istore 5", "aload_0", buffer, "aload_1", "iload_2", "iload 5",
             "invokevirtual java/nio/ByteBuffer.get:([BII)Ljava/nio/ByteBuffer;", "pop",
             "iload_2", "iload 5", "iadd", "istore_2", "iload_3", "iload 5", "isub", "istore_3",
             "iload 4", "iload 5", "iadd", "istore 4"]
    require(read.sequence(110, 152) == block, "copy length is not consumed by the expected write and accounting")
    indices = {call: pc for pc, call in read.members.items() if 110 <= pc < 152}
    return {"minimumBCI": indices["java/lang/Math", "min", "(II)I"],
            "destinationGetBCI": indices["java/nio/ByteBuffer", "get", "([BII)Ljava/nio/ByteBuffer;"],
            "bulkBodySha256": hashlib.sha256(read.code).hexdigest()}


def main():
    target = ROOT / OUTPUT / "io"
    profile = json.loads((target / "charset-profiles.json").read_bytes())
    require(all(p["bufferClasses"][1] == "java.nio.HeapByteBuffer" for p in profile["profiles"]), "unbound byte buffer")
    heap_buffer, _ = change_helpers.original_class("java.nio.HeapByteBuffer", [], JDK)
    get = Body(heap_buffer, "get", "([BII)Ljava/nio/ByteBuffer;")
    require(get.sequence(47, 53) == ["aload_1", "iload_2", "iload_3",
            "invokestatic java/lang/System.arraycopy:(Ljava/lang/Object;ILjava/lang/Object;II)V"],
            "JDK copy no longer receives the original destination, offset and checked length")
    math, _ = change_helpers.original_class("java.lang.Math", [], JDK)
    minimum = Body(math, "min", "(II)I")
    # iload_0, iload_1, if_icmpgt 9, iload_0, goto 10, iload_1, ireturn.
    require(minimum.flags == 9 and minimum.code.hex() == "1a1ba300071aa700041bac", "unexpected minimum implementation")
    result = {"minimum": {"code": minimum.code.hex(), "classSha256": hashlib.sha256(math).hexdigest(),
                           "assurance": "Signed comparison and one of the two original operands on all int pairs. At the public call the frozen verifier supplies its certified finite result."},
              "destination": {"type": "java.nio.HeapByteBuffer", "classSha256": hashlib.sha256(heap_buffer).hexdigest(),
                              "getBodySha256": hashlib.sha256(get.code).hexdigest(), "systemArraycopyBCI": 50},
              "sides": {}}
    with zipfile.ZipFile(target / "first/plans.zip") as archive:
        cold = json.loads(archive.read("cold.json"))
        for side in ("old", "new"):
            src, = json.loads((CASE / side / "prepared.json").read_bytes())["classpath"]
            require(sha(Path(src["file"])) == src["sha256"], "changed original JAR")
            code = runtime_jar.read_class(Path(src["file"]), OWNER)
            frame = instruction_sites(code)
            records = []
            for node in cold["claims"]:
                if node["cohort"] != "registered":
                    continue
                require(node["status"] == "established", "open checked public claim")
                payload = archive.read(node["receipt"]["path"])
                require(hashlib.sha256(payload).hexdigest() == node["receipt"]["sha256"], "unbound original cold receipt")
                receipt = json.loads(payload)
                proof = receipt["helperProofs"][side]
                require(proof["classSha256"] == result["minimum"]["classSha256"] and proof["provider"] == "java.base",
                        "different JDK minimum")
                for trial in receipt["sides"][side]["trials"]:
                    history, selection = receipt["cases"][trial["input"]]["args"]
                    require(selection == "explicit", "unexpected constructor selection")
                    expected, copies = reference(history, side == "new")
                    hits = [{"caller": ENTRY, "bci": frame["minimumBCI"], "args": c["args"], "result": c["result"]} for c in copies]
                    applications = trial["checkedApplications"]
                    require(trial["observations"] == [expected] * 2 and trial["qualifiedMethodEntries"] == 2
                            and len(applications) == 2 and all(a["proofKey"] == proof["key"] and a["applications"] == hits
                            and a["startupArguments"] for a in applications), "public bytes, startup or ordered copy lengths differ")
                    records.append({"history": history, "claim": node["claimKey"], "receiptSha256": node["receipt"]["sha256"],
                                    "proofKey": proof["key"], "copiesPerTrial": copies, "independentFreshTrials": 2})
            require(len(records) == 4, "missing registered input")
            result["sides"][side] = {"artifactSha256": src["sha256"], **frame, "inputs": records}
    (target / "copy-frame.json").write_text(json.dumps(result, indent=2) + "\n")
    print("Every checked copy length, destination offset, byte window and complete public observation agreed on both JARs.")


if __name__ == "__main__":
    main()
