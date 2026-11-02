# -*- coding: utf-8 -*-
# dbg_anchor_align.py — 锚点行号 ↔ 源码行 对齐体检
# 假设: 锚点行号=编译单元(KTRANS 展开 %INCLUDE 后)源码行号。
# 体检: 锚点行落在 语句行 / 注释行 / 空行 的比例，按「有无 %INCLUDE」分组看错位来源。
import os, re, sys

SC = r'D:\Downloads\Decompile-pcode-staging\scripts'
src = open(os.path.join(SC, 'pc2kl3.py'), encoding='utf-8').read()
ns = {'re': re, 'os': os, 'sys': sys}
for fname in ('printable', 'scan'):
    m = re.search(r'^def %s\(.*?(?=^\S)' % fname, src, re.S | re.M)
    exec(compile(m.group(0), 'pc2kl3_' + fname, 'exec'), ns)
scan = ns['scan']


def expand(path, seen=None):
    seen = seen if seen is not None else set()
    if path in seen:
        return ''
    seen.add(path)
    txt = open(path, encoding='utf-8', errors='replace').read()

    def rep(mm):
        rel = mm.group(1).strip().replace('\\', '/')
        cands = [rel, rel + '.kl', rel.upper() + '.KL']
        b0 = os.path.basename(rel)
        cands += [b0, b0 + '.kl', b0.upper() + '.KL']
        for cand in cands:
            for base in (os.path.dirname(path), os.path.join(os.path.dirname(path), 'include')):
                p = os.path.join(base, cand)
                if os.path.exists(p):
                    return expand(p, seen)
        return ''
    return re.sub(r'(?mi)^\s*%INCLUDE\s+(\S+)', rep, txt)


FAMILIES = [
    ('JLR',  r'D:\Downloads\Decompile-pcode-tests\corpus\jlr16_pairs\src',
             r'D:\Downloads\Decompile-pcode-tests\corpus\jlr16_pairs\dec'),
    ('M9',   r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\work\src_v174\src',
             r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\work\pc_dec_mm'),
    ('饰板', r'D:\Downloads\_extract_karel_src\karel\src',
             r'D:\Downloads\Decompile-pcode-tests\output_shipban'),
]


def is_stmt(line):
    s = line.strip()
    return bool(s) and not s.startswith('--')


tot = {'有INCLUDE': [0, 0, 0], '无INCLUDE': [0, 0, 0]}   # stmt/comment/blank
bad = []
for label, sdir, ddir in FAMILIES:
    srcs = {re.sub(r'\.kl$', '', f, flags=re.I).lower(): os.path.join(sdir, f)
            for f in os.listdir(sdir) if f.lower().endswith('.kl')}
    decs = {}
    for f in os.listdir(ddir):
        if f.lower().endswith('.dec'):
            decs[re.sub(r'\.pc\.dec$|\.dec$', '', f, flags=re.I).lower()] = os.path.join(ddir, f)
    for stem in sorted(set(srcs) & set(decs)):
        raw = open(srcs[stem], encoding='utf-8', errors='replace').read()
        has_inc = bool(re.search(r'(?mi)^\s*%INCLUDE', raw))
        txt = expand(srcs[stem])
        lines = txt.splitlines()
        dec = open(decs[stem], 'rb').read()
        N = len(dec)
        jt = dec.find(b'\x7f\x00\x00\x00\xff')
        hi = jt if 0 < jt < N else N
        anch, prev = [], -1
        for mm in re.finditer(rb'\x3e([\x00-\x05])([\x00-\xff])', dec[0x30:hi]):
            off = 0x30 + mm.start()
            if off + 5 > hi:
                continue
            line = mm.group(1)[0] * 256 + mm.group(2)[0]
            if line < prev:
                continue
            prev = line
            anch.append((off, line))
        key = '有INCLUDE' if has_inc else '无INCLUDE'
        n_ok = 0
        for _, line in anch:
            if not (0 < line <= len(lines)):
                tot[key][2] += 1
                continue
            s = lines[line - 1].strip()
            if not s:
                tot[key][2] += 1
            elif s.startswith('--'):
                tot[key][1] += 1
            else:
                tot[key][0] += 1
                n_ok += 1
        rate = n_ok / max(1, len(anch))
        if rate < 0.8:
            bad.append((rate, label, stem, len(anch), has_inc))

for key, (a, b, c) in tot.items():
    t = a + b + c
    print('%s: 语句行 %d/%d (%.0f%%)  注释 %d  空/越界 %d' % (key, a, t, 100.0 * a / max(1, t), b, c))
print()
for rate, label, stem, n, hi_ in sorted(bad)[:20]:
    print('  %-6s %-18s 锚点%-4d 语句行率 %.0f%%  %s' % (label, stem, n, 100 * rate, 'INC' if hi_ else ''))
