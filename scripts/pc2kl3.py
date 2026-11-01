# pc2kl3.py — .pc → 可编译 .kl（v3：例程切段 + 签名形参 + 类型推断 + 外部声明）
# Usage: python -I pc2kl3.py <dec> <out.kl>
import os, re, sys, json

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
        # 参数族（PROBE5 + 探针 T_PARAM/T_PARAM2 落锤）：17/74=引用 2d=读 2f=写整 a2=写串 a1=读串
        # 编码 = op ff <i32BE 槽号>。槽号规律（27 组 0 矛盾）：形参【逆声明序】从 0 向下分配，
        # STRING 形参占 2 槽（r_ss(x,y:STRING) → x=-3 y=-1），引用编码=该形参区域底部槽。
        # token val = 槽号 int；发射时按名字表形参签名解析成 p<序号>，无签名兜底 pp<hex>。
        if b in (0x17, 0x74, 0x2d, 0x2f, 0xa1, 0xa2) and i + 5 < len(seg) and seg[i + 1] == 0xff:
            _slot = int.from_bytes(seg[i + 2:i + 6], 'big', signed=True)
            if -64 <= _slot <= 0:
                _kk = {0x17: 'PREF', 0x74: 'PREF', 0x2d: 'PLD', 0x2f: 'PST',
                       0xa1: 'PLDSTR', 0xa2: 'PSTSTR'}[b]
                out.append((base + i, _kk, _slot, 6)); i += 6; continue
        if b in (0x17, 0x74) and i + 5 < len(seg):
            out.append((base + i, 'PREF', 'pp' + seg[i+1:i+6].hex()[-2:], 6)); i += 6; continue
        if b == 0x32 and i + 2 < len(seg) and seg[i + 1] == 0x00:
            # 32 00 <偏移> [5E]：5E=串字段访问第4字节（串变长，寻址比整型字段多1字节）。
            # 罗塞塔实证 dcpfault_mh: `DCPPLCText = RobotName + ',Tool-' + ToolID + ',' +
            #   DCPText.DCPLine1 + DCPText.DCPLine2` → `REF v6 FLD 4 5E CAT`（DCPLine1=串字段）。
            # 不吃掉 5E 会让它落 UNK→push '0'，串字段被当整数，整条拼接链垮掉。
            if i + 3 < len(seg) and seg[i + 3] == 0x5E:
                out.append((base + i, 'FLDSTR', seg[i+2], 4)); i += 4; continue
            out.append((base + i, 'FLD', seg[i+2], 3)); i += 3; continue
        # 0x33=EADDR 单字节（PROBE5 + dcpclear 实证）：33 32=元素+字段两操作码，勿复合吞偏移
        if b == 0x63 and i + 2 < len(seg):
            out.append((base + i, 'UNINIT', None, 3)); i += 3; continue
        if seg[i:i+5] == b'\x12\x43\xab\x00\x03' or seg[i:i+3] == b'\x13\x05\x04' \
                or seg[i:i+2] in (b'\x81\x18', b'\x1b\x01'):
            n2 = 5 if seg[i:i+5] == b'\x12\x43\xab\x00\x03' else (3 if seg[i:i+3] == b'\x13\x05\x04' else 2)
            out.append((base + i, 'NOP', None, n2)); i += n2; continue
        if b in (0x40, 0x41) and i + 4 < len(seg) and seg[i+1:i+3] == b'\x00\x00':
            out.append((base + i, 'SEL40' if b == 0x40 else 'SEL41',
                        int.from_bytes(seg[i+1:i+5], 'big'), 5)); i += 5; continue
        if b == 0x42:
            out.append((base + i, 'SEL42', None, 1)); i += 1; continue
        if b == 0x43:
            out.append((base + i, 'SEL43', None, 1)); i += 1; continue
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
               0x0d: ('ENABLE', None), 0x3c: ('PURGE', None), 
               0x4d: ('SIGEVENT', None), 0x62: ('CONNTMR', None), 0x28: ('DISCTMR', None),
               0x10: ('PAUSE', None), 0x16: ('RELEASE', None), 0x3a: ('ABORT', None),
               0x4e: ('RESUME', None), 0x4f: ('STOP', None), 0x33: ('EADDR', None)}
        if b in ONE:
            k, v = ONE[b]
            out.append((base + i, k, v, 1)); i += 1; continue
        out.append((base + i, 'UNK', b, 1)); i += 1
    return out


# FN 族 `76 <id>` = KAREL 内建函数调用（编译器内建表，全局稳定，跨模块同 id 同名）。
# 来源：fn_census.py 投票普查（四族配对语料+探针，锚点行号归因）+ T_FNS 系列探针落锤。
# 旧映射 {14:'str_len', 15:'sub_str', 4:'chr'} 的键是十六进制 0x14/0x15 误写成十进制
# （4=chr 系 0x04 恰等值才命中过）——已纠正。id 序≈内建名 ASCII 序（1-23 段），
# 25/26=追加段（SYSTEM 组转换）；0/9/24 为未见面层名的内部槽（fnN 兜底）。
# 不进本表：ABS=算子 0x50(整)/0x67(实)、UNINIT=0x63、GET_VAR/SET_VAR=af/b0（均有专用算子）；
# CNV_INT_STR 族/CHECK_*/GET_TSK_INFO 等=CALLIMP（名字表已还原）。
_FN_NAMES = {
    1: 'acos', 2: 'asin', 3: 'atan2', 4: 'chr', 5: 'cos', 6: 'curjpos', 7: 'curpos',
    8: 'exp', 10: 'frame', 11: 'index', 12: 'inv', 13: 'in_range', 14: 'ln', 15: 'ord',
    16: 'pos', 17: 'round', 18: 'sin', 19: 'sqrt', 20: 'str_len', 21: 'sub_str',
    22: 'tan', 23: 'trunc', 25: 'cnv_jpos_rel', 26: 'cnv_rel_jpos',
}


def _stdlib_sigs():
    """KTRANS 支持库(core.ev)权威签名：NAME\x00 ff ff <argc u8> <ret u16BE> <参数 NAME\x00 3B类型>
    ret 0000=VOID/0010=INTEGER/1fxx=STRING；参数 (00,10)=int (1f,..)=str (00,1d)=file (00,11)=real"""
    def _cls(bs):
        t = bs[:2]
        if t[0] in (0x20, 0x3f):
            # 数组 desc 5B：20 <元素型> 00 00 00 / 3f <串长> <数>=ARRAY OF STRING
            # （类型表 `3f c8 00 06` ⟷ ARRAY[6] OF STRING[200] 落锤——旧映射 'ag'=通配 是错的，
            #  DISCTRL_FORM VALUE_ARRAY 实证：'ag'→'ARRAY OF INTEGER' 与 KTRANS 内建签名相撞）
            if t[0] == 0x3f:
                return 'as'
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
# ---- FN 族内建签名（KAREL 手册 A.x 权威形参/返回型；id→名=fn_census 实测，_FN_NAMES）----
# 返回型: v=过程(裸调用)/i=INTEGER/r=REAL/s=STRING/b=BOOLEAN/pos=POSITION/jpos=JOINTPOS。
# 可选参（CURPOS 第3组号/FRAME 第4点）暂按必选元数截断——语料实测调用均不含可选参。
STD_SIGS['CHR'] = ('s', ['i'], 1)
STD_SIGS['SUB_STR'] = ('s', ['s', 'i', 'i'], 3)
STD_SIGS['STR_LEN'] = ('i', ['s'], 1)
STD_SIGS['INDEX'] = ('i', ['s', 's'], 2)
STD_SIGS['ORD'] = ('i', ['s', 'i'], 2)
STD_SIGS['ROUND'] = ('i', ['r'], 1)
STD_SIGS['TRUNC'] = ('i', ['r'], 1)
STD_SIGS['CURPOS'] = ('pos', ['i', 'i'], 2)      # (axis_limit_mask, ovr_trv_mask)
STD_SIGS['CURJPOS'] = ('jpos', ['i', 'i'], 2)    # (axs_lim_mask, ovr_trv_mask)
STD_SIGS['CNV_JPOS_REL'] = ('v', ['jpos', 'ar', 'i'], 3)   # (jointpos, real_array, status)
STD_SIGS['CNV_REL_JPOS'] = ('v', ['ar', 'jpos', 'i'], 3)   # (real_array, joint_pos, status)
STD_SIGS['ACOS'] = ('r', ['r'], 1)
STD_SIGS['ASIN'] = ('r', ['r'], 1)
STD_SIGS['ATAN2'] = ('r', ['r', 'r'], 2)
STD_SIGS['COS'] = ('r', ['r'], 1)
STD_SIGS['EXP'] = ('r', ['r'], 1)
STD_SIGS['LN'] = ('r', ['r'], 1)
STD_SIGS['SIN'] = ('r', ['r'], 1)
STD_SIGS['SQRT'] = ('r', ['r'], 1)
STD_SIGS['TAN'] = ('r', ['r'], 1)
STD_SIGS['IN_RANGE'] = ('b', ['pos'], 1)         # (posn:XYZWPREXT)
STD_SIGS['INV'] = ('pos', ['pos'], 1)
STD_SIGS['FRAME'] = ('pos', ['pos', 'pos', 'pos'], 3)
STD_SIGS['POS'] = ('pos', ['r', 'r', 'r', 'r', 'r', 'r', 'i'], 7)  # 末参 c:CONFIG 无对应 kind，退 'i' 保原式
STD_SIGS['SET_POS_REG'] = ('v', ['i', 'pos', 'i'], 3)
STD_SIGS['SET_EPOS_REG'] = ('v', ['i', 'pos', 'i'], 3)
STD_SIGS['SET_JPOS_REG'] = ('v', ['i', 'jpos', 'i'], 3)
STD_SIGS['GET_POS_REG'] = ('pos', ['i', 'i'], 2)
STD_SIGS['GET_JPOS_REG'] = ('jpos', ['i', 'i'], 2)

# STDLIB 已由 STD_SIGS 提供

