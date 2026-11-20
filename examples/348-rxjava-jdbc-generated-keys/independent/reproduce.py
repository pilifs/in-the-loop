"""Replay CompSuite i-87 on two fresh source trees. Run acquire.py once to fill the inputs directory."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import time
import xml.etree.ElementTree as ET
import zipfile

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'inputs.json').read_text())
HISTORY = json.loads((HERE.parent / 'target.json').read_text())['history']
TEST = 'com.github.davidmoten.rx.jdbc.DatabaseSyncTest'
METHOD = 'testReturnGeneratedKeysForMultipleInsertedValuesInOneStatement'
COMPANION = 'testReturnGeneratedKeysForMultipleCallsOfInsert'
PARENT = 'com.github.davidmoten:sonatype-parent:0.1:pom'
VERSIONS = {'old': '1.4.192', 'new': '1.4.200'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def run(command, cwd, log):
    started = time.monotonic()
    with log.open('w') as stream:
        p = subprocess.run(command, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT)
    return {'exit': p.returncode, 'seconds': round(time.monotonic() - started, 3)}


def require(command, cwd, log):
    result = run(command, cwd, log)
    if result['exit']:
        raise RuntimeError(f'{log.name} failed: {log.read_text()[-2000:]}')
    return result


def classpath(paths):
    return os.pathsep.join(map(str, paths))


def report(xml, save):
    tree = ET.parse(xml)
    root = tree.getroot()
    cases = root.findall('testcase')
    # VM properties contain local paths. Preserve the actual testcase, type, message and stack.
    properties = root.find('properties')
    if properties is not None:
        root.remove(properties)
    tree.write(save, encoding='utf-8', xml_declaration=True)
    return {'originalXmlSha256': sha(xml), 'publicXmlSha256': sha(save), 'suite': root.attrib,
            'testcases': [{**case.attrib, **{x.tag: x.attrib for x in case if x.tag in ('failure', 'error', 'skipped')}} for case in cases]}


def jar_of_classes(root, dest):
    entries = sorted(root.rglob('*.class'))
    with zipfile.ZipFile(dest, 'w') as z:
        for entry in entries:
            name = entry.relative_to(root).as_posix()
            z.writestr(zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0)), entry.read_bytes())
    return {'files': len(entries), 'jarSha256': sha(dest)}


def replay(args):
    work, public = args.work.resolve(), args.output.resolve()
    work.mkdir(parents=True, exist_ok=False)
    public.mkdir(parents=True, exist_ok=False)
    inputs, jdk, mvn = args.inputs.resolve(), args.java_home.resolve(), args.maven_home.resolve()
    jarpaths = {c: inputs / artifact['file'] for c, artifact in LOCK['artifacts'].items()}
    for c, path in jarpaths.items():
        if sha(path) != LOCK['artifacts'][c]['sha256']:
            raise ValueError(f'Unexpected artifact bytes for {c}')
    if sha(inputs / LOCK['mavenDistribution']['file']) != LOCK['mavenDistribution']['sha256']:
        raise ValueError('Unexpected Maven distribution')
    os.environ['JAVA_HOME'] = str(jdk)
    java = [jdk/'bin/java', '-Xmx512m', '-Duser.timezone=UTC', '-Duser.language=en', '-Duser.country=US', '-Dfile.encoding=UTF-8']
    javac = [jdk/'bin/javac', '-J-Xmx512m', '-encoding', 'UTF-8', '-g', '-source', '1.7', '-target', '1.7']
    git = ['git', '--git-dir=' + str(args.repository.resolve())]
    def rev(ref):
        return subprocess.check_output([*git, 'rev-parse', ref], text=True).strip()
    old, new = (HISTORY['revisions'][s]['commit'] for s in VERSIONS)
    changed = subprocess.check_output([*git, 'diff', '--name-only', old, new], text=True).splitlines()
    if changed != ['pom.xml'] or rev(new + '^') != old:
        raise ValueError('Unexpected upgrade diff or parent')
    result = {'case': 'CompSuite i-87', 'changedFiles': changed, 'subjectRuntime': subprocess.check_output([*java, '-version'], stderr=subprocess.STDOUT, text=True).splitlines(),
              'subjectJavaSha256': sha(jdk/'bin/java'), 'subjectJavacSha256': sha(jdk/'bin/javac'),
              'subjectRtJarSha256': sha(jdk/'jre/lib/rt.jar'), 'platform': list(platform.uname())[0:1] + [platform.machine()],
              'initialCache': 'hash-checked JARs available; upstream Maven lifecycle attempted offline', 'sides': {}}
    modelcp = classpath([mvn/'lib/*', mvn/'boot/*'])
    model = work/'model'; model.mkdir()
    require([*javac, '-proc:none', '-cp', modelcp, '-d', model, HERE/'EffectivePom.java'], work, work/'model-compile.log')
    repo = args.maven_repo.resolve() if args.maven_repo else work/'maven-repository'
    parentpath = repo/'com/github/davidmoten/sonatype-parent/0.1'/jarpaths[PARENT].name
    parentpath.parent.mkdir(parents=True, exist_ok=True)
    if not parentpath.exists(): shutil.copyfile(jarpaths[PARENT], parentpath)
    if sha(parentpath) != LOCK['artifacts'][PARENT]['sha256']: raise ValueError('Wrong cached parent POM')
    for side, version in VERSIONS.items():
        commit, tag = (HISTORY['revisions'][side][k] for k in ('commit', 'tag'))
        if rev(tag + '^{}') != commit: raise ValueError(f'Unexpected tag {tag}')
        tree, saved = work/side, public/side
        tree.mkdir(); saved.mkdir()
        data = subprocess.check_output([*git, 'archive', commit])
        with tarfile.open(fileobj=io.BytesIO(data)) as archive: archive.extractall(tree, filter='data')
        cp = {key: [f'com.h2database:h2:{version}' if item == 'H2' else item for item in LOCK[key]] for key in ('compile', 'test', 'observation', 'surefire')}
        def deps(group): return [jarpaths[c] for c in cp[group]]
        one = {'revision': commit, 'tag': tag, 'srcMainGitTree': rev(commit+':src/main'), 'pomSha256': sha(tree/'pom.xml'), 'classpathOrder': cp}
        result['sides'][side] = one
        lifecycle = run([mvn/'bin/mvn', '-o', '-B', '-Dmaven.repo.local='+str(repo), 'test'], tree, tree/'maven.log')
        lifecycle['errors'] = [line.replace(str(repo), '${maven.repo.local}') for line in (tree/'maven.log').read_text().splitlines() if line.startswith('[ERROR]')][:4]
        lifecycle['testcases'] = sum(len(ET.parse(f).getroot().findall('testcase')) for f in (tree/'target/surefire-reports').glob('TEST-*.xml'))
        one['originalMavenTest'] = lifecycle
        raw_model = tree/'effective.xml'
        require([*java, '-cp', classpath([model, modelcp]), 'EffectivePom', tree/'pom.xml', jarpaths[PARENT], raw_model], tree, tree/'model.log')
        normalized_model = saved/'effective-pom.xml'; normalized_model.write_text(raw_model.read_text().replace(str(tree), '${project.basedir}'))
        one['effectivePom'] = {'rawSha256': sha(raw_model), 'portableSha256': sha(normalized_model)}
        app, tests, drivers = (tree/name for name in ['compiled-app','compiled-tests','compiled-observers'])
        for dest in (app, tests, drivers): dest.mkdir()
        one['compileProduction'] = require([*javac,'-proc:none','-cp',classpath(deps('compile')),'-d',app,*sorted((tree/'src/main/java').rglob('*.java'))],tree,tree/'compile.log')
        one['production'] = jar_of_classes(app, tree/'client.jar')
        one['compileTests'] = require([*javac,'-cp',classpath([app,*deps('test')]),'-d',tests,*sorted((tree/'src/test/java').rglob('*.java'))],tree,tree/'test-compile.log')
        shutil.copytree(tree/'src/test/resources', tests, dirs_exist_ok=True)
        # Historical jndi.properties opens target/test-classes/jndi relative to the project.
        (tree/'target').mkdir(exist_ok=True)
        test_resources = tree/'target/test-classes'
        if not test_resources.exists():
            test_resources.symlink_to(tests, target_is_directory=True)
        require([*javac,'-proc:none','-d',drivers,'-cp',classpath([app,*deps('test'),*deps('surefire')]),HERE/'Observe.java',HERE/'NamedSurefire.java'],tree,tree/'observers-compile.log')
        testcp = classpath([drivers, tests, app, *deps('test'), *deps('surefire')]); one['namedSurefire'] = {}
        for name, method in [('trigger',METHOD),('companion',COMPANION)]:
            cwd = tree/name; cwd.mkdir()
            receipt = run([*java,'-Dcalibration.reports='+str(cwd/'target/surefire-reports'),'-cp',testcp,'NamedSurefire',TEST,method],tree,cwd/'console.log')
            receipt.update(report(cwd/'target/surefire-reports'/f'TEST-{TEST}.xml',saved/f'{name}-surefire.xml'))
            if len(receipt['testcases']) != 1 or (receipt['testcases'][0]['classname'],receipt['testcases'][0]['name']) != (TEST,method): raise ValueError(f'Wrong testcase on {side}/{name}')
            one['namedSurefire'][name] = receipt
        if args.whole_suite:
            cwd = tree/'whole'; cwd.mkdir()
            names = sorted(f.relative_to(tests).with_suffix('').as_posix().replace('/','.') for f in tests.rglob('*.class') if '$' not in f.name and re.fullmatch(r'(?:Test.*|.*Test|.*Tests|.*TestCase)\.class',f.name))
            receipt = run([*java,'-Dcalibration.reports='+str(cwd/'target/surefire-reports'),'-cp',testcp,'NamedSurefire','--suite',*names],tree,cwd/'console.log')
            receipt['suites'] = {xml.stem:report(xml,saved/xml.name) for xml in sorted((cwd/'target/surefire-reports').glob('TEST-*.xml'))}
            if not receipt['suites']: raise RuntimeError((cwd/'console.log').read_text()[-1000:])
            one['wholeSurefire'] = receipt
        one['jvmObservations'] = {}
        for shape in ('combined', 'separate'):
            log = tree/(shape+'.log')
            obs = require([*java,'-cp',classpath([drivers,app,*deps('observation')]),'Observe',shape],tree,log)
            lines = log.read_text().splitlines()
            def single(prefix):
                matches = [line[len(prefix):] for line in lines if line.startswith(prefix)]
                if len(matches)!=1: raise ValueError(f'{shape}: expected one {prefix} line')
                return matches[0]
            loaded_app, loaded_h2 = Path(single('client=')).resolve(), Path(single('driver=')).resolve()
            if loaded_app != app or loaded_h2 != jarpaths[f'com.h2database:h2:{version}']: raise ValueError('Unexpected loaded application or driver')
            obs.update(keys=json.loads(single('keys=')), rows=[[int(key),text] for key,text in (line[4:].split('\t',1) for line in lines if line.startswith('row='))], application=one['production']['jarSha256'], h2Sha256=sha(loaded_h2))
            one['jvmObservations'][shape] = obs
        write_json(public/'jvm-receipt.json', result)
    if result['sides']['old']['production'] != result['sides']['new']['production']: raise ValueError('Different application bytecode')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inputs','repository','java-home','maven-home','work','output'): parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--maven-repo',type=Path)
    parser.add_argument('--whole-suite',action='store_true')
    replay(parser.parse_args())
