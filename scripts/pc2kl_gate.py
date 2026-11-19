# pc2kl_gate.py — 反编译重建质量门（六道门）
#   G1 编译门:   KTRANS 0 error
#   G2 语义指纹门: 消息串/常量在 原始.dec ↔ 重建.pc 间一致
#   G3 结构门:   块配平/ROUTINE 块完整/无非法左值/无 ? 残留
#   G4 渲染门:   未渲染语句(注释降级)占比 ≤ 15%
#   G5 流拓扑门: REPEAT/UNTIL 配平 + 跨界嵌套签名（loop↔branch 降级专检，T_UNTIL 探针）
#   G6 名字绑定: 真名声明未引用（声明/使用断裂 lint）
# Usage: python -I pc2kl_gate.py <原始.dec> <重建.KL> <重建.pc> [report.txt]
import os, re, subprocess, sys, tempfile

dec_path, kl_path, pc_path = sys.argv[1:4]
report_path = sys.argv[4] if len(sys.argv) > 4 else kl_path + '.gate.txt'
KTRANS = r'D:\program\roboguide\WinOLPC\bin\ktrans.exe'
DECSCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'scripts', 'pc_decompress.mjs')
DECSCRIPT = os.path.normpath(DECSCRIPT)

results = []

def gate(name, ok, detail):
    results.append((name, ok, detail))
    return ok

dec = open(dec_path, 'rb').read()
kl = open(kl_path, encoding='gbk', errors='replace').read()
kl_lines = kl.splitlines()

# G1 编译门
g1_ok, g1_detail = False, ''
try:
    with tempfile.TemporaryDirectory() as td:
        out_pc = os.path.join(td, 'out.pc')
        r = subprocess.run([KTRANS, kl_path, out_pc], capture_output=True, text=True, timeout=120)
        txt = r.stdout + r.stderr
        errs = len(re.findall(r'ERROR', txt))
        warns = len(re.findall(r'WARNING', txt))
        g1_ok = 'Translation successful' in txt and errs == 0
        m = re.search(r'(\d+) bytes of p-code', txt)
        g1_detail = f'errors={errs} warnings={warns} p-code={m.group(1) if m else "?"}B'
except Exception as e:
    g1_detail = f'ktrans 异常: {e}'
gate('G1 编译', g1_ok, g1_detail)

# G2 语义指纹门
g2_hits, g2_total = 0, 0
g2_detail = ''
try:
    pc_bytes = b''
    if os.path.exists(pc_path):
        with tempfile.TemporaryDirectory() as td:
            subprocess.run(['node', DECSCRIPT, td, pc_path], capture_output=True, timeout=60)
            outs = os.listdir(td)
            if outs:
                pc_bytes = open(os.path.join(td, outs[0]), 'rb').read()
    # 指纹口径 = 3f 推串（程序真实引用的字面串）+ 2e 推整；只取语句体区间
    # （锚点分区 ≤800B，与 pc2kl3 词法覆盖对齐——分派表/名字堆等数据区的 2e 00 00 假常量不计）
    N_DEC = len(dec)
    _markers = [(m.start(), m.group(2)[0]) for m in re.finditer(rb'\x3e([\x00-\x05])(.)', dec) if m.start() + 5 <= N_DEC]
    _bodies = []
    for _i, (_off, _lid) in enumerate(_markers):
        _end = _markers[_i + 1][0] if _i + 1 < len(_markers) else N_DEC
        _body = dec[_off + 5:_end]
        if len(_body) > 800 or _off < 0x30:
            continue
        _bodies.append(_body)
    _code = b''.join(_bodies) if _bodies else dec
    key = []
    for m in re.finditer(rb'\x3f([\x00-\xff])', _code):
        ln = m.group(1)[0]
        s = _code[m.end():m.end() + ln]
        if len(s) == ln and re.match(rb'^[ -~]*$', s) and re.search(rb'[A-Za-z]{3}', s):
            key.append(s.decode())
    key = sorted(set(key))
    consts = set()
    for m in re.finditer(rb'\x2e\x00\x00(.{2})', _code):
        v = int.from_bytes(m.group(1), 'big')
        i = m.start()
        # 分派表伪影过滤：候选落在 {XX 00 00 YY} 步进单元连跑里（前后单元同构）→ 非真 INT 推送
        u_prev = _code[i - 4:i]
        u_next = _code[i + 4:i + 8]
        in_table = (len(u_prev) == 4 and u_prev[1:3] == b'\x00\x00'
                    and len(u_next) == 4 and u_next[1:3] == b'\x00\x00')
        if 1000 <= v <= 99999 and not in_table:
            consts.add(v)
    for s in key:
        g2_total += 1
        if s in kl and (not pc_bytes or s.encode() in pc_bytes):
            g2_hits += 1
    ck = sum(1 for v in consts if v.to_bytes(4, 'big') in dec and (str(v) in kl or (pc_bytes and v.to_bytes(4, 'big') in pc_bytes)))
    g2_detail = f'串命中 {g2_hits}/{g2_total}  常量命中 {ck}/{len(consts)}  (基线门: 串≥70% 常≥60%)'
    str_ok = g2_total == 0 or g2_hits / g2_total >= 0.70
    con_ok = len(consts) == 0 or ck / len(consts) >= 0.60
    g2_ok = str_ok and con_ok
