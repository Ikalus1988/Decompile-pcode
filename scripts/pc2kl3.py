# pc2kl3.py — .pc → 可编译 .kl（v3：例程切段 + 签名形参 + 类型推断 + 外部声明）
# Usage: python -I pc2kl3.py <dec> <out.kl>
import os, re, sys

dec_path, out_path = sys.argv[1], sys.argv[2]
dec = open(dec_path, 'rb').read()
N = len(dec)

def printable(b):
    return all(32 <= c < 127 or c in (9, 10, 13) for c in b)

def scan(seg, base):
    out, i = [], 0
    while i < len(seg):
        b = seg[i]
        if b == 0x3e and i + 4 < len(seg) and seg[i + 1] <= 5:
            out.append((base + i, 'ANCHOR', seg[i + 2], 5)); i += 5; continue
        if b in (0x21, 0x22, 0x23, 0x73, 0x75, 0x9e, 0x9f) and i + 5 < len(seg) \
                and seg[i + 1] in (0x01, 0xff) and seg[i + 2:i + 4] == b'\x00\x00':
            # PROBE5 实证：op <01共享|ff局部> <00 00> <u16BE 槽号>（槽号可 >255，见 yamazumi 514）
            VN = {0x21: 'LDi', 0x22: 'REF', 0x23: 'STi', 0x73: 'LDs', 0x75: 'STs', 0x9e: 'STlpT', 0x9f: 'STlpD'}
            out.append((base + i, 'VAR', (VN[b], 'v' if seg[i+1] == 0x01 else 'l',
                                          int.from_bytes(seg[i + 4:i + 6], 'big')), 6)); i += 6; continue
        if b == 0x3f and i + 1 < len(seg):
            ln = seg[i + 1]
            if i + 2 + ln <= len(seg):
                s = seg[i + 2:i + 2 + ln]
                if printable(s) and re.match(rb'^[ -~]*$', s):
                    # 长度不设 62 上限（JLR dcp_tucker 64+ 字符串实证：旧上限把长串扫成假代码）
                    out.append((base + i, 'STR', s.decode(), 2 + ln)); i += 2 + ln; continue
        if b == 0x2e and i + 4 < len(seg):
            out.append((base + i, 'INT', int.from_bytes(seg[i+1:i+5], 'big'), 5)); i += 5; continue
        # 参数族（PROBE5 实证）：17/74=引用 2d=读 2f=写整 a2=写串 a1=读串；槽号=i32BE（负小数）
        if b in (0x17, 0x74) and i + 5 < len(seg):
            out.append((base + i, 'PREF', 'pp' + seg[i+1:i+6].hex()[-2:], 6)); i += 6; continue
        if b == 0x2d and i + 5 < len(seg) and seg[i + 1] == 0xff:
            out.append((base + i, 'PLD', 'pp' + seg[i+2:i+6].hex()[-2:], 6)); i += 6; continue
        if b == 0x2f and i + 5 < len(seg) and seg[i + 1] == 0xff:
            out.append((base + i, 'PST', 'pp' + seg[i+2:i+6].hex()[-2:], 6)); i += 6; continue
        if b == 0xa1 and i + 5 < len(seg) and seg[i + 1] == 0xff:
            out.append((base + i, 'PLDSTR', 'pp' + seg[i+2:i+6].hex()[-2:], 6)); i += 6; continue
        if b == 0xa2 and i + 5 < len(seg) and seg[i + 1] == 0xff:
            out.append((base + i, 'PSTSTR', 'pp' + seg[i+2:i+6].hex()[-2:], 6)); i += 6; continue
        if b == 0x32 and i + 2 < len(seg) and seg[i + 1] == 0x00:
            out.append((base + i, 'FLD', seg[i+2], 3)); i += 3; continue
        # 0x33=EADDR 单字节（PROBE5 + dcpclear 实证）：33 32=元素+字段两操作码，勿复合吞偏移
        if b == 0x63 and i + 2 < len(seg):
            out.append((base + i, 'UNINIT', None, 3)); i += 3; continue
        if seg[i:i+5] == b'\x12\x43\xab\x00\x03' or seg[i:i+3] == b'\x13\x05\x04' \
                or seg[i:i+2] in (b'\x81\x18', b'\x1b\x01'):
            n2 = 5 if seg[i:i+5] == b'\x12\x43\xab\x00\x03' else (3 if seg[i:i+3] == b'\x13\x05\x04' else 2)
            out.append((base + i, 'NOP', None, n2)); i += n2; continue
        if b in (0x40, 0x41) and i + 4 < len(seg) and seg[i+1:i+3] == b'\x00\x00':
            out.append((base + i, 'SEL', None, 5)); i += 5; continue
        if b in (0xaf, 0xb0) and i + 2 < len(seg):
            # PROBE T44-45 落锤：b0=SET_VAR、af=GET_VAR（`b0 1f 00` / `af 1f 10`）
            out.append((base + i, 'VSET' if b == 0xb0 else 'VGET', None, 3)); i += 3; continue
        if b == 0x7f and i + 4 < len(seg):
            out.append((base + i, 'RET', None, 5)); i += 5; continue
        if b in (0x20, 0x45) and i + 8 < len(seg) and seg[i+5:i+9] == b'\x2c\x00\x00\x01':
            out.append((base + i, 'LOOPBACK', None, 9)); i += 9; continue
        if b in (0x12, 0x13) and i + 2 < len(seg):
            n3 = 3 if b == 0x13 else 5
            out.append((base + i, 'NOP', None, n3)); i += n3; continue
        if seg[i:i+2] in (b'\x0f\x02', b'\x1f\x02'):
            out.append((base + i, 'PULSE', None, 2)); i += 2; continue
        if b == 0x76 and i + 1 < len(seg):
            out.append((base + i, 'FN', seg[i+1], 2)); i += 2; continue
        if b == 0xaa and i + 2 < len(seg) and seg[i+1] == 0x00:
            out.append((base + i, 'CALLLOC', seg[i+2], 3)); i += 3; continue
        if b == 0x31 and i + 2 < len(seg) and seg[i+1] == 0x00:
            out.append((base + i, 'CALLIMP', seg[i+2], 3)); i += 3; continue
        if b == 0x2a and i + 1 < len(seg):
            out.append((base + i, 'NOP', None, 2)); i += 2; continue
        # WRITE 语句族（ad 开头 + 37 描述符 + 2c 01 ff ff 收尾，罗塞塔 JLR 实证）
        if seg[i:i+4] == b'\x2c\x01\xff\xff':
            out.append((base + i, 'WREND', None, 4)); i += 4; continue
        if b == 0xad:
            out.append((base + i, 'WR', None, 1)); i += 1; continue
        if b == 0x3d:
            out.append((base + i, 'OPENF', None, 1)); i += 1; continue
        if seg[i:i+3] == b'\x37\x1f\x00':
            out.append((base + i, 'WIT_STR', None, 3)); i += 3; continue
        if seg[i:i+3] == b'\x37\x00\x10':
            out.append((base + i, 'WIT_INT', None, 3)); i += 3; continue
        if seg[i:i+3] == b'\x37\x00\xd6':
            out.append((base + i, 'WIT_CR', None, 3)); i += 3; continue
        if b in (0x79, 0x7a) and i + 4 < len(seg):
            out.append((base + i, 'JZ' if b == 0x79 else 'JMP', int.from_bytes(seg[i+1:i+5], 'big'), 5)); i += 5; continue
        if b in (0x19, 0x1a) and i + 1 < len(seg):
            out.append((base + i, 'IORD' if b == 0x19 else 'IOWR', seg[i+1], 2)); i += 2; continue
        ONE = {0x9c: ('INT', 0), 0x9d: ('INT', 1), 0x7d: ('CAT', None), 0x27: ('ARG', None),
               0x11: ('DELAY', None), 0x51: ('NEG', None), 0x52: ('ADD', None), 0x53: ('SUB', None),
               0x54: ('MUL', None), 0x55: ('DIV', None), 0x56: ('MOD', None), 0x5f: ('NOT', None),
               0x57: ('EQ', None), 0x58: ('NE', None), 0x59: ('LT', None), 0x5a: ('LE', None),
               0x5b: ('GT', None), 0x5c: ('GE', None), 0x83: ('EQ', None), 0x84: ('NE', None),
               0x46: ('AND', None), 0x47: ('OR', None), 0x29: ('ITOR', None), 0x64: ('ITOR', None),
               0x69: ('ADDR', None), 0x6a: ('SUBR', None), 0x6b: ('MULR', None), 0x6c: ('DIVR', None),
               0x6d: ('EQ', None), 0x6e: ('NE', None), 0x6f: ('LT', None), 0x70: ('LE', None),
               0x71: ('GT', None), 0x72: ('GE', None),
               0x34: ('LDFLD', None), 0x35: ('STFLD', None), 0x61: ('STFLD', None),
               0x0d: ('ENABLE', None), 0x3c: ('PURGE', None), 0x42: ('NOP', None), 0x43: ('NOP', None),
               0x4d: ('SIGEVENT', None), 0x62: ('CONNTMR', None), 0x28: ('DISCTMR', None),
               0x10: ('PAUSE', None), 0x16: ('RELEASE', None), 0x3a: ('ABORT', None),
               0x4e: ('RESUME', None), 0x4f: ('STOP', None), 0x33: ('EADDR', None)}
        if b in ONE:
            k, v = ONE[b]
            out.append((base + i, k, v, 1)); i += 1; continue
        out.append((base + i, 'UNK', b, 1)); i += 1
    return out


