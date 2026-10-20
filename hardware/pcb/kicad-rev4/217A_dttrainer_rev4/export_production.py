#!/usr/bin/env python3
"""Export the DTT rev4 manufacturing package from its KiCad source."""
import argparse
import collections
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from zipfile import ZIP_DEFLATED, ZipFile

PROJECT = Path(__file__).resolve().parent
ROOT = PROJECT.parents[3]
STEM = '217A_dttrainer_rev4'
LAYERS = 'F.Cu,B.Cu,F.Mask,B.Mask,F.Paste,B.Paste,F.SilkS,B.SilkS,Edge.Cuts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref_key(ref):
    match = re.fullmatch(r'([A-Za-z]+)(\d+)', ref)
    return (match[1], int(match[2])) if match else (ref, 0)


def write_csv(path, header, rows):
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(header)
        writer.writerows(rows)


def source_files():
    paths = [path for path in PROJECT.rglob('*') if path.is_file() and path.suffix in {'.kicad_pcb','.kicad_sch','.kicad_pro','.kicad_sym','.kicad_mod'} and not any(part.endswith('-backups') for part in path.parts)]
    return sorted(paths + [PROJECT/'fp-lib-table', PROJECT/'sym-lib-table', Path(__file__).resolve()])


def check_package(out):
    manifest = json.loads((out/'manifest.json').read_text())
    actual = {str(path.relative_to(ROOT)): sha(path) for path in source_files()}
    if actual != manifest['source_sha256']:
        raise ValueError('KiCad sources changed; regenerate the manufacturing package')
    for name, expected in manifest['output_sha256'].items():
        if sha(out/name) != expected:
            raise ValueError(f'Manufacturing output changed: {name}')
    for line in (out/'SHA256SUMS').read_text().splitlines():
        expected, name = line.split('  ', 1)
        if sha(out/name) != expected:
            raise ValueError(f'Package checksum mismatch: {name}')
    preview = ROOT/'assembly-docs/assets/kicanvas/kicad-rev4/217A_dttrainer_rev4'/ (STEM+'.kicad_pcb')
    if sha(preview) != sha(PROJECT/(STEM+'.kicad_pcb')):
        raise ValueError('KiCanvas preview differs from the PCB source')
    print('Manufacturing source/output hashes and KiCanvas preview match.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kicad-cli', default=shutil.which('kicad-cli') or '/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
    parser.add_argument('--output', type=Path, default=ROOT/'hardware/pcb/production')
    parser.add_argument('--check', action='store_true', help='Check source/output hashes without KiCad or regenerating files')
    args = parser.parse_args()
    out = args.output.resolve()
    if args.check:
        check_package(out)
        return
    out.mkdir(parents=True, exist_ok=True)
    board = PROJECT/(STEM+'.kicad_pcb')
    schematic = PROJECT/(STEM+'.kicad_sch')

    def run(*command):
        subprocess.run([args.kicad_cli, *map(str, command)], check=True)

    with tempfile.TemporaryDirectory(prefix='dtt-manufacturing-') as temporary:
        temp = Path(temporary)
        gerbers = temp/'gerbers'
        gerbers.mkdir()
        run('pcb', 'export', 'gerbers', '-l', LAYERS, '--use-drill-file-origin', '-o', str(gerbers)+'/', board)
        run('pcb', 'export', 'drill', '--excellon-units', 'mm', '--drill-origin', 'plot', '-o', str(gerbers)+'/', board)
        run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm', '--use-drill-file-origin', '-o', temp/'pick-and-place.csv', board)
        run('sch', 'export', 'python-bom', '-o', temp/'bom.xml', schematic)
        run('sch', 'export', 'pdf', '-o', temp/'schematic.pdf', schematic)

        components = ET.parse(temp/'bom.xml').findall('./components/comp')
        rows = []
        for component in components:
            fields = {field.get('name'): field.text or '' for field in component.findall('./fields/field')}
            dnp = any(prop.get('name') == 'dnp' for prop in component.findall('property'))
            rows.append([component.get('ref'), component.findtext('value', ''), component.findtext('footprint', ''), fields.get('LCSC', ''), 'No' if dnp else 'Yes'])
        rows.sort(key=lambda row: ref_key(row[0]))
        populated = {row[0] for row in rows if row[4] == 'Yes'}
        with (temp/'pick-and-place.csv').open(newline='') as stream:
            positions = list(csv.DictReader(stream))
        if {row['Ref'] for row in positions} != populated or len(positions) != len(populated):
            raise ValueError('BOM population and placement references disagree')
        if any(not row[3] or row[3] == 'DNP' for row in rows if row[4] == 'Yes'):
            raise ValueError('A populated component has no procurement code')
        write_csv(temp/'pcb-bom.csv', ['Reference','Value','Footprint','LCSC','Populate'], rows)
        groups = collections.defaultdict(list)
        for row in rows:
            if row[4] == 'Yes':
                groups[(row[1], row[3])].append(row)
        assembly = []
        for (value, part), members in groups.items():
            assembly.append([value, ','.join(row[0] for row in members), ','.join(row[2] for row in members), part, len(members)])
        write_csv(temp/'assembly-bom.csv', ['Comment','Designator','Footprint','LCSC Part #','Quantity'], assembly)

        if (out/'gerbers').exists():
            shutil.rmtree(out/'gerbers')
        shutil.copytree(gerbers, out/'gerbers')
        with ZipFile(out/'Trainer_gerber.zip', 'w', ZIP_DEFLATED) as archive:
            for path in sorted(gerbers.iterdir()):
                archive.write(path, path.name)
        for name in ['pcb-bom.csv','assembly-bom.csv','pick-and-place.csv','schematic.pdf']:
            shutil.copyfile(temp/name, out/name)

    sources = source_files()
    outputs = sorted(list((out/'gerbers').iterdir()) + [out/name for name in ['Trainer_gerber.zip','pcb-bom.csv','assembly-bom.csv','pick-and-place.csv','schematic.pdf']])
    manifest = {
        'project': str(PROJECT.relative_to(ROOT)),
        'kicad_version': subprocess.check_output([args.kicad_cli, 'version'], text=True).strip(),
        'units': 'mm',
        'origin': 'KiCad auxiliary drill/place origin; X right, Y up',
        'pcb_components': len(rows),
        'populated_components': len(populated),
        'dnp_references': [row[0] for row in rows if row[4] == 'No'],
        'source_sha256': {str(path.relative_to(ROOT)): sha(path) for path in sorted(sources)},
        'output_sha256': {str(path.relative_to(out)): sha(path) for path in outputs},
    }
    (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    outputs.append(out/'manifest.json')
    (out/'SHA256SUMS').write_text(''.join(f'{sha(path)}  {path.relative_to(out)}\n' for path in sorted(outputs)))
    if out == ROOT/'hardware/pcb/production':
        preview = ROOT/'assembly-docs/assets/kicanvas/kicad-rev4/217A_dttrainer_rev4'/ (STEM+'.kicad_pcb')
        shutil.copyfile(board, preview)
    print(f'Exported {len(rows)} PCB components; {len(populated)} populated placements to {out}')


if __name__ == '__main__':
    main()
