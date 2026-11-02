# -*- coding: utf-8 -*-
# dbg_hexdump_stmt.py — 指定锚点行的语句体原始十六进制（词表攻坚用）
# 用法: python -I dbg_hexdump_stmt.py <dec> <行号,逗号分隔>
import re, sys

dec = open(sys.argv[1], 'rb').read()
want = set(int(x) for x in sys.argv[2].split(','))
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
    if line not in want:
        continue
    end = anch[ai + 1][0] if ai + 1 < len(anch) else hi
    body = dec[aoff + 5:end]
    print('line %d  off %04x  body(%d):' % (line, aoff, len(body)))
    for i in range(0, min(len(body), 96), 16):
        print('   ', body[i:i + 16].hex(' '))
