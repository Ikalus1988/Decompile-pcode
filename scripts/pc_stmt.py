# pc_stmt.py — mi04_ssw_rout 语句表 v3（行号锚点切分 + 全量词表）
#
# 词表来源：70 对罗塞塔（MM_* 30 + CJLR JLR 40）归纳+交叉验证，已解字节覆盖率 82.9%（JLR 语料）。
# v3 相对 v2 新增：比较全家 57-5c、字段/元素族 32/33/34/35/61、UNINIT 63、PURGE 3c、
#   WHEN 固定块、表单族 40/41/42、VGET af/VSET b0、REAL? 17+5B、分派表 TBL、空串 3f 00、
#   锚点全收 3e <tag 0-5> <行号> <u16>（只收 3e 00 会让句体吞进下个例程！）。
#
# Usage: python -I pc_stmt.py <dec> <out.txt>
import re, sys

dec_path, out_path = sys.argv[1], sys.argv[2]
dec = open(dec_path, 'rb').read()
N = len(dec)

def printable(b):
    return all(32 <= c < 127 or c in (9, 10, 13) for c in b)

def scan(seg, base):
    out, i = [], 0
    while i < len(seg):
        b = seg[i]
        # 语句锚点：3e <tag 0-5> <行号> <u16BE>
        if b == 0x3e and i + 4 < len(seg) and seg[i + 1] <= 5:
            out.append((base + i, 'T', f'«行{seg[i + 2]}»', 5))
            i += 5
            continue
        # 变量引用：21/22/23/73/75 + 表旗(01 共享 / ff 局部) + 00 00 00 + idx
        if b in (0x21, 0x22, 0x23, 0x73, 0x75, 0x9e, 0x9f) and i + 5 < len(seg) \
                and seg[i + 1] in (0x01, 0xff) and seg[i + 2:i + 5] == b'\x00\x00\x00':
            VN = {0x21: 'LD.i', 0x22: 'REF', 0x23: 'ST.i', 0x73: 'LD.s', 0x75: 'ST.s',
                  0x9e: 'ST.lp.TO?', 0x9f: 'ST.lp.DOWN?'}
            tbl = 'SHV' if seg[i + 1] == 0x01 else 'LOC'
            out.append((base + i, 'T', f'{VN[b]} {tbl}[{seg[i + 5]}]', 6))
            i += 6
            continue
        if b == 0x3f and i + 1 < len(seg):
            ln = seg[i + 1]
            if ln <= 0x3e and i + 2 + ln <= len(seg):
                s = seg[i + 2:i + 2 + ln]
                if printable(s) and re.match(rb'^[ -~]*$', s):
                    out.append((base + i, 'T', repr(s.decode()), 2 + ln))
                    i += 2 + ln
                    continue
        if b == 0x2e and i + 4 < len(seg):
            out.append((base + i, 'T', f'#{int.from_bytes(seg[i + 1:i + 5], "big")}', 5))
            i += 5
            continue
        if b == 0x17 and i + 5 < len(seg):
            out.append((base + i, 'T', f'P.arg({seg[i+1:i+6].hex()})', 6))
            i += 6
            continue
        if b == 0x74 and i + 5 < len(seg):
            out.append((base + i, 'T', f'P.sarg({seg[i+1:i+6].hex()})', 6))
            i += 6
            continue
        # 字段/元素族
        if b == 0x32 and i + 2 < len(seg) and seg[i + 1] == 0x00:
            out.append((base + i, 'T', f'FLD+{seg[i + 2]:#04x}', 3))
            i += 3
            continue
        if b == 0x33 and i + 3 < len(seg) and seg[i + 1] == 0x32:
            out.append((base + i, 'T', f'EIDX+{seg[i + 3]:#04x}?', 4))
            i += 4
            continue
        if b == 0x33 and i + 1 < len(seg) and seg[i + 1] in (0x34, 0x35):
            out.append((base + i, 'T', 'ELD?' if seg[i + 1] == 0x34 else 'EST?', 2))
            i += 2
            continue
        if b == 0x63 and i + 2 < len(seg):
            out.append((base + i, 'T', f'UNINIT({seg[i+1]:02x} {seg[i+2]:02x})', 3))
            i += 3
            continue
        # WHEN/CONDITION 固定描述块（JLR 实测零变体）
        if seg[i:i + 5] == b'\x12\x43\xab\x00\x03':
            out.append((base + i, 'T', 'WHEN.desc', 5))
            i += 5
            continue
        if seg[i:i + 3] == b'\x13\x05\x04':
            out.append((base + i, 'T', 'WHEN.t2', 3))
            i += 3
            continue
        if seg[i:i + 2] == b'\x81\x18':
            out.append((base + i, 'T', 'WHEN.81?', 2))
            i += 2
            continue
        if seg[i:i + 2] == b'\x1b\x01':
            out.append((base + i, 'T', 'WHEN.1b?', 2))
            i += 2
            continue
        # 表单族（dcp_form 类模块）：40/41 + u32BE，42 = 收尾
        if b in (0x40, 0x41) and i + 4 < len(seg) and seg[i + 1:i + 3] == b'\x00\x00':
            v = int.from_bytes(seg[i + 3:i + 5], 'big')
            out.append((base + i, 'T', f'F{b:02x}({v:#x})', 5))
            i += 5
            continue
        # 分派表：{u16BE 目标, u16 0} 递增连跑
        if i + 3 < len(seg):
            j, vals = i, []
            while j + 4 <= len(seg):
                v = int.from_bytes(seg[j:j + 2], 'big')
                pad = int.from_bytes(seg[j + 2:j + 4], 'big')
                if pad == 0 and (len(vals) < 2 or v > vals[-1]):
                    vals.append(v)
                    j += 4
                else:
                    break
            if len(vals) >= 3 and vals[-1] > 0:
                out.append((base + i, 'T', f'TBL[{",".join(hex(v) for v in vals)}]', j - i))
                i = j
                continue
        # 参数访问：2d/2f + ff + u32（PROBE 实证：p1=2d ff ff ff ff ff，p2=2d ff 00 00 00 00）
        if b in (0x2d, 0x2f) and i + 5 < len(seg) and seg[i + 1] == 0xff:
            op = 'PLD' if b == 0x2d else 'PST'
            out.append((base + i, 'T', f'{op}({seg[i+2:i+6].hex()})', 6))
            i += 6
            continue
        if b == 0x2a and i + 1 < len(seg):
            out.append((base + i, 'T', 'IMP?', 2))
            i += 2
            continue
        # IO 族（PROBE v2 实证）：19 <m>=读 DI、1a <m>=写 DO、0f 02=PULSE
        if b in (0x19, 0x1a) and i + 1 < len(seg):
            out.append((base + i, 'T',
                        f'{"DI.rd" if b == 0x19 else "DO.wr"}({seg[i+1]:02x})', 2))
            i += 2
            continue
        if seg[i:i + 2] == b'\x0f\x02':
            out.append((base + i, 'T', 'PULSE?', 2))
            i += 2
            continue
        if seg[i:i + 2] == b'\x1f\x02':
            out.append((base + i, 'T', 'PULSE.r?(-)', 2))
            i += 2
            continue
        # SELECT 分派族（PROBE v2 实证，推翻旧"表单族"误读）
        if b in (0x40, 0x41) and i + 4 < len(seg) and seg[i + 1:i + 3] == b'\x00\x00':
            v = int.from_bytes(seg[i + 3:i + 5], 'big')
            out.append((base + i, 'T', f'{"SEL.hdr" if b == 0x40 else "SEL.val"}({v:#x})', 5))
            i += 5
            continue
        if b == 0x76 and i + 1 < len(seg):
            out.append((base + i, 'T', f'FN#{seg[i+1]}', 2))
            i += 2
            continue
        ONE = {0x9c: '#0', 0x9d: '#1', 0x7d: 'CONCAT', 0x27: '·arg',
               0x11: 'DELAY?', 0x51: 'NEG', 0x52: 'ADD', 0x53: 'SUB', 0x54: 'MUL',
               0x55: 'DIV', 0x56: 'MOD', 0x5f: 'NOT',
               0x57: 'EQ.i', 0x58: 'NE.i', 0x59: 'LT.i', 0x5a: 'LE.i',
               0x5b: 'GT.i', 0x5c: 'GE.i', 0x83: 'EQ.s', 0x84: 'NE.s',
               0x46: 'AND', 0x47: 'OR',
               0x29: 'ITOR', 0x64: 'ITOR?', 0x69: 'ADD.r', 0x6a: 'SUB.r',
               0x6b: 'MUL.r', 0x6c: 'DIV.r',
               0x6d: 'EQ.r?', 0x6e: 'NE.r?', 0x6f: 'LT.r', 0x70: 'LE.r?',
               0x71: 'GT.r', 0x72: 'GE.r',
               0x33: 'EADDR?', 0x34: 'LD.fld', 0x35: 'ST.fld', 0x61: 'ST.fld.s',
               0x0d: 'ENB?', 0x3c: 'PURGE?', 0x42: 'SEL.end?', 0x43: 'SEL.else?',
               0x4d: 'SIG.EVENT?', 0x81: 'WHEN?',
               0x62: 'CONN.TMR', 0x28: 'DISC.TMR',
               0x10: 'PAUSE', 0x16: 'RELEASE', 0x3a: 'ABORT', 0x4e: 'RESUME', 0x4f: 'STOP'}
        if b in ONE:
            out.append((base + i, 'T', ONE[b], 1))
            i += 1
            continue
        if b in (0xaf, 0xb0) and i + 2 < len(seg):
            out.append((base + i, 'T',
                        f'{"VGET?" if b == 0xaf else "VSET?"}({seg[i+1]:02x} {seg[i+2]:02x})', 3))
            i += 3
            continue
        # END 尾声（模式定死）：7f <rid?> 00 00 2b 00 00 2c 01 00 <n> 7b
        if b == 0x7f and i + 11 < len(seg) and seg[i + 2:i + 5] == b'\x00\x00\x2b' \
                and seg[i + 5:i + 10] == b'\x00\x00\x2c\x01\x00' and seg[i + 11] == 0x7b:
            out.append((base + i, 'T', f'END.epi(rid={seg[i+1]},n={seg[i+10]})', 12))
            i += 12
            continue
        # 循环回边：20/45 + u32BE + 2c 00 00 01（TO/DOWNTO 两向）
        if b in (0x20, 0x45) and i + 8 < len(seg) and seg[i + 5:i + 9] == b'\x2c\x00\x00\x01':
            v = int.from_bytes(seg[i + 1:i + 5], 'big')
            out.append((base + i, 'T', f'LOOP.{"TO" if b == 0x20 else "DOWN"}({v:#x})', 9))
            i += 9
            continue
        # WHEN 动作框架：12 <u8> ab 00 <u8> / 13 <u8> <u8>
        if b == 0x12 and i + 4 < len(seg) and seg[i + 2:i + 4] == b'\xab\x00':
            out.append((base + i, 'T', f'ACT.hdr({seg[i+1]:02x},{seg[i+4]:02x})', 5))
            i += 5
            continue
        if b == 0x13 and i + 2 < len(seg):
            out.append((base + i, 'T', f'ACT.end({seg[i+1]:02x},{seg[i+2]:02x})', 3))
            i += 3
            continue
        if b == 0x7f and i + 4 < len(seg):
            out.append((base + i, 'T', f'END?({int.from_bytes(seg[i+1:i+5], "big"):#x})', 5))
            i += 5
            continue
        if b == 0xaa and i + 2 < len(seg) and seg[i + 1] == 0x00:
            out.append((base + i, 'T', f'CALL.local#{seg[i + 2]}', 3))
            i += 3
            continue
        if b == 0x31 and i + 2 < len(seg) and seg[i + 1] == 0x00:
            out.append((base + i, 'T', f'CALL.imp#{seg[i + 2]:#04x}', 3))
            i += 3
            continue
        if b in (0x79, 0x7a) and i + 4 < len(seg):
            tgt = int.from_bytes(seg[i + 1:i + 5], 'big')
            out.append((base + i, 'T', f'{"JZ" if b == 0x79 else "JMP"} +{tgt}', 5))
            i += 5
            continue
        out.append((base + i, 'B', f'{b:02x}', 1))
        i += 1
    return out

