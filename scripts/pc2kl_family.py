# pc2kl_family.py — 批量跑 pc2kl3 + 质量门（家族横扫）
# Usage: python -I pc2kl_family.py <dec_dir> <out_dir> [report.txt]
#   dec_dir 内 *.dec（或 *.pc.dec）逐个转 .KL 并过四道门，汇总报告
import os, re, subprocess, sys

dec_dir, out_dir = sys.argv[1], sys.argv[2]
rep_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(out_dir, '家族验收.txt')
SC = os.path.dirname(os.path.abspath(__file__))
os.makedirs(out_dir, exist_ok=True)

decs = sorted(f for f in os.listdir(dec_dir) if f.endswith('.dec'))
rows = []
for df in decs:
    stem = re.sub(r'\.pc\.dec$|\.dec$', '', df, flags=re.I).upper()
    dec_path = os.path.join(dec_dir, df)
    kl_path = os.path.join(out_dir, stem + '.KL')
    gate_path = kl_path + '.gate.txt'
    r1 = subprocess.run([sys.executable, '-I', os.path.join(SC, 'pc2kl3.py'), dec_path, kl_path],
                        capture_output=True, text=True, timeout=300)
    if r1.returncode != 0 or not os.path.exists(kl_path):
        rows.append((stem, False, 'BUILD_FAIL ' + (r1.stderr or r1.stdout)[-200:]))
        continue
    pc_path = os.path.join(out_dir, stem + '.pc')
    KTRANS = r'D:\program\roboguide\WinOLPC\bin\ktrans.exe'
    subprocess.run([KTRANS, kl_path, pc_path], capture_output=True, text=True, timeout=300)
    r2 = subprocess.run([sys.executable, '-I', os.path.join(SC, 'pc2kl_gate.py'),
                         dec_path, kl_path, pc_path, gate_path],
                        capture_output=True, text=True, timeout=300)
    txt = (r2.stdout or '') + (r2.stderr or '')
    ok = '总判定: PASS' in txt
    det = []
    for line in (r2.stdout or '').splitlines():
        m = re.search(r'\[(PASS|FAIL)\] ([^:]+): (.*)', line)
        if m:
            det.append('%s%s' % (m.group(2)[:2], 'ok' if m.group(1) == 'PASS' else '[X]' + m.group(3)[:60]))
    rows.append((stem, ok, ' | '.join(det)))

npass = sum(1 for _, ok, _ in rows if ok)
with open(rep_path, 'w', encoding='utf-8') as f:
    f.write('# pc2kl3 家族横扫 %s → %s\n' % (dec_dir, out_dir))
    f.write('通过 %d/%d\n\n' % (npass, len(rows)))
    for stem, ok, det in rows:
        f.write('  %-16s %s  %s\n' % (stem, 'PASS' if ok else 'FAIL', det))
print('通过 %d/%d → %s' % (npass, len(rows), rep_path))
for stem, ok, det in rows:
    print('  %-16s %s  %s' % (stem, 'PASS' if ok else 'FAIL', det))
sys.exit(0 if npass == len(rows) else 1)
