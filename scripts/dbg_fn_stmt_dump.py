# -*- coding: utf-8 -*-
# dbg_fn_stmt_dump.py — 指定模块逐语句 token 倒查（FN 归因调试伴随）
# 用法: python -I dbg_fn_stmt_dump.py <dec 文件> <源码 .kl> [行号筛选,逗号分隔]
import os, re, sys

SC = r'D:\Downloads\Decompile-pcode-staging\scripts'
src = open(os.path.join(SC, 'pc2kl3.py'), encoding='utf-8').read()
ns = {'re': re, 'os': os, 'sys': sys}
for fname in ('printable', 'scan'):
    m = re.search(r'^def %s\(.*?(?=^\S)' % fname, src, re.S | re.M)
    exec(compile(m.group(0), 'pc2kl3_' + fname, 'exec'), ns)
scan = ns['scan']

dec_path, src_path = sys.argv[1], sys.argv[2]
want = set(int(x) for x in sys.argv[3].split(',')) if len(sys.argv) > 3 else None

srclines = open(src_path, encoding='utf-8', errors='replace').read().splitlines()
dec = open(dec_path, 'rb').read()
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
    if end <= aoff + 5:
        continue
    body = dec[aoff + 5:end]
    if len(body) > 800:
        continue
    if want is not None and line not in want:
        continue
    toks = scan(body, aoff + 5)
    kinds = ' '.join(k if v in (None, 0) else '%s(%s)' % (k, v) for _, k, v, _ in toks)
    sl = srclines[line - 1].strip() if 0 < line <= len(srclines) else '??'
    print('%-4d |%-42s| %s' % (line, sl[:42], kinds[:400]))
