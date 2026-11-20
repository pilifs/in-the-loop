"""The historical assertions, independently queried rows, and adapter correspondence."""
import base64
import json


def driver_args():
    return ["combined", "separate"]


def observations(lines):
    rows = [json.loads(line) for line in lines]
    if [row['shape'] for row in rows] != driver_args():
        raise ValueError('Require a fresh observation for both shapes, in order')
    return rows


def problems(lines):
    differences = []
    for row in observations(lines):
        expected = [2] if row['shape'] == 'combined' else [1, 2]
        stored = [(key, base64.b64decode(text, validate=True).decode()) for key, text in row['rows']]
        if row['direct'] != expected or stored != [(1, 'something'), (2, 'again')]:
            differences.append([row['shape'], {'expectedKeys': expected, 'observed': row}])
    return differences


def correspondence(lines):
    rows = observations(lines)
    return {'cases': len(rows), 'disagreements': sum(row['direct'] != row['adapter'] for row in rows)}
