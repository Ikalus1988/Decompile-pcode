# -*- coding: utf-8 -*-
# fn_census.py — FN 族（`76 <id>`）id→真名 投票普查（P2 缺口：FN 族 id→真名）
# 方法: (源码.kl ↔ .pc.dec) 配对 → 3e 锚点行号定位语句 → FN token 站点 ↔ 源码行函数名候选 投票。
#   - 锚点编码 `3e <行号 u16BE> <偏移 u16BE>`（T_PARAM3 落锤；行号=主文件 raw 行号——
#     dbg_anchor_align 落锤：include 内只发声明不发锚点；多语句行每语句一锚点共用行号）
#   - scan() 运行时从 pc2kl3.py 抽取（工具真源唯一，防复制漂移）
#   - 强票: 语句内恰 1 个 FN 且源码行恰 1 个函数名候选；同名重复=同票；其余记弱线索
# 用法: python -I fn_census.py   （stdout + Decompile-pcode-tests\reports\fn_census.txt）
import os, re, sys, json, collections

SC = r'D:\Downloads\Decompile-pcode-staging\scripts'
TESTS = r'D:\Downloads\Decompile-pcode-tests'
REPORT = os.path.join(TESTS, 'reports', 'fn_census.txt')

FAMILIES = [
    # (label, src_dir, dec_dir)   配对键=文件名 stem（.kl / .pc.dec 去后缀，大小写不敏感）
    ('JLR',  os.path.join(TESTS, r'corpus\jlr16_pairs\src'),
             os.path.join(TESTS, r'corpus\jlr16_pairs\dec')),
    ('M9',   r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\work\src_v174\src',
             r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\work\pc_dec_mm'),
    ('饰板', r'D:\Downloads\_extract_karel_src\karel\src',
             os.path.join(TESTS, 'output_shipban')),
    ('探针', os.path.join(TESTS, 'probes'),
             os.path.join(TESTS, 'probes')),
]

# 纯语法关键字（IF(/WHILE(/WRITE ( 等）不当函数名候选
KW = set('''IF ELSEIF WHILE UNTIL ROUTINE CASE SELECT ELSE OF AND OR NOT XOR TRUE FALSE
BEGIN END ENDIF ENDWHILE ENDSELECT REPEAT FOR TO STEP ENDFOR THEN DO RETURN
VAR CONST TYPE STRUCTURE ENDSTRUCTURE BYTES DIV MOD SHL SHR STRING INTEGER REAL BOOLEAN
POSITION JOINTPOS FILE ARRAY PROGRAM WRITE READ OPEN CLOSE CONNECT DISCONNECT
DELAY PAUSE RELEASE ABORT STOP RESUME ENABLE DISABLE PURGE'''.split())

# 已落锤三条（0x04=CHR、0x14=STR_LEN、0x15=SUB_STR——旧代码把十六进制键写成十进制14/15
# 导致映射从不命中，fn_census 落锤）。作方法学自检。
KNOWN = {4: 'chr', 20: 'str_len', 21: 'sub_str'}


def load_scan():
    """从 pc2kl3.py 抽出 printable()+scan() 执行（防复制第二份工具源）"""
    src = open(os.path.join(SC, 'pc2kl3.py'), encoding='utf-8').read()
    ns = {'re': re, 'os': os, 'sys': sys, 'json': json}
    for fname in ('printable', 'scan'):
        m = re.search(r'^def %s\(.*?(?=^\S)' % fname, src, re.S | re.M)
        if not m:
            raise SystemExit('fn_census: 无法从 pc2kl3.py 抽取 %s()' % fname)
        exec(compile(m.group(0), 'pc2kl3_' + fname, 'exec'), ns)
    return ns['scan']


def cands_of(line):
    out = []
    for m in re.finditer(r'\b([A-Za-z_][A-Za-z0-9_]*)\s*\(', line):
        nm = m.group(1)
        if nm.upper() not in KW:
            out.append(nm)
    return out


def anchors_of(dec, lo, hi):
    """[(off, line)]：3e <行号 u16BE> <偏移 u16BE>，行号 hi 字节 ≤5，单调不减过滤假锚点"""
    out, prev = [], -1
    for m in re.finditer(rb'\x3e([\x00-\x05])([\x00-\xff])', dec[lo:hi]):
        off = lo + m.start()
        if off + 5 > hi:
            continue
        line = m.group(1)[0] * 256 + m.group(2)[0]
        if line < prev:
            continue
        prev = line
        out.append((off, line))
    return out


def main():
    scan = load_scan()
    votes = collections.defaultdict(collections.Counter)     # id -> strong name counter
    wvotes = collections.defaultdict(collections.Counter)    # id -> weak name counter
    sites = collections.defaultdict(list)                    # id -> [(fam, mod, line, name|None, src)]
    arity = collections.defaultdict(collections.Counter)     # id -> arg-ish context counter (记 token 形态)
    stat = collections.Counter()

    for label, sdir, ddir in FAMILIES:
        if not (os.path.isdir(sdir) and os.path.isdir(ddir)):
            print('!! 缺目录 %s' % label)
            continue
        srcs = {}
        for f in os.listdir(sdir):
            if f.lower().endswith('.kl'):
                srcs[re.sub(r'\.kl$', '', f, flags=re.I).lower()] = os.path.join(sdir, f)
        decs = {}
        for f in os.listdir(ddir):
            if f.lower().endswith('.dec'):
                stem = re.sub(r'\.pc\.dec$|\.dec$', '', f, flags=re.I).lower()
                decs[stem] = os.path.join(ddir, f)
        paired = sorted(set(srcs) & set(decs))
        stat['%s 配对' % label] = len(paired)
        for stem in paired:
            try:
                srclines = open(srcs[stem], encoding='utf-8', errors='replace').read().splitlines()
            except Exception:
                continue
            dec = open(decs[stem], 'rb').read()
            N = len(dec)
            jt = dec.find(b'\x7f\x00\x00\x00\xff')
            hi = jt if 0 < jt < N else N
            anch = anchors_of(dec, 0x30, hi)
            # 锚点行号=【主文件 raw 行号】（dbg_anchor_align 落锤：include 只有声明不发锚点；
            # 多语句行 `A;B;C` 每语句一锚点共用行号）→ 按行聚合再计票
            per_line = collections.OrderedDict()
            for ai, (aoff, line) in enumerate(anch):
                end = anch[ai + 1][0] if ai + 1 < len(anch) else hi
                if end <= aoff + 5:
                    continue
                body = dec[aoff + 5:end]
                if len(body) > 800:
                    continue
                try:
                    toks = scan(body, aoff + 5)
                except Exception:
                    continue
                fns = [t for t in toks if t[1] == 'FN']
                if not fns:
                    continue
                per_line.setdefault(line, []).append((aoff, fns))
            for line, items in per_line.items():
                srcline = srclines[line - 1] if 0 < line <= len(srclines) else ''
                cands = cands_of(srcline)
                allfns = [t for _, fs in items for t in fs]
                stat['FN 站点'] += len(allfns)
                for t in allfns:
                    sites[t[2]].append((label, stem, line, srcline[:90]))
                if not (0 < line <= len(srclines)):
                    stat['越界锚点'] += 1
                    continue
                s = srcline.strip()
                if not s or s.startswith('--'):
                    stat['注释/空行'] += 1
                    continue
                if len(allfns) == 1 and len(cands) == 1:
                    votes[allfns[0][2]][cands[0]] += 1
                    stat['强票'] += 1
                elif len(cands) >= 1 and len(set(t[2] for t in allfns)) == 1 \
                        and len(set(cands)) == 1 and len(allfns) == len(cands):
                    votes[allfns[0][2]][cands[0]] += 1     # 同 id × 同名 重复 → 同票
                    stat['同票'] += 1
                elif len(cands) >= 1:
                    for t in allfns:
                        for c in set(cands):
                            wvotes[t[2]][c] += 1
                    stat['弱线索'] += 1
                else:
                    stat['无候选行'] += 1

    # ---- 报告 ----
    lines = []
    lines.append('FN 族（76<id>）投票普查 — %d 个 id' % len(sites))
    lines.append('统计: ' + ' · '.join('%s %d' % kv for kv in stat.most_common()))
    lines.append('')
    for i in sorted(sites):
        s = votes[i]
        w = wvotes[i]
        kn = KNOWN.get(i, '')
        head = 'fn%-3d 站点%-4d 强票[%s] 弱[%s]' % (
            i, len(sites[i]),
            ' '.join('%s×%d' % kv for kv in s.most_common(4)),
            ' '.join('%s×%d' % kv for kv in w.most_common(4)))
        if kn:
            head += '  已知=%s' % kn
        lines.append(head)
        for fam, stem, line, srcline in sites[i][:3]:
            lines.append('      %s %s:%d  %s' % (fam, stem, line, srcline.strip()))
    # 方法学自检
    lines.append('')
    lines.append('— 方法学自检（已知三条应复现）—')
    for i, kn in KNOWN.items():
        top = votes[i].most_common(1)
        ok = top and top[0][0].lower() == kn
        lines.append('fn%-3d 已知=%-8s 普查=%-12s %s' % (i, kn, top[0][0] if top else '(无)', 'PASS' if ok else 'FAIL'))
    rep = '\n'.join(lines)
    os.makedirs(os.path.dirname(REPORT), exist_ok=True)
    open(REPORT, 'w', encoding='utf-8').write(rep)
    print(rep)
    print('\n→ %s' % REPORT)


main()
