"""Regression checks for the original Maven operand and historical testcase evidence."""
import hashlib
import io
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "baselines"))
import engineering
from corpus_ci import fresh_reports
from complete_client import declared_scope, jar_directory
from maven_mirror import artifact_path, declared_releases, open_release
from restore_archived import restore


class OriginalInputs(unittest.TestCase):
    def test_native_extraction_uses_the_entry_bound_by_the_running_checker(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            jar = root / "client.jar"
            entry = "META-INF/versions/21/p/Caller.class"
            with zipfile.ZipFile(jar, "w") as archive:
                archive.writestr("p/Caller.class", b"base")
                archive.writestr(entry, b"selected")
            sha = hashlib.sha256(b"selected").hexdigest()
            binding = {"class": "p.Caller", "provider": str(jar), "entry": entry, "sha256": sha, "selected_by": "version"}
            entries = {"manifest": "enabled", "entries": {"p/Caller.class": entry}}
            reply = {"old": {"bindings": [binding], "entries": {"0": entries}}}
            paths = {"old": [jar]}
            with patch.object(engineering.class_binding, "ask", return_value=(reply, 21)):
                data, logical = engineering.selected_originals("current", root / "checker", "current-build",
                    {"JVMCONTRACT_JAR_RELEASE": "21"}, root, paths, "p.Caller", "read", engineering.runtime_jar)
                self.assertEqual((data["old"], logical["old"]), (b"selected", entries))
                binding["sha256"] = hashlib.sha256(b"base").hexdigest()
                with self.assertRaisesRegex(ValueError, "binding|checker|preparation|prepared"):
                    engineering.selected_originals("current", root / "checker", "current-build",
                        {"JVMCONTRACT_JAR_RELEASE": "21"}, root, paths, "p.Caller", "read", engineering.runtime_jar)

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

            # Frameworks enumerate package directories before reading their component classes.
            classes = Path(temp) / "classes"
            package = classes / "example/beans"
            package.mkdir(parents=True)
            (package / "Component.class").write_bytes(b"fixture")
            archive = Path(temp) / "test-classes.jar"
            jar_directory(classes, archive, include_directories=True)
            with zipfile.ZipFile(archive) as jar:
                self.assertTrue(jar.getinfo("example/beans/").is_dir())
                self.assertEqual(jar.read("example/beans/Component.class"), b"fixture")

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
