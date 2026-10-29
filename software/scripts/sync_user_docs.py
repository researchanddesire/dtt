#!/usr/bin/env python3
"""Mirror Simple Docs' DTT content into docs/."""
import argparse
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
UPSTREAM = 'https://github.com/researchanddesire/simple-docs.git'


def files(directory):
    return {path.relative_to(directory): path.read_bytes()
            for path in directory.rglob('*') if path.is_file()}


def sync(source, destination, check=False):
    expected = files(source)
    if not expected or Path('index.mdx') not in expected:
        raise ValueError('Expected Simple Docs content/dtt with index.mdx')
    actual = files(destination)
    changed = sorted(name for name in expected.keys() | actual.keys()
                     if expected.get(name) != actual.get(name))
    if check:
        if changed:
            raise ValueError('User docs differ: ' + ', '.join(map(str, changed)))
    elif changed:
        for name in actual.keys() - expected.keys():
            (destination/name).unlink()
        for name, data in expected.items():
            path = destination/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        for path in sorted(destination.rglob('*'), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
    print(f'{len(expected)} DTT documentation files; {len(changed)} differences.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, help='Local Simple Docs checkout')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if args.source:
        sync(args.source/'content/dtt', ROOT/'docs', args.check)
        return
    with tempfile.TemporaryDirectory(prefix='dtt-user-docs-') as temporary:
        checkout = Path(temporary)/'simple-docs'
        subprocess.run(['git','clone','--quiet','--depth=1','--filter=blob:none',
                        '--sparse','--branch','main',UPSTREAM,str(checkout)], check=True)
        subprocess.run(['git','-C',str(checkout),'sparse-checkout','set','content/dtt'], check=True)
        sync(checkout/'content/dtt', ROOT/'docs', args.check)


if __name__ == '__main__':
    main()