_NAME_ANCHOR = -1
routines, imports, call_names = [], {}, {}
import_ptypes = {}     # 导入例程形参类型码（名字表 desc 权威）
# 名字表锚点：通用 = <单字母前缀><程序名>\0（'VMI0' 只是 V 前缀撞名特例，123/125 模块踩空）
_prog = dec[4:20].split(b'\x00')[0]
_m0 = re.search(rb'\x00([ -~]{2,})\x00', dec[4:80])
_hdr_comment = _m0.group(1).decode() if _m0 else 'decompiled v3'
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
            # 本地例程 desc = 00 <entry u16> <ret u16> <argc u8> <形参类型 2B×argc>
            # 形参类型码同符号表：00 10=INT 00 11=REAL 00 12=BOOL 00 1d=FILE 1f<len>=STRING
            #                    11 <idx>=结构体引用（idx=类型表定义序）——T_PARAM 探针落锤
            _ac = desc[5] if desc[5] <= 24 else 0
            _pt = [(desc[6 + 2 * k], desc[7 + 2 * k]) for k in range(_ac)
                   if 8 + 2 * k <= len(desc)]
            routines.append({'name': nm, 'entry': int.from_bytes(desc[1:3], 'big'),
                             'ret': int.from_bytes(desc[3:5], 'big'), 'argc': _ac,
                             'ptypes': _pt, 'ei': ei})
        elif re.match(rb'[\x01-\x0f]\xff\xff', desc):
            # 导入 desc = <库号> ff ff <ret u16> <argc u8> <形参类型 2B×argc>
            imports[nm] = desc[3] if len(desc) > 3 else 0x10
            _ac2 = desc[5] if len(desc) > 5 and desc[5] <= 24 else 0
            _pt2 = [(desc[6 + 2 * k], desc[7 + 2 * k]) for k in range(_ac2)
                    if 8 + 2 * k <= len(desc)]
            import_ptypes[nm] = _pt2
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
        # 维度字节判定：t0 高半字节 >= 2 才带 u16 维度。
        # 旧判据 `t0 in (0x20,0x3f)` 太窄——0x31(结构/复合) 也带维度，
        # 漏掉就失步、提前 break，真名全丢（真实备份 dcp_hist 实证：
        #   DCPTEXT 'fd 11 00' 无dim / DCPTEXTHIST 'fd 31 00' 有dim(20) /
        #   FKEYS 'fd 3f 0c' 有dim(10)）。
        if (t0 >> 4) >= 2 and k + 2 <= gpos:
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

# ---- 类型表 + 结构体字段名还原（probe_symenc 落锤定编码）----
# 符号表条目 = <scope> NAME \0 <flags:1> <type:2> [<dim:u16> if type[0]==0x20]
# 类型表条目 = TYPENAME \0 <字段数:1>，字段 = FIELDNAME \0 03 <type:2> [<dim:u16>]
# type: 00 10=INT 00 11=REAL 00 12=BOOL 1f<len>=STRING 20<el><dim>=ARRAY
#       01 02=POSITION(36B)  11 <idx>=结构体引用（idx=定义顺序）
# 用途：把合成名 基_f<偏移> 还原成 基.字段名（ISV_VG 实证 11/11 偏移吻合）
def _parse_types(dec):
    types, i = [], 0
    while i < len(dec) - 2:
        m = re.match(rb'([A-Za-z_][A-Za-z0-9_]*)\x00([\x01-\x20])', dec[i:])
        if not m:
            i += 1
            continue
        tname, nfields = m.group(1).decode(), m.group(2)[0]
        j, fields, ok = i + m.end(), [], True
        for _ in range(nfields):
            m2 = re.match(rb'([A-Za-z_][A-Za-z0-9_]*)\x00\x03([\x00-\xff]{2})', dec[j:])
            if not m2:
                ok = False
                break
            fname = m2.group(1).decode()
            t0, t1 = m2.group(2)[0], m2.group(2)[1]
            j += m2.end()
            dim = None
            # 维度字节：t0 高半字节 >= 2 带 u16 维度（与符号表同规则）。
            # 0x3f <串长> <u16 数> = ARRAY[n] OF STRING[len]（XYZ_MSG_T MSG_ARRAY_
            # `3f c8 00 06` ⟷ ARRAY[6] OF STRING[200]，'mlen=quot*200+rema' 对拍）
            if (t0 >> 4) >= 2 and j + 2 <= len(dec):
                dim = int.from_bytes(dec[j:j + 2], 'big')
                j += 2
            fields.append((fname, t0, t1, dim))
        if ok and fields:
            types.append((tname, fields))
            i = j
        else:
            i += 1
    return types


def _tsize(t0, t1, dim, types, depth=0):
    if depth > 6:
        return 4
    if (t0, t1) in ((0x01, 0x02), (0x01, 0x03)):
        return 36                      # POSITION / JOINTPOS
    if t0 == 0x1f:
        return 4 + (t1 or 1)
    if t0 == 0x20:
        return 4 + (dim or 1) * 4
    if t0 == 0x3f:
        return 4 + (dim or 1) * 4    # ARRAY[n] OF STRING[len]（3f <len> <n>）
    if t0 == 0x11 and t1 is not None and t1 < len(types):
        return sum(_tsize(f[1], f[2], f[3], types, depth + 1) for f in types[t1][1])
    return 4


def _fld_offsets(types, tidx, base=0, path='', out=None, depth=0):
    if out is None:
        out = {}
    if depth > 6 or tidx >= len(types):
        return out
    off = base
    for fname, t0, t1, dim in types[tidx][1]:
        full = (path + '.' + fname) if path else fname
        out[off] = full
        if t0 == 0x11 and t1 is not None and t1 < len(types):
            _fld_offsets(types, t1, off, full, out, depth + 1)
        off += _tsize(t0, t1, dim, types, depth + 1)
    return out


_P2K_FIELDS = os.environ.get('P2K_FIELDS', '0') == '1'   # 程序级字段名还原开关
_TYPES = _parse_types(dec)     # 类型表总是解析：名字表形参签名（11 <idx>）要查它
_TYPE_DECLS = [(t, f) for t, f in _TYPES]          # 供输出 TYPE 块
_FIELD_BY_PATH = {}      # '基' 或 '基.DDD' → {偏移: 子字段名}（FLD 增量合成用）
_STRUCT_TYPE = {}        # 变量名 → 结构体类型名（声明用）
_STRUCT_TYPE_IDX = {}    # 变量名 → 类型表 idx（TYPE 块按需发射用）


def _build_fldmap(types, tidx, path, out, depth=0):
    if depth > 6 or tidx >= len(types):
        return
    out[path] = {}
    off = 0
    for fname, t0, t1, dim in types[tidx][1]:
        out[path][off] = fname
        if t0 == 0x11 and t1 is not None and t1 < len(types):
            _build_fldmap(types, t1, path + '.' + fname, out, depth + 1)
        elif (t0, t1) in ((0x01, 0x02), (0x01, 0x03)):
            # POSITION/JOINTPOS 内建类型的分量（实测 ISV_VG：+8..+28 = X/Y/Z/W/P/R）
            out[path + '.' + fname] = {8: 'X', 12: 'Y', 16: 'Z', 20: 'W', 24: 'P', 28: 'R'}
        off += _tsize(t0, t1, dim, types, depth + 1)


def _build_pmap(types, tidx, path, si, depth=0):
    """形参结构体字段表：_par_fldmap[(段号, 路径)][偏移] = (字段名, t0, t1)
    （字段名+字段类型均取类型表——名字表形参签名定位类型，权威非推断）"""
    if depth > 6 or tidx >= len(types):
        return
    out = {}
    _par_fldmap[(si, path)] = out
    off = 0
    for fname, t0, t1, dim in types[tidx][1]:
        out[off] = (fname, t0, t1)
        if t0 == 0x11 and t1 is not None and t1 < len(types):
            _build_pmap(types, t1, path + '.' + fname, si, depth + 1)
        off += _tsize(t0, t1, dim, types, depth + 1)


if _TYPES:
    _g, _o = dec.find(b'\xff$GROUP\x00\xfd'), dec.find(b'$ORNT_MROT')
    if _g >= 0 and _o >= 0:
        for _m in re.finditer(rb'([A-Za-z_][A-Za-z0-9_]{1,})\x00', dec[_o:_g]):
            _vnm = _m.group(1).decode()
            _k = _o + _m.end()
            if _k + 3 > _g:
                break
            _t0, _t1 = dec[_k + 1], dec[_k + 2]
            if _t0 in (0x11, 0x31) and _t1 < len(_TYPES):
                # 11 <idx>=结构体引用；31 <idx>=结构体数组引用（元素类型=idx）
                # 「变量→结构体类型」绑定=符号表权威，总是生效（声明才对得上形参签名）；
                # 字段名点路径还原（_FIELD_BY_PATH）仍是 P2K_FIELDS 实验特性
                if _P2K_FIELDS:
                    _build_fldmap(_TYPES, _t1, _vnm, _FIELD_BY_PATH)
                _STRUCT_TYPE_IDX[_vnm] = _t1
                if _t0 == 0x11:
                    _STRUCT_TYPE[_vnm] = _TYPES[_t1][0]
                else:
                    # 0x31 = 结构体数组：必须按元素类型声明，否则 CURRES[i].字段 报
                    # "Id type is not a STRUCTURE"（ISV_VG 实证 95 错）
                    _STRUCT_TYPE[_vnm] = 'ARRAY[64] OF %s' % _TYPES[_t1][0]
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

# ---- 形参槽位分配（探针 T_PARAM/T_PARAM2 落锤，27 组 0 矛盾）----
# 从 0 向下分配、逆声明序（末参最靠 0）；每参 1 槽，STRING 占 2 槽；
# 引用编码 = 该形参区域底部槽。槽号 → (形参序号, 类型码)
def _alloc_slots(ptypes):
    cur, m = 0, {}
    for ord_ in range(len(ptypes) - 1, -1, -1):
        t = ptypes[ord_]
        # 槽宽（T_PARAM2/3/4 落锤）：STRING(1f) 与聚合型 POS/JOINTPOS(01 xx) 占 2 槽，
        # 其余（11 结构引用 / 20 ARRAY / 00 10 INT / 00 11 REAL / 00 12 BOOL / 00 1d FILE）1 槽
        size = 2 if t[0] in (0x1f, 0x01) else 1
        ref = cur - (size - 1)
        for s in range(ref, cur + 1):
            m[s] = (ord_, t)
        cur = ref - 1
    return m


# 形参例程作用域类型集（名字表权威；键=(段号, 名)，防跨例程污染）
_par_str = set()      # (段号, 名)
_par_strarr = set()   # (段号, 名) — 元素为串的数组形参
_par_real = set()
_par_bool = set()
_par_file = set()
_par_struct = {}      # (段号, 名) → 结构体类型 idx
_par_fldmap = {}      # (段号, 路径) → {偏移: (字段名, t0, t1)}

_PARAMS = {}   # 例程序号 → {槽号: (形参序号, 类型码)}
for _si, _r in enumerate(routines):
    if _r.get('ptypes'):
        _PARAMS[_si] = _alloc_slots(_r['ptypes'])
_PAR_T = {}    # (段号, 'p<序号>') → 类型码（名字表权威）
for _si, _pm in _PARAMS.items():
    for _slot, (_ord, _t) in _pm.items():
        _PAR_T[(_si, 'p%d' % _ord)] = _t
        if _t[0] == 0x11 and _t[1] is not None and _t[1] < len(_TYPES):
            _build_pmap(_TYPES, _t[1], 'p%d' % _ord, _si)   # 形参→结构体类型绑定（字段偏移布局）

name = dec[4:20].split(b'\x00')[0].decode(errors='replace')
ver = dec[4 + len(name) + 1:][:12].split(b'\x00')[0].decode(errors='replace')

