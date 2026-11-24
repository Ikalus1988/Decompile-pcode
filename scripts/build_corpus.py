# -*- coding: utf-8 -*-
# build_corpus.py — 语料库三步建库（方案见 docs/语料库建设方案.md）
# ①去重入库：35,978 库件 + 配对件 → store/<hash前2>/<hash>.pc（内容寻址）
# ②配对绑定：源码名↔编译件（同版/漂移/dec-only/无源）
# ③签名库解析：KTRANS support *.ev → signatures/stdlib.json
# 用法: python -I build_corpus.py [all|1|2|3]     —— 幂等，可分步重跑
import os, re, sys, json, hashlib, shutil, glob, random

CORPUS = r'D:\Downloads\Decompile-pcode-tests\corpus'
STORE = os.path.join(CORPUS, 'store')
MANIFEST = os.path.join(CORPUS, 'manifest.jsonl')
SIGDIR = os.path.join(CORPUS, 'signatures')
LIB_ROOT = r'D:\Downloads\01_机器人备份'
EV_GLOB = r'D:\program\roboguide\WinOLPC\Versions\*\support\*.ev'

# 配对语料（原件位置；jlr16 已抢救进 corpus/）
PAIR_PC = {  # .pc 原件目录 → corpus 标签
    os.path.join(CORPUS, 'jlr16_pairs', 'raw'): 'jlr16',
    r'D:\Downloads\10_KAREL反编译\_extract_shipban_pc\新建文件夹': 'shipban',
    r'D:\Downloads\10_KAREL反编译\_extract_FT20261102_bestfit': 'ft20_bestfit',
    r'D:\Downloads\10_KAREL反编译\_extract_F_20261109\QOROS COMMON\CUSTOM\PC': 'qoros',
}
PAIR_DEC = {  # dec-only（原件 .pc 已被覆盖/未保留）→ corpus 标签
    r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\work\pc_dec_mm': 'm9_v174',
    os.path.join(CORPUS, 'mifap_dec'): 'mi04_mifap',
}
SRC_DIRS = [  # 真源码目录（%INCLUDE 不展开，配对按文件名）
    (os.path.join(CORPUS, 'jlr16_pairs', 'src'), 'jlr16'),
    (r'D:\Downloads\凸点焊450_诊断分析_2026-10-28\work\src_v174\src', 'm9_v174'),
    (r'D:\Downloads\10_KAREL反编译\_extract_karel_src\karel\src', 'shipban'),
    (r'D:\Downloads\10_KAREL反编译\_src_pairs_spr_fds_20261105', 'sprfds_src'),
    (r'D:\Downloads\10_KAREL反编译\_extract_F_20261109\KL', 'qoros'),
    (r'D:\Downloads\01_机器人备份\ss010r04_FEW测试_patch\src', 'ss010r04_few'),
]


def md5(p):
    h = hashlib.md5()
    with open(p, 'rb') as f:
        for blk in iter(lambda: f.read(1 << 20), b''):
            h.update(blk)
    return h.hexdigest()


def step1_store():
    """去重入库：每唯一哈希存一份，回扫清单（name/hash/size/拷贝数/来源）"""
    seen = {}   # hash -> row
    files = []
    for root, _dirs, names in os.walk(LIB_ROOT):
        for n in names:
            if n.lower().endswith('.pc'):
                files.append((os.path.join(root, n), 'library', n[:-3]))
    for d, tag in PAIR_PC.items():
        for n in os.listdir(d):
            if n.lower().endswith('.pc'):
                files.append((os.path.join(d, n), tag, n[:-3]))
    print('① 扫描 %d 个 .pc …' % len(files))
    for i, (p, tag, name) in enumerate(files):
        try:
            h = md5(p)
        except OSError:
            continue
        row = seen.get(h)
        if row is None:
            seen[h] = {'name': name.lower(), 'hash': h, 'size': os.path.getsize(p),
                       'corpus': tag, 'example': p, 'n_copies': 1}
        else:
            row['n_copies'] += 1
            if tag != 'library':
                row['corpus'] = tag      # 配对件标签优先于 library
        if (i + 1) % 5000 == 0:
            print('    … %d/%d' % (i + 1, len(files)))
    os.makedirs(STORE, exist_ok=True)
    for h, row in seen.items():
        dst = os.path.join(STORE, h[:2], h + '.pc')
        if not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(row['example'], dst)
    print('① 入库 %d 唯一 .pc（源 %d 文件）→ %s' % (len(seen), len(files), STORE))
    return seen


