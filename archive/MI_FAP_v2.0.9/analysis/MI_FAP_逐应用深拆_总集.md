# MI_FAP v2.0.9 逐应用深拆 · 总集与索引

> 18 应用 × 五件套（指令级时序图 / 参数表 / GUI 流程 / 异常路径 / 与 TP 交互）× 三方对照（反编译实读 × 手册 v20 × 更新日志）。
> 全系列 2026-11-03 ~ 11-04 完成。姊妹篇：[00_架构时序与缺陷分析](00_架构时序与缺陷分析.html)（全量概览，先读）· [MI_FAP_手册README勘误表](MI_FAP_手册README勘误表.md)。

---

## 一、文档索引

| # | 深拆文档 | 覆盖站 | 手册章 |
|---|---|---|---|
| 1 | [MI01_CMN](MI01_CMN_逐应用深拆.md) | PLC 网关/后台框架 | §6 |
| 2 | [MI02_TCH](MI02_TCH_逐应用深拆.md) | 换枪（Walther/Staubli） | §7 |
| 3 | [MI03_GRP](MI03_GRP_逐应用深拆.md) | 抓手群控 | §8 |
| 4 | [MI04_SSW](MI04_SSW_逐应用深拆.md) | 点焊（三焊机+ISV） | §9 |
| 5 | [MI08_DSP](MI08_DSP_逐应用深拆.md) | 涂胶（SCA/DMTS） | §10 |
| 6 | [MI09_DSD](MI09_DSD_逐应用深拆.md) | 涂胶视觉检测（三品牌） | §11 |
| 7 | [MI11_APL](MI11_APL_逐应用深拆.md) | Arplas 焊+Dimple | §12 |
| 8 | [MI13_RVH](MI13_RVH_逐应用深拆.md) | SPR 旧 Tucker | §13 |
| 9 | [MI14_MI15_SPR](MI14_MI15_SPR_逐应用深拆.md) | SPR 新 Tucker + 固极（三胞胎对照） | §14/15 |
| 10 | [MI17_OBJ](MI17_OBJ_逐应用深拆.md) | 视觉引导坐标（壳+贝特威） | §16 |
| 11 | [MI19_CLI](MI19_CLI_逐应用深拆.md) | TOX 压铆（伺服/液压） | §17 |
| 12 | [MI20_MI21_SWH](MI20_MI21_SWH_逐应用深拆.md) | 螺柱焊双胞胎 | §18/19 |
| 13 | [MI22_FDS](MI22_FDS_逐应用深拆.md) | FDS 流钻螺丝 | §20 |
| 14 | [MI24_MI25_MI26](MI24_MI25_MI26_逐应用深拆.md) | 弧焊清枪 + TRUMPF 激光 + FEW（收官三联） | §21-23 |

配套：[勘误表](MI_FAP_手册README勘误表.md)（A README×8 / B 手册×18 / C 数值差异×5 / D 代码瑕疵）· 各站高亮源码页 `<应用>.html` · `ref_手册v20.txt` / `ref_更新日志FAP_v2.0.9.txt`。

---

## 二、18 应用全景（一行判读版）