# ⚠️ 行号字节用 [\x00-\xff] 不用 '.'：'.' 不匹配 0x0a，源码行号=10 的锚点会被整条丢掉
#   （PROBE7 SYM_SEL=3 消失实证；中途锚点丢失会让语句并进上一体、首个丢失直接蒸发）
markers = [(m.start(), m.group(2)[0]) for m in re.finditer(rb'\x3e([\x00-\x05])([\x00-\xff])', dec) if m.start() + 5 <= N]
# 跳转表位置 = 代码区终点：其后是表/名字堆/数据，不能再当语句扫
# （表内 0x43/0x41 字节被误标成 SEL43/SEL41 → 野 ELSE:/CASE(3466) 实证）
_JT_POS = dec.find(b'\x7f\x00\x00\x00\xff')
bodies = []
for i, (off, lid) in enumerate(markers):
    end = markers[i + 1][0] if i + 1 < len(markers) else N
    if _JT_POS > off and _JT_POS < end:
        end = _JT_POS          # 尾体截到跳转表前：表/数据区不当语句扫
    if _JT_POS >= 0 and off >= _JT_POS:
        bodies.append((lid, off, [], True, True)); continue
    body = dec[off + 5:end]
    if len(body) > 800:
        bodies.append((lid, off, [], True, True)); continue
    toks = scan(body, off + 5)
    # off<0x30 原本一刀切当"头部/数据区"，但有的模块第一条真语句就在偏移 35-47
    # （dcp_form lid=44 SET_PORT_VAL(2,3099,1,…) 实证：整条被丢）。
    # 判据改为"有无真实语句 token"——头部噪声扫出来全是 UNK/NOP。
    if off < 0x30 and not any(t[1] not in ('UNK', 'NOP', 'ANCHOR') for t in toks):
        bodies.append((lid, off, [], True, True)); continue
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

# ---- 代码基址校准（探针 T_PARAM/T_PARAM2 落锤）----
# 名字表 entry =【代码区相对偏移】，基址=首例程段起点（v1=0x33 / v2=0x34 实测）。
# 旧代码把 entry 当绝对偏移用，误差=基址字节数 → 上一段尾部（END 体=返回 stub）
# 并进下一段顶部：每个例程开头多一句 RETURN(0)、段尾语句串段
# （XYZ_PKT：GET_MLEN 的尾语句被分进 ADD_MSG，逐字节实证）。
# 基址判据：①段界落在「返回 stub 尾」②形参槽号在所属例程形参区域内（错基址必越界）。
# 两项证据都拿不到 → 回退 0（旧行为），不瞎猜。
def _estimate_code_base():
    if not routines:
        return 0
    stub_ends = set()
    for m in re.finditer(rb'\x7f[\x00-\x08][\x00\x04\xff][\x00\x04\xfd\xff]', dec):
        stub_ends.add(m.end())
    anc_offs = sorted(a for a, _ in markers)

    def _next_anc(b):
        for a in anc_offs:
            if a >= b:
                return a
        return None

    body_slots = {}
    for lid, off, toks, ie, idt in bodies:
        if idt:
            continue
        s = {t[2] for t in toks
             if t[1] in ('PREF', 'PLD', 'PST', 'PLDSTR', 'PSTSTR') and isinstance(t[2], int)}
        if s:
            body_slots[off] = s
    best, best_sc, best_ev = 0, -10 ** 9, 0
    for B in range(0, 0x120):
        sc, ev = 0, 0
        for n, r in enumerate(routines):
            b = B + r['entry']
            if b in stub_ends:
                sc += 3
                ev += 1
            na = _next_anc(b)
            if na is not None and 0 <= na - b <= 0x48:
                sc += 1
            else:
                sc -= 2
        for off, slots in body_slots.items():
            rel = off - B
            idx = len(routines)
            for n, r in enumerate(routines):
                if rel >= r['entry']:
                    idx = n
            valid = set(_PARAMS.get(idx, {}))
            if not valid:
                continue
            if slots <= valid:
                sc += 2
                ev += 1
            else:
                sc -= 3
        if sc > best_sc:
            best, best_sc, best_ev = B, sc, ev
    return best if best_ev else 0


_CODE_BASE = _estimate_code_base()


def section_of(off):
    idx = len(routines)  # 默认主程序段
    rel = off - _CODE_BASE
    for n, r in enumerate(routines):
        if rel >= r['entry']:
            idx = n
    return idx
sec_stmts = {}
for bi, (lid, off, toks, is_empty, is_data) in enumerate(bodies):
    if not is_data:
        sec_stmts.setdefault(section_of(off), []).append(bi)

_CUR_SEC = 0          # 当前例程段号（局部名作用域用）
_LOCALS = set()       # 已用到的 (段号, 局部槽号)

# ---- 形参（名字表签名权威）：显示名 p<序号>，类型走例程作用域表防跨例程污染 ----
# （集合声明在 _PARAMS 构建前，_build_pmap 要写 _par_fldmap）


def _is_par(nm):
    return bool(re.match(r'^p\d+$', str(nm)))


def _pnm(slot):
    """形参槽号→显示名：本例程名字表签名命中→p<序号>；否则兜底 pp<hex>（旧口径）。
    非 int（旧式 PREF 兜底 token）原样返回。"""
    if isinstance(slot, str):
        return slot
    m = _PARAMS.get(_CUR_SEC, {})
    if slot in m:
        nm = 'p%d' % m[slot][0]
        return ('zp%d' % m[slot][0]) if nm.upper() in _TAKEN_UP else nm
    return 'pp%02x' % (slot & 0xff)


def _reg_par(nm):
    """按名字表类型码登记形参类型（例程作用域）——权威，不走使用点推断"""
    t = _PAR_T.get((_CUR_SEC, nm))
    if t is None:
        return
    t0, t1 = t
    if t0 == 0x1f:
        _par_str.add((_CUR_SEC, nm))
    elif t0 == 0x11:
        _par_struct[(_CUR_SEC, nm)] = t1
    elif t0 == 0x20 and t1 == 0x1f:
        _par_strarr.add((_CUR_SEC, nm))
    elif t0 == 0x00 and t1 == 0x11:
        _par_real.add((_CUR_SEC, nm))
    elif t0 == 0x00 and t1 == 0x12:
        _par_bool.add((_CUR_SEC, nm))
    elif t0 == 0x00 and t1 == 0x1d:
        _par_file.add((_CUR_SEC, nm))


# 方案1 跨实例名字映射（tests/build_name_map.py 产出，三族语料源码↔PC 对拍反推）：
# 命中 (模块,例程,槽号) → 例程局部用真名。机制已验证（续12 XYZ_PKT 115 处替换），
# 未命中自动退 r<段>_lc<槽> 合成名，零回归风险。
_NAME_MAP = {}
_MAPPED_UP = set()
_mp = os.environ.get('P2K_NAME_MAP',
                     r'D:\Downloads\Decompile-pcode-tests\tests\name_map.json')
if os.path.exists(_mp):
    try:
        _NAME_MAP = json.load(open(_mp, encoding='utf-8'))
    except Exception:
        _NAME_MAP = {}


def vn(tbl, idx):
    if tbl == 'v' and idx in SHV_NAMES:
        return SHV_NAMES[idx]
    if tbl != 'v':
        # 例程局部槽位必须带段号：不同例程用同一槽位存不同类型
        # （ISV_VG 实证：lc2 在 ISV2_GIN 是标量，却被全局推成 ARRAY[64] OF REAL，
        #  FOR 循环索引报 "must be an INTEGER"）→ r<段>_lc<槽> 各例程独立作用域
        _LOCALS.add((_CUR_SEC, idx))
        if _NAME_MAP and _CUR_SEC < len(routines):
            _rn = _NAME_MAP.get('%s|%s|%d' % (
                name.lower(), routines[_CUR_SEC]['name'].lower(), idx))
            # 真名有效性：标识符合法、不撞符号表真名（KAREL 不分大小写）
            if _rn and re.match(r'^[A-Za-z_]\w*$', _rn) and _rn.upper() not in _TAKEN_UP:
                _MAPPED_UP.add(_rn.upper())
                _SEC_LOCALS.setdefault(_CUR_SEC, set()).add(_rn)
                return _rn
        base = 'r%d_lc%d' % (_CUR_SEC, idx)
    else:
        base = 'v' + str(idx)
    if base.upper() in _TAKEN_UP:  # KAREL 不分大小写：回退名让位于真名（V37/v37 实证）
        if tbl != 'v':
            _SEC_LOCALS.setdefault(_CUR_SEC, set()).add('zz' + base)
        return 'zz' + base
    if tbl != 'v':
        _SEC_LOCALS.setdefault(_CUR_SEC, set()).add(base)
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

# ---- 类型证据作用域（续17：ISV_VG lc2 合成名教训的真名版）----
# name_map 真名 = 例程局部：同名局部在不同例程类型可以不同，证据按 (段,名) 键控，
# 不进全局集（xyz_bkgd state_ : INTEGER 被别段 ELD/EST 元素访问证据毒成
# ARRAY[64] OF REAL 实证）。程序级名、合成 v<n>、主程序段局部仍走全局集。
_SEC_LOCALS = {}   # si -> set(例程局部名)（vn() 解析时登记）
_SEC_T = {}        # (si, name) -> set(kind)
_TSETS = {'s': str_vars, 'r': real_vars, 'a': arr_vars, 'sa': str_arr_vars,
          'ba': bool_arr_vars, 'f': file_vars, 'b': bool_vars, 'fl': fld_vars}


def _is_local(x):
    # 主程序段（si >= len(routines)）的 ff 槽也走全局：历史路径=extras 程序级声明
    return _CUR_SEC < len(routines) and str(x) in _SEC_LOCALS.get(_CUR_SEC, ())


def _tmark(name, kind):
    name = str(name)
    if _is_local(name):
        _SEC_T.setdefault((_CUR_SEC, name), set()).add(kind)
    else:
        _TSETS[kind].add(name)


def _thas(name, kind):
    name = str(name)
    if _is_local(name):
        return kind in _SEC_T.get((_CUR_SEC, name), ())
    return name in _TSETS[kind]

for lid, off, toks, is_empty, is_data in bodies:
    seq = toks
    for x, t in enumerate(seq):
        if t[0] != 0:
            pass
    for t in toks:
        if t[1] == 'VAR' and t[2][0] in ('STs', 'LDs'):
            _tmark(vn(t[2][1], t[2][2]), 's')
    for x in range(len(toks) - 1):
        if toks[x][1] == 'STR' and toks[x+1][1] == 'VAR' and toks[x+1][2][0] in ('STi', 'STs'):
            _tmark(vn(toks[x+1][2][1], toks[x+1][2][2]), 's')

call_args, imp_args = {}, {}
ARITY = {}
KINDS = {}
BUILTIN_SIG = {'POST_ERR': 'isii', 'SET_INT_REG': 'iii', 'SET_REAL_REG': 'iii',
               'GET_REG': 'iiiii', 'DB_PROMPT': 'issi', 'CALL_PROG': 'si'}

def is_str(x):
    # 单字面量判定要严：'a' + '' 两端带引号但不是字面量（旧判定把它当纯串整个吞成 0）
    if re.match(r"^'(?:[^']|'')*'$", str(x)) or (_thas(x, 's')) \
            or str(x) == 'sv_s' or ((_CUR_SEC, str(x)) in _par_str):   # sv_s=串累加器，类型内建
        return True
    mb = re.match(r'^([\w.]+)(?:\[[^\]]*\])+$', str(x))   # 基名可含点、可多维（v15[v1][v13]）
    return bool(mb and (_thas(mb.group(1), 'sa')
                        or (_CUR_SEC, mb.group(1)) in _par_strarr))

