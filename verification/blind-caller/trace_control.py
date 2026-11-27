"""A returned call on one instance must not be attributed to the same method on a different instance."""
import os
from pathlib import Path
import subprocess
import tempfile

import parquet_trace as run
from targets import public_histories, upgrade_replay
from targets.change_inventory import file_digest


def check(root):
    jdk = run.JDK
    prod, tests, output = (root/k for k in ("production","tests","events"))
    for path in (prod,tests,output):
        path.mkdir()
    (root/"Value.java").write_text("""package sample;
public class Value {
    public int read() { return 4; }
    public int finish() { return changed(); }
    private int changed() { return 2; }
}""")
    (root/"Original.java").write_text("""package checks;
import sample.Value;
public class Original {
    public static void main(String[] args) throws Exception {
        Value a = new Value(), b = new Value();
        if (a.read() != 4 || b.finish() != 2 || a.finish() != 2) throw new AssertionError();
        if (args.length == 0) {
            int code = new ProcessBuilder(System.getProperty("java.home") + "/bin/java", "-cp",
                System.getProperty("java.class.path"), Original.class.getName(), "child").inheritIO().start().waitFor();
            if (code != 0) throw new AssertionError(code);
        }
    }
}""")
    subprocess.run([jdk/"bin/javac","-g","-d",prod,root/"Value.java"],check=True)
    subprocess.run([jdk/"bin/javac","-g","-cp",prod,"-d",tests,root/"Original.java"],check=True)
    agent = root/"history.so"
    subprocess.run(["g++","-std=c++17","-shared","-fPIC","-O2","-I"+str(jdk/"include"),"-I"+str(jdk/"include/linux"),
                    run.AGENT,"-o",agent],check=True)
    config = root/"config.tsv"
    config.write_text("directory\t"+str(output)+"\nlimit\t1000\nprefix\tsample/\ntest\tchecks/Original\n"
                      "changed\tsample/Value#changed()I\npublic\tread()I\npublic\tfinish()I\n")
    command = [jdk/"bin/java","-cp",os.pathsep.join(map(str,(tests,prod))),"checks.Original"]
    subprocess.run(command,check=True,timeout=15)
    subprocess.run(command,check=True,timeout=20,env={**os.environ,"JAVA_TOOL_OPTIONS":
                   "-agentpath:"+str(agent)+"="+str(config)+" -Xlog:class+load=info:file="+str(output/"%p.loads")})
    events = list(output.glob("*.events"))
    assert len(events) == 2, "the original child JVM was missed"
    for path in events:
        fork = public_histories.read_fork(path,[{"file":str(prod),"sha256":file_digest(prod)}],
                                         tests,"unit fixture","synthetic",upgrade_replay.sha(jdk/"release"),21)
        assert fork["stop"] is None
        rows = public_histories.witnesses(fork)
        hits = [r for r in rows if r["entry"]=="sample/Value#finish()I" and r["relationship"]=="nested"]
        later = [r for r in rows if r["entry"]=="sample/Value#read()I" and r["relationship"]=="later on retained receiver"]
        assert len(hits)==2 and len(later)==1 and later[0]["hitEvent"]==hits[1]["hitEvent"], rows
    print("Both test JVMs bound the two nested calls and just the later call on the retained receiver")


if __name__ == "__main__":
    with tempfile.TemporaryDirectory(prefix="original-test-history-") as scratch:
        check(Path(scratch))
