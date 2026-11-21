import argparse
import json
import sys
from harness import read, validate, score


def main():
    parser = argparse.ArgumentParser(description='Validate Track 2 output and optionally score labeled hits.')
    parser.add_argument('output', nargs='?', default='output/dev.jsonl')
    parser.add_argument('--hits', help='hits.jsonl, to require exact coverage and alert IDs')
    parser.add_argument('--score', dest='labels', help='practice_labels.jsonl or another labeled subset')
    args = parser.parse_args()
    try:
        rows = read(args.output)
        errors, warnings = validate(rows, read(args.hits) if args.hits else None)
        result = dict(valid=not errors, predictions=len(rows), errors=errors, warnings=warnings)
        if not errors and args.labels:
            result['metrics'] = score(rows, read(args.labels))
        print(json.dumps(result, indent=2))
        return int(bool(errors))
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
