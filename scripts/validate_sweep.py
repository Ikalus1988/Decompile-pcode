# -*- coding: utf-8 -*-
# validate_sweep.py — 深度横扫验证：真源码 × 产物(dec/KL/重编译pc) 三层校验
# 用法: python -I validate_sweep.py <src_dir> <dec_dir> <kl_dir> [report.txt]
# 列：串缺/常缺（KL 覆盖，多重集）| 源码缺（真源码串保真）| 锚点/渲染 + RT回环
import os, re, sys, subprocess, collections, tempfile

KTRANS = r'D:\program\roboguide\WinOLPC\bin\ktrans.exe'
DECOMP = r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\scripts\pc_decompress.mjs'

def dec_strings(dec, windowed=True, dedup=True):
    """windowed=True：语句体窗口口径（dec→KL 覆盖，剔数据区）。
    windowed=False：全文件多重集（RT 保真口径）。
    ⚠️ 第4坑：'body>800B=数据区' 是布局相关的——重编译产物语句体更密，
    真代码会被当数据区剔掉，把在场字面量误判成丢失（mm_module 实测 12/21 误剔）。
    故 RT 对拍两侧必须同用 windowed=False。"""
    raw = collections.Counter()
    N = len(dec)
    offs = [m.start() for m in re.finditer(rb'\x3e[\x00-\x05](.)', dec) if m.start() + 5 <= N]
    ranges = []
    if windowed:
        for i, off in enumerate(offs):
            end = offs[i + 1] if i + 1 < len(offs) else N
            body = dec[off + 5:end]
            if len(body) > 800 or off < 0x30:
                continue  # 数据区（表/名字堆）不计——与流水线覆盖契约一致
            ranges.append((off + 5, end))
    else:
        ranges = [(0, N)]
    for a, b in ranges:
        # 第6坑：finditer 非重叠推进，遇到 `3f 3f <len>`（0x3f 既是 STR 标记又是
        # 前邻 opcode/长度字节）会把真长度字节当长度吞掉 63 字节，串抽不出来。
        # 改逐字节滑动 + 候选校验：不成立只前进 1 字节，永不吞掉下一个真标记。
        i = a
        while i + 2 <= b:
            if dec[i] == 0x3F:
                ln = dec[i + 1]
                s = dec[i + 2:i + 2 + ln]
                if ln and len(s) == ln and re.match(rb'^[ -~]*$', s) and re.search(rb'[A-Za-z]{3}', s):
                    raw[s.decode()] += 1
                    i += 2 + ln
                    continue
            i += 1
    keys = list(raw)
    out = collections.Counter()
    if dedup:
        for k in keys:
            if any(k != o and (k in o or k[1:] in o or k[2:] in o) for o in keys):
                continue  # 长串子串/'?'头假候选（0x3f 误读）剔除
            out[k] = raw[k]
    else:
        out = raw
    return out

def sym_dedup(ca, cb):
    """第5坑：子串去重逐文件算会不对称（两侧字面量环境不同→去重结果不同→假丢失）。
    对拍两侧必须对【并集】对称去重，再比较。"""
    keys = set(ca) | set(cb)
    drop = set()
    for k in keys:
        if any(k != o and (k in o or k[1:] in o or k[2:] in o) for o in keys):
            drop.add(k)
    return ({k: v for k, v in ca.items() if k not in drop},
            {k: v for k, v in cb.items() if k not in drop})

def dec_consts(dec, windowed=True):
    out = collections.Counter()
    N = len(dec)
    offs = [m.start() for m in re.finditer(rb'\x3e[\x00-\x05](.)', dec) if m.start() + 5 <= N]
    ranges = []
    if windowed:
        for i, off in enumerate(offs):
            end = offs[i + 1] if i + 1 < len(offs) else N
            body = dec[off + 5:end]
            if len(body) > 800 or off < 0x30:
                continue
            ranges.append((off + 5, end))
    else:
        ranges = [(0, N)]
    for a, b in ranges:
        for m in re.finditer(rb'\x2e\x00\x00(..)', dec[a:b], re.S):
            v = int.from_bytes(m.group(1), 'big')
            if 1000 <= v <= 99999:
                i0 = a + m.start()
                up, un = dec[i0-4:i0], dec[i0+4:i0+8]
                if len(up) == 4 and up[1:3] == b'\x00\x00' and len(un) == 4 and un[1:3] == b'\x00\x00':
                    continue  # 分派表步进伪影
                out[str(v)] += 1
    return out

def kl_strings(kl):
    return collections.Counter(re.findall(r"'([^']*)'", kl))

def anchor_count(dec):
    return len(re.findall(rb'\x3e[\x00-\x05].', dec))

def kl_body_lines(kl):
    n = 0
    for ln in kl.splitlines():
        t = ln.strip()
        if t and not t.startswith('--') and not re.match(r'^(PROGRAM|VAR|BEGIN|END|ROUTINE|%)', t):
            n += 1
    return n

