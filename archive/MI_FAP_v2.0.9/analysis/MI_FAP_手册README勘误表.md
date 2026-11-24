# MI_FAP v2.0.9 手册 / README 勘误表

> 依据：pc2kl3 反编译实读（118 .pc）× 手册 v20 × 更新日志三方对照（14 份逐应用深拆的对照结论汇总）。
> 用途：官方文档下一版修订清单 / 现场培训防误导。分四类：A README 身份勘误、B 手册文字勘误、C 手册×代码数值差异、D 代码侧已知瑕疵（非文档责任）。
> 标注【实证】处均可在 `decompiled\*.KL` 或 `ref_手册v20.txt` 定位。生成 2026-11-04。

---

## A. README 模块表身份勘误（6 处）

### A1. archive\MI_FAP_v2.0.9\README.md（Decompile-pcode 归档版）

| # | 现文 | 应为 | 依据 |
|---|---|---|---|
| 1 | MI13_rvh「RVH 焊枪管理（枪号 1~3、回枪位）」 | **自冲铆 SPR 旧款 Tucker**（Init/Rivet/Positioning/PrepareDock/LoadEPF/GunState，枪号 1~2） | 手册 13.1 |
| 2 | MI19_cli「CLI 信号联锁（Wait Signal）」 | **TOX 压铆（Clinch）**（INIT/LOAD/TOX_Start/TOX_End，伺服/液压双模式） | 手册 17.1 + MI19_ROUT 双族 |
| 3 | MI24_arc「ARC 弧焊（信号联锁）」 | **弧焊清枪**（TD 剪丝 / MOTOR 铣刀 / WIRE 送丝） | 手册 21.1 |
| 4 | MI26_few「FEW 流程/位置控制」 | **摩擦元件焊接**（Init/GunOpen/FewWeld/Feed/Dock） | 手册 23.1 + 更新日志 v2.0.9 |
| 5 | MI17_obj「OBJ 坐标/对象（GGTFRAME）」 | 视觉引导坐标应用——**壳+贝特威 VS_\* 工具链**（GGTFRAME 只是 UFrame 转换工具之一） | 手册 16.1 + VS_* 五件套 %COMMENT |
| 6 | MI09_dsd「TCP3D 三维视觉」 | 三品牌涂胶检测（BetterWay/Coherix 2D/3D）；**TCP=Tool Center Point 位姿流**非网络协议 | 手册 11 + MI09_COHERIX_3D_TCP |

### A2. mi-fap 仓库 README（发版页）

| # | 现文 | 应为 |
|---|---|---|
| 7 | MI25 行「LASER、**RUMP**、AIR」 | **TRUMP**（TRUMPF 激光源，手册 22.2.2 标题同错） |
| 8 | MI24 行「弧焊：TD、Motor、Wire」 | 建议补"清枪"二字，避免误读为弧焊工艺本体 |

---

## B. 手册 v20 文字/列表勘误（18 处）

