# -*- coding: utf-8 -*-
# dbg_meta_survey.py — 例程尾元数据块形态普查（7f 前缀 + 7b 尾）：确认无真语句混入
# 用法: python -I dbg_meta_survey.py <dec 目录>...
import re, sys, os

SC = r'D:\Downloads\Decompile-pcode-staging\scripts'
src = open(os.path.join(SC, 'pc2kl3.py'), encoding='utf-8').read()
ns = {'re': re, 'os': os, 'sys': sys}
for fname in ('printable', 'scan'):
    m = re.search(r'^def %s\(.*?(?=^\S)' % fname, src, re.S | re.M)
    exec(compile(m.group(0), 'pc2kl3_' + fname, 'exec'), ns)
scan = ns['scan']

REAL = {'VAR', 'CALLLOC', 'CALLIMP', 'FN', 'AGGREF', 'AGGARG', 'STFLD', 'EST', 'ELD',
        'WREND', 'WR', 'JZ', 'JMP', 'RET', 'RSTUB', 'STi'}
tot = hit = suspicious = 0
for d in sys.argv[1:]:
    for f in sorted(os.listdir(d)):
        if not f.lower().endswith('.dec'):
            continue
        dec = open(os.path.join(d, f), 'rb').read()
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
        for ai, (aoff, line) in enumerate(anch):
            end = anch[ai + 1][0] if ai + 1 < len(anch) else hi
            body = dec[aoff + 5:end]
            if body and body[0] == 0x7f and body[-1] == 0x7b:
                tot += 1
                try:
                    toks = scan(body, aoff + 5)
                except Exception:
                    toks = []
                kinds = {t[1] for t in toks}
                if REAL & kinds:
                    suspicious += 1
                    print('!! 疑似真语句 %s:%d len=%d toks=%s' % (
                        f, line, len(body),
                        ' '.join(k for _, k, _, _ in toks)[:90]))
                else:
                    hit += 1
print('元数据形态 %d（其中疑似真语句 %d、纯描述 %d）' % (tot, suspicious, hit))
