# -*- coding: utf-8 -*-
# dbg_body_find.py — 按 token 形态找语句体并十六进制倒出（无源码模块用）
# 用法: python -I dbg_body_find.py <dec> <kind1,kind2,...> [max_hits]
import re, sys

SC = r'D:\Downloads\Decompile-pcode-staging\scripts'
src = open(SC + r'\pc2kl3.py', encoding='utf-8').read()
ns = {'re': re, 'os': __import__('os'), 'sys': sys}
for fname in ('printable', 'scan'):
    m = re.search(r'^def %s\(.*?(?=^\S)' % fname, src, re.S | re.M)
    exec(compile(m.group(0), 'pc2kl3_' + fname, 'exec'), ns)
scan = ns['scan']

dec = open(sys.argv[1], 'rb').read()
want = set(sys.argv[2].split(','))
max_hits = int(sys.argv[3]) if len(sys.argv) > 3 else 6
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
hits = 0
for ai, (aoff, line) in enumerate(anch):
    end = anch[ai + 1][0] if ai + 1 < len(anch) else hi
    if end <= aoff + 5:
        continue
    body = dec[aoff + 5:end]
    if len(body) > 300:
        continue
    toks = scan(body, aoff + 5)
    kinds = {t[1] for t in toks}
    if want & kinds:
        print('line %d off %04x len %d  toks: %s' % (
            line, aoff, len(body),
            ' '.join(k if v in (None, 0) else '%s(%s)' % (k, v) for _, k, v, _ in toks)[:150]))
        print('   ', body[:64].hex(' '))
        hits += 1
        if hits >= max_hits:
            break