except Exception as e:
    g2_ok, g2_detail = False, f'异常: {e}'
gate('G2 语义指纹', g2_ok, g2_detail)

# G3 结构门
# 先拼接续行：长条件按顶层运算符断行（KTRANS 256 上限，probe_linelen 实测），
# 逐行匹配会把 IF 计漏（ISV_VG 实证：IF/ENDIF 文件级 114/114 配平，G3 却报 -1）
_g3_lines = []
for _l in kl_lines:
    if _g3_lines and re.search(r'( AND | OR |, | \+ )\s*$', _g3_lines[-1]):
        _g3_lines[-1] = _g3_lines[-1].rstrip() + ' ' + _l.strip()
    else:
        _g3_lines.append(_l)
g3_problems = []
opens = {'IF': 0, 'WHILE': 0, 'FOR': 0}
for l in _g3_lines:
    t = l.strip()
    if re.match(r'^IF .* THEN$', t):
        opens['IF'] += 1
    elif t == 'ENDIF':
        opens['IF'] -= 1
    elif re.match(r'^WHILE .* DO$', t):
        opens['WHILE'] += 1
    elif t == 'ENDWHILE':
        opens['WHILE'] -= 1
    elif re.match(r'^FOR .* DO$', t):
        opens['FOR'] += 1
    elif t == 'ENDFOR':
        opens['FOR'] -= 1
    if re.match(r'^\s+0\s*=', l) or re.match(r'^\s+\'\'\s*=', l):
        g3_problems.append('非法左值: ' + t[:40])
    code_part = re.sub(r"'[^']*'", '', t)
    if '?' in code_part and not t.startswith('--'):
        g3_problems.append('未知占位: ' + t[:40])
for k, v in opens.items():
    if v != 0:
        g3_problems.append(f'{k} 块不配平: {v}')
routines = [m.group(1) for m in re.finditer(r'^ROUTINE (\w+)(\(.*\))? ?(: [A-Z]+(\[\d+\])?)?$', kl, re.M) if 'FROM' not in m.group(0)]
ends = re.findall(r'^END (\w+)', kl, re.M)
if sorted(routines + [re.search(r'PROGRAM (\w+)', kl).group(1)]) != sorted(ends):
    g3_problems.append('ROUTINE/END 名称不匹配')
g3_ok = not g3_problems
gate('G3 结构', g3_ok, '通过' if g3_ok else '; '.join(g3_problems[:5]))

# G4 渲染门
body_lines = [l for l in kl_lines if l.strip() and not l.strip().startswith('--') and not re.match(r'^(PROGRAM|VAR|BEGIN|END|ROUTINE|%|\s*--)', l.strip())]
fallback = [l for l in kl_lines if re.match(r'^\s*-- L\d+', l)]
total_stmt = len(body_lines) + len(fallback)
ratio = len(fallback) / max(total_stmt, 1)
g4_ok = ratio <= 0.15
gate('G4 渲染覆盖', g4_ok, f'未渲染 {len(fallback)}/{total_stmt} = {ratio:.1%} (阈值15%)')

