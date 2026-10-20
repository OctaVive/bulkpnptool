"""Capture Python reference behavior for the standalone PHP regression suite."""
import ast
from dataclasses import asdict
import json
from pathlib import Path
import random
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root.parent))
import app
import number_splitter as ns
from pe_processor import get_pe_processor

cases = []
def add(function, args, expected):
    cases.append(dict(function=function, args=args, expected=expected))

tokens = {'', 'garbage', '0455688200', '455688200', '+31455688200', '0031455688200',
          '31455688200', '45568820X', '45568820xx', '04556882xx', '0455688xxx',
          '045568xxxx', '04556xxxxx', '04556x8x00', '0455688200-0455688299',
          '0455688201-0455688300', '0455688200-0455688202', '0455688299-0455688200',
          '0501234567', '501234567', '50123456', '0521123456', '05981234xx'}
tree = ast.parse((root.parent/'tests/test_number_splitter.py').read_text())
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) < 150:
        tokens.add(node.value)
for token in sorted(tokens):
    add('normalize_number', [token], ns.normalize_number(token))
    add('parse_block', [token], asdict(ns.parse_block_string(token)))
    add('parse_numbers', [token], [asdict(p) for p in app._parse_numbers(token)])

processor = get_pe_processor()
for line in (root.parent/'data/pe_codes.txt').read_text().splitlines():
    if ';' not in line or line.startswith('#'): continue
    prefix = line.split(';')[0].strip()
    for number in (prefix + '1234567', prefix.lstrip('0')+'1234567'):
        add('resolve_pe', [number], processor.resolve_pe_code(number))

split_cases = [([], []), ([], ['0455688200']), (['bad'], ['bad']),
               (['05012345xx'], ['0501234500']),
               (['04556882xx - PBX: 1234567 - Locatie: Office'], ['0455688250', '0711234567 - PBX: 7654321']),
               (['0455688200'], ['0455688200']),
               (['04556882xx'], ['04556882xx']),
               (['04556882xx', '045568825x'], ['0455688251'])]
rng = random.Random(21)
for _ in range(75):
    size = rng.choice([10,100,1000,10000])
    start = 455600000 // size * size
    source = ns.format_to_telecom_notation(f'{start:010}', size)
    removes = []
    for _ in range(rng.randrange(0,8)):
        rem_size = rng.choice([s for s in [1,10,100,1000] if s <= size])
        rem_start = (start + rng.randrange(size)) // rem_size * rem_size
        removes.append(ns.format_to_telecom_notation(f'{rem_start:010}', rem_size))
    split_cases.append(([source], removes))
for sources, removes in split_cases:
    result = ns.calculate_bulk_split(sources,removes)
    payload = asdict(result)
    add('calculate_split',[sources,removes],payload)
    add('delete_items',[payload],[asdict(b) for b in ns._collect_delete_items(result)])
    add('raw_text',[payload],ns.build_splitter_raw_text(result))
    add('special_blocks',[payload],[asdict(b) for b in ns.collect_special_add_blocks(result)])
    overrides = {b.lookup_key: '01' for b in ns.collect_special_add_blocks(result)}
    files = ns.build_splitter_csv_files(result,'pe_code',processor,'1000001',overrides)
    # Empty associative arrays become JSON objects on Python's side.
    add('splitter_files',[payload,'1000001',overrides],files)
    add('zip_filename',[files],ns.build_zip_filename(files))

for operation in ['ADD','DELETE','MOVE']:
    numbers = app._parse_numbers('0455688200\n45568820X\n0501234567\n50123456\n05211234xx\ninvalid\n+31711234567')
    overrides = {p.lookup_national:'01' for p in numbers if p.lookup_national and app._get_special_prefix(p.lookup_national)}
    add('provisioning_rows',[[asdict(p) for p in numbers],operation,'1000001','1000002',overrides],app._build_csv_rows(numbers,operation,'1000001','1000002',overrides))

(root/'tests/fixtures.json').write_text(json.dumps(cases,ensure_ascii=False,indent=2),encoding='utf-8')
print(f'Captured {len(cases)} reference cases')
