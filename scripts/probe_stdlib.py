# 生成 stdlib 探针 KL：声明全部候选例程 FROM MI_LIB，KTRANS 报 "already defined" 的 = 活动基础支持集
import re, glob, subprocess, os

sigs = set()
for p in glob.glob('D:/program/roboguide/WinOLPC/Versions/*/support/*.ev'):
    d = open(p, 'rb').read()
    for m in re.finditer(rb'([A-Za-z_][A-Za-z0-9_]{2,})\x00\xff\xff', d):
        sigs.add(m.group(1).decode())

names = sorted(n for n in sigs if re.match(r'^[A-Za-z]', n))
probe = ['PROGRAM ZZPROBE', 'VAR', '  zzr : INTEGER']
for nm in names:
    probe.append('ROUTINE %s : INTEGER FROM MI_LIB' % nm)
probe += ['BEGIN', '  zzr = 0', 'END ZZPROBE']
kl = os.environ.get('TEMP', '.') + '/probe_stdlib.KL'
open(kl, 'w', encoding='ascii', errors='replace').write('\n'.join(probe))
r = subprocess.run([r'D:\program\roboguide\WinOLPC\bin\ktrans.exe', kl, os.environ.get('TEMP', '.') + '/probe_stdlib.pc'],
                   capture_output=True, text=True, timeout=300)
txt = r.stdout + r.stderr
defined = set()
for m in re.finditer(r'Id is already defined.*?Id: (\S+)', txt):
    defined.add(m.group(1).upper())
for m in re.finditer(r'already defined.*?Routine: (\S+)', txt):
    defined.add(m.group(1).upper())
out = r'D:/Downloads/凸点焊450_诊断分析_2026-10-28/scripts/stdlib_basic.txt'
open(out, 'w', encoding='utf-8').write('\n'.join(sorted(defined)))
print('candidates:', len(names), 'basic-defined:', len(defined), '->', out)