def _stdlib_sigs():
    """KTRANS 支持库(core.ev)权威签名：NAME\x00 ff ff <argc u8> <ret u16BE> <参数 NAME\x00 3B类型>
    ret 0000=VOID/0010=INTEGER/1fxx=STRING；参数 (00,10)=int (1f,..)=str (00,1d)=file (00,11)=real"""
    def _cls(bs):
        t = bs[:2]
        if t[0] in (0x20, 0x3f):
            # 数组 desc 5B：20 <元素型> 00 00 00 / 3f 通配（必须先于元素型判定）
            if t[0] == 0x3f:
                return 'ag'
            if len(bs) > 1 and bs[1] == 0x1f:
                return 'as'
            if len(bs) > 1 and bs[1] == 0x12:
                return 'ab'
            return 'ai'
        if t[0] == 0x1f or (len(t) > 1 and t[1] == 0x1f):
            return 's'
        if 0x1d in t:
            return 'f'
        if 0x11 in t:
            return 'r'
        if 0x12 in t:
            return 'b'
        if t == b'\x01\x02':
            return 'pos'
        if t == b'\x01\x03':
            return 'jpos'
        return 'i'
    sigs = {}
    try:
        import glob as _g
        for _p in _g.glob('D:/program/roboguide/WinOLPC/Versions/*/support/*.ev'):
            _d = open(_p, 'rb').read()
            for _m in re.finditer(rb'([A-Za-z_][A-Za-z0-9_]{2,})\x00\xff\xff', _d):
                _nm = _m.group(1).decode().upper()
                _j = _m.end()
                if _j + 3 > len(_d):
                    continue
                _argc = _d[_j]
                if _argc > 24:
                    continue
                _retb = _d[_j + 1:_j + 3]
                _ret = 'v' if _retb == b'\x00\x00' else ('s' if 0x1f in _retb else 'i')
                _k = _j + 3
                _pt = []
                for _ in range(min(_argc, 16)):
                    _mm = re.match(rb'[A-Za-z_][A-Za-z0-9_]*\x00...', _d[_k:], re.S)
                    if not _mm:
                        break
                    _ne = _k + _mm.end()
                    _desc = _d[_ne - 3:_ne]
                    if _desc[0] in (0x20, 0x3f) and _ne + 2 <= len(_d):
                        _desc = _d[_ne - 3:_ne + 2]
                    _pt.append(_cls(_desc))
                    _k += (len(_mm.group(0)) - 3) + len(_desc)
                sigs[_nm] = (_ret, _pt, _argc)  # 后版本覆盖旧版（V640 串型=0x08 vs V720+=1f）
    except Exception:
        pass
    return sigs
STD_SIGS = _stdlib_sigs()
def _basic_set():
    try:
        _p = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'stdlib_basic.txt')
        return {x.strip().upper() for x in open(_p, encoding='utf-8') if x.strip()}
    except Exception:
        return set(STD_SIGS)
STDLIB = _basic_set()
# 基础集 REGOPE 签名与 V940 ev 不一致——以 KTRANS 裸调用探针为准（argc, ret）
REGOPE_BASIC = {'CNV_INT_STR': (4, 'v'), 'GET_REG': (5, 'v'), 'POS_REG_TYPE': (5, 'v'),
                'SET_INT_REG': (3, 'v'), 'SET_REAL_REG': (3, 'v'), 'SET_STR_REG': (3, 'v'),
                'CALL_PROG': (2, 'v'), 'SET_EPOS_REG': (3, 'v'), 'SET_JPOS_REG': (3, 'v'),
                'SET_POS_REG': (3, 'v'), 'GET_POS_REG': (2, 'pos'), 'GET_JPOS_REG': (2, 'jpos'),
                'DB_PROMPT': (4, 'i')}  # 元数=JLR/M9 真源码 + KTRANS 探针双证
for _nm, (_ac, _rt) in REGOPE_BASIC.items():
    _old = STD_SIGS.get(_nm)
    _pt = list(_old[1])[:_ac] if _old else []
    _pt += ['i'] * (_ac - len(_pt))
    STD_SIGS[_nm] = (_rt, _pt, _ac)
STD_SIGS['CNV_INT_STR'] = ('v', ['i', 'i', 'i', 's'], 4)  # TARGET=STRING（ev 走查断链兜底）

# STDLIB 已由 STD_SIGS 提供

_NAME_ANCHOR = -1
routines, imports, call_names = [], {}, {}
# 名字表锚点：通用 = <单字母前缀><程序名>\0（'VMI0' 只是 V 前缀撞名特例，123/125 模块踩空）
_prog = dec[4:20].split(b'\x00')[0]
i = -1  # VMI0 特例已废（=例程数低位+'MI0' 撞名，锚点差 1 字节）
if _prog:
    for m in re.finditer(re.escape(_prog) + rb'\x00', dec):
        tail = dec[m.end():m.end() + 3]
        if (tail[:1] == b'\x00' and tail[1:3] != b'\xff\xff') or re.match(rb'[\x01-\x0f]\xff\xff', tail):
            i = m.start()
if i >= 0:
    _NAME_ANCHOR = i
    seg = dec[i:]
    ents = [(m.start(), m.group(1).decode()) for m in re.finditer(rb'([A-Za-z_][A-Za-z0-9_]{2,})\x00', seg)]
    for ei, (off, nm) in enumerate(ents):
        call_names[ei] = nm
        if ei == 0:
            continue
        desc = seg[off + len(nm.encode()) + 1:]
        if desc[:1] == b'\x00' and len(desc) >= 6 and desc[1:3] != b'\xff\xff':
            routines.append({'name': nm, 'entry': int.from_bytes(desc[1:3], 'big'), 'argc': desc[5] if desc[5] <= 24 else 0, 'ei': ei})
        elif re.match(rb'[\x01-\x0f]\xff\xff', desc):
            imports[nm] = desc[3] if len(desc) > 3 else 0x10
_prog_s = _prog.decode(errors='replace').upper()
routines = [r for r in routines
            if not (r['name'].upper() == _prog_s
                    or (len(r['name']) == len(_prog_s) + 1 and r['name'][1:].upper() == _prog_s))]

# ---- 符号表 + $GROUP 槽位映射（PROBE6 落锤）：程序级变量真名/真类型复原 ----
def _parse_symtable(dec):
    syms = []  # (name, t0, t1, dim)
    gpos = dec.find(b'\xff$GROUP\x00\xfd')
    spos = dec.find(b'$ORNT_MROT')
    if gpos < 0 or spos < 0:
        return syms
    k = spos
    # 跳过 $ORNT_MROT 系统变量条目本身 + 条目区头 00 <count>
    k += len(b'$ORNT_MROT') + 1 + 3
    if k + 2 <= gpos and dec[k] == 0x00:
        k += 2
    while k < gpos:
        if dec[k:k+1] == b'\xff':
            break
        k += 1  # scope 字节
        m = re.match(rb'([A-Za-z_][A-Za-z0-9_]{1,})\x00', dec[k:gpos])
        if not m:
            break
        nm = m.group(1).decode()
        k += m.end()
        if k + 3 > gpos:
            break
        flags, t0, t1 = dec[k], dec[k+1], dec[k+2]
        k += 3
        dim = None
        if t0 in (0x20, 0x3f) and k + 2 <= gpos:
            dim = int.from_bytes(dec[k:k+2], 'big')
            k += 2
        syms.append((nm, t0, t1, dim))
    return syms