def str_rhs(x):
    """右值携带字符串语义：字面量、串变量、或含串字面量的拼接表达式"""
    return is_str(x) or "'" in str(x)

def arg_kind(x):
    """实参类型：'as'/'ai'=整个数组传址，'s'=串，'r'=实，'i'=整（元素访问=标量元素类型）"""
    xs = str(x)
    mb = re.match(r'^([\w.]+)(?:\[[^\]]*\])+$', xs)   # 基名可含点、可多维
    if mb:
        base = mb.group(1)
        if _thas(base, 'sa') or (_CUR_SEC, base) in _par_strarr:
            return 's'
        return 'r' if _thas(base, 'r') else 'i'
    # 形参实参：类型码权威（名字表签名），不走使用点推断
    if (_CUR_SEC, xs) in _par_str:
        return 's'
    if (_CUR_SEC, xs) in _par_strarr:
        return 'as'
    if (_CUR_SEC, xs) in _par_file:
        return 'f'
    if (_CUR_SEC, xs) in _par_bool:
        return 'b'
    if (_CUR_SEC, xs) in _par_real:
        return 'r'
    if _thas(xs, 's'):
        return 's'
    if _thas(xs, 'sa'):
        return 'as'
    if _thas(xs, 'f'):
        return 'f'
    if _thas(xs, 'b'):
        return 'b'
    if _thas(xs, 'a'):
        return 'ai'
    if _thas(xs, 'r'):
        return 'r'
    if any(_thas(nm2, 'r') for nm2 in re.findall(r'\b[A-Za-z_]\w*\b', xs)):
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


def _ptype_name(t):
    """名字表类型码 → KAREL 类型名（权威）。结构体引用 → 类型表真名；
    类型表缺失该 idx（跨模块引用）→ 退 INTEGER（字段访问走合成名兜底）。"""
    t0, t1 = t
    if t0 == 0x1f:
        return 'STRING'
    if t0 == 0x11 and t1 is not None and t1 < len(_TYPE_DECLS):
        return _TYPE_DECLS[t1][0]
    if t0 == 0x20:
        return 'ARRAY OF ' + {0x10: 'INTEGER', 0x11: 'REAL',
                              0x12: 'BOOLEAN', 0x1f: 'STRING'}.get(t1, 'INTEGER')
    if t0 == 0x01:
        return 'POSITION' if t1 in (0x01, 0x02, 0x03) else 'JOINTPOS'
    if t0 == 0x00 and t1 in (0x10, 0x11, 0x12, 0x1d):
        return {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x1d: 'FILE'}[t1]
    return 'INTEGER'


def fmt_ptypes(ptypes):
    """按类型分组压缩形参行：p0 : XYZ_MSG_T; p1 : STRING"""
    groups, cur_t, cur_ids = [], None, []
    for x, t in enumerate(ptypes):
        tn = _ptype_name(t)
        if tn != cur_t:
            if cur_ids:
                groups.append((', '.join(cur_ids), cur_t))
            cur_t, cur_ids = tn, []
        cur_ids.append('p%d' % x)
    if cur_ids:
        groups.append((', '.join(cur_ids), cur_t))
    return '; '.join('%s : %s' % (ids, tn) for ids, tn in groups)


def _pk(t):
    """名字表类型码 → 实参强转用 kind 字符。'st'=结构体传址（不强转）"""
    t0, t1 = t
    if t0 == 0x1f:
        return 's'
    if t0 == 0x11:
        return 'st'
    if t0 == 0x20:
        return 'as' if t1 == 0x1f else 'ai'
    if t0 == 0x01:
        return 'pos'
    if t0 == 0x00:
        return {0x10: 'i', 0x11: 'r', 0x12: 'b', 0x1d: 'f'}.get(t1, 'i')
    return 'i'

def boolish(x):
    bare = re.sub(r"'[^']*'", '', str(x))
    return bool(re.search(r' (AND|OR) |^NOT ', bare) or re.search(r'[<>]|<>', bare)
                or bare.startswith('UNINIT(') or 'UNINIT(' in bare
                or bare == 'sv_b')   # sv_b=布尔累加器，类型内建


def looks_real(x):
    """右值是实型结果：浮点字面量、实除 '/'（0x6c）表达式、或引用了已知 REAL 名 → 存储目标声明 REAL"""
    xs = str(x)
    if re.search(r'\d+\.\d', xs) or re.search(r'[^/<>] / ', xs):
        return True
    return any(_thas(nm, 'r') or nm == 'sv_r' or (_CUR_SEC, nm) in _par_real   # sv_r=实累加器，类型内建
               for nm in re.findall(r'\b[A-Za-z_]\w*\b', xs))

def vtype(name):
    if name in _STRUCT_TYPE:
        return _STRUCT_TYPE[name]     # 结构体变量按真类型名声明（类型表已解析）
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
    if _thas(name, 'f'):
        return 'FILE'
    if _thas(name, 'b'):
        return 'BOOLEAN'
    if _thas(name, 'a'):
        if _thas(name, 'sa'):
            return 'ARRAY[64] OF STRING[64]'
        if _thas(name, 'ba'):
            return 'ARRAY[64] OF BOOLEAN'
        if _thas(name, 's'):
            return 'STRING[64]'  # 幽灵数组项（无元素使用证据，标量串才是真用法，MM_MODULE v1 实证）
        return 'ARRAY[64] OF REAL' if _thas(name, 'r') else 'ARRAY[64] OF INTEGER'
    if _thas(name, 's'):
        return 'STRING[64]'
    if _thas(name, 'r'):
        return 'REAL'
    return 'INTEGER'


def _is_bool_name(nm):
    return False  # 纯名字模式：符号表类型不参与渲染判定（与 INTEGER 声明一致）


# 只在【顶层逻辑/连接】运算符后断行。不能包含 '='/'<'/'>' 等比较符：
# 它们出现在 (A = B) 子表达式内部，断在其后会产出 `(A = ` / `B)` 这种非法续行
# （ISV_VG 实证：断在 '=' 后 → 行尾 ')'、下一行 'AND (...' → KTRANS "THEN expected"）
_WRAP_OPS = (' AND ', ' OR ')   # 只用探针验证过的断点（probe_linelen：AND 结尾续行 OK）


def _wrap_stmt(s, limit=250):
    """KTRANS 源码行长上限 256（probe_linelen 实测 247 OK / 259 FAIL）。
    KAREL 只支持【运算符在行尾】的续行（实测：`AND` 结尾续行 OK、`AND` 开头续行 FAIL）。
    超长语句按运算符后断行；找不到安全断点则原样输出（宁可超长也不破坏语义）。"""
    if len(s) <= limit:
        return [s]
    cuts, i, inq = [], 0, False
    while i < len(s):
        c = s[i]
        if c == "'":
            inq = not inq
        elif not inq:
            for op in _WRAP_OPS:
                if s.startswith(op, i):
                    cuts.append(i + len(op))
                    break
        i += 1
    if not cuts:
        return [s]
    out, start, last = [], 0, 0
    # ⚠️ 行尾也要当边界：只检查运算符位置会漏掉"最后一段超长"
    #   （实证：断点都在 246<250，但整行 295 → 一段都没拆，KTRANS 超 256 上限）
    for c in cuts + [len(s)]:
        if c - start > limit:
            if last > start:
                out.append(s[start:last])
                start = last
            else:                      # 单段就超长，硬切（无安全断点）
                out.append(s[start:start + limit])
                start += limit
        last = c
    if start < len(s):
        out.append(s[start:])
    return out


def _wline(f, line, indent='  '):
    for p in _wrap_stmt(indent + line):
        f.write(p + '\n')


def _cmt_lines(prefix, text):
    """注释折行：KTRANS 行长上限 256，超长注释会断裂成真代码
    （MI04_SSW stmt61 残差 400+ 字符单行 → 'Invalid statement' ×25 实证）"""
    out, cur = [], prefix
    for w in str(text).split(' '):
        while len(w) > 200:          # 超长单词（无空格长串）硬切
            if cur != prefix:
                out.append(cur)
                cur = prefix
            out.append(prefix + w[:200])
            w = w[200:]
        if len(cur) + 1 + len(w) > 240:
            out.append(cur)
            cur = prefix + w
        else:
            cur = (cur + ' ' + w) if cur != prefix else (prefix + w)
    out.append(cur)
    return out


def _cmt_write(f, prefix, text):
    for _l in _cmt_lines(prefix, text):
        f.write(_l + chr(10))


def _emit_residue(f, toks, written, lid):
    """语句字面量残差兜底：串/常量未进产物文本 → 留痕（静默丢失清零）"""
    _lost = []
    _budget = {}
    for _t in toks:
        if _t[1] == 'STR':
            _key = repr(_t[2])
        elif _t[1] == 'INT' and 1000 <= abs(_t[2]) <= 99999:
            _key = str(_t[2])
        else:
            continue
        _budget[_key] = _budget.get(_key, 0) + 1
    for _key, _n in _budget.items():
        _present = written.count(_key)
        for _ in range(_n - _present):
            _lost.append(_key)
    if _lost:
        _cmt_write(f, '  -- stmt%d residue ' % lid, ', '.join(_lost))