def mset_missing(need, have):
    miss = {}
    for k, v in need.items():
        d = v - have.get(k, 0)
        if d > 0:
            miss[k] = d
    return miss

def main():
    src_dir, dec_dir, kl_dir = sys.argv[1:4]
    rep_path = sys.argv[4] if len(sys.argv) > 4 else os.path.join(kl_dir, 'deep_sweep.txt')
    rows = []
    for df in sorted(os.listdir(dec_dir)):
        if not df.endswith('.dec'):
            continue
        stem = re.sub(r'\.pc\.dec$', '', df, flags=re.I)
        kl_path = os.path.join(kl_dir, stem.upper() + '.KL')
        if not os.path.exists(kl_path):
            kl_path = os.path.join(kl_dir, stem + '.KL')
        if not os.path.exists(kl_path):
            rows.append((stem, 'NO_KL', '-', ''))
            continue
        dec = open(os.path.join(dec_dir, df), 'rb').read()
        kl = open(kl_path, encoding='gbk', errors='replace').read()
        ds, dc = dec_strings(dec), dec_consts(dec)
        ks = kl_strings(kl)
        miss_s = mset_missing(ds, ks)
        miss_c = mset_missing(dc, collections.Counter(re.findall(r'\b(\d{4,5})\b', kl)))
        src_path = os.path.join(src_dir, stem + '.kl')
        if not os.path.exists(src_path):
            src_path = os.path.join(src_dir, stem.upper() + '.KL')
        src_miss = {}
        drift = 0
        if os.path.exists(src_path):
            src_txt = open(src_path, encoding='utf-8', errors='replace').read()
            src_s = kl_strings(src_txt)
            drift = sum(mset_missing(src_s, ds).values())
            src_miss = {}
            for k, v in src_s.items():
                ref = min(v, ds.get(k, 0))   # 真丢失口径 = min(源码,dec) 中产物缺的
                d = ref - ks.get(k, 0)
                if d > 0:
                    src_miss[k] = d
        n_anch, n_body = anchor_count(dec), kl_body_lines(kl)
        rt = ''
        with tempfile.TemporaryDirectory() as td:
            r = subprocess.run([KTRANS, kl_path, os.path.join(td, 'rt.pc')], capture_output=True, text=True, timeout=120)
            if 'Translation successful' in (r.stdout + r.stderr) and os.path.exists(os.path.join(td, 'rt.pc')):
                subprocess.run(['node', DECOMP, td, os.path.join(td, 'rt.pc')], capture_output=True, timeout=60)
                outs = [x for x in os.listdir(td) if x.endswith('.dec')]
                if outs:
                    rt_dec = open(os.path.join(td, outs[0]), 'rb').read()
                    # RT 保真口径 = 【原始字节计数】，不用扫描器抽串做判据：
                    #   扫描器有 0x3f 标记歧义（finditer 非重叠吞标记 / 滑动贪心吃假候选
                    #   吞真标记），两侧扫描不对称就会造出假丢失。字面量"在不在"
                    #   唯一诚实的判据是字节计数。扫描器只用来【定哪些字面量要看】。
                    # 串：变长 `3f<len>` 标记有歧义（见上），用字节计数判"在不在"
                    rt_s = {}
                    for k, v in dec_strings(dec, windowed=False).items():
                        d = v - rt_dec.count(k.encode('latin-1', 'replace'))
                        if d > 0:
                            rt_s[k] = d
                    # 常量：定宽 `2e <u32BE>`，无变长歧义 → 直接两侧对称扫（更准）
                    #   ⚠️ 不要用 ASCII 数字计数（'1000' 数的是含这四位的串，非常量）
                    #   也不要用 2e 00 00 <u32>（多拼一个 00，6 字节永远匹配不上）
                    rt_c = mset_missing(dec_consts(dec, windowed=False),
                                        dec_consts(rt_dec, windowed=False))
                    rt = 'RT丢串%d丢常%d' % (sum(rt_s.values()), sum(rt_c.values()))
                else:
                    rt = 'RT解包失败'
            else:
                rt = 'RT编译失败'
        rows.append((stem, '串缺%d/常缺%d' % (sum(miss_s.values()), sum(miss_c.values())),
                     '真丢%d/漂移%d' % (sum(src_miss.values()), drift),
                     '锚%d/渲%d %s' % (n_anch, n_body, rt)))
        if miss_s or miss_c or src_miss:
            rows.append((stem + '  .detail', str(list(miss_s.items())[:4]), str(list(miss_c.items())[:4]), 'src:' + str(list(src_miss.items())[:4])))
    with open(rep_path, 'w', encoding='utf-8') as f:
        f.write('# deep sweep %s\n' % dec_dir)
        for r in rows:
            f.write('  %-24s %-16s %-12s %s\n' % r)
    print('report:', rep_path)
    for r in rows:
        print('  %-24s %-16s %-12s %s' % r)

main()
