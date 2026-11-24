# -*- coding: utf-8 -*-
# dbg_render_find.py — 逐语句体求值，抓渲染文本包含指定子串的现场
# 用法: python -I dbg_render_find.py <dec> <子串> [max]
import re, sys, os

SC = r'D:\Downloads\Decompile-pcode-staging\scripts'
src = open(os.path.join(SC, 'pc2kl3.py'), encoding='utf-8').read()
ns = {'re': re, 'os': os, 'sys': sys, 'json': __import__('json')}
# 抽取 eval_expr 依赖的函数与全局
for fname in ('printable', 'scan', 'boolish', 'is_str', 'str_rhs', 'looks_real', 'arg_kind',
              'vtype', '_is_par', '_reg_par', '_pnm', 'fmt_params', 'fmt_ptypes', '_ptype_name',
              '_pk', '_alloc_slots', '_build_pmap', '_ret_kind', 'returns_str', 'emit_assign',
              '_tmark', '_thas', '_is_local', 'vn', '_wild', '_covered'):
    m = re.search(r'^def %s\(.*?(?=^\S|\Z)' % re.escape(fname), src, re.S | re.M)
    if m:
        try:
            exec(compile(m.group(0), 'pc2kl3_' + fname, 'exec'), ns)
        except Exception:
            pass
# 模块级数据（顺序近似）
exec(compile('import re, os, sys, json', 'x', 'exec'), ns)
m = re.search(r'^_NAME_MAP = \{\}.*?^str_vars = set\(\).*?^bool_arr_vars = set\(\).*?\n', src, re.S | re.M)
print('manual-mode: 仅用 scan 输出 token 形态', file=sys.stderr)

dec = open(sys.argv[1], 'rb').read()
needle = sys.argv[2]
max_hits = int(sys.argv[3]) if len(sys.argv) > 3 else 5
m2 = re.search(r'^def scan\(.*?(?=^\S)', src, re.S | re.M)
exec(compile(m2.group(0), 'pc2kl3_scan', 'exec'), ns)
scan = ns['scan']
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
    if len(body) > 300:
        continue
    toks = scan(body, aoff + 5)
    kinds = ' '.join(k if v in (None, 0) else '%s(%s)' % (k, v) for _, k, v, _ in toks)
    if needle in kinds or needle in body.decode('latin1'):
        print('line %d off %04x len %d' % (line, aoff, len(body)))
        print('  toks:', kinds[:220])
        print('  hex :', body[:72].hex(' '))
        max_hits -= 1
        if max_hits <= 0:
            break
