# MI_FAP v2.0.9（全套焊装自动化应用）

> 来源：`08_软件安装包\MI_FAP_v2.0.9.zip`（2026-11-03 归档）。
> 18 个应用 + core 共 **118 个 .pc**，全部完成 .kl 反编译（pc2kl3 @ 8c79f18）。
> `analysis\index.html` = 逻辑辅助分析注解总入口。

## 应用清单（pc/ 与 decompiled/ 按应用同名分目录）

| 应用 | 定位 | 模块 | G1 零错 |
|---|---|---|---|
| core | 核心库（lib_misc/lib_rout/user_loader） | 3 | 1 |
| MI01_cmn | CMN 公共支撑（报警/日志/IO 助手） | 18 | 16 |
| MI02_tch | ATC 自动换枪站（Tool Changer） | 6 | 5 |
| MI03_grp | GRP 抓手群控（MH_GRIPPERS） | 4 | 3 |
| MI04_ssw | SSW 点焊工位（含 isv_vg 视觉、td_pop） | 9 | 8 |
| MI08_dsp | DSP 涂胶（TCP_COMM 对接 BizLink 胶机） | 8 | 5 |
| MI09_dsd | DSD 视觉检测（TCP3D 三维视觉、VA） | 6 | 6 |
| MI11_apl | APL 焊点调度（Spot selection） | 5 | 4 |
| MI13_rvh | RVH 焊枪管理（枪号 1~3、回枪位） | 7 | 7 |
| MI14_spr | SPR 自冲铆 工位 1 | 5 | 5 |
| MI15_spr | SPR 自冲铆 工位 2 | 5 | 4 |
| MI17_obj | OBJ 坐标/对象（GGTFRAME） | 11 | 9 |
| MI19_cli | CLI 信号联锁（Wait Signal） | 4 | 4 |
| MI20_swh | SWH 螺柱焊 工位 1 | 6 | 5 |
| MI21_swh | SWH 螺柱焊 工位 2 | 5 | 5 |
| MI22_fds | FDS 流钻螺丝（拧紧枪 1~3、FDS_MAN） | 6 | 6 |
| MI24_arc | ARC 弧焊（信号联锁） | 4 | 4 |
| MI25_las | LAS 激光（TRUMPF 激光源） | 3 | 3 |
| MI26_few | FEW 流程/位置控制 | 3 | 2 |
| **合计** | | **118** | **102** |

G1 零错 102/118；16 件非零错集中在 **TCP_COMM/TCP_MEA/TCP_MSG（socket 协议模块，60 错）**
及少数聚合/收口残留类——错误不影响其余 102 件的可读交付。

## analysis\（逻辑辅助分析注解，HTML）

每应用一页：**应用定位注解**（依据蓝图缩写+模块/TP 命名+反编译串证三方核对）、
模块/例程清单、SELECT 状态机密度、外部调用与消息协议串、KAREL 高亮源码内嵌。
入口：`analysis\index.html`。**`analysis/00_架构时序与缺陷分析.html` = 总纲**（架构分层/执行时序/缺陷 B1-B7/待完善 F1-F9/手册×更新日志×代码三方对照）。