def emit_assign(lines, lhs, rhs):
    """布尔右值赋给整型目标 → IF/ELSE 1/0 包装（KAREL 不允许 bool 直接赋 int）"""
    if _is_bool_name(lhs) and str(rhs) in ('0', '1', 'TRUE', 'FALSE'):
        lines.append('%s = %s' % (lhs, 'TRUE' if str(rhs) in ('1', 'TRUE') else 'FALSE'))
        return
    if boolish(rhs):
        _t, _f = ('TRUE', 'FALSE') if _thas(str(lhs).split('[')[0], 'b') else ('1', '0')
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
                    if _thas(nm, 's') and not str_rhs(rhs):
                        rhs = "''"
                    elif not _thas(nm, 's') and str_rhs(rhs):
                        _tmark(nm, 's')  # 串写入 → 目标即串型（旧版吞成 0 丢串，G2 实证）
                    if looks_real(rhs):
                        _tmark(nm, 'r')
                    emit_assign(lines, nm, rhs)
            else:
                stack.append(nm)
        elif kind in ('PREF', 'PLD', 'PLDSTR'):
            val = _pnm(val)
            if _is_par(val):
                _reg_par(val)                 # 形参：名字表类型码权威，例程作用域
                if kind == 'PLDSTR':
                    _par_str.add((_CUR_SEC, val))
            else:
                par_vars.add(val)             # 兜底 pp<hex>：模块级声明（旧口径）
                if kind == 'PLDSTR':
                    _tmark(val, 's')
            stack.append(val)
        elif kind in ('PST', 'PSTSTR'):
            val = _pnm(val)
            rhs = stack.pop() if stack else '0'
            if _is_par(val):
                _reg_par(val)
                if kind == 'PSTSTR' or str_rhs(rhs):
                    _par_str.add((_CUR_SEC, val))
                elif (_CUR_SEC, val) in _par_str:
                    rhs = "''"
            else:
                par_vars.add(val)
                if kind == 'PSTSTR' or str_rhs(rhs):
                    _tmark(val, 's')
                elif _thas(val, 's'):
                    rhs = "''"
                if looks_real(rhs):
                    _tmark(val, 'r')
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
                # 串型判定用 str_rhs（携带串语义的表达式），不能用 is_str：
                # 复合串表达式 `('a' + v) + 'b'` 的 is_str=False，旧判定会把整段抹成 ''
                if str_rhs(b1) and not str_rhs(b2):
                    b2 = "''"
                elif str_rhs(b2) and not str_rhs(b1):
                    b1 = "''"
            elif kind in ('EQ', 'NE'):
                if str_rhs(b1) and not str_rhs(b2):
                    b2 = "''"
                elif str_rhs(b2) and not str_rhs(b1):
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
                    _tmark(nm2, 'r')
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
            if re.search(r'[=<>]', a1) or str(a1).startswith('UNINIT(') or _thas(a1, 'b'):
                stack.append('NOT (' + a1 + ')')
            else:
                stack.append('(' + a1 + ' = 0)')
        elif kind in ('ITOR', 'UNINIT'):
            if kind == 'UNINIT':
                # UNINIT(x) 是 KAREL 布尔谓词（mifap mi04_td_pop `63 00 10` 实证）——不能吞成 0
                a1 = stack.pop() if stack else vn('v', 1)
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
        elif kind in ('FLD', 'FLDSTR'):
            # REF基址 + 字段偏移 → 合成独立字段名（折叠到基变量会串型炸编译）
            # FLDSTR（32 00 <off> 5E）=串字段：合成名必须进 str_vars，
            # 否则 is_str/str_rhs 判不出串型，CAT 会把它抹成 ''（',Tool-' 残差根因）
            if not stack:
                continue  # WRITE 设备选择符（ad 后 32 00 01），无基址可弹
            base = stack.pop()
            mb = re.match(r'^(\w+)\[([^\]]*)\]?$', str(base))
            if mb:
                _bname, _idx = mb.group(1), mb.group(2)
                _pm = _par_fldmap.get((_CUR_SEC, _bname))
                if _pm and val in _pm:
                    _sub, _t0, _t1 = _pm[val]
                    nm2 = '%s[%s].%s' % (_bname, _idx, _sub)   # 基[i].字段
                    if kind == 'FLDSTR' or _t0 == 0x1f:
                        _par_str.add((_CUR_SEC, nm2))
                    if _t0 == 0x3f or (_t0 == 0x20 and _t1 == 0x1f):
                        _par_strarr.add((_CUR_SEC, '%s.%s' % (_bname, _sub)))
                else:
                    _sub = _FIELD_BY_PATH.get(_bname, {}).get(val)
                    if _sub:
                        nm2 = '%s[%s].%s' % (_bname, _idx, _sub)   # 基[i].字段
                        if kind == 'FLDSTR':
                            _tmark(nm2, 's')
                    else:
                        nm2 = '%s_f%02x[%s]' % (_bname, val, _idx)
                        _tmark('%s_f%02x' % (_bname, val), 'a')
                        if kind == 'FLDSTR':
                            _tmark('%s_f%02x' % (_bname, val), 'sa')
            elif re.match(r'^[A-Za-z_][\w.\[\]]*$', str(base)):
                # 结构体字段名还原：类型表有真名就用 点路径（VGCONFIG_f6c → VGCONFIG.OFFSET_PT）
                # ⚠️ base 可能是 'CURRES[pp00].OFFSET' 这种带下标+点的形式，
                #    查表前要剥掉 [..] 得到 'CURRES.OFFSET'（否则二级字段丢失，
                #    POSITION 被当标量 → "Data type of Id is incompatible" ×80）
                _key = re.sub(r'\[[^\]]*\]', '', str(base))
                _pm = _par_fldmap.get((_CUR_SEC, _key))
                if _pm and val in _pm:
                    # 形参结构体字段：名字表类型码权威，字段名/字段类型全还原
                    _sub, _t0, _t1 = _pm[val]
                    nm2 = str(base) + '.' + _sub
                    if kind == 'FLDSTR' or _t0 == 0x1f:
                        _par_str.add((_CUR_SEC, nm2))
                    if _t0 == 0x3f or (_t0 == 0x20 and _t1 == 0x1f):
                        _par_strarr.add((_CUR_SEC, nm2))   # 数组字段基名（元素串型）
                else:
                    _sub = _FIELD_BY_PATH.get(_key, {}).get(val)
                    if _sub:
                        nm2 = str(base) + '.' + _sub       # 点路径=字段访问，无需单独声明
                        # ⚠️ 不要往 str_vars 塞：类型已由 TYPE 块决定，
                        #    塞进去会把当 FOR 索引用的字段推成 STRING（JLR SCHEDULE_IDX 实证回归）
                    else:
                        nm2 = '%s_f%02x' % (base, val)
                        _tmark(nm2, 'fl')
                        if kind == 'FLDSTR':
                            _tmark(nm2, 's')
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
            arr = stack.pop() if stack else vn('v', 1)
            if re.match(r'^[A-Za-z_]\w*$', str(arr)):
                _tmark(arr, 'a')
            stack.append(str(arr) + '[' + idx + ']')
        elif kind == 'ELD':
            idx = stack.pop() if stack else '1'
            arr = stack.pop() if stack else vn('v', 1)
            if re.match(r'^[A-Za-z_]\w*$', str(arr)):
                _tmark(arr, 'a')
            stack.append(str(arr) + '[' + idx + ']')
        elif kind == 'EST':
            idx = stack.pop() if stack else '1'
            arr = stack.pop() if stack else vn('v', 1)
            rhs = stack.pop() if stack else '0'
            if re.match(r'^[A-Za-z_]\w*$', str(arr)):
                _tmark(arr, 'a')
                if looks_real(rhs):
                    _tmark(str(arr), 'r')
            emit_assign(lines, str(arr) + '[' + idx + ']', rhs)
        elif kind == 'STFLD':
            fld = stack.pop() if stack else vn('v', 1)
            rhs = stack.pop() if stack else '0'
            fs = str(fld)
            if not re.match(r'^[A-Za-z_]\w*((\.\w+)|(\[[^\]]*\]))*$', fs):
                # 点路径/下标交错（p0.FA / 基[i].字段 / A[i].b.c[j]）都是合法赋值目标——
                # 旧正则不含点、且只许尾下标，复合目标被兜底砸成 vn('v',1)
                # （名字丢、字面量还在，门查不出；vn('v',1)=SHV_NAMES[1]=SCHEDULE_IDX
                #  时还会把真变量污染成串型 → JLR SCHEDULE_IDX 回归的真正源头）
                fs = vn('v', 1)   # 兜底必须走 vn()：硬编码 'v1' 在槽位1已复原真名时不会被声明
            base_n = fs.split('[')[0]
            if str_rhs(rhs):
                if '[' in fs and '.' not in fs:
                    _tmark(base_n, 'a')
                    _tmark(base_n, 'sa')
                elif '.' not in fs:
                    _tmark(fs, 's')
                # 基[i].字段 / 基.字段（含点）：基是结构体，串性由 TYPE 块/作用域表决定，
                # 不能标基（否则整个结构体数组被推成串数组 → 全部字段赋值被抹成 ''
                #  DCPFAULTNUM = '' 实证）
            elif _thas(fs, 's') or ((_CUR_SEC, fs) in _par_str) \
                    or (_thas(base_n, 'sa') and '.' not in fs):
                rhs = "''"
            if looks_real(rhs):
                _tmark(base_n if '[' in fs else fs, 'r')
            emit_assign(lines, fs, rhs)
        elif kind == 'ARG':
            stack.append('<ARG>')
        elif kind in ('CALLLOC', 'CALLIMP', 'FN'):
            if kind == 'CALLLOC':
                # id 空间 = 名字表全索引（本地+导入交错，dcp_spot DCPDISP(ei=1) 落锤：
                # 源码 812 `DCPDISP(DCPText)` 是导入调用，旧 loc_by_id 只索引本地 → 失配变 rtn1）
                nm = call_names.get(val, _wild('rtn', val))
            elif kind == 'CALLIMP':
                nm = call_names.get(val, _wild('imp', val))
            else:
                nm = _FN_NAMES.get(val, _wild('fn', val))
            # ---- 实参区提取（XYZ_PKT 嵌套 + DCP_HIST DISCTRL_FORM 落锤）----
            # <ARG>(0x27)=实参前缀，但【不严格每参一个】（有的实参裸推）——实参=
            # 区域内扁平化。调用头可能是 `27 27` 双连标记（DISCTRL_FORM/rtn3 落锤）：
            # 嵌套调用的内层区起点 = 栈上【最后一个双连标记对的前一个】；
            # 劈在对的后一个会把头拆散 → 游离标记被 CAT 当操作数吞掉、外层实参错位
            # （SUB_STR 吞掉 xdat → 外层 PKT_ADD_DAT 实参变假 0/''）。
            _mpos = [i for i, it in enumerate(stack) if it == '<ARG>']
            if _mpos:
                _start = _mpos[0]
                for _j in range(1, len(_mpos)):
                    if _mpos[_j] == _mpos[_j - 1] + 1:
                        _start = _mpos[_j - 1]
                region = stack[_start:]
                stack = stack[:_start]
            else:
                region = []
            segs, cur = [], []
            for it in region:
                if it == '<ARG>':
                    if cur: segs.append(cur); cur = []
                else:
                    cur.append(it)
            if cur: segs.append(cur)
            a = [x for sg in segs for x in sg]
            if kind == 'CALLLOC':
                if collect:
                    call_args.setdefault(nm, []).append([arg_kind(x) for x in a[:24]])
            elif kind == 'CALLIMP':
                if collect:
                    imp_args.setdefault(nm, []).append([arg_kind(x) for x in a[:24]])
            else:
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
                    if _x >= len(kinds2):
                        break
                    if _k2 in ('ag', 'ar', 'ab', 'as', 'ai') and kinds2[_x] in ('i', 'b', 'r', 'f', 's'):
                        # std 判数组而推断只有标量形态（混样冲突降级实证）→ std 为准
                        # （DCP_HIST DISCTRL_FORM p2 'ag' 被降级 'i' → VALUE_ARRAY 被砸成 0）
                        kinds2[_x] = _k2
                    elif _k2 in ('ab', 'as', 'ar') and kinds2[_x] == 'ai':
                        # std 精确数组类型（BOOLEAN 数组/串数组）> 泛型数组证据 'ai'
                        # （INACT_ARRAY 被 'ai' 盖住 → 声明 ARRAY OF INTEGER 与内建 BOOLEAN 撞）
                        kinds2[_x] = _k2
                    elif _k2 in ('pos', 'jpos'):
                        # 位置形参权威盖过一切使用点证据——聚合/位置实参常被 arg_kind
                        # 误判 'ai'（元素访问形态），走"数组证据优先"会漏替换 → 类型不匹配
                        # （XYZ_MOTION cnv_jpos_rel(i__, ret, joint_data) 实证）
                        kinds2[_x] = _k2
                    elif kinds2[_x] not in ('as', 'ai') and _k2 not in ('ag', 'ar'):
                        kinds2[_x] = _k2  # 数组证据（元素访问实证）优先于 desc 走查
                kinds2 = kinds2[:want]
            while len(a) < want:
                a.append("''" if (len(kinds2) > len(a) and kinds2[len(a)] == 's') else '0')
            a = a[:want]
            a2 = []
            dropped = []
            for _x2 in range(len(a)):
                if re.match(r'^[A-Za-z_][\w.]*\[[^\]]+\](\[[^\]]+\])*$', str(a[_x2])):
                    a[_x2] = '(' + str(a[_x2]) + ')'  # KAREL：数组元素按值传需括号（ISRA_AV 实证）
            for x, arg in enumerate(a):
                k = kinds2[x] if x < len(kinds2) else 'i'
                orig = arg
                if k == 's' and not str_rhs(arg):
                    if re.match(r'^[A-Za-z_]\w*$', str(arg)) and not _is_par(arg) \
                            and str(arg) not in ('TRUE', 'FALSE') \
                            and not _thas(str(arg), 'a') and not _thas(str(arg), 'f') \
                            and not _thas(str(arg), 'r'):
                        # 串形参反推实参类型（签名权威）：旧分支一刀切抹成 ''，真名还原后
                        # 错型实参无法自愈（YAMAZUMI SUB_STR(TimeDate,1,2) 实证：TIMEDATE 真型
                        # STRING[18] 被推成 INTEGER，旧代码被通配名 fn21 掩盖）。形参类型为准，
                        # 标串保留；已有强证据（数组/文件/REAL）不翻案（弱证据不盖强证据）。
                        _tmark(str(arg), 's')
                    else:
                        arg = "''"   # 复合/未知表达式仍抹（保编译，is_str 认不出 (a+'b')）
                elif k == 'i' and re.match(r'^[A-Za-z_]\w*$', str(arg)) and _thas(str(arg), 'r'):
                    dropped.append(orig); arg = '0'  # REAL 实参入 INTEGER 形参弃参留痕
                elif k == 'i' and (str_rhs(arg) or re.search(r'[=<>]', arg)
                                   or (re.match(r'^[A-Za-z_]\w*$', str(arg))
                                       and (_thas(str(arg), 'a') or _thas(str(arg), 'f')))):
                    arg = '0'
                elif k == 'pos' and str(arg) != 'sv_p':
                    dropped.append(orig); arg = 'sv_p'
                elif k == 'jpos' and str(arg) != 'sv_j':
                    dropped.append(orig); arg = 'sv_j'
                elif k == 'ar':
                    # ARRAY OF REAL 形参（CNV_JPOS_REL/CNV_REL_JPOS 第2参，手册权威）：
                    # 整组实参（裸名）保留并反推 ARRAY OF REAL；元素/字面量/表达式替换 sv_a 留痕
                    _a = str(arg)
                    if re.match(r'^[A-Za-z_]\w*$', _a) and not _is_par(_a):
                        _tmark(_a, 'a'); _tmark(_a, 'r')
                    else:
                        dropped.append(orig); arg = 'sv_a'
                elif k == 'r' and _thas(str(arg), 's'):
                    dropped.append(orig); arg = '0.0'
                elif k in ('r', 's', 'f') and re.match(r'^[A-Za-z_]\w*$', str(arg)) \
                        and not _is_par(arg) and not _thas(str(arg), 'a'):
                    # std 形参类型反推实参变量类型（GET_REG 第4参 REAL 实证）
                    # 形参名跳过：类型码权威（_PAR_T），塞全局集会跨例程污染；
                    # 数组名跳过：整组传标量形参是错渲染，不该反向污染数组元素类型
                    # （MM_MODULE v80 被标 REAL → ARRAY OF REAL 撞 fn26 ARRAY OF INTEGER）
                    if k == 'r':
                        _tmark(str(arg), 'r')
                    elif k == 's':
                        _tmark(str(arg), 's')
                    else:
                        _tmark(str(arg), 'f')
                elif k in ('ai', 'as', 'ab') and re.match(r'^[A-Za-z_]\w*$', str(arg)) \
                        and not _is_par(arg):
                    _tmark(str(arg), 'a')
                    if k == 'as':
                        _tmark(str(arg), 'sa')
                    elif k == 'ab':
                        _tmark(str(arg), 'ba')
                elif k == 'b' and str(arg) not in ('TRUE', 'FALSE') and not re.search(r'[<>]', str(arg)) and not str(arg).startswith('UNINIT(') \
                        and not str_rhs(arg):
                    # BOOLEAN 形参：整型实参 (x <> 0) 包装（KAREL 双向都无隐式强转）
                    # 串实参不包装：`('' + '.DT' <> 0)` 是非法比较（MI04_SSW_MON DELETE_FILE 实证）
                    arg = '(' + str(arg) + ' <> 0)'
                if arg != orig:
                    dropped.append(orig)
                a2.append(arg)
            _std = STD_SIGS.get(nm.upper())
            if nm.upper() == _prog_s:
                lines.extend(_cmt_lines('-- 重入调用(名字表歧义): ', nm + '(' + ', '.join(a2) + ')'))
                dropped.append(nm + '(' + ', '.join(a2) + ')')
                stack.append('sv_i')
                continue
            _call = (nm + '(' + ', '.join(a2) + ')') if a2 else nm  # 0 参裸调用（r = Q 合法，Q() 非法）
            if nm in ('POST_ERR', 'SET_INT_REG', 'SET_REAL_REG') or (_std and _std[0] == 'v'):
                lines.append(_call)
                stack.append('0')
            else:
                # 返回类型与声明谓词一致（imports ret 高字节==0x1f 或名字启发式）——
                # 否则 desc 说 STRING、临时却用 sv_i : INTEGER → 类型不匹配
                # （DCPFAULT_MH GET_EPLANREF 实证）
                _ret = _std[0] if _std else (
                    's' if (imports.get(nm) == 0x1f or returns_str(nm)) else 'i')
                tgt = {'s': 'sv_s', 'pos': 'sv_p', 'jpos': 'sv_j',
                       'r': 'sv_r', 'b': 'sv_b'}.get(_ret, 'sv_i')
                lines.append(tgt + ' = ' + _call)
                stack.append(tgt)
            if dropped:
                lines.extend(_cmt_lines('-- 弃参原式: ', ' | '.join(dropped)))
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
            # 组名/变量名形参：串型判定用 str_rhs——`v13 + '.$COMMENT'` 是复合串表达式，
            # is_str 认不出会把整个变量名抹成 ''（mm_module '.$STATE'/'.$COMMENT' 残差根因）
            a[0] = '0' if str_rhs(a[0]) else a[0]
            if not str_rhs(a[1]):
                a[1] = "''"
            if not str_rhs(a[2]):
                a[2] = "''"
            a[4] = '0' if str_rhs(a[4]) else a[4]
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
            items = [str(x) for x in stack]
            if 1 <= len(items) <= 6 and re.match(r'^[A-Za-z_]\w*$', items[0]):
                stack = []
                _tmark(items[0], 'f')
                lines.append('OPEN FILE ' + items[0] + '(' + ', '.join(items[1:]) + ')')
            else:
                stack.append('0')
        elif kind == 'UNK':
            stack.append('0')
    return lines, (stack[-1] if stack else None), params, list(stack)

