#!/usr/bin/env python3
"""
usage: make_compilable.py <pdf_modules_dir> <baseline_dir> [out_dir]

1. removes comment-continuation lines that the PDF wrapped (they lost their '--')
2. splits '}' glued to the following definition
3. re-diffs the result (token by token) against the baseline: what remains
   should be genuine schema changes only.
"""
import re, sys, os, glob, difflib

CODE = re.compile(r'::=|[{}]|\b(OPTIONAL|BOOLEAN|INTEGER|SEQUENCE|ENUMERATED|CHOICE|STRING|'
                  r'FROM|IMPORTS|EXPORTS|BEGIN|END|DEFINITIONS|SIZE|NULL)\b|\.\.\.')
FIELD_TYPE = re.compile(r'^[a-z][A-Za-z0-9-]*\s+[A-Z][A-Za-z0-9-]*\s*,?\s*$')
BARE_TYPE  = re.compile(r'^[A-Z][A-Za-z0-9-]*\s*,?\s*$')

def code_part(l):
    return re.sub(r'--.*$', '', l).strip()

def is_code(l, allow_bare=False):
    if l.startswith('--'):
        return True
    c = code_part(l)          # judge the code only, never the trailing comment
    return bool(CODE.search(c) or FIELD_TYPE.match(c) or (allow_bare and BARE_TYPE.match(c)))

def open_comment(l):
    i = l.find('--')
    return i >= 0 and '--' not in l[i + 2:]

def clean(lines):
    out, removed, in_cmt, prev_code = [], [], False, ''
    for l in lines:
        for piece in re.sub(r'\}(?=[A-Za-z])', '}\n', l).split('\n'):
            # a bare type name is only real code right after '... OF'
            if in_cmt and not is_code(piece, allow_bare=prev_code.endswith('OF')):
                removed.append((out[-1] if out else '', piece))
                continue
            out.append(piece)
            in_cmt = open_comment(piece)
            prev_code = code_part(piece)
    return out, removed

HDR = re.compile(r'^\s*([A-Za-z][A-Za-z0-9-]*)\s+DEFINITIONS\s+AUTOMATIC\s+TAGS\s*::=\s*$')
END = re.compile(r'^\s*END\s*$')
def base_modules(d):
    mods = {}
    for f in sorted(glob.glob(os.path.join(d, '*.asn'))):
        cur = None
        for raw in open(f, encoding='utf-8', errors='replace').read().split('\n'):
            l = raw.rstrip()
            if cur is None:
                m = HDR.match(l)
                if m: name, cur = m.group(1), [l.strip()]
                continue
            if l.strip():
                cur.append(l.strip())
                if END.match(l): mods[name] = cur; cur = None
    return mods

TOK = re.compile(r'::=|\.\.\.|\.\.|[A-Za-z][A-Za-z0-9-]*|\d+|[^\sA-Za-z0-9]')
def tokens(lines):
    return TOK.findall('\n'.join(re.sub(r'--.*$', '', l) for l in lines))

def main():
    pdf_dir, base_dir = sys.argv[1], sys.argv[2]
    out_dir = sys.argv[3] if len(sys.argv) > 3 else 'pdf206'
    os.makedirs(out_dir, exist_ok=True)
    base = base_modules(base_dir)
    total_removed = 0
    for f in sorted(glob.glob(os.path.join(pdf_dir, '*.asn'))):
        name = os.path.basename(f)[:-4]
        lines = [l.rstrip('\n') for l in open(f, encoding='utf-8')]
        out, removed = clean(lines)
        open(os.path.join(out_dir, name + '.asn'), 'w').write('\n'.join(out) + '\n')
        total_removed += len(removed)
        for prev, r in removed:
            print(f'[removed in {name}] {r!r}    (after: {prev[-60:]!r})')
        if name in base:
            a, b = tokens(base[name]), tokens(out)
            if a != b:
                print(f'=== {name} still differs from baseline:')
                for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes():
                    if op == 'equal': continue
                    print(f'  [{op}] after: ... {" ".join(a[max(0, i1-6):i1])}')
                    if i2 > i1: print('     baseline:', ' '.join(a[i1:i2])[:4000])
                    if j2 > j1: print('     PDF     :', ' '.join(b[j1:j2])[:4000])
    print(f'\nremoved {total_removed} comment-continuation lines in total')

main()