def step2_bind(seen):
    """配对绑定：名字→源码/版本关系 → manifest.jsonl"""
    srcs = {}   # name -> (path, tag)
    for d, tag in SRC_DIRS:
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if n.lower().endswith('.kl'):
                srcs[n[:-3].lower()] = (os.path.join(d, n), tag)
    by_name = {}
    for h, r in seen.items():
        by_name.setdefault(r['name'], []).append(r)
    for r in seen.values():
        r['versions_of_name'] = len(by_name[r['name']])
        r['n_names'] = None
    rows = list(seen.values())
    # dec-only 行（m9/mi04 原件只剩 .pc.dec）
    for d, tag in PAIR_DEC.items():
        if not os.path.isdir(d):
            continue
        for n in os.listdir(d):
            if n.lower().endswith('.pc.dec'):
                p = os.path.join(d, n)
                name = n[:-7].lower()
                h = md5(p)
                dst = os.path.join(STORE, h[:2], h + '.pc.dec')
                if not os.path.exists(dst):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(p, dst)
                rows.append({'name': name, 'hash': h, 'size': os.path.getsize(p),
                             'corpus': tag, 'n_copies': 1,
                             'kind': 'dec_only', 'versions_of_name': len(by_name.get(name, []))})
    out = []
    for r in rows:
        name = r['name']
        src = srcs.get(name)
        r.setdefault('kind', 'pc')
        r['has_source'] = bool(src)
        r['source_path'] = src[0] if src else None
        if r['kind'] == 'dec_only':
            r['pair_quality'] = 'dec_only' if src else 'none'
        elif r['corpus'] in ('jlr16', 'shipban'):
            r['pair_quality'] = 'same' if src else 'paired_nosrc'
        elif src:
            r['pair_quality'] = 'drift'      # 名字有源码、哈希≠配对原件
        else:
            r['pair_quality'] = 'none'
        out.append({'name': name, 'hash': r['hash'], 'size': r['size'], 'kind': r['kind'],
                    'n_copies': r['n_copies'], 'versions_of_name': r['versions_of_name'],
                    'corpus': r['corpus'], 'pair_quality': r['pair_quality'],
                    'has_source': r['has_source'], 'source_path': r['source_path'],
                    'store': 'store/%s/%s.%s' % (r['hash'][:2], r['hash'],
                                                 'pc' if r['kind'] == 'pc' else 'pc.dec'),
                    # 以下度量字段由一键度量脚本回填（schema 预留）
                    'gates': None, 'similarity': None, 'name_rate': None, 'known_gaps': None})
    out.sort(key=lambda x: (x['name'], x['hash']))
    with open(MANIFEST, 'w', encoding='utf-8') as f:
        for row in out:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
    n_src = sum(1 for r in out if r['has_source'])
    q = {}
    for r in out:
        q[r['pair_quality']] = q.get(r['pair_quality'], 0) + 1
    print('② manifest %d 行 → %s' % (len(out), MANIFEST))
    print('   有源码 %d 行；pair_quality 分布 %s' % (n_src, q))
    return out


def step3_sigs():
    """签名库解析：*.ev → signatures/stdlib.json（形参类型码 + 参数名）"""
    def cls(bs):
        t = bs[:2]
        if t[0] in (0x20, 0x3f):
            return {0x3f: 'as'}.get(t[0], ('as' if len(bs) > 1 and bs[1] == 0x1f else
                                          'ab' if len(bs) > 1 and bs[1] == 0x12 else 'ai'))
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
    for p in sorted(glob.glob(EV_GLOB)):
        ver = p.split(os.sep)[-3]
        lib = os.path.splitext(os.path.basename(p))[0].upper()
        d = open(p, 'rb').read()
        for m in re.finditer(rb'([A-Za-z_][A-Za-z0-9_]{2,})\x00\xff\xff', d):
            nm = m.group(1).decode().upper()
            j = m.end()
            if j + 3 > len(d):
                continue
            argc = d[j]
            if argc > 24:
                continue
            retb = d[j + 1:j + 3]
            ret = 'v' if retb == b'\x00\x00' else ('s' if 0x1f in retb else 'i')
            k = j + 3
            params = []
            for _ in range(min(argc, 16)):
                mm = re.match(rb'([A-Za-z_][A-Za-z0-9_]*)\x00...', d[k:], re.S)
                if not mm:
                    break
                pname = mm.group(1).decode()
                ne = k + mm.end()
                desc = d[ne - 3:ne]
                if desc[0] in (0x20, 0x3f) and ne + 2 <= len(d):
                    desc = d[ne - 3:ne + 2]
                params.append({'name': pname, 'type': desc.hex(),
                               'kind': cls(desc)})
                k += (len(mm.group(0)) - 3) + len(desc)
            e = sigs.setdefault(nm, {'argc': argc, 'ret': ret, 'retb': retb.hex(),
                                     'params': params, 'lib': set(), 'versions': {}})
            e['lib'].add(lib)
            e['versions'][ver] = {'argc': argc, 'ret': ret,
                                  'params': [x['type'] for x in params]}
    for e in sigs.values():
        e['lib'] = sorted(e['lib'])
    os.makedirs(SIGDIR, exist_ok=True)
    with open(os.path.join(SIGDIR, 'stdlib.json'), 'w', encoding='utf-8') as f:
        json.dump(sigs, f, ensure_ascii=False, indent=1)
    print('③ 签名库 %d 条例程 → %s' % (len(sigs), os.path.join(SIGDIR, 'stdlib.json')))
    return sigs


def selfcheck(rows):
    """验收判据：随机 10 行——store 命中+重哈希一致、has_source→源文件在"""
    random.seed(20261101)
    pick = random.sample(rows, min(10, len(rows)))
    bad = 0
    for r in pick:
        p = os.path.join(CORPUS, r['store'].replace('/', os.sep))
        ok = os.path.exists(p) and md5(p) == r['hash']
        ok = ok and ((not r['has_source']) or os.path.exists(r['source_path']))
        if not ok:
            bad += 1
            print('   ✗', r['name'], r['hash'][:8])
    print('自检 抽 %d 行：%s' % (len(pick), '全通过' if bad == 0 else '%d 行失败' % bad))


if __name__ == '__main__':
    step = sys.argv[1] if len(sys.argv) > 1 else 'all'
    seen = rows = None
    if step in ('all', '1'):
        seen = step1_store()
    if step in ('all', '2'):
        if seen is None:
            print('step2 需要 step1 的扫描结果，请跑: python -I build_corpus.py all')
            sys.exit(1)
        rows = step2_bind(seen)
    if step in ('all', '3'):
        step3_sigs()
    if rows:
        selfcheck(rows)
