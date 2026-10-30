import subprocess, os, json

KTRANS = r'D:\program\roboguide\WinOLPC\bin\ktrans.exe'
TMP = os.environ.get('TEMP', '.')
names = ['CNV_INT_STR', 'GET_JPOS_REG', 'GET_POS_REG', 'GET_REG', 'POS_REG_TYPE',
         'SET_EPOS_REG', 'SET_INT_REG', 'SET_JPOS_REG', 'SET_POS_REG', 'SET_REAL_REG',
         'SET_STR_REG', 'DB_PROMPT', 'CALL_PROG']

def try_bare(nm, n):
    args = ', '.join(['0'] * n)
    call = nm + '(' + args + ')' if n else nm
    kl = ['PROGRAM ZZPROBE3', 'VAR', '  zzr : INTEGER', 'BEGIN', '  ' + call, '  zzr = 0', 'END ZZPROBE3']
    p = os.path.join(TMP, 'zzp3.KL')
    open(p, 'w', encoding='ascii').write('\n'.join(kl))
    r = subprocess.run([KTRANS, p, os.path.join(TMP, 'zzp3.pc')], capture_output=True, text=True, timeout=60)
    t = r.stdout + r.stderr
    if 'Translation successful' in t:
        return 'ok'
    if 'more arguments' in t:
        return 'more'
    if 'less arguments' in t:
        return 'less'
    return 'other:' + t.strip().splitlines()[-1][:50] if t.strip() else 'other'

res = {}
for nm in names:
    classes = [(n, try_bare(nm, n)) for n in range(0, 10)]
    print(nm, classes[:8])
    # count = 最后一个非 more 的 n
    cnt = None
    for n, c in classes:
        if c == 'ok' or c.startswith('other'):
            cnt = n
        elif c == 'more':
            break
    res[nm] = cnt
json.dump(res, open(r'D:/Downloads/凸点焊450_诊断分析_2026-10-28/scripts/regope_basic_sigs.json', 'w'))
print(res)
