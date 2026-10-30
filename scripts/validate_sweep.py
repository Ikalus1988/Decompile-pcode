# -*- coding: utf-8 -*-
# validate_sweep.py — 深度横扫验证：真源码 × 产物(dec/KL/重编译pc) 三层校验
# 用法: python -I validate_sweep.py <src_dir> <dec_dir> <kl_dir> [report.txt]
# 列：串缺/常缺（KL 覆盖，多重集）| 源码缺（真源码串保真）| 锚点/渲染 + RT回环
import os, re, sys, subprocess, collections, tempfile

KTRANS = r'D:\program\roboguide\WinOLPC\bin\ktrans.exe'
DECOMP = r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\scripts\pc_decompress.mjs'

def dec_strings(dec):
    raw = collections.Counter()
    N = len(dec)
    offs = [m.start() for m in re.finditer(rb'\x3e[\x00-\x05](.)', dec) if m.start() + 5 <= N]
    for i, off in enumerate(offs):
        end = offs[i + 1] if i + 1 < len(offs) else N
        body = dec[off + 5:end]
        if len(body) > 800 or off < 0x30:
            continue  # 数据区（表/名字堆）不计——与流水线覆盖契约一致
        for m in re.finditer(rb'\x3f([\x00-\xff])', body):
            ln = m.group(1)[0]
            s = body[m.end():m.end() + ln]
            if len(s) == ln and re.match(rb'^[ -~]*$', s) and re.search(rb'[A-Za-z]{3}', s):
                raw[s.decode()] += 1
    keys = list(raw)
    out = collections.Counter()
    for k in keys:
        if any(k != o and (k in o or k[1:] in o or k[2:] in o) for o in keys):
            continue  # 长串子串/'?'头假候选（0x3f 误读）剔除
        out[k] = raw[k]
    return out

def dec_consts(dec):
    out = collections.Counter()
    N = len(dec)
    offs = [m.start() for m in re.finditer(rb'\x3e[\x00-\x05](.)', dec) if m.start() + 5 <= N]
    for i, off in enumerate(offs):
        end = offs[i + 1] if i + 1 < len(offs) else N
        body = dec[off + 5:end]
        if len(body) > 800 or off < 0x30:
            continue
        for m in re.finditer(rb'\x2e\x00\x00(..)', body, re.S):
            v = int.from_bytes(m.group(1), 'big')
            if 1000 <= v <= 99999:
                i0 = m.start()
                up, un = body[i0-4:i0], body[i0+4:i0+8]
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
                    rt_s = mset_missing(ds, dec_strings(rt_dec))
                    rt_c = mset_missing(dc, dec_consts(rt_dec))
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
