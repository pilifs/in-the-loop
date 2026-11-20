from pathlib import Path
import json
import subprocess

src = Path("/case/work/Test.java")
src.write_text(
    "public class Test { public static void main(String[] args){System.out.println(neutral.Counter.increment(41));} }"
)
values = []
for side in ("old", "new"):
    d = Path("/case/work") / side
    d.mkdir()
    subprocess.run(
        [
            "javac",
            "-d",
            str(d),
            str(Path("/case/packet") / side / "src/main/java/neutral/Counter.java"),
            str(src),
        ],
        check=True,
    )
    values.append(int(subprocess.check_output(["java", "-cp", str(d), "Test"], text=True)))
print(json.dumps(values))
