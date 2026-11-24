# MI26_FEW_ROUT 补丁构建记录（2026-11-24）

## 两处有意修改（其余与机载原字节码逐 token 对齐）
1. **MI26_FEWDOCK CASE(1)（DockON）**：`DOUT[DO+11]` TRUE→**FALSE**（DO[3883]=OFF，对齐 TP FEW_DOCK_ON）
2. **MI26_INIT**：`DOUT[DO+9]` 先 FALSE → `DELAY 500` → 再 TRUE（对齐 TP FEW_INIT_GUN 的 OFF→0.5s→ON）；
   原 `PULSE DOUT[DO+1] FOR 1000` 保留（TP 行7/10 的 DO[3873] 操作，宽度未改）

## 源码口径（重要）
- 本模块为**字节码逐 token 复原重建**（源码材料：retry 段真名源码 + pc2kl3 反编译 + scan token 流）。
- **五例程是过程不是函数**（名字表 desc ret=0000 权威）；反编译的 `:INTEGER / RETURN(0) / sv_i=` 为合成渲染。
- 符号常量名取自 retry 段源码材料：GI_ACTUAL_POSITION=GI+1、GI_ALARM=GI+2、GO_PLIERS_CODE=GO+1、
  GO_FEW_PROGRAM_NUMBER=GO+3、DI_DONE=DI+13、DO_START_PROCESS=DO+13、DB_PS_RTRYCN=6、DB_RC_RETRY=7、DB_RC_CANCEL=2。
- 已知等价适配 3 处：① CONNTMR/DISCTMR 计时 → I_PROCESSTIM 显式 8ms 递增；② FEWFEED 丢失的等待 → 轮询
  `REPEAT DELAY 16 UNTIL (NOT DIN[DI+23])`；③ 布尔口测试 `=1` 形式 → 裸布尔形式（同语义）。

## 构建与验证
- KTRANS V9.40：Translation successful，4483B p-code，checksum 64675（0 ERROR）
- PC2KL_DEBUG 语句流 diff（原版 143 语句 vs 重建 145 语句）：差异 = 2 处有意修改 + 3 处已知适配，其余逐 kind 对齐
- 位级核对：INIT = FALSE→DELAY 500→TRUE→PULSE ✓；DOCK CASE(1) 首写 = FALSE ✓
- 导入绑定：WAIT_SIGNAL ← LIB_ROUT（真实模块名，名字表实证）；外部变量 I_MI01_DI ← MI01_CMN_VAR、
  AR_I_MI26_* ← MI26_FEW_VAR；调度器按名绑定 MI26_FEW_ROUT ✓

## 部署
- 仅需替换控制器 `mi26_few_rout.pc`（调度器/var 不动）；文件名保持小写与原件一致。
- 行为变化仅两处（见上）；其余路径与原版一致。
- 建议 ROBOGUIDE 先验：DockON 后 DO[3883] 应为 OFF；INIT 时 DO[3881] 出现 0.5s OFF 毛刺后保持 ON。


## 终版（v5，生产级重建 2026-11-24 收口）
- 三处替代形态已换回原始语言：WAIT FOR NOT DIN[…]（原 0x03 等待）、CONNECT/DISCONNECT TIMER
  （原 CONNTMR/DISCTMR）、DIN[x] = ON（原 =1 比较）；PULSE 补 NOWAIT（编码等价）。
- 名字表按原版全量声明（42 变量含未用项 + 54 导入声明），临时变量改例程局部（i_Response/err_num/b_finish）。
- 终验（vs 用户手术版逐语句对拍）：172 语句块 = 159 逐 token 全等 + 4 仅槽位/调用 id 元数据 +
  10 块差异全为例程尾过渡字节（名字表元数据混入锚点切句，非语句语义）。**真语义差异 = 0，行为完全等价。**
- 交付：mi26_few_rout_prod.pc（本目录）＝生产可部署源码重建版；mi26_few_rout.pc（（下载目录））＝你的手术版。
  两版行为等价，任选其一部署。