# 名字表形参签名是权威：ARITY/KINDS 覆盖调用点推断（形参字段类型错乱的根治）
# ⚠️ 必须在 pass-1 收集【之前】就位：收集期的实参类型回传（file_vars/str_vars 标记）
#    要按权威 kind 走，否则声明先于标记写出（ZJFILE : INTEGER 而真型 FILE 实证）。
#    推断循环之后还有一份（防推断覆盖），幂等。
for _r in routines:
    if _r.get('ptypes'):
        ARITY[_r['name']] = len(_r['ptypes'])
        KINDS[_r['name']] = [_pk(_t) for _t in _r['ptypes']]
for _nm2, _pt2 in import_ptypes.items():
    if _pt2:
        ARITY[_nm2] = len(_pt2)
        KINDS[_nm2] = [_pk(_t) for _t in _pt2]

# pass 1: 收集（跑两轮：字段/元素类型沿赋值链传播）
for _pass in range(2):
    for si, bis in sec_stmts.items():
        _CUR_SEC = si
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

# 名字表形参签名是权威：ARITY/KINDS 覆盖调用点推断（形参字段类型错乱的根治）
for _r in routines:
    if _r.get('ptypes'):
        ARITY[_r['name']] = len(_r['ptypes'])
        KINDS[_r['name']] = [_pk(_t) for _t in _r['ptypes']]
for _nm2, _pt2 in import_ptypes.items():
    if _pt2:
        ARITY[_nm2] = len(_pt2)
        KINDS[_nm2] = [_pk(_t) for _t in _pt2]
