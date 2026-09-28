#!/usr/bin/env python3
"""
Extract the ASN.1 modules from a pdftotext dump of OMA-TS-ULP and diff them,
token by token, against Pycrate's bundled ULP .asn files.

usage: clean_ulp.py <pdf_text> <baseline_dir> [out_dir]
"""
import re, sys, os, glob, difflib

HDR = re.compile(r'^\s*([A-Za-z][A-Za-z0-9-]*)\s+DEFINITIONS\s+AUTOMATIC\s+TAGS\s*::=\s*$')
END = re.compile(r'^\s*END\s*$')

# page furniture inserted by the PDF: copyright line, permission line, running header
NOISE = [
    re.compile(r'Open Mobile Alliance\.\s*$'),
    re.compile(r'^\s*Used with the permission of the Open Mobile Alliance'),
    re.compile(r'^\s*OMA-TS-ULP-\S+\s+Page \d+ \(\d+\)\s*$'),
]

def split_modules(lines, strip_noise):
    mods, cur, name = {}, None, None
    for raw in lines:
        line = raw.replace('\f', '').rstrip()
        if cur is None:
            m = HDR.match(line)
            if m:
                name, cur = m.group(1), [line.strip()]
            continue
        if strip_noise and any(p.search(line) for p in NOISE):
            continue
        if not line.strip():
            continue
        cur.append(line.strip())
        if END.match(line):
            mods[name] = cur
            cur = None
    return mods

def join_wrapped(lines):
    """A line ending in 'x-' followed by a line starting with a letter is an
    identifier that the PDF wrapped at its hyphen: glue it back together."""
    out = []
    for l in lines:
        if out and re.search(r'[A-Za-z0-9]-$', out[-1]) and re.match(r'[A-Za-z0-9]', l):
            out[-1] += l
        else:
            out.append(l)
    return out

TOK = re.compile(r'::=|\.\.\.|\.\.|[A-Za-z][A-Za-z0-9-]*|\d+|[^\sA-Za-z0-9]')

def tokens(lines):
    text = '\n'.join(re.sub(r'--.*$', '', l) for l in lines)   # drop ASN.1 comments
    return TOK.findall(text)

def main():
    pdf_txt, base_dir = sys.argv[1], sys.argv[2]
    out_dir = sys.argv[3] if len(sys.argv) > 3 else 'pdf_modules'
    os.makedirs(out_dir, exist_ok=True)

    pdf = split_modules(open(pdf_txt, encoding='utf-8', errors='replace').read().split('\n'), True)
    base = {}
    for f in sorted(glob.glob(os.path.join(base_dir, '*.asn'))):
        base.update(split_modules(open(f, encoding='utf-8', errors='replace').read().split('\n'), False))

    for name, lines in pdf.items():
        with open(os.path.join(out_dir, name + '.asn'), 'w') as fh:
            fh.write('\n'.join(join_wrapped(lines)) + '\n')

    print(f'modules in PDF: {len(pdf)}   modules in baseline: {len(base)}')
    print('only in PDF     :', sorted(set(pdf) - set(base)))
    print('only in baseline:', sorted(set(base) - set(pdf)))
    print()
    same = []
    for name in pdf:
        if name not in base:
            continue
        a, b = tokens(join_wrapped(base[name])), tokens(join_wrapped(pdf[name]))
        if a == b:
            same.append(name)
            continue
        print(f'=== {name}: baseline {len(a)} tokens, PDF {len(b)} tokens')
        sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == 'equal':
                continue
            ctx = ' '.join(a[max(0, i1 - 6):i1])
            print(f'  [{op}] after: ... {ctx}')
            if i2 > i1: print('     baseline:', ' '.join(a[i1:i2])[:4000])
            if j2 > j1: print('     PDF     :', ' '.join(b[j1:j2])[:4000])
        print()
    print(f'identical modules ({len(same)}):', ', '.join(same))

main()
