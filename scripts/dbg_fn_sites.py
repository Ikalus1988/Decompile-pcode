# -*- coding: utf-8 -*-
# dbg_fn_sites.py — FN 站点逐条手验（fn_census 的调试伴随）
# 打印指定 id 的 (锚点行号, 源码行, 前后 token 形态)
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
        base0 = os.path.basename(rel)
        cands += [base0, base0 + '.kl', base0.upper() + '.KL']
        for cand in cands:
            for base in (os.path.dirname(path), os.path.join(os.path.dirname(path), 'include')):
                p = os.path.join(base, cand)
                if os.path.exists(p):
                    return expand(p, seen)
        return ''
    return re.sub(r'(?mi)^\s*%INCLUDE\s+(\S+)', rep, txt)


MODULES = [
    ('xyz_pkt', r'D:\Downloads\_extract_karel_src\karel\src\xyz_pkt.kl',
     r'D:\Downloads\Decompile-pcode-tests\output_shipban\XYZ_PKT.PC.dec'),
    ('dcpclear', r'D:\Downloads\Decompile-pcode-tests\corpus\jlr16_pairs\src\dcpclear.kl',
     r'D:\Downloads\Decompile-pcode-tests\corpus\jlr16_pairs\dec\dcpclear.pc.dec'),
    ('xyz_bkgd', r'D:\Downloads\_extract_karel_src\karel\src\xyz_bkgd.kl',
     r'D:\Downloads\Decompile-pcode-tests\output_shipban\XYZ_BKGD.PC.dec'),
    ('xyz_abt_bkgd', r'D:\Downloads\_extract_karel_src\karel\src\xyz_abt_bkgd.kl',
     r'D:\Downloads\Decompile-pcode-tests\output_shipban\XYZ_ABT_BKGD.PC.dec'),
]
WANT = set(int(x) for x in (sys.argv[1:] or ['4', '14', '15', '20', '21']))

for stem, sf, df in MODULES:
    if not (os.path.exists(sf) and os.path.exists(df)):
        print('skip', stem)
        continue
    txt = expand(sf)
    lines = txt.splitlines()
    dec = open(df, 'rb').read()
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
    print('===== %s  anchors=%d  srclines=%d' % (stem, len(anch), len(lines)))
    for ai, (aoff, line) in enumerate(anch):
        end = anch[ai + 1][0] if ai + 1 < len(anch) else hi
        if end <= aoff + 5:
            continue
        body = dec[aoff + 5:end]
        if len(body) > 800:
            continue
        toks = scan(body, aoff + 5)
        fns = [t for t in toks if t[1] == 'FN']
        if not fns:
            continue
        sl = lines[line - 1] if 0 < line <= len(lines) else '??'
        for t in fns:
            if t[2] in WANT:
                kinds = ' '.join(k for _, k, _, _ in toks[:14])
                print('fn%-3d %s:%-4d |%s|' % (t[2], stem, line, sl.strip()[:76]))
                print('        toks: %s' % kinds[:100])
