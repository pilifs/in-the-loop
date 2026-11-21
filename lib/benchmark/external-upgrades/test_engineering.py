"""Regression checks for the original Maven operand and historical testcase evidence."""
import hashlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "baselines"))
import engineering
from corpus_ci import fresh_reports
from complete_client import declared_scope
from maven_mirror import artifact_path, declared_releases, open_release
from restore_archived import restore


class OriginalInputs(unittest.TestCase):
    def test_pinned_archive_is_checked_before_installation_and_on_reuse(self):
        name = "group/tool/1/tool-1.jar"
        archive = "https://example.invalid/"
        expected = {"bytes": 3, "sha256": hashlib.sha256(b"jar").hexdigest()}
        with tempfile.TemporaryDirectory() as temp, patch("restore_archived.urlopen") as fetch:
            repo = Path(temp).resolve() / "repository"
            def response(raw):
                stream = io.BytesIO(raw)
                stream.geturl = lambda: archive + name
                return stream
            fetch.side_effect = [response(b"bad"), response(b"jar")]
            with self.assertRaisesRegex(ValueError, "archived bytes differ"):
                restore(repo, archive, name, expected)
            self.assertFalse((repo/name).exists())
            restore(repo, archive, name, expected)
            restore(repo, archive, name, expected)
            self.assertEqual(fetch.call_count, 2)
            self.assertEqual((repo/(name + ".sha1")).read_text().strip(), hashlib.sha1(b"jar").hexdigest())
            (repo/name).write_bytes(b"bad")
            with self.assertRaisesRegex(ValueError, "existing cached bytes differ"):
                restore(repo, archive, name, expected)

    def test_environment_scope_comes_from_the_direct_module_declaration(self):
        with tempfile.TemporaryDirectory() as temp:
            pom = Path(temp) / "pom.xml"
            dependency = "<dependency><groupId>g</groupId><artifactId>a</artifactId><scope>{}</scope></dependency>"
            managed = "<dependencyManagement><dependencies>" + dependency.format("test") + "</dependencies></dependencyManagement>"
            for direct in ("", "provided", "test"):
                deps = "<dependencies>" + (dependency.format(direct) if direct else "") + "</dependencies>"
                pom.write_text('<project xmlns="http://maven.apache.org/POM/4.0.0">' + managed + deps + "</project>")
                self.assertEqual(declared_scope(pom, "g:a"), direct or None)

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

    def test_declared_release_repository_follows_a_missing_artifact(self):
        endpoint = "https://repository.jboss.org/nexus/repository/public-jboss/"
        original = "https://repository.jboss.org/nexus/content/groups/public-jboss/"
        name = Path("org/example/artifact/1/artifact-1.pom")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pom.xml").write_text(
                f'<project xmlns="http://maven.apache.org/POM/4.0.0"><repositories>'
                f'<repository><url>{original}</url></repository></repositories></project>')
            self.assertEqual(declared_releases(root, ["pom.xml"]), [endpoint])
            self.assertEqual(declared_releases(root, []), [])
        with patch("maven_mirror.urlopen") as fetch:
            response = unittest.mock.Mock()
            response.geturl.return_value = endpoint + name.as_posix()
            fetch.side_effect = [HTTPError("central", 404, "absent", {}, None), response]
            self.assertIs(open_release(name, [endpoint]), response)
            self.assertEqual(fetch.call_count, 2)
            fetch.reset_mock()
            fetch.side_effect = HTTPError("central", 403, "denied", {}, None)
            with self.assertRaises(HTTPError) as failure:
                open_release(name, [endpoint])
            failure.exception.close()
            self.assertEqual(fetch.call_count, 1)


if __name__ == "__main__":
    unittest.main()