# 通配名（FN 族 id 未映射 / 名字表失配兜底）身份不确定 → 数组形态压回 'i'（弃参留痕），
# 标量类型（s/r/f/b）保留。数组形态精确化会与混样实参相撞（MM_MODULE fn26=CNV_REL_JPOS：
# 首参 ARRAY OF REAL + JOINTPOS 聚合实参被扁平化拆散，INT/REAL 数组混样即此错；旧注释
# "fn26=Sock_Send" 是误读——fn26=CNV_REL_JPOS、fn17=ROUND）；但标量类型不能压——
# fn17=ROUND 的实参是 REAL（r1_lc25 * 1000），压成 INTEGER 反而撞（实证）。
for _wn in list(KINDS):
    if re.match(r'^(?:rtn|fn|imp)\d+x?$', _wn):
        KINDS[_wn] = [_k if _k in ('s', 'r', 'f', 'b') else 'i' for _k in KINDS[_wn]]

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
        jmp_only = bool(kinds) and ('JMP' in kinds) and all(k in ('JMP', 'INT', 'VAR', 'ARG', 'NOP', 'UNK', 'PAR', 'SEL40', 'SEL41', 'SEL42', 'SEL43') for k in kinds)
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
    # ⚠️ 签名是 5 字节 `7f 00 00 00 ff` + u16BE count——旧签名含尾 00，
    # 那个 00 其实是 count 高字节：count≥256（dcp_spr1_1 322 子句）时签名失配、
    # 跳表整体解析为空 → SELECT 收口/REPEAT 全瞎（「共锚点消歧未解」的最深根因）
    pos = dec.find(b'\x7f\x00\x00\x00\xff')
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
    _offset = set(_offs)
    # 基址打分：跳转目标 = 锚点（语句首）【或 SELECT 子句头/ELSE 标记（40/43，落在体中）
    # 或锚点前 1 字节（43 紧贴锚点）】——旧打分只认锚点，PROBE7 里目标指向子句头时
    # 错基址凭两个巧合锚点 2:1 赢过真基址（ENDSELECT 不落、SELECT 结构全错的根因）。
    _best, _bestn = None, -1
    for _b in range(0, 0x200):
        _hit = 0
        for _ti, t in enumerate(_JT):
            _q = t + _b
            if not (0 <= _q < N):
                continue
            # 严格形态：目标= `40 00 00 00 <u32>` 子句头 / `43 3e` ELSE 头 / 锚点。
            # 松判（任意 0x40/0x43 字节 + 锚点邻接）会被字符串区假锚点灌分——
            # dcp_spr1_1 323 项目标错基址 960 vs 真基址 650 的翻车实证。
            _strict = ((dec[_q] == 0x40 and _q + 5 <= N
                        and int.from_bytes(dec[_q + 1:_q + 5], 'big') <= 0xffff)
                       or (dec[_q] == 0x43 and _q + 1 < N and dec[_q + 1] == 0x3e))
            if _strict:
                _hit += 4
            elif _q in _offset:
                # 表[0] = 公共收口（ENDSELECT）必落锚点，加权定盘
                _hit += 8 if _ti == 0 else 1
        if _hit > _bestn:
            _best, _bestn = _b, _hit
    if _bestn >= max(1, len(_JT) // 4):
        _JT_BASE = _best

def _jt_stmt(targets_off):
    # 目标偏移 → bodies 序。目标可能落在锚点上（语句首）或体中（SELECT 子句头），
    # 取 ≥ 目标的首个锚点体。⚠️ 返回 bodies 索引不是 markers 索引——旧版两者混用，
    # 一体多子句（锚点丢失合并）时 REPEAT/SELECT_ENDS 判定整体错位。
    for k, (_l, _o, _s, _ie, _id) in enumerate(bodies):
        if _o >= targets_off:
            return k
    return None

# 每语句的 JZ/JMP 目标语句号
JZ_TO, JMP_TO = {}, {}
if _JT_BASE is not None:
    for _bi, (_lid, _off, _toks, _ie, _id) in enumerate(bodies):
        for _t in _toks:
            if _t[1] in ('JZ', 'JMP') and isinstance(_t[2], int) and _t[2] < len(_JT):
                _tgt = _jt_stmt(_JT[_t[2]] + _JT_BASE)
                if _tgt is not None:
                    (JZ_TO if _t[1] == 'JZ' else JMP_TO)[_bi] = _tgt
# SELECT 收口点：select 语句内 JMP 的跳转目标 = ENDSELECT 处（跳转表精确落点）
SELECT_ENDS = set()
for _bi2, (_l2, _o2, _tk2, _ie2, _id2) in enumerate(bodies):
    if any(t[1] in ('SEL40', 'SEL41', 'SEL42', 'SEL43') for t in _tk2) and any(t[1] == 'JMP' for t in _tk2):
        if _bi2 in JMP_TO:
            SELECT_ENDS.add(JMP_TO[_bi2])

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

# 类型标记预热：KINDS/ARITY 就位后重跑一遍发射求值，让实参类型回传
# （file/str/arr/bool_vars 标记）在【声明写出前】完成——声明先于发射，
# 标记晚到就会写出错误类型（ZJFILE : INTEGER 而真型 FILE、
# INACT_ARRAY : ARRAY OF INTEGER 而真型 BOOLEAN 实证）。
for _si3, _bis3 in sec_stmts.items():
    _CUR_SEC = _si3
    for _bi3 in _bis3:
        eval_expr(bodies[_bi3][2])

BUILTIN = {'POST_ERR', 'SET_INT_REG', 'SET_REAL_REG', 'GET_REG', 'DB_PROMPT', 'CALL_PROG'}

# 形参签名引用到的结构体类型（含传递依赖）→ TYPE 块按需发射
_used_tidx = set()


def _mark_tidx(idx, depth=0):
    if depth > 6 or idx is None or idx >= len(_TYPES) or idx in _used_tidx:
        return
    _used_tidx.add(idx)
    for _fn, _t0, _t1, _dim in _TYPES[idx][1]:
        if _t0 == 0x11:
            _mark_tidx(_t1, depth + 1)


for _r in routines:
    for _t in (_r.get('ptypes') or []):
        if _t[0] == 0x11:
            _mark_tidx(_t[1])
for _pt in import_ptypes.values():
    for _t in _pt:
        if _t[0] == 0x11:
            _mark_tidx(_t[1])
for _ti in _STRUCT_TYPE_IDX.values():
    _mark_tidx(_ti)      # 符号表结构体变量的声明也要 TYPE 块支撑
with open(out_path, 'w', encoding='gbk', errors='replace') as f:
    f.write('-- ' + os.path.basename(out_path) + ' (decompiled v3)\n')
    f.write('PROGRAM ' + name + '\n')
    f.write("%%COMMENT = '%s'\n" % (_hdr_comment.replace("'", "''")))
    f.write('%NOBUSYLAMP\n%NOLOCKGROUP\n%NOPAUSE = COMMAND + TPENABLE + ERROR\n%NOABORT = ERROR + COMMAND\n')
    # TYPE 块：结构体类型真名+真字段名（probe_symenc 定的编码，字段名不再退化成 _f<偏移>）
    # 默认只发形参签名引用到的类型（含传递依赖）；P2K_FIELDS 实验模式发全量
    _emit_types = [_TYPE_DECLS[_i] for _i in sorted(_used_tidx)] if not _P2K_FIELDS else _TYPE_DECLS
    if _emit_types:
        f.write('TYPE\n')
        # POSITION/JOINTPOS 是内建类型、无命名字段，.X 访问非法。
        # 渲染成同形结构体（X/Y/Z/W/P/R），使字段访问合法且语义等价
        f.write('\tT_POS = STRUCTURE\n\tX: INTEGER\n\tY: INTEGER\n\tZ: INTEGER\n'
                '\tW: INTEGER\n\tP: INTEGER\n\tR: INTEGER\n\tENDSTRUCTURE\n')
        for _tn, _fs in _emit_types:
            f.write('\t%s = STRUCTURE\n' % _tn)
            for _fn, _t0, _t1, _dim in _fs:
                if _t0 == 0x1f:
                    _tt = 'STRING[%d]' % max(_t1, 1)
                elif _t0 == 0x3f:
                    # ARRAY[n] OF STRING[len]：3f <len u8> <n u16>
                    _tt = 'ARRAY[%d] OF STRING[%d]' % (max(_dim or 1, 1), max(_t1, 1))
                elif _t0 == 0x20:
                    _tt = 'ARRAY[%d] OF %s' % (max(_dim or 1, 1),
                                               {0x10: 'INTEGER', 0x11: 'REAL',
                                                0x12: 'BOOLEAN', 0x1f: 'STRING[64]'}.get(_t1, 'INTEGER'))
                elif (_t0, _t1) in ((0x01, 0x02), (0x01, 0x03)):
                    _tt = 'T_POS'      # 用同形结构体替代内建 POSITION，.X 等字段访问才合法
                elif _t0 == 0x11 and _t1 < len(_TYPE_DECLS):
                    _tt = _TYPE_DECLS[_t1][0]
                else:
                    _tt = {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN',
                           0x1d: 'FILE'}.get(_t0, 'INTEGER')
                f.write('\t%s: %s\n' % (_fn, _tt))
            f.write('\tENDSTRUCTURE\n')
    f.write('VAR\n')
    for nm in sorted(io_vars):
        f.write('  %s : ARRAY[512] OF INTEGER\n' % nm)
    for n in range(1, n_v):
        f.write('  %s : %s\n' % (vn('v', n), vtype(vn('v', n))))
    # 符号表里有、但代码零引用的变量（声明未用）也要补上——保真要求源码声明全在。
    # ⚠️ 要从 _SYMS 取，不能只用 SHV_NAMES：声明未用的变量不占槽位、进不了槽映射
    #    （ISV_VG 实证：_SYMS 14 名含 TIMER1，SHV_NAMES 只 13 个，TIMER1 被漏）
    # 未引用者无代码证据，类型直接取符号表（t0/t1/dim），比 vtype() 的默认 INTEGER 准
    def _symtype(t0, t1, dim):
        if t0 == 0x1f:
            return 'STRING[%d]' % max(t1, 1)
        if t0 == 0x3f:
            return 'ARRAY[%d] OF STRING[%d]' % (max(dim or 1, 1), max(t1, 1))
        if t0 == 0x20:
            _el = {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x1f: 'STRING'}.get(t1, 'INTEGER')
            return 'ARRAY[%d] OF %s' % (max(dim or 1, 1), _el)
        if (t0 >> 4) >= 2:
            return 'ARRAY[64] OF INTEGER'
        return {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x1d: 'FILE'}.get(t0, 'INTEGER') \
            if t0 in (0x10, 0x11, 0x12, 0x1d) else \
            {0x10: 'INTEGER', 0x11: 'REAL', 0x12: 'BOOLEAN', 0x1d: 'FILE'}.get(t1, 'INTEGER')
    # ⚠️ KAREL 不分大小写：比对必须统一大写，否则 'V8' 会绕过 'v8' 的已声明检查 → 重复声明
    _emitted = {vn('v', n).upper() for n in range(1, n_v)}
    for _s in _SYMS:
        _nm = _s[0]
        if _nm.upper() in _emitted or _nm.upper() in ('SV_I', 'SV_S', 'SV_P', 'SV_J', 'SV_R', 'SV_B', 'SV_A'):
            continue
        _emitted.add(_nm.upper())
        f.write('  %s : %s\n' % (_nm, _symtype(_s[1], _s[2], _s[3])))
    # 例程局部槽位不再进程序级 VAR：改由各例程自己的 VAR 块声明（作用域独立，
    # 避免不同例程同槽位不同类型互相污染——ISV_VG lc2 实证）
    # 字段合成名/派生数组名（v<n>_f<off> 等）补声明
    def _covered(nm):
        nm2 = nm[2:] if nm.startswith('zz') else nm
        if re.match(r'^r\d+_lc\d+$', nm2) or nm2.upper() in _MAPPED_UP:
            return True   # 例程局部（合成名/映射真名）已由各例程 VAR 块声明，勿重复
        m = re.match(r'^v(\d+)$', nm2)
        if m:
            return int(m.group(1)) < n_v
        m = re.match(r'^lc(\d+)$', nm2)
        if m:
            return int(m.group(1)) < max_lc
        return False
    _declared_syms = set(SHV_NAMES.values())
    extras = {nm for nm in (fld_vars | arr_vars | str_vars | real_vars | par_vars) if nm not in _declared_syms
              if nm.upper() not in ('SV_I', 'SV_S', 'SV_P', 'SV_J', 'SV_R', 'SV_B', 'SV_A')
              if not _covered(nm) and not re.match(r'^p\d+$', nm) and re.match(r'^[A-Za-z_]\w*$', nm)}
    for nm in sorted(extras):
        f.write('  %s : %s\n' % (nm, vtype(nm)))
    main_decls = set()
    for si2, bis2 in sec_stmts.items():
        _CUR_SEC = si2
        if si2 >= len(routines):
            for bi2 in bis2:
                _lid, _off, _toks, _ie, _id = bodies[bi2]
                _l, _e, pp, _s = eval_expr(_toks)
                main_decls |= pp
    for d in sorted(main_decls):
        if re.match(r'^pp[0-9a-f]{2}$', d):
            continue  # 参数合成名已由 extras 按类型声明
        f.write('  %s : INTEGER\n' % d)
    f.write('  sv_i : INTEGER\n  sv_s : STRING[64]\n  sv_p : POSITION\n  sv_j : JOINTPOS\n'
            '  sv_r : REAL\n  sv_b : BOOLEAN\n  sv_a : ARRAY[9] OF REAL\n')
    f.write('\n')
    # 野名字（RTN*/FN* 等动态槽位）自动补外部声明
    used = set()
    for si2, bis2 in sec_stmts.items():
        _CUR_SEC = si2
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
        if import_ptypes.get(nm):
            plist = fmt_ptypes(import_ptypes[nm])   # 名字表签名权威
        else:
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
    _NODECL = {'sv_i', 'sv_s', 'sv_p', 'sv_j', 'sv_r', 'sv_b', 'sv_a'} \
        | set(_FN_NAMES.values())   # 内建名/累加器 KTRANS 原生或已声明，免自动补声明
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
        _CUR_SEC = si
        bis = sec_stmts[si]
        _rev = {b2: b1 for b1, b2 in zip(bis, bis[1:])}
        if si < len(routines):
            r = routines[si]
            if r.get('ptypes'):
                plist = fmt_ptypes(r['ptypes'])   # 名字表签名权威（不再按调用点加码元数）
            else:
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
        _locs = set()
        for bi in bis:
            lid, off, toks, is_empty, is_data = bodies[bi]
            _, _, p, _s = eval_expr(toks)
            declp |= p
            for _t in toks:
                if _t[1] == 'VAR' and _t[2][1] == 'l':
                    _locs.add(vn('l', _t[2][2]))   # 例程局部 → 各例程 VAR 块独立声明
        declp2 = [d for d in sorted(declp) if not re.match(r'^(?:pp[0-9a-f]{2}|p\d+)$', d)] + sorted(_locs)
        if declp2 and si < len(routines):
            f.write('VAR\n')
            for d in declp2:
                f.write('  %s : %s\n' % (d, vtype(d)))
        f.write('BEGIN\n')
        _sel_open = False
        _sel_base_depth = 0

        def _sel_drain():
            # 共锚点：「ENDIF 空锚点」可能与下个子句头合并（体带 SEL 标记非空），
            # "空锚点=ENDIF" 规则落空 → IF 跨进下一个 CASE。子句边界收拢未闭块。
            # ⚠️ 只收 SELECT 开启【后】新增的块：外层 IF 包裹 SELECT（IF…SELECT…
            # ENDSELECT…ENDIF，MI04_SSW_ROUT 实证）时外层 IF 必须活过整个 SELECT。
            while len(open_blocks) > _sel_base_depth:
                _b = open_blocks.pop()
                f.write('  %s\n' % {'if': 'ENDIF', 'while': 'ENDWHILE',
                                    'for': 'ENDFOR'}.get(_b, 'ENDIF'))
        _sel_case_buf = []   # 共锚点多值 CASE：相邻 SEL41 值聚成一行（T_CASE 探针定语法）
        _sel_clause_seen = False   # 已落过 CASE 行 → 后续子句边界可收拢未闭块（护外层 IF）
        open_blocks = []          # 段内块平衡栈: 'if'/'while'/'for'
        for bi in bis:
            lid, off, toks, is_empty, is_data = bodies[bi]
            kinds = [t[1] for t in toks]
            if _sel_open and bi in SELECT_ENDS:
                # SELECT 收口统一在体开头落：目标体可能是空锚点、下一个 SELECT 的
                # 子句头（共锚点，MI04_SSW 串联 SELECT 实证）或普通语句体
                if _sel_case_buf:
                    f.write('  CASE(%s):\n' % ', '.join(str(v) for v in _sel_case_buf))
                    _sel_case_buf = []
                _sel_drain()
                f.write('  ENDSELECT\n')
                _sel_open = False
            if any(k in kinds for k in ('SEL40', 'SEL41', 'SEL42', 'SEL43')):
                if bi in REPEAT_HEADS:
                    f.write('  REPEAT\n')
                if bi in UNTIL_AT:
                    _uc = expr if False else None
                _SELM = {'SEL40', 'SEL41', 'SEL42', 'SEL43'}
                _idxs = [x for x, t in enumerate(toks) if t[1] in _SELM]
                _bounds = [0] + _idxs + [len(toks)]
                _last_expr = None
                _seg_written = []
                for _bi3 in range(len(_bounds) - 1):
                    _seg = toks[_bounds[_bi3]:_bounds[_bi3 + 1]]
                    if _seg and _seg[-1][1] == 'JMP':
                        _seg = _seg[:-1]
                    if _seg:
                        if _sel_case_buf:
                            # 标签在前体在后（共锚点：体尾带下一句头）——先落 CASE 行
                            if _sel_clause_seen:
                                _sel_drain()
                            f.write('  CASE(%s):\n' % ', '.join(str(v) for v in _sel_case_buf))
                            _sel_case_buf = []
                            _sel_clause_seen = True
                        _ls, _ex, _pp, _st = eval_expr(_seg)
                        for _l in _ls:
                            _wline(f, _l)
                            _seg_written.append(_l)
                        if _ex and _ex != '0':
                            _last_expr = _ex
                    if _bounds[_bi3 + 1] < len(toks):
                        _mk = toks[_bounds[_bi3 + 1]]
                        if _mk[1] == 'SEL41':
                            if not _sel_open:
                                # 串联 SELECT：子句头可带前段尾跳（共锚点），不能因 JMP 前缀不开句
                                f.write('  SELECT %s OF\n' % (_last_expr or 'sv_i'))
                                _sel_open = True
                                _sel_clause_seen = False
                                _sel_base_depth = len(open_blocks)   # 外层包裹块不许收
                            if _sel_open:
                                _sel_case_buf.append(_mk[2])   # 多值 CASE 聚行（T_CASE: CASE(7, 8, 9):）
                        elif _mk[1] == 'SEL42' and _sel_open:
                            if _sel_case_buf:
                                if _sel_clause_seen:
                                    _sel_drain()
                                f.write('  CASE(%s):\n' % ', '.join(str(v) for v in _sel_case_buf))
                                _sel_case_buf = []
                                _sel_clause_seen = True
                        elif _mk[1] == 'SEL43' and _sel_open:
                            if _sel_case_buf:
                                if _sel_clause_seen:
                                    _sel_drain()
                                f.write('  CASE(%s):\n' % ', '.join(str(v) for v in _sel_case_buf))
                                _sel_case_buf = []
                                _sel_clause_seen = True
                            if _sel_clause_seen:
                                _sel_drain()
                            f.write('  ELSE:\n')
                        # SEL40 = 子句头（失败跳表指针，纯字节码控制流，无源码对应）
                if bi in UNTIL_AT and _last_expr:
                    f.write('  UNTIL(' + _last_expr + ')\n')
                # ⚠️ _seg_written 是 list，而 _emit_residue 用 written.count(子串) 判在场：
                #    list.count 是"元素全等"、str.count 才是"子串"——传 list 会让在场数恒为 0，
                #    把已渲染的字面量全误报成残差（MM:VISION_*=1001 一族假阳性根因）。
                _emit_residue(f, toks, ' '.join(_seg_written), lid)
                continue
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
                if _sel_open and not SELECT_ENDS and n_close_if.get(bi, 0) == 0:
                    # 兜底：跳表失效（SELECT_ENDS 空）时按旧口径在空锚点收口
                    if _sel_case_buf:
                        f.write('  CASE(%s):\n' % ', '.join(str(v) for v in _sel_case_buf))
                        _sel_case_buf = []
                    _sel_drain()
                    f.write('  ENDSELECT\n')
                    _sel_open = False
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
                _emit_residue(f, toks, '', lid)
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
                    _wline(f, l)
                f.write('  FOR %s = %s TO 3 DO\n' % (forvar, init))
                open_blocks.append('for')
                continue
            if bi in else_lines:
                if open_blocks and open_blocks[-1] == 'if':
                    f.write('  ELSE\n')
                _emit_residue(f, toks, '', lid)
                continue
            if bi in UNTIL_AT:
                cond = expr if expr and expr != '0' else 'TRUE'
                if cond != 'TRUE' and not re.search(r'[=<>]', cond) and not cond.startswith('UNINIT(') and not cond.startswith('NOT ('):
                    cond = '(' + cond + ' <> 0)'
                f.write('  UNTIL(' + cond + ')\n')
                _emit_residue(f, toks, '', lid)
                continue
            if 'JZ' in kinds:
                cond = expr if expr and expr != '0' else 'TRUE'
                if cond != 'TRUE' and not re.search(r'[=<>]', cond) and not cond.startswith('UNINIT(') and not cond.startswith('NOT (') and not _thas(cond, 'b'):
                    cond = '(' + cond + ' <> 0)'
                if close_of.get(bi, (None, ''))[1] == 'while':
                    _wline(f, 'WHILE (%s) DO' % cond)   # 长条件按顶层运算符续行（256 上限）
                    open_blocks.append('while')
                else:
                    _wline(f, 'IF (%s) THEN' % cond)
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
                _wline(f, l)
            _stray = [str(x) for x in stk if str(x) not in ('0', '<ARG>')]   # 引导标记是元数据不是值
            if _stray:
                _cmt_write(f, '  -- stmt%d stray ' % lid, ' | '.join(_stray))
            _emit_residue(f, toks, ' '.join(cleaned) + ' ' + ' '.join(_stray), lid)
        while open_blocks:
            k = open_blocks.pop()
            f.write('  %s\n' % {'if': 'ENDIF', 'while': 'ENDWHILE', 'for': 'ENDFOR'}[k])
        if si < len(routines):
            f.write('  RETURN(0)\n')
        if _sel_open:
            # 段尾兜底收口：收口体被切到别的段/丢失时，SELECT 不能挂到 END 例程
            # （MI04_SSW_GUI ST_MACHINE 实证）。正常路径已在体开头收口，这里只兜漏。
            if _sel_case_buf:
                f.write('  CASE(%s):\n' % ', '.join(str(v) for v in _sel_case_buf))
                _sel_case_buf = []
            _sel_drain()
            f.write('  ENDSELECT\n')
            _sel_open = False
        f.write('END %s\n\n' % (routines[si]['name'] if si < len(routines) else name))
    if not any(si >= len(routines) for si in sec_stmts):
        f.write('BEGIN\nEND %s\n' % name)

# 模块级字面量残差兜底（分支出口遗漏清零）
_budget = {}
for _lid, _off, _toks, _ie, _idd in bodies:
    if _idd:
        continue
    for _t in _toks:
        if _t[1] == 'STR':
            _k = repr(_t[2])
        elif _t[1] == 'INT' and 1000 <= abs(_t[2]) <= 99999:
            _k = str(_t[2])
        else:
            continue
        _budget[_k] = _budget.get(_k, 0) + 1
_txt = open(out_path, encoding='gbk', errors='replace').read()
_missing = []
for _k, _n in _budget.items():
    for _ in range(_n - _txt.count(_k)):
        _missing.append(_k)
if _missing:
    with open(out_path, 'a', encoding='gbk', errors='replace') as _f:
        _f.write('-- module-residue ' + ', '.join(_missing) + chr(10))
print('wrote', out_path, 'routines:', len(routines), 'sections:', len(sec_stmts))
