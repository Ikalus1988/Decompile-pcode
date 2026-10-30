# Decompile-pcode

FANUC KAREL p-code（`.pc`，LZSS `FE EF 00 01` 容器）→ 可编译 `.kl` 源码的反编译流水线。
核心思路：**质量门驱动**——重建的 .kl 必须能被 KTRANS 重新编译，且语义指纹（串/常量）与原件一致。

## 能力

- **语句级重建**：表达式、IF/ELSE/WHILE/REPEAT…UNTIL、WRITE/GET_VAR/SET_VAR、I/O 读写、调用链
- **程序级变量真名复原**：符号表（名字+类型+维度）+ `$GROUP` 槽位映射表全解析，槽位名→真名机械替换
- **跳转表结构重建**：JZ/JMP 操作数=跳转表索引，回边→REPEAT/UNTIL 精确判定（带块自含护栏）
- **工具链签名对齐**：解析编译器支持库签名（core.ev）+ KTRANS 探针实测「已定义」集合与真实元数
- **四道质量门**（`pc2kl_gate.py`）：G1 编译 0 错 / G2 语义指纹 / G3 结构 / G4 渲染覆盖 ≤15%

## 用法

```bash
# 解包 .pc（LZSS）
node scripts/pc_decompress.mjs <out_dir> <xxx.pc>       # → <out_dir>/xxx.pc.dec

# 反编译
python -I scripts/pc2kl3.py <xxx.pc.dec> <out.kl>

# 质量门（需本机 KTRANS，见下）
python -I scripts/pc2kl_gate.py <xxx.pc.dec> <out.kl> <rebuilt.pc> [report.txt]

# 家族横扫（多模块批跑+汇总）
python -I scripts/pc2kl_family.py <dec_dir> <out_dir> [report.txt]
```

G1 编译门需要 Windows + FANUC ROBOGUIDE KTRANS（`D:\program\roboguide\WinOLPC\bin\ktrans.exe`），
不在 CI 里跑；CI 只做语法/结构自检。支持库名册由 `scripts/probe_stdlib.py` 在本机生成
（`stdlib_basic.txt`，不入库）。

## 校准探针（probes/）

自写源码→KTRANS 编译→反编译对拍的 ground-truth 探针，词表/编码全部经 141+ 测试点 0 矛盾校准：
PROBE 系列（算术/类型/IO/循环/跳转）、PROBE5（变量槽位/参数四形态）、PROBE6（符号表/槽位映射）。

## 文档

- `docs/编码表.md` — p-code 编码速查（变量引用/参数/符号表/跳转表/类型码/REGOPE 签名）

## 状态

四语料家族横扫：MI_FAP 家族 8/8、JLR 39/40、M9 26/30、部署版变体 6/8（四门口径，2026-10-30）。
剩余尾巴=实参类型保真（POSITION/REAL/BOOLEAN 跨界），弃参留痕可追溯。

## 授权维护

本仓由 Claude Code 协助维护（经维护者本机 gh 授权操作）。
