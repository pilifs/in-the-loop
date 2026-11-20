"""Run the historical full test set through the pinned Surefire provider and retain its complete failure inventory."""
from pathlib import Path
import argparse
import json
import os
import subprocess
import sys
import tempfile
import zipfile

from acquire import acquire

HERE = Path(__file__).resolve().parent


def summarize(receipt):
    summary = {}
    for side, data in receipt['sides'].items():
        full = data['wholeSurefire']
        totals = {field: 0 for field in ('tests', 'failures', 'errors', 'skipped')}
        failed = []
        for suite in full['suites'].values():
            for field in totals:
                totals[field] += int(suite['suite'][field])
            for case in suite['testcases']:
                if 'failure' in case or 'error' in case:
                    failed.append(case)
        trigger = next((c for suite in full['suites'].values() for c in suite['testcases']
                        if c['classname'].endswith('.DatabaseSyncTest') and c['name'] == 'testReturnGeneratedKeysForMultipleInsertedValuesInOneStatement'), None)
        if trigger is None:
            raise ValueError(f'{side} missing the concrete trigger')
        summary[side] = {'seconds': full['seconds'], 'exit': full['exit'], 'suiteCount': len(full['suites']),
                         'totals': totals, 'trigger': trigger, 'failuresAndErrors': failed,
                         'upstreamMavenLifecycle': data['originalMavenTest'], 'production': data['production'],
                         'classpathOrder': data['classpathOrder']['test']}
    return summary


def main():
    temp = Path(os.environ['TMPDIR']) if 'TMPDIR' in os.environ else Path.home()/'.cache/in-the-loop/tmp'
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--inputs', type=Path, default=Path(os.environ.get('RXJAVA_CALIBRATION_INPUTS', temp/'external-upgrade-rxjava/i87-download')))
    p.add_argument('--java-home', type=Path, default=Path.home()/'.sdkman/candidates/java/8.0.512.0+9-tem')
    p.add_argument('--output', type=Path, default=HERE.parent/'records/whole-suite.json')
    args = p.parse_args()
    temp.mkdir(exist_ok=True, parents=True)
    acquire(args.inputs, temp/'external-upgrade-network.lock')
    with tempfile.TemporaryDirectory(prefix='rxjava-i87-suite-', dir=temp) as tmp:
        work = Path(tmp)
        with zipfile.ZipFile(args.inputs/'apache-maven-3.6.3-bin.zip') as distribution:
            distribution.extractall(work)
        maven = work/'apache-maven-3.6.3'
        (maven/'bin/mvn').chmod(0o755)
        output = work/'receipts'
        subprocess.run([sys.executable, HERE/'reproduce.py', '--inputs', args.inputs, '--repository', args.inputs/'subject.git',
                        '--java-home', args.java_home, '--maven-home', maven, '--work', work/'build', '--output', output,
                        '--whole-suite'], check=True)
        results = summarize(json.loads((output/'jvm-receipt.json').read_text()))
    args.output.write_text(json.dumps(results, indent=2)+'\n')
    for side, result in results.items():
        print(side, result['totals'], result['seconds'], 'seconds', flush=True)


if __name__ == '__main__':
    main()
