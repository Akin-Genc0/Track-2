"""Recover browse-only data; not a replacement for original JSONL files."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET
import zipfile


def extract(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(source) as z:
        strings = [''.join(x.itertext()) for x in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        def rows(number):
            with z.open(f'xl/worksheets/sheet{number}.xml') as stream:
                for _, row in ET.iterparse(stream, events=('end',)):
                    if row.tag != '{'+ns['s']+'}row':
                        continue
                    values = {}
                    for cell in row:
                        column = ''.join(c for c in cell.get('r', '') if c.isalpha())
                        value = cell.find('s:v', ns)
                        text = value.text if value is not None else ''
                        values[column] = strings[int(text)] if cell.get('t') == 's' else text
                    if any(values.values()):
                        yield values
                    row.clear()
        names = ['alerts', 'hits', 'customers', 'accounts', 'onboarding', 'kyc_checks', 'notes', 'search_results', 'practice_labels']
        for number, name in enumerate(names, 2):
            iterator = rows(number)
            headers = next(iterator)
            with (destination / (name+'.jsonl')).open('w') as output:
                for row in iterator:
                    record = {v: row.get(k, '') for k, v in headers.items() if v}
                    if name == 'practice_labels':
                        for key in ('reason_codes', 'customer_record_ids', 'evidence'):
                            record[key] = record[key].split('; ') if record[key] else []
                    output.write(json.dumps(record, ensure_ascii=False)+'\n')
        policy = [r.get('A', '') for r in rows(11)]
        split = policy.index('name_variants.json')
        (destination/'POLICY.md').write_text('\n\n'.join(policy[:split])+'\n')
        variants = policy[split+1:]
        (destination/'name_variants.json').write_text(json.dumps({'groups': [x.split(', ') for x in variants[1:-1]], 'company_legal_forms': variants[-1].split(': ', 1)[1].split(', ')}, indent=2))
        (destination/'name_variants.browse.txt').write_text('\n'.join(policy[split+1:])+'\n')
    (destination/'PROVENANCE.txt').write_text('Recovered from Screening Dev Set - browse.xlsx. Spreadsheet strings and flattened lists retained, except practice label lists. Long text may be truncated at 32000 characters. Not the original data-room JSONL schema.\n')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    extract(args.workbook, args.destination)