| # | 章 | 现文 | 应为 | 依据 |
|---|---|---|---|---|
| 1 | 6.2 | Parameter select「7：FestoCheck」 | 「7: RIPCheck」+ 补「8: ProgNumberCheck」（v2.0.9 新增） | 代码 8 指令；6.3.7 已更名 RIPCheck（v2.0.4） |
| 2 | 7.2 | 「7：ChangTool」 | ChangeTool | 拼写 |
| 3 | 7.2.5 | 「Lock 表示解锁」 | **UnLock** 表示解锁 | 串名 |
| 4 | 7.2.8 | 「UnlockChek」 | UnlockChk | 拼写 |
| 5 | 10.2.3 | 「参数 4：ProgNo 表示参数号」 | 「参数 4：**ParaNo** 表示参数号」 | 参数名与描述错位 |
| 6 | 10.2.4 | 「参数 3：GunNo 选择 T_Dsp OFF 或者 ON」 | 「参数 3：**T_Dsp** 选择…」 | 参数名错 |
| 7 | 11.2.1 | 标题「BetterrWay」 | BetterWay | 拼写 |
| 8 | 11.3 | Setup 品牌「BetterWay、Coherix 3D 和 **ISV**」 | 与指令树一致：BetterWay / **Coherix 2D** / Coherix 3D（ISV 无对应指令码，属 MI04 的 ISV_VG） | 手册内部自相矛盾 |
| 9 | 11.2.1.5 | `ToolNum=1'...'` | `ToolNum=1, '...'`（缺逗号） | 格式 |
| 10 | 12.2 | Parameter select「2: ArplasWeld」 | 「2: **Dimple**」 | 代码 CASE(2)=Dimple |
| 11 | 12.2.1.1 | 「GI[121]乘以…系数」 | **GI[112]** | 代码 io_12[112]；§12.3 自身写 GI[112] |
| 12 | 12.2.1 | ArplasWeld 与 Tipdress 子节均编号 12.2.1.1 | 后者应为 12.2.1.2 | 编号重复 |
| 13 | 12.3 | 「Origial TCP saved(mm)」 | Original | 拼写 |
| 14 | 13.3 vs 13.4.1 | Max Gun Number 1~2 vs MAN 页 Max.Guns 1~3 | 统一口径（代码 CHECKMAXGUNNUMBER 以 Setup 为准） | 手册内部不一致 |
| 15 | 15.2 | Parameter select 列 8 项 | 补「9: DieCheck」（15.2.9 已文档） | select 滞后 |
| 16 | 15.2.9 | 「参数 1：SendBSNNum」 | 「参数 1：**DieCheck**」 | 复制粘贴错 |
| 17 | 15.2.6 | 「FiilMag」 | FillMag | 拼写 |
| 18 | 17.2.5 | 「Couple 表示设备连接；Couple 表示设备断开」 | 第二处「**Decouple** 表示设备断开」 | 串名 |

---

## C. 手册 × 代码数值/行为差异（5 处，建议手册改或加注）

| # | 项 | 手册 | 代码/日志 | 建议 |
|---|---|---|---|---|
| 1 | BG Scan Time 上限（MI03/MI08/MI09） | 32~**1024**ms | DELAY 钳 32~**256**（MI11/MI13 为 1024 与手册一致） | 统一：或手册改 256，或代码放 1024 |
| 2 | MI02 STABLI unlock 默认 | — | 代码默认 2913；更新日志 v2.0.5 称"改为 2925" | 手册注明以 Setup 实配为准 |
| 3 | MI09 第二设备 IO 偏移 | 6.1.2 表 **3048** | v2.0.8 起 **3512**（新机生效，旧机需手动改） | 更新 6.1.2 表 |
| 4 | MI01 Init 复位范围 | "干涉区/夹具信号复位" | 只复位 **1~3**（CollZone/Fixture 指令支持 1~32） | 手册注明仅 1~3 或改代码 |
| 5 | Timeout 默认偏短 | MI13 Rivet 500ms / MI22 FDS 500ms | MI14 同类已改 4000ms（v2.0.8） | 建议同类默认上调 |

---

## D. 代码侧已知瑕疵（供开发，非文档责任）

1. **MI08 INIT 变量误赋值**：`IF (UNINIT(I_COMPONET)) THEN I_DISPENSER = 1`——判定与赋值变量不一致，I_COMPONET 未默认化（双组份判据可能不稳）。
2. **MI04 CONTROLMOTOR 函数体空**（Remove/Eject 脉冲细节不可见）——反编译字面量丢失或真真空体，须真机验证。
3. **MI11_SENDBSNUM 死代码**（传车身码功能已删，例程残留）。
4. **显示层拼写群**（不影响逻辑）：'Wait Singal'（MI19×2）/'AIR KINFE'（MI25）/'Syetem'（MI13/MI15）/'sucessfully'（MI01 AUTOBK）/'Create floder'/'diffence'/'Toleraces'/'emtpy'/'Singal'。
5. **BSN 起点每站各异**——PLC 组态对照表（横扫必查）：

| 站 | BSN DO 起点 | 站 | BSN DO 起点 |
|---|---|---|---|
| MI08 | DO+81 | MI11 | DO+145 |
| MI09 BTW/2D/3D | DO+17 / +49 / +337 | MI13 | RC_DO+97 |
| MI15 | 第 81 点起（v2.0.9） | MI17 | DO+233 |
| MI20/21 | （DO+17.. 族，见深拆） | | |

---

*汇总自：14 份逐应用深拆 §6 对照结论。勘误项均可按 B 表"依据"列回溯到深拆文档对应章节。*