def _parse_symmap(dec, nsyms):
    # name-table 锚点前：<u16 例程数><u16 ×nsyms 映射>
    out = []
    try:
        if _NAME_ANCHOR < 0:
            return out
        rc = int.from_bytes(dec[_NAME_ANCHOR-2:_NAME_ANCHOR], 'big')
        if not (0 < rc < 400):
            return out
        # 自验证切片：从 $GROUP 标记后取 u16 流，找恰为 0..nsyms-1 排列的切片
        g = dec.find(b'\xff$GROUP\x00\xfd')
        if g < 0:
            return out
        seg = dec[g + 9:_NAME_ANCHOR - 2]
        vals = [int.from_bytes(seg[2*k:2*k+2], 'big') for k in range(len(seg)//2)]
        body = vals[1:]  # 跳 0x31xx 标记
        cand = body[3:]  # 跳 3 个头 u16
        if cand and len(set(cand)) == len(cand) and max(cand) < nsyms:
            return cand  # 槽 k+1 → 符号 cand[k]
        return out
    except Exception:
        pass
    return out

_SYMS = _parse_symtable(dec)
_SYMMAP = _parse_symmap(dec, len(_SYMS))
# 槽号 k(1起) → 符号名（映射表=槽→声明序）
SHV_NAMES, SHV_TYPE = {}, {}
_TAKEN_UP = set()
if _SYMS and _SYMMAP:
    for _slot, _si in enumerate(_SYMMAP, start=1):
        if 0 <= _si < len(_SYMS) and _SYMS[_si][0].upper() not in ('SV_I', 'SV_S'):
            SHV_NAMES[_slot] = _SYMS[_si][0]
            SHV_TYPE[_slot] = _SYMS[_si][1:]
            _TAKEN_UP.add(_SYMS[_si][0].upper())
# I/O 端口字节 → KAREL 内建口名（答案1 校准：io_01=DIN io_0b=OPIN io_0e=TPIN io_13=GOUT io_23=FLG）
IO_PORT_NAMES = {0x01: 'DIN', 0x02: 'DOUT', 0x0b: 'OPIN', 0x0e: 'TPIN',
                 0x13: 'GOUT', 0x23: 'FLG', 0x21: 'GIN', 0x33: 'ROUT'}

routines.sort(key=lambda r: r['entry'])
loc_by_id = {r.get('ei', n + 1): r['name'] for n, r in enumerate(routines)}
_KNOWN = {x.upper() for x in list(call_names.values()) + [r['name'] for r in routines] + list(imports)} | STDLIB
def _wild(prefix, val):
    nm = prefix + str(val)
    return nm + 'x' if nm.upper() in _KNOWN else nm
rname_to_idx = {r['name']: n for n, r in enumerate(routines)}

name = dec[4:20].split(b'\x00')[0].decode(errors='replace')
ver = dec[4 + len(name) + 1:][:12].split(b'\x00')[0].decode(errors='replace')

markers = [(m.start(), m.group(2)[0]) for m in re.finditer(rb'\x3e([\x00-\x05])(.)', dec) if m.start() + 5 <= N]
bodies = []
for i, (off, lid) in enumerate(markers):
    end = markers[i + 1][0] if i + 1 < len(markers) else N
    body = dec[off + 5:end]
    if len(body) > 800 or off < 0x30:
        bodies.append((lid, off, [], True, True)); continue
    toks = scan(body, off + 5)
    subs, cur = [], []
    for t in toks:
        if t[1] == 'ANCHOR':
            if cur:
                subs.append(cur)
            cur = []
        else:
            cur.append(t)
    if cur:
        subs.append(cur)
    if not subs:
        subs = [[]]
    for sub in subs:
        bodies.append((lid, off, sub, len(sub) == 0, False))

def section_of(off):
    idx = len(routines)  # 默认主程序段
    for n, r in enumerate(routines):
        if off >= r['entry']:
            idx = n
    return idx
sec_stmts = {}
for bi, (lid, off, toks, is_empty, is_data) in enumerate(bodies):
    if not is_data:
        sec_stmts.setdefault(section_of(off), []).append(bi)

def vn(tbl, idx):
    if tbl == 'v' and idx in SHV_NAMES:
        return SHV_NAMES[idx]
    base = ('v' if tbl == 'v' else 'lc') + str(idx)
    if base.upper() in _TAKEN_UP:  # KAREL 不分大小写：回退名让位于真名（V37/v37 实证）
        return 'zz' + base
    return base

str_vars = set()
arr_vars = set()
real_vars = set()
io_vars = set()
fld_vars = set()       # 字段合成名 v<n>_f<off>（FLD 偏移不再折叠丢弃）
str_arr_vars = set()   # 元素类型为 STRING 的数组基名
par_vars = set()       # 参数合成名 pp<槽号hex>（2d/2f/17/a1/a2 四形态）
file_vars = set()      # FILE 型变量（OPEN FILE 首项）
bool_vars = set()      # BOOLEAN 变量（std 形参 0x12 实证）
bool_arr_vars = set()  # BOOLEAN 数组（DISCTRL_FORM INACT_ARRAY 5B desc 实证）
for lid, off, toks, is_empty, is_data in bodies:
    seq = toks
    for x, t in enumerate(seq):
        if t[0] != 0:
            pass
    for t in toks:
        if t[1] == 'VAR' and t[2][0] in ('STs', 'LDs'):
            str_vars.add(vn(t[2][1], t[2][2]))
    for x in range(len(toks) - 1):
        if toks[x][1] == 'STR' and toks[x+1][1] == 'VAR' and toks[x+1][2][0] in ('STi', 'STs'):
            str_vars.add(vn(toks[x+1][2][1], toks[x+1][2][2]))

call_args, imp_args = {}, {}
ARITY = {}
KINDS = {}
BUILTIN_SIG = {'POST_ERR': 'isii', 'SET_INT_REG': 'iii', 'SET_REAL_REG': 'iii',
               'GET_REG': 'iiiii', 'DB_PROMPT': 'issi', 'CALL_PROG': 'si'}

def is_str(x):
    # 单字面量判定要严：'a' + '' 两端带引号但不是字面量（旧判定把它当纯串整个吞成 0）
    if re.match(r"^'(?:[^']|'')*'$", str(x)) or (x in str_vars):
        return True
    mb = re.match(r'^(\w+)\[[^\]]*\]$', str(x))
    return bool(mb and mb.group(1) in str_arr_vars)

def str_rhs(x):
    """右值携带字符串语义：字面量、串变量、或含串字面量的拼接表达式"""
    return is_str(x) or "'" in str(x)

def arg_kind(x):
    """实参类型：'as'/'ai'=整个数组传址，'s'=串，'r'=实，'i'=整（元素访问=标量元素类型）"""
    xs = str(x)
    mb = re.match(r'^(\w+)\[[^\]]*\]$', xs)
    if mb:
        base = mb.group(1)
        if base in str_arr_vars:
            return 's'
        return 'r' if base in real_vars else 'i'
    if xs in str_vars:
        return 's'
    if xs in str_arr_vars:
        return 'as'
    if xs in file_vars:
        return 'f'
    if xs in bool_vars:
        return 'b'
    if xs in arr_vars:
        return 'ai'
    if xs in real_vars:
        return 'r'
    if any(nm2 in real_vars for nm2 in re.findall(r'\b(?:v|lc|p)\w*\b', xs)):
        return 'r'
    return 's' if is_str(x) else 'i'

STR_RETNAMES = {'CHR', 'SUB_STR', 'STR_LEN', 'UPPERCASE', 'GETCURPROG', 'CURR_LANG',
                'READFILELINE', 'GETTPEPRMSTR', 'KILLBLANKS'}
def returns_str(nm):
    u = nm.upper()
    return u.endswith('STR') or u in STR_RETNAMES  # INTTO* 启发式误伤 INTTOOLID，收窄

def fmt_params(kinds):
    """按类型分组压缩形参行（KAREL 行宽 ~128）：p0, p1 : INTEGER; p2 : STRING"""
    TNAME = {'s': 'STRING', 'as': 'ARRAY OF STRING', 'ai': 'ARRAY OF INTEGER', 'f': 'FILE', 'r': 'REAL', 'b': 'BOOLEAN', 'ab': 'ARRAY OF BOOLEAN', 'ag': 'ARRAY OF INTEGER', 'i': 'INTEGER'}
    groups = []
    cur_k, cur_ids = None, []
    for x, k in enumerate(kinds):
        if k != cur_k:
            if cur_ids:
                groups.append((', '.join(cur_ids), cur_k))
            cur_k, cur_ids = k, []
        cur_ids.append('p%d' % x)
    if cur_ids:
        groups.append((', '.join(cur_ids), cur_k))
    return '; '.join('%s : %s' % (ids, TNAME.get(k, 'INTEGER')) for ids, k in groups)

def boolish(x):
    bare = re.sub(r"'[^']*'", '', str(x))
    return bool(re.search(r' (AND|OR) |^NOT ', bare) or re.search(r'[<>]|<>', bare)
                or bare.startswith('UNINIT(') or 'UNINIT(' in bare)

def looks_real(x):
    """右值是实型结果：浮点字面量、实除 '/'（0x6c）表达式、或引用了已知 REAL 名 → 存储目标声明 REAL"""
    xs = str(x)
    if re.search(r'\d+\.\d', xs) or re.search(r'[^/<>] / ', xs):
        return True
    return any(nm in real_vars for nm in re.findall(r'\b(?:v|lc|p)\w*\b', xs))

def vtype(name):
    for _slot, _nm in ():  # 符号表类型覆盖已禁用（连带类型错误 > 收益，仅保留真名）
        if _nm == name and _slot in SHV_TYPE:
            _t0, _t1, _dim = SHV_TYPE[_slot]
            if _t0 == 0x1f:
                return 'STRING[%d]' % max(_t1, 1)
            if _t0 == 0x20:
                _el = {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x1f: 'STRING'}.get(_t1, 'INTEGER')
                return 'ARRAY[%d] OF %s' % (max(_dim or 1, 1), _el)
            if _t0 == 0x00:
                return {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x1d: 'FILE'}.get(_t1, 'INTEGER')
            break
    if name in file_vars:
        return 'FILE'
    if name in bool_vars:
        return 'BOOLEAN'
    if name in arr_vars:
        if name in str_arr_vars:
            return 'ARRAY[64] OF STRING[64]'
        if name in bool_arr_vars:
            return 'ARRAY[64] OF BOOLEAN'
        if name in str_vars:
            return 'STRING[64]'  # 幽灵数组项（无元素使用证据，标量串才是真用法，MM_MODULE v1 实证）
        return 'ARRAY[64] OF REAL' if name in real_vars else 'ARRAY[64] OF INTEGER'
    if name in str_vars:
        return 'STRING[64]'
    if name in real_vars:
        return 'REAL'
    return 'INTEGER'


def _is_bool_name(nm):
    return False  # 纯名字模式：符号表类型不参与渲染判定（与 INTEGER 声明一致）

def emit_assign(lines, lhs, rhs):
    """布尔右值赋给整型目标 → IF/ELSE 1/0 包装（KAREL 不允许 bool 直接赋 int）"""
    if _is_bool_name(lhs) and str(rhs) in ('0', '1', 'TRUE', 'FALSE'):
        lines.append('%s = %s' % (lhs, 'TRUE' if str(rhs) in ('1', 'TRUE') else 'FALSE'))
        return
    if boolish(rhs):
        _t, _f = ('TRUE', 'FALSE') if str(lhs).split('[')[0] in bool_vars else ('1', '0')
        lines.append('IF ' + rhs + ' THEN')
        lines.append('  ' + lhs + ' = ' + _t)
        lines.append('ELSE')
        lines.append('  ' + lhs + ' = ' + _f)
        lines.append('ENDIF')
    else:
        lines.append(lhs + ' = ' + rhs)

def eval_expr(toks, collect=False, pad=None):
    lines, stack, params, wr = [], [], set(), []
    for off, kind, val, n in toks:
        if kind == 'INT':
            lit = str(val if val < 0x80000000 else val - 0x100000000)  # signed int32（3992977455 越界实证）
            if (0x3a000000 <= val <= 0x4b000000) or (0xba000000 <= val <= 0xcb000000):
                try:
                    import struct as _st
                    fv = _st.unpack('>f', val.to_bytes(4, 'big'))[0]
                    if fv == fv and abs(fv) < 1e7 and fv != 0:
                        lit = ('%.6g' % fv)
                except Exception:
                    pass
            stack.append(lit)
        elif kind == 'STR':
            stack.append("'" + val.replace("'", "''") + "'")
        elif kind == 'VAR':
            op, tbl, idx = val
            nm = vn(tbl, idx)
            if op.startswith('LD') or op == 'REF':
                stack.append(nm)
            elif op.startswith('STlp'):
                if stack: stack.pop()
                lines.append('<<FORVAR:' + nm + '>>')
            elif op.startswith('ST'):
                rhs = stack.pop() if stack else '0'
                if boolish(rhs):
                    lines.append('IF ' + rhs + ' THEN')
                    lines.append('  ' + nm + ' = 1')
                    lines.append('ELSE')
                    lines.append('  ' + nm + ' = 0')
                    lines.append('ENDIF')
                else:
                    if nm in str_vars and not str_rhs(rhs):
                        rhs = "''"
                    elif nm not in str_vars and str_rhs(rhs):
                        str_vars.add(nm)  # 串写入 → 目标即串型（旧版吞成 0 丢串，G2 实证）
                    if looks_real(rhs):
                        real_vars.add(nm)
                    emit_assign(lines, nm, rhs)
            else:
                stack.append(nm)
        elif kind in ('PREF', 'PLD', 'PLDSTR'):
            par_vars.add(val)
            if kind == 'PLDSTR':
                str_vars.add(val)
            stack.append(val)
        elif kind in ('PST', 'PSTSTR'):
            par_vars.add(val)
            rhs = stack.pop() if stack else '0'
            if kind == 'PSTSTR' or str_rhs(rhs):
                str_vars.add(val)
            elif val in str_vars:
                rhs = "''"
            if looks_real(rhs):
                real_vars.add(val)
            params.add(val)
            emit_assign(lines, val, rhs)
        elif kind in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'ADDR', 'SUBR', 'MULR', 'DIVR',
                      'EQ', 'NE', 'LT', 'LE', 'GT', 'GE', 'AND', 'OR', 'CAT'):
            # 0x55=整数除（KAREL 关键字 DIV），0x6c=实除 /（PROBE T14-17 + ISRA_AV 实证）
            m = {'ADD': '+', 'SUB': '-', 'MUL': '*', 'DIV': 'DIV', 'MOD': 'MOD',
                 'ADDR': '+', 'SUBR': '-', 'MULR': '*', 'DIVR': '/',
                 'EQ': '=', 'NE': '<>',
                 'LT': '<', 'LE': '<=', 'GT': '>', 'GE': '>=', 'AND': 'AND', 'OR': 'OR', 'CAT': '+'}
            b2 = stack.pop() if stack else '0'
            b1 = stack.pop() if stack else '0'
            if kind == 'CAT':
                if is_str(b1) and not is_str(b2):
                    b2 = "''"
                elif is_str(b2) and not is_str(b1):
                    b1 = "''"
            elif kind in ('EQ', 'NE'):
                if is_str(b1) and not is_str(b2):
                    b2 = "''"
                elif is_str(b2) and not is_str(b1):
                    b1 = "''"
                if b2 in ('0', '1') and _is_bool_name(b1):
                    _pos = (kind == 'EQ') == (b2 == '1')
                    stack.append('(' + b1 + ' = ' + ('TRUE' if _pos else 'FALSE') + ')')
                    continue
                if b2 in ('0', '1') and (boolish(b1) or str(b1).startswith('UNINIT(')):
                    # 布尔(UNINIT/比较式)与 0/1 比较 → NOT/原式（KAREL 布尔=整型非法）
                    _pos = (kind == 'EQ') == (b2 == '1')
                    stack.append('(' + b1 + ')' if _pos else 'NOT (' + b1 + ')')
                    continue
                if b1 in ('0', '1') and (boolish(b2) or str(b2).startswith('UNINIT(')):
                    _pos = (kind == 'EQ') == (b1 == '1')
                    stack.append('(' + b2 + ')' if _pos else 'NOT (' + b2 + ')')
                    continue
            elif kind in ('ADD', 'SUB', 'MUL', 'DIV', 'MOD', 'ADDR', 'SUBR', 'MULR', 'DIVR'):
                if is_str(b1):
                    b1 = '0'
                if is_str(b2):
                    b2 = '0'
            res = b1 + ' ' + m[kind] + ' ' + b2
            if kind in ('EQ', 'NE', 'LT', 'LE', 'GT', 'GE'):
                res = '(' + res + ')'
            if re.search(r'\d+\.\d', b1 + b2):
                for nm2 in re.findall(r'\b(?:v|lc|p)\w+\b', b1 + b2):
                    real_vars.add(nm2)
            elif kind in ('AND', 'OR'):
                def boolify(x):
                    if re.search(r'[=<>]', x) or x in ('TRUE', 'FALSE') or str(x).startswith(('UNINIT(', 'NOT (')):
                        return x
                    return '(' + x + ' <> 0)'
                res = boolify(b1) + ' ' + m[kind] + ' ' + boolify(b2)
            stack.append(res)
        elif kind == 'NEG':
            x = stack.pop() if stack else '0'
            if re.match(r'^-?\d+$', str(x)) and int(x) < 0:
                stack.append(str(-int(x)))   # 负字面量折叠回正（避免双负号）
            else:
                stack.append('(0 - ' + x + ')')  # KAREL 表达式里一元负号非法，统一 (0 - N)
        elif kind == 'NOT':
            a1 = stack.pop() if stack else '0'
            if re.search(r'[=<>]', a1) or str(a1).startswith('UNINIT(') or a1 in bool_vars:
                stack.append('NOT (' + a1 + ')')
            else:
                stack.append('(' + a1 + ' = 0)')
        elif kind in ('ITOR', 'UNINIT'):
            if kind == 'UNINIT':
                # UNINIT(x) 是 KAREL 布尔谓词（mifap mi04_td_pop `63 00 10` 实证）——不能吞成 0
                a1 = stack.pop() if stack else 'v1'
                stack.append('UNINIT(%s)' % a1)
            # ITOR/64 = 类型转换标记，栈空转（禁 DUP！）
        elif kind == 'IORD':
            idx = stack.pop() if stack else '0'
            nm = 'io_%02x' % val
            io_vars.add(nm)
            stack.append(nm + '[' + idx + ']')
        elif kind == 'IOWR':
            idx = stack.pop() if stack else '0'
            v2 = stack.pop() if stack else '0'
            nm = 'io_%02x' % val
            io_vars.add(nm)
            lines.append(nm + '[' + idx + '] = ' + v2)
        elif kind == 'FLD':
            # REF基址 + 字段偏移 → 合成独立字段名（折叠到基变量会串型炸编译）
            if not stack:
                continue  # WRITE 设备选择符（ad 后 32 00 01），无基址可弹
            base = stack.pop()
            mb = re.match(r'^(\w+)\[([^\]]*\])$', str(base))
            if mb:
                nm2 = '%s_f%02x[%s' % (mb.group(1), val, mb.group(2))
                arr_vars.add('%s_f%02x' % (mb.group(1), val))
            elif re.match(r'^[A-Za-z_]\w*$', str(base)):
                nm2 = '%s_f%02x' % (base, val)
                fld_vars.add(nm2)
            else:
                nm2 = base
            stack.append(nm2)
        elif kind == 'EIDX':
            stack.append(str(val))
        elif kind == 'LDFLD':
            pass  # 顶栈已是字段引用名（值语义），无操作
        elif kind == 'EADDR':
            # 元素地址（'' REF SHV[18] #i EADDR ST.fld.s = FKEYS[i]=''）→ 合成元素引用
            idx = stack.pop() if stack else '1'
            arr = stack.pop() if stack else 'v1'
            if re.match(r'^[A-Za-z_]\w*$', str(arr)):
                arr_vars.add(arr)
            stack.append(str(arr) + '[' + idx + ']')
        elif kind == 'ELD':
            idx = stack.pop() if stack else '1'
            arr = stack.pop() if stack else 'v1'
            if re.match(r'^[A-Za-z_]\w*$', str(arr)):
                arr_vars.add(arr)
            stack.append(str(arr) + '[' + idx + ']')
        elif kind == 'EST':
            idx = stack.pop() if stack else '1'
            arr = stack.pop() if stack else 'v1'
            rhs = stack.pop() if stack else '0'
            if re.match(r'^[A-Za-z_]\w*$', str(arr)):
                arr_vars.add(arr)
                if looks_real(rhs):
                    real_vars.add(str(arr))
            emit_assign(lines, str(arr) + '[' + idx + ']', rhs)
        elif kind == 'STFLD':
            fld = stack.pop() if stack else 'v1'
            rhs = stack.pop() if stack else '0'
            fs = str(fld)
            if not re.match(r'^[A-Za-z_]\w*(\[[^\]]*\])?$', fs):
                fs = 'v1'
            base_n = fs.split('[')[0]
            if str_rhs(rhs):
                if '[' in fs:
                    arr_vars.add(base_n)
                    str_arr_vars.add(base_n)
                else:
                    str_vars.add(fs)
            elif fs in str_vars or base_n in str_arr_vars:
                rhs = "''"
            if looks_real(rhs):
                real_vars.add(base_n if '[' in fs else fs)
            emit_assign(lines, fs, rhs)
        elif kind == 'ARG':
            stack.append('<ARG>')
        elif kind in ('CALLLOC', 'CALLIMP', 'FN'):
            deepest = -1
            for si, it in enumerate(stack):
                if it == '<ARG>':
                    deepest = si
                    break
            region = stack[deepest:] if deepest >= 0 else []
            stack = stack[:deepest] if deepest >= 0 else []
            segs, cur = [], []
            for it in region:
                if it == '<ARG>':
                    if cur: segs.append(cur); cur = []
                else:
                    cur.append(it)
            if cur: segs.append(cur)
            a = [x for sg in segs for x in sg]
            if kind == 'CALLLOC':
                nm = loc_by_id.get(val, _wild('rtn', val))
                if collect:
                    call_args.setdefault(nm, []).append([arg_kind(x) for x in a[:24]])
            elif kind == 'CALLIMP':
                nm = call_names.get(val, _wild('imp', val))
                if collect:
                    imp_args.setdefault(nm, []).append([arg_kind(x) for x in a[:24]])
            else:
                nm = {14: 'str_len', 15: 'sub_str', 4: 'chr'}.get(val, _wild('fn', val))
                if collect:
                    imp_args.setdefault(nm, []).append([arg_kind(x) for x in a])
            _std = STD_SIGS.get(nm.upper())
            want = ARITY.get(nm, len(a))
            kinds2 = list(KINDS.get(nm, ['i'] * want))
            if _std:
                # 记录头 argc 是权威元数（不截断）；形参类型 = 调用点推断 ⊕ ev 已解析位覆盖
                want = min(_std[2], 24) if _std else min(want, 24)  # 签名元数权威截断
                kinds2 += ['i'] * (want - len(kinds2))
                for _x, _k2 in enumerate(_std[1]):
                    if _x < len(kinds2) and kinds2[_x] not in ('as', 'ai') and _k2 != 'ag':
                        kinds2[_x] = _k2  # 数组证据（元素访问实证）优先于 desc 走查
                kinds2 = kinds2[:want]
            while len(a) < want:
                a.append("''" if (len(kinds2) > len(a) and kinds2[len(a)] == 's') else '0')
            a = a[:want]
            a2 = []
            dropped = []
            for _x2 in range(len(a)):
                if re.match(r'^[A-Za-z_]\w*\[[^\]]+\]$', str(a[_x2])):
                    a[_x2] = '(' + str(a[_x2]) + ')'  # KAREL：数组元素按值传需括号（ISRA_AV 实证）
            for x, arg in enumerate(a):
                k = kinds2[x] if x < len(kinds2) else 'i'
                orig = arg
                if k == 's' and not is_str(arg):
                    arg = "''"
                elif k == 'i' and (str_rhs(arg) or re.search(r'[=<>]', arg)
                                   or (re.match(r'^[A-Za-z_]\w*$', str(arg))
                                       and (str(arg) in arr_vars or str(arg) in file_vars))):
                    arg = '0'
                elif k == 'pos' and str(arg) != 'sv_p':
                    dropped.append(orig); arg = 'sv_p'
                elif k == 'jpos' and str(arg) != 'sv_j':
                    dropped.append(orig); arg = 'sv_j'
                elif k == 'r' and str(arg) in str_vars:
                    dropped.append(orig); arg = '0.0'
                elif k in ('r', 's', 'f') and re.match(r'^[A-Za-z_]\w*$', str(arg)):
                    # std 形参类型反推实参变量类型（GET_REG 第4参 REAL 实证）
                    if k == 'r':
                        real_vars.add(str(arg))
                    elif k == 's':
                        str_vars.add(str(arg))
                    else:
                        file_vars.add(str(arg))
                elif k in ('ai', 'as', 'ab') and re.match(r'^[A-Za-z_]\w*$', str(arg)):
                    arr_vars.add(str(arg))
                    if k == 'as':
                        str_arr_vars.add(str(arg))
                    elif k == 'ab':
                        bool_arr_vars.add(str(arg))
                elif k == 'b' and str(arg) not in ('TRUE', 'FALSE') and not re.search(r'[<>]', str(arg)) and not str(arg).startswith('UNINIT('):
                    # BOOLEAN 形参：整型实参 (x <> 0) 包装（KAREL 双向都无隐式强转）
                    arg = '(' + str(arg) + ' <> 0)'
                if arg != orig:
                    dropped.append(orig)
                a2.append(arg)
            _std = STD_SIGS.get(nm.upper())
            _call = (nm + '(' + ', '.join(a2) + ')') if a2 else nm  # 0 参裸调用（r = Q 合法，Q() 非法）
            if nm in ('POST_ERR', 'SET_INT_REG', 'SET_REAL_REG') or (_std and _std[0] == 'v'):
                lines.append(_call)
                stack.append('0')
            else:
                _ret = _std[0] if _std else ('s' if returns_str(nm) else 'i')
                tgt = {'s': 'sv_s', 'pos': 'sv_p', 'jpos': 'sv_j'}.get(_ret, 'sv_i')
                lines.append(tgt + ' = ' + _call)
                stack.append(tgt)
            if dropped:
                lines.append('-- 弃参原式: ' + ' | '.join(dropped))
        elif kind in ('VSET', 'VGET'):
            deepest = -1
            for si, it in enumerate(stack):
                if it == '<ARG>':
                    deepest = si
                    break
            region = stack[deepest:] if deepest >= 0 else []
            stack = stack[:deepest] if deepest >= 0 else []
            segs, cur = [], []
            for it in region:
                if it == '<ARG>':
                    if cur: segs.append(cur); cur = []
                else:
                    cur.append(it)
            if cur: segs.append(cur)
            a = [x for sg in segs for x in sg]
            while len(a) < 5:
                a.append('0')
            a = a[:5]
            a[0] = '0' if is_str(a[0]) else a[0]
            if not is_str(a[1]):
                a[1] = "''"
            if not is_str(a[2]):
                a[2] = "''"
            a[4] = '0' if is_str(a[4]) else a[4]
            lines.append(('SET_VAR(' if kind == 'VSET' else 'GET_VAR(') + ', '.join(a) + ')')
            stack.append('0')
        elif kind == 'DELAY':
            t = stack.pop() if stack else '0'
            lines.append('DELAY ' + str(t))
            stack.append('0')
        elif kind in ('CONNTMR', 'DISCTMR'):
            if stack: stack.pop()
        elif kind == 'PULSE':
            if stack: stack.pop()
            if stack: stack.pop()
        elif kind in ('ENABLE', 'PURGE', 'SIGEVENT', 'PAUSE', 'RELEASE', 'ABORT', 'RESUME', 'STOP'):
            if kind == 'SIGEVENT':
                # KTRANS 实证 SIGEVENT(n) 非法 KAREL——0x4d 语义未钉死，留痕不冒充
                a1 = stack.pop() if stack else '?'
                lines.append('-- SIGEVENT[未解] arg=' + str(a1))
            elif kind in ('ENABLE', 'PURGE'):
                if stack:
                    stack.pop()
                lines.append(kind + ' CONDITION[1]')
            else:
                lines.append(kind)
        elif kind == 'WR':
            wr = []
        elif kind in ('WIT_STR', 'WIT_INT'):
            if stack: stack.pop()  # 宽度
            if stack: stack.pop()  # 精度
            v = stack.pop() if stack else '0'
            wr.append(str(v) if str(v) else "''")
        elif kind == 'WIT_CR':
            if stack: stack.pop()
            if stack: stack.pop()
            wr.append('CR')
        elif kind == 'WREND':
            if wr:
                lines.append('WRITE(' + ', '.join(wr) + ')')
            wr = []
        elif kind == 'OPENF':
            # OPEN FILE fileComm('RO', 'FR:Rivet.DT')：栈=文件变量 + 参数（0x3d 语句码）
            # 护栏：0x3d 亦是 ASCII '='，栈深 >6 视为乱流不吞（dcpclear/tucker 实证）
            if 1 <= len(stack) <= 6:
                items = [str(x) for x in stack]
                stack = []
                if re.match(r'^(v|lc|p)\w*$', items[0]):
                    file_vars.add(items[0])
                lines.append('OPEN FILE ' + items[0] + '(' + ', '.join(items[1:]) + ')')
            else:
                stack.append('0')
        elif kind == 'UNK':
            stack.append('0')
    return lines, (stack[-1] if stack else None), params, list(stack)

# pass 1: 收集（跑两轮：字段/元素类型沿赋值链传播）
for _pass in range(2):
    for si, bis in sec_stmts.items():
        for bi in bis:
            lid, off, toks, is_empty, is_data = bodies[bi]
            eval_expr(toks, collect=True)
for nm, argss in list(call_args.items()) + list(imp_args.items()):
    base = 1
    for r in routines:
        if r['name'] == nm:
            base = r['argc']
    if nm in BUILTIN_SIG:
        base = len(BUILTIN_SIG[nm])
    ARITY[nm] = max([base] + [len(x) for x in argss])
    kinds = ['i'] * ARITY[nm]
    if nm in BUILTIN_SIG:
        kinds = [c for c in BUILTIN_SIG[nm]]
    else:
        prio = {'as': 6, 'ai': 5, 's': 4, 'f': 3, 'r': 2, 'b': 1, 'i': 0}
        for alist in argss:
            for x in range(min(len(kinds), len(alist))):
                if prio.get(alist[x], 1) > prio.get(kinds[x], 1):
                    kinds[x] = alist[x]
        # 实参形态冲突（数组 vs 标量，fn25 双形态实证）→ 整型形参，异形态实参弃参留痕
        for x in range(len(kinds)):
            seen = {alist[x] for alist in argss if x < len(alist)}
            if ('ai' in seen or 'as' in seen) and len(seen) > 1:
                kinds[x] = 'i'
    KINDS[nm] = kinds

n_v, max_lc = 1, 0
for lid, off, toks, is_empty, is_data in bodies:
    for _, k, v, _n in toks:
        if k == 'VAR':
            if v[1] == 'v':
                n_v = max(n_v, v[2] + 1)
            else:
                max_lc = max(max_lc, v[2] + 1)

def block_struct(bis):
    close_of, open_stack = {}, []
    for bi in bis:
        lid, off, toks, is_empty, is_data = bodies[bi]
        kinds = [t[1] for t in toks]
        jmp_only = bool(kinds) and ('JMP' in kinds) and all(k in ('JMP', 'INT', 'VAR', 'ARG', 'NOP', 'UNK', 'PAR') for k in kinds)
        if is_empty and open_stack:
            close_of[open_stack.pop()] = (bi, 'if')
        elif 'JZ' in kinds:
            open_stack.append(bi)
    for oi in open_stack:
        jmp_ci = None
        for bi in bis:
            if bi <= oi:
                continue
            lid, off, toks, is_empty, is_data = bodies[bi]
            kinds = [t[1] for t in toks]
            if kinds and ('JMP' in kinds) and all(k in ('JMP', 'INT', 'VAR', 'ARG', 'NOP', 'UNK', 'PAR') for k in kinds):
                jmp_ci = bi
                break
        if jmp_ci is None:
            continue
        # jmp-only 行之后若还有空锚点 → 该 jmp 是 ELSE，块型 IF，收尾=空锚点；否则=WHILE 回边
        tail_empty = None
        for b2 in bis:
            if b2 > jmp_ci and bodies[b2][3]:
                tail_empty = b2
                break
        if tail_empty is not None:
            close_of[oi] = (tail_empty, 'if')
        else:
            close_of[oi] = (jmp_ci, 'while')
    return close_of

# ---- 跳转表 + 回边（REPEAT/UNTIL 重建） ----
def _parse_jumptable(dec):
    pos = dec.find(b'\x7f\x00\x00\x00\xff\x00')
    if pos < 0:
        return []
    count = int.from_bytes(dec[pos+5:pos+7], 'big')
    if not (0 < count < 4000):
        return []
    out = []
    for k in range(count):
        q = pos + 7 + 4*k
        if q + 4 > len(dec):
            break
        out.append(int.from_bytes(dec[q:q+4], 'big'))
    return out

_JT = _parse_jumptable(dec)
_JT_BASE = None
if _JT and markers:
    _offs = sorted({m for m, _l in markers})
    _best, _bestn = None, -1
    for _b in range(0, 0x80):
        _hit = sum(1 for t in _JT if (t + _b) in _offs)
        if _hit > _bestn:
            _best, _bestn = _b, _hit
    if _bestn >= max(1, len(_JT) // 4):
        _JT_BASE = _best

def _jt_stmt(targets_off):
    # 目标偏移 → 语句序（取 ≥ 目标的首个锚点语句）
    import bisect
    _offs = [m for m, _l in markers]
    k = bisect.bisect_left(_offs, targets_off)
    return k if k < len(_offs) else None

# 每语句的 JZ/JMP 目标语句号
JZ_TO, JMP_TO = {}, {}
if _JT_BASE is not None:
    for _bi, (_lid, _off, _toks, _ie, _id) in enumerate(bodies):
        for _t in _toks:
            if _t[1] in ('JZ', 'JMP') and isinstance(_t[2], int) and _t[2] < len(_JT):
                _tgt = _jt_stmt(_JT[_t[2]] + _JT_BASE)
                if _tgt is not None:
                    (JZ_TO if _t[1] == 'JZ' else JMP_TO)[_bi] = _tgt
# 回边：JZ 目标语句 ≤ 当前 → REPEAT 头/UNTIL 尾（护栏：头须为实语句且非跳转句）
REPEAT_HEADS, UNTIL_AT = set(), {}
for _bi, _t in JZ_TO.items():
    if _t < _bi:
        _hk = [t[1] for t in bodies[_t][2]]
        if bodies[_t][3] or any(k in _hk for k in ('JZ', 'JMP')):
            continue
        # 块自含校验：区内 IF 开闭须配平（跨界 IF 会炸 KTRANS）
        _depth, _ok = 0, True
        for _r in range(_t, _bi):
            _k2 = [tt[1] for tt in bodies[_r][2]]
            if 'JZ' in _k2:
                _depth += 1
            if bodies[_r][3]:
                _depth -= 1
            if _depth < 0:
                _ok = False
                break
        if not (_ok and _depth == 0):
            continue
        REPEAT_HEADS.add(_t)
        UNTIL_AT[_bi] = _t

BUILTIN = {'POST_ERR', 'SET_INT_REG', 'SET_REAL_REG', 'GET_REG', 'DB_PROMPT', 'CALL_PROG'}
with open(out_path, 'w', encoding='gbk', errors='replace') as f:
    f.write('-- ' + os.path.basename(out_path) + ' (decompiled v3)\n')
    f.write('PROGRAM ' + name + '\n')
    f.write("%COMMENT = 'decompiled v3'\n")
    f.write('%NOBUSYLAMP\n%NOLOCKGROUP\n%NOPAUSE = COMMAND + TPENABLE + ERROR\n%NOABORT = ERROR + COMMAND\n')
    f.write('VAR\n')
    for nm in sorted(io_vars):
        f.write('  %s : ARRAY[512] OF INTEGER\n' % nm)
    for n in range(1, n_v):
        f.write('  %s : %s\n' % (vn('v', n), vtype(vn('v', n))))
    for n in range(max_lc):
        f.write('  %s : %s\n' % (vn('l', n), vtype(vn('l', n))))
    # 字段合成名/派生数组名（v<n>_f<off> 等）补声明
    def _covered(nm):
        m = re.match(r'^v(\d+)$', nm)
        if m:
            return int(m.group(1)) < n_v
        m = re.match(r'^lc(\d+)$', nm)
        if m:
            return int(m.group(1)) < max_lc
        return False
    _declared_syms = set(SHV_NAMES.values())
    extras = {nm for nm in (fld_vars | arr_vars | str_vars | real_vars | par_vars) if nm not in _declared_syms
              if not _covered(nm) and not re.match(r'^p\d+$', nm) and re.match(r'^[A-Za-z_]\w*$', nm)}
    for nm in sorted(extras):
        f.write('  %s : %s\n' % (nm, vtype(nm)))
    main_decls = set()
    for si2, bis2 in sec_stmts.items():
        if si2 >= len(routines):
            for bi2 in bis2:
                _lid, _off, _toks, _ie, _id = bodies[bi2]
                _l, _e, pp, _s = eval_expr(_toks)
                main_decls |= pp
    for d in sorted(main_decls):
        if re.match(r'^pp[0-9a-f]{2}$', d):
            continue  # 参数合成名已由 extras 按类型声明
        f.write('  %s : INTEGER\n' % d)
    f.write('  sv_i : INTEGER\n  sv_s : STRING[64]\n  sv_p : POSITION\n  sv_j : JOINTPOS\n')
    f.write('\n')
    # 野名字（RTN*/FN* 等动态槽位）自动补外部声明
    used = set()
    for si2, bis2 in sec_stmts.items():
        for bi2 in bis2:
            lid, off, toks, is_empty, is_data = bodies[bi2]
            ls, _e, _p, _s = eval_expr(toks)
            for l in ls:
                for mm in re.findall(r'\b((?:RTN|FN|IMP|rtn|fn|imp)\w*)\s*\(', l):
                    used.add(mm)
    _seen_upper = {r['name'].upper() for r in routines} | {n.upper() for n in BUILTIN} | STDLIB
    for nm, ret in imports.items():
        if nm in BUILTIN or nm.upper() in _seen_upper or nm.upper() == _prog_s:
            continue
        _seen_upper.add(nm.upper())
        argc = ARITY.get(nm, 1)
        kinds = ['i'] * argc
        for alist in imp_args.get(nm, []):
            for x in range(min(argc, len(alist))):
                if alist[x] == 's':
                    kinds[x] = 's'
        plist = fmt_params(kinds)
        rett = 'STRING' if (ret == 0x1f or returns_str(nm)) else 'INTEGER'
        f.write('ROUTINE %s(%s) : %s FROM MI_LIB\n' % (nm, plist, rett))
    _with_body = {routines[si]['name'] for si in sec_stmts if si < len(routines)}
    for r in routines:
        if r['name'] not in _with_body and r['name'].upper() not in STDLIB and r['name'] not in BUILTIN:
            # 名字表例程但无语句体 → 按外部例程声明（INTJOBDONE 实证：两路声明都跳过）
            _seen_upper.add(r['name'].upper())
            _ac = ARITY.get(r['name'], 0)
            _kd = KINDS.get(r['name'], ['i'] * _ac)
            _pl = fmt_params(_kd[:_ac] if len(_kd) >= _ac else _kd + ['i'] * (_ac - len(_kd)))
            f.write('ROUTINE %s(%s) : INTEGER FROM MI_LIB\n' % (r['name'], _pl) if _pl
                    else 'ROUTINE %s : INTEGER FROM MI_LIB\n' % r['name'])

    declared = set(imports) | {r['name'] for r in routines} | BUILTIN
    declared |= {n.upper() for n in declared}
    _NODECL = {'chr', 'sub_str', 'str_len', 'sv_i', 'sv_s'}
    for u in sorted(set(used) | set(call_args) | set(imp_args)):
        if u in _NODECL or u.upper() == _prog_s:
            continue
        if u not in declared and u.upper() not in declared and u.upper() not in STDLIB:
            ac = ARITY.get(u, 1)
            kd = KINDS.get(u, ['i'] * ac)
            plist = fmt_params(kd[:ac] if len(kd) >= ac else kd + ['i'] * (ac - len(kd)))
            f.write('ROUTINE %s(%s) : INTEGER FROM MI_LIB\n' % (u, plist))
    f.write('\n')

    # 例程段发射序：被调用者在前（KAREL 定义先于使用，WRITEDATA 例证）
    _name_si = {r['name'].upper(): si for si, r in enumerate(routines)}
    _deps = {}
    for si in sec_stmts:
        if si >= len(routines):
            continue
        _called = set()
        for bi in sec_stmts[si]:
            for _t in bodies[bi][2]:
                if _t[1] == 'CALLLOC':
                    _n2 = loc_by_id.get(_t[2])
                elif _t[1] == 'CALLIMP':
                    _n2 = call_names.get(_t[2])
                else:
                    _n2 = None
                if _n2 and _n2.upper() in _name_si:
                    _called.add(_name_si[_n2.upper()])
        _deps[si] = _called
    _order, _seen = [], set()
    def _topo(x, stack=()):
        if x in _seen or x in stack:
            return
        for y in _deps.get(x, ()):
            _topo(y, stack + (x,))
        _seen.add(x)
        _order.append(x)
    for _x in sorted(_deps):
        _topo(_x)
    _order += [si for si in sorted(sec_stmts) if si >= len(routines)]
    for si in _order:
        if si not in sec_stmts:
            continue  # 拓扑依赖到的无语句例程段（KeyError 防护）
        bis = sec_stmts[si]
        _rev = {b2: b1 for b1, b2 in zip(bis, bis[1:])}
        if si < len(routines):
            r = routines[si]
            ar = call_args.get(r['name'], []) + imp_args.get(r['name'], [])
            argc = max([r['argc']] + [len(x) for x in ar])
            kinds = ['i'] * argc
            for alist in ar:
                for x in range(min(argc, len(alist))):
                    if alist[x] == 's':
                        kinds[x] = 's'
            plist = fmt_params(kinds)
            f.write('ROUTINE %s(%s) : INTEGER\n' % (r['name'], plist) if plist else 'ROUTINE %s : INTEGER\n' % r['name'])
        else:
            pass
        close_of = block_struct(bis)
        endif_lines = {ci for ci, t in close_of.values() if t == 'if'}
        endwhile_lines = {ci for ci, t in close_of.values() if t == 'while'}
        n_close_if = {}
        n_close_wh = {}
        for _oi, (_ci, _t) in close_of.items():
            d = n_close_if if _t == 'if' else n_close_wh
            d[_ci] = d.get(_ci, 0) + 1
        else_lines = set()
        for oi2, (ci2, t2) in close_of.items():
            if t2 != 'if':
                continue
            seen = False
            for b2 in bis:
                if not (oi2 < b2 < ci2):
                    continue
                k2 = [t[1] for t in bodies[b2][2]]
                if k2 and ('JMP' in k2) and all(k in ('JMP', 'INT', 'VAR', 'ARG', 'NOP', 'UNK', 'PAR') for k in k2) \
                        and b2 not in endwhile_lines and not seen:
                    else_lines.add(b2)
                    seen = True
        declp = set()
        for bi in bis:
            lid, off, toks, is_empty, is_data = bodies[bi]
            _, _, p, _s = eval_expr(toks)
            declp |= p
        if declp and si < len(routines):
            declp2 = [d for d in sorted(declp) if not re.match(r'^pp[0-9a-f]{2}$', d)]
            if declp2:
                f.write('VAR\n')
                for d in declp2:
                    f.write('  %s : INTEGER\n' % d)
        f.write('BEGIN\n')
        open_blocks = []          # 段内块平衡栈: 'if'/'while'/'for'
        for bi in bis:
            lid, off, toks, is_empty, is_data = bodies[bi]
            kinds = [t[1] for t in toks]
            expr_lines, expr, _p, stk = eval_expr(toks)
            forvar = None
            cleaned = []
            for l in expr_lines:
                m = re.match(r'<<FORVAR:(\w+)>>', l)
                if m:
                    forvar = m.group(1)
                else:
                    cleaned.append(l)
            if bi in REPEAT_HEADS:
                f.write('  REPEAT\n')
            if is_empty:
                for _ in range(n_close_if.get(bi, 0)):
                    if open_blocks and open_blocks[-1] == 'if':
                        open_blocks.pop()
                        f.write('  ENDIF\n')
                continue
            if bi in endwhile_lines:
                for _ in range(n_close_wh.get(bi, 0)):
                    if open_blocks and open_blocks[-1] == 'while':
                        open_blocks.pop()
                        f.write('  ENDWHILE\n')
                continue
            if forvar:
                init = '1'
                rest = []
                for l in cleaned:
                    m = re.match(re.escape(forvar) + r' = (-?\d+)$', l)
                    if m:
                        init = m.group(1)
                    else:
                        rest.append(l)
                for l in rest:
                    f.write('  ' + l + '\n')
                f.write('  FOR %s = %s TO 3 DO\n' % (forvar, init))
                open_blocks.append('for')
                continue
            if bi in else_lines:
                if open_blocks and open_blocks[-1] == 'if':
                    f.write('  ELSE\n')
                continue
            if bi in UNTIL_AT:
                cond = expr if expr and expr != '0' else 'TRUE'
                if cond != 'TRUE' and not re.search(r'[=<>]', cond) and not cond.startswith('UNINIT(') and not cond.startswith('NOT ('):
                    cond = '(' + cond + ' <> 0)'
                f.write('  UNTIL(' + cond + ')\n')
                continue
            if 'JZ' in kinds:
                cond = expr if expr and expr != '0' else 'TRUE'
                if cond != 'TRUE' and not re.search(r'[=<>]', cond) and not cond.startswith('UNINIT(') and not cond.startswith('NOT (') and cond not in bool_vars:
                    cond = '(' + cond + ' <> 0)'
                if close_of.get(bi, (None, ''))[1] == 'while':
                    f.write('  WHILE (%s) DO\n' % cond)
                    open_blocks.append('while')
                else:
                    f.write('  IF (%s) THEN\n' % cond)
                    open_blocks.append('if')
                continue
            if 'LOOPBACK' in kinds:
                if open_blocks and open_blocks[-1] == 'for':
                    open_blocks.pop()
                    f.write('  ENDFOR\n')
                continue
            if any(t[1] == 'RET' for t in toks):
                f.write('  RETURN(0)\n' if si < len(routines) else '  RETURN\n')
                continue
            for l in cleaned:
                f.write('  ' + l + '\n')
            if not cleaned and expr and expr != '0':
                f.write('  -- L%d: %s\n' % (lid, expr))
        while open_blocks:
            k = open_blocks.pop()
            f.write('  %s\n' % {'if': 'ENDIF', 'while': 'ENDWHILE', 'for': 'ENDFOR'}[k])
        if si < len(routines):
            f.write('  RETURN(0)\n')
        f.write('END %s\n\n' % (routines[si]['name'] if si < len(routines) else name))
    if not any(si >= len(routines) for si in sec_stmts):
        f.write('BEGIN\nEND %s\n' % name)

print('wrote', out_path, 'routines:', len(routines), 'sections:', len(sec_stmts))
