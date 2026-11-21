"""Regression checks for the original Maven operand and historical testcase evidence."""
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "baselines"))
import engineering
from corpus_ci import fresh_reports
from maven_mirror import artifact_path


class OriginalInputs(unittest.TestCase):
    def test_relocated_operand_follows_the_published_pom_to_the_runtime_jar(self):
        case = {"dependency": "old.group:client", "versions": {"new": "1"}}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root/"old/group/client/1/client-1.pom"
            source.parent.mkdir(parents=True)
            def pom(group):
                return "<project><distributionManagement><relocation><groupId>" + group + "</groupId></relocation></distributionManagement></project>"
            source.write_text(pom("new.group"))
            target = root/"new/group/client/1/client-1.jar"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"actual artifact")
            path, trace = engineering.resolved_operand(root, case, "new")
            self.assertEqual(path, target)
            self.assertEqual(trace, [{"from":"old.group:client:1","to":"new.group:client:1","pomSha256":engineering.digest(source)}])
            target.with_suffix(".pom").write_text(pom("old.group"))
            with self.assertRaisesRegex(ValueError, "cyclic"):
                engineering.resolved_operand(root, case, "new")

    def test_only_a_fresh_named_testcase_records_the_developer_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            reports = root/"app/target/surefire-reports"
            reports.mkdir(parents=True)
            (reports/"TEST-cases.xml").write_text('<testsuite><testcase classname="pkg.Cases" name="works[0]"/>'
                       '<testcase classname="pkg.Cases" name="works[1]"><failure type="AssertionError"/></testcase>'
                       '<testcase classname="pkg.Cases" name="worksLater"><skipped/></testcase></testsuite>')
            row = fresh_reports(root, ["Cases","works"], root/"out")
            self.assertEqual([r["outcome"] for r in row["named"]], ["passed","failure"])
            self.assertEqual((row["tests"],row["failures"],row["skipped"]), (3,1,1))
        self.assertIsNotNone(artifact_path("/org/codehaus/mojo/signature/java16/1.1/java16-1.1.signature.sha1"))
        diagnostic = "[ERROR] Non-resolvable parent POM for app:1 -> [Help 1]"
        self.assertEqual(engineering.failure("[INFO] Scanning for projects...\n" + diagnostic), [diagnostic])


if __name__ == "__main__":
    unittest.main()