def render(seg, base):
    parts, run = [], []
    for off, kind, val, n in scan(seg, base):
        if kind == 'B':
            run.append(val)
        else:
            if run:
                parts.append('{' + ' '.join(run) + '}')
                run = []
            parts.append(val)
    if run:
        parts.append('{' + ' '.join(run) + '}')
    return '  '.join(parts)

# ---- 符号表原文（顺序≠SHV 序号，仅供对照） ----
syms = [(m.start(), m.group(1).decode())
        for m in re.finditer(rb'\x02([A-Za-z_][A-Za-z0-9_]{2,})\x00', dec)]

# ---- 锚点全收 ----
markers = [(m.start(), m.group(2)[0]) for m in re.finditer(rb'\x3e([\x00-\x05])(.)', dec)
           if m.start() + 5 <= N]

known = total = 0
with open(out_path, 'w', encoding='utf-8') as f:
    f.write('# mi04_ssw_rout 语句表 v3 — 行号锚点切分 + 70 对罗塞塔全量词表（JLR 覆盖率 82.9%）\n')
    f.write('# 体格式：·arg=实参前缀  CONCAT=串拼接  SHV[n]=共享变量  LOC[n]=局部变量  «行N»=锚点  {xx}=未解字节\n')
    f.write('# ⚠️ 源码行文本缺失（只存了行号）；SHV 序号=编译流首次使用序，符号表顺序≠序号（命名不可按表序推）。\n')
    f.write('# 消息规律：等 DI 类消息（Wait DI/TD Motor）尾参恒为 (#0,#1)，其余恒为 (#0,#0)。\n')
    f.write(f'# 锚点 {len(markers)} 个（含 tag 0-5 全系列）；符号表 {len(syms)} 项\n\n')
    f.write('════ 符号表原文（顺序≠SHV 序号，仅供对照）════\n')
    for i, (off, name) in enumerate(syms, 1):
        f.write(f'  #{i:2d} @{off:6d}  {name}\n')
    f.write('\n════ 语句体（按锚点偏移序）════\n')
    prev = 0
    data_bytes = 0
    for i, (off, lid) in enumerate(markers):
        end = markers[i + 1][0] if i + 1 < len(markers) else N
        body = dec[off + 5:end]
        if len(body) > 800 or off < 0x40:
            # 数据区（符号表/跳转总表/名字堆）：按数据渲染，不计未知算子
            data_bytes += len(body)
            strs_in = [s.decode() for s in re.findall(rb'[ -~]{4,}', body)]
            tbls = len(re.findall(rb'[\x00-\xff]\x00{3}', body))
            f.write(f'\n行{lid:4d} @{off:#06x}  【数据区 len={len(body)}：符号表/跳转总表/名字堆，非语句】\n')
            f.write(f'  ASCII 串 {len(strs_in)} 条：' + '  '.join(repr(s) for s in strs_in[:20]) + '\n')
            prev = lid
            continue
        if body:
            total += len(body)
            toks = scan(body, off + 5)
            known += sum(n for _, k, _, n in toks if k != 'B')
            r = render(body, off + 5)
        else:
            r = ''
        if prev and lid > prev + 1:
            f.write(f'\n  ── 行 {prev + 1}..{lid - 1} 无锚点 ──\n')
        f.write(f'\n行{lid:4d} @{off:#06x}\n  {r}\n')
        prev = lid

print('wrote', out_path, 'markers', len(markers), 'syms', len(syms))
print(f'已解字节 {known}/{total} = {known / max(total, 1):.1%}   数据区另计 {data_bytes}B')