# G5 控制流拓扑门（T_UNTIL 探针落锤：loop↔branch 降级四门全盲区，须专检）
# ① REPEAT/UNTIL 配平；② 跨界嵌套签名「CASE/ELSE: 标签行紧跟 UNTIL(」= 循环跨子句
#    （MI04_SSW_ROUT CHECKCAPVAL 实证，KTRANS 拒编）——正确形态是 UNTIL 先于下个标签。
_code_lines = [re.sub(r'--.*$', '', l) for l in _g3_lines]
g5_problems = []
_n_repeat = sum(1 for l in _code_lines if re.match(r'^\s*REPEAT\s*$', l))
_n_until = sum(1 for l in _code_lines if re.match(r'^\s*UNTIL\(', l))
if _n_repeat != _n_until:
    g5_problems.append(f'REPEAT/UNTIL 不配平: {_n_repeat}/{_n_until}')
for _i5, _l5 in enumerate(_code_lines):
    if re.match(r'^\s*(CASE\([^)]*\):|ELSE:)\s*$', _l5):
        for _l6 in _code_lines[_i5 + 1:_i5 + 2]:
            if re.match(r'^\s*UNTIL\(', _l6):
                g5_problems.append(f'跨界嵌套: 行{_i5+1} 标签后紧跟 UNTIL')
g5_ok = not g5_problems
gate('G5 流拓扑', g5_ok, '通过' if g5_ok else '; '.join(g5_problems[:5]))

# G6 名字绑定 lint（declared-but-unused 真名=声明与使用断裂，T_UNTIL B_1OOPOUT 实证）
# 仅扫 VAR 块声明（TYPE 结构体字段不计——X/Y/Z/W/P/R 族实证误报 69 处）；
# 语义为 lint：有命中记警告，不阻断（真名经字符串形参引用等合法形态存在），
# 严格清点走 tests/loop_census.py 的 lint 通道。
_g6_warn = []
_decl_re = re.compile(r'^\s*([A-Za-z_]\w*)\s*:\s*(?:ARRAY|BOOLEAN|INTEGER|REAL|STRING|POSITION|JOINTPOS|FILE)')
_synth_re = re.compile(r'^(?:v\d+|r\d+_lc\d+|sv_[a-z]|p\d+_f[0-9a-f]+|p\d+$|pp[0-9a-f]{2}|fn\d+x?|rtn\d+x?|imp\d+x?|l\d+_\w+)')
_body_txt = '\n'.join(_code_lines)
_in_type = False
for _l5 in kl_lines:
    _t5 = _l5.strip()
    if _t5.startswith('TYPE'):
        _in_type = True
    if _t5.startswith('VAR') or _t5.startswith('ROUTINE') or _t5 == 'BEGIN':
        _in_type = False
    if _in_type:
        continue
    _m5 = re.match(r'^\s*([A-Za-z_]\w*)\s*:\s*BOOLEAN', _l5)   # 口径=BOOLEAN 真名（共享 VAR 膨胀实证淹没泛口径）
    if _m5 and not _synth_re.match(_m5.group(1)):
        _nm5 = _m5.group(1)
        _uses = len(re.findall(r'\b' + re.escape(_nm5) + r'\b', _body_txt))
        if _uses <= 1:
            _g6_warn.append(_nm5)
gate('G6 名字绑定', True, '通过' if not _g6_warn else f'警告 {len(_g6_warn)} 处真名声明未用: {", ".join(_g6_warn[:5])}')

# 报告
with open(report_path, 'w', encoding='utf-8') as f:
    f.write('# pc2kl 质量门报告\n')
    f.write(f'# KL: {kl_path}\n\n')
    allok = True
    for name, ok, detail in results:
        allok = allok and ok
        f.write(f'  [{"PASS" if ok else "FAIL"}] {name:12s}  {detail}\n')
    f.write(f'\n总判定: {"PASS" if allok else "FAIL"}\n')
print('总判定:', 'PASS' if allok else 'FAIL')
for name, ok, detail in results:
    print(f'  [{"PASS" if ok else "FAIL"}] {name}: {detail}')
print('报告:', report_path)
sys.exit(0 if allok else 1)
