"""Run a command five times, comparing per-hit decisions and reason codes."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from harness import read, validate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', required=True)
    parser.add_argument('--hits')
    parser.add_argument('--timeout', type=float, default=1800)
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='after --: command containing {data} and {output} placeholders')
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if not command or not any('{output}' in x for x in command) or args.timeout <= 0:
        parser.error('command must contain {output}; timeout must be positive')
    try:
        hits = read(args.hits) if args.hits else None
        baseline = None
        diffs = []
        with tempfile.TemporaryDirectory(prefix='track2-repro-') as temporary:
            for run in range(1, 6):
                output = Path(temporary)/f'run-{run}.jsonl'
                cmd = [x.replace('{data}', str(Path(args.data).resolve())).replace('{output}', str(output)) for x in command]
                subprocess.run(cmd, check=True, timeout=args.timeout, stdout=sys.stderr)
                rows = read(output)
                errors, _ = validate(rows, hits)
                if errors:
                    raise ValueError(f'run {run}: ' + '; '.join(errors))
                current = {k: (v['decision'], v['reason_code']) for k, v in rows.items()}
                if baseline is None:
                    baseline = current
                else:
                    for hit in sorted(baseline.keys() | current.keys()):
                        if baseline.get(hit) != current.get(hit):
                            diffs.append(dict(run=run, hit_id=hit, first=baseline.get(hit), actual=current.get(hit)))
        print(json.dumps(dict(runs=5, reproducible=not diffs, differences=diffs), indent=2))
        return int(bool(diffs))
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

if __name__ == '__main__':
    sys.exit(main())