| 站 | 真实身份 | 一句话核心 | 关键坑 |
|---|---|---|---|
| MI01 | PLC 网关 | 8 指令分发+4 后台体（监控/PRIO/备份/PROG RECORD） | 手册 7 指令缺 ProgNumCheck；Init 只清 1~3 区 |
| MI02 | 换枪 | Walther 5s 自锁+Staubli Euchner 双时序，品牌路由 DECIDE_DIO | 模板注释反义；STB unlock 默认值存疑 |
| MI03 | 抓手 | MHGRIPDT→固定 DO 区镜像+10 路连续检测 | 循环界 1..3 vs"扩到4"；BG 256vs1024 |
| MI04 | 点焊 | 三焊机位图+水流量闭环+修磨闪烁握手+ISV 视觉 | I_DT_TYPE 参数移位；CONTROLMOTOR 空体 |
| MI08 | 涂胶 | R[28] 质量协议+双组份双路径+SCA 新旧 BSN | I_COMPONET 误赋值；TCP 三件套=缺陷密集区 |
| MI09 | 涂胶检测 | 三品牌分流；**TCP=位姿流**（RETURNINT/DEC 防溢出） | 双例程树兼容；ISV 有名无码 |
| MI11 | Arplas+Dimple | 焊点号双字+修磨 TCP 补偿（GI[112]→Tool1 Z） | 手册两笔误；Dimple CANCEL 旁路 |
| MI13 | SPR 旧 Tucker | 双铆钉号预送+缺钉计数+枪开口闭环 | README 身份错；弹窗族最复杂 |
| MI14/15 | SPR 新 Tucker/固极 | 主轴定位/档位开口/铆模检测 DieCheck | 三站 RC 协议各异；MI15 select 漏 DieCheck |
| MI17 | 视觉引导 | 壳+贝特威 VS_* 五件套（版本不齐） | BSN 起点 233；手册只写壳 |
| MI19 | TOX 压铆 | 液压/伺服双实现单接口 | 'Wait Singal'；IO 三连迁移 |
| MI20/21 | 螺柱焊 | StudID 双字+start weld 清场 | 双枪须配设备/控制器数量=2 |
| MI22 | FDS | 24 位点号+结果校验+换刀/服务族 | Timeout 500ms 偏短；FDS_MAN 恢复闭环 |
| MI24 | 弧焊清枪 | TD/MOTOR/WIRE 七动作 | README 身份错 |
| MI25 | TRUMPF 激光 | TRUMP Init(高压保持)/Parameters+气刀 | 'AIR KINFE'；无 GUI |
| MI26 | FEW 摩擦元件焊 | 五指令五例程（v2.0.9 新增） | 界面未建 |

---

## 三、系列级发现（横扫/移植必读）

### 3.1 参数向导兼容——三种实现并存（改参数勿套用）

| 实现 | 站 | 机制 |
|---|---|---|
| 参数整体移位 | MI04、MI08 | I_DT_TYPE=1 时参数序右移一位 |
| 双例程树 | MI09 | ACTIONSELECT / ACTIONSELECT_OLD 两套分发 |
| 无兼容层 | 其余 | 直接收现行参数 |

### 3.2 通病清单（详见[勘误表](MI_FAP_手册README勘误表.md)）

①手册 select 滞后 5 处 ②README 身份失真 8 处 ③I_MON 256vs1024（MI03/08/09）④IO 迁移不联动（MI19 三连/Coherix 3512/MI02）⑤拼写群 ⑥BSN 起点每站各异（17/49/81/97/145/233/337…）

### 3.3 协议指纹速查（换供应商=换协议表）

| 工艺族 | 协议特征 | 站 |
|---|---|---|
| SPR 铆接 | RC 信号偏移表三套各异（+1/+2/+5… / +10/+21… / +11/+17/+24…） | MI13/14/15 |
| 涂胶 | BSN 镜像+GO/GI 回显握手（ProgNum/ParaNum echo） | MI08/MI09 |
| 焊接类 | DO[42] 进程信号全系共用 + GO[6] 错误号域 | 全系 |
| 视觉 | 位姿流（MI09 GO 双字）/ VS_* 信号定义（MI17）/ socket（MI08 BizLink） | MI08/09/17 |

### 3.4 与 00_总纲 缺陷编号的映射

B1（寄存器不检查）→ MI01/MI04 实证；B2（TCP 缺陷密集）→ MI08 深拆 §1.7 审计要点；B3（标志竞态）→ MI01 MON；B4（CONDITION 脆弱）→ MI02 AUTO_LOCK 迁移实证；B5（协议 ELSE 空）→ MI04 INIT；B6（'Wait Singal'）→ MI19 代码落锤；B7（人因旁路）→ MI11 Dimple/MI13 弹窗族。

---

## 四、材料地图

```
analysis\            ← 本目录（00 总纲 + 19 个 <应用>.html 注解页 + 14 份深拆 md + 勘误表 + 总集）
decompiled\<应用>\   ← pc2kl3 反编译 .KL（118 模块）
pc\<应用>\           ← 原始 .pc
ref_手册v20.txt      ← 小米标准软件手册 v20（23 章）
ref_更新日志FAP_v2.0.9.txt ← 更新日志（v2.0.9→v1.0.x）
仓库串证             ← git.n.xiaomi.com/jiahenglong/mi-fap（.LS/.tx/.vr 真源）
```

*生成：2026-11-04 · pc2kl3 @ Decompile-pcode-staging · 证据标注约定同 00 总纲（【实证】/【推断】/【存疑】）。*
