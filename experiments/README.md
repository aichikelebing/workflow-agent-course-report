# 实验复核说明

主实验对同一批论文记录分别运行三种查询策略。每条记录初始只显示题名，左、右元数据来自 DBLP 和 ACM。每次查询返回一个字段的两个值，每组最多两次。三个系统最终都由同一个确定性打分器分类。

## 重放本次结果

在仓库根目录运行以下命令。需要 Python 3.9 或更高版本，只用标准库。仓库中的 40 对记录以及控制器已选定的动作足以重放全部评分。

```sh
python3 experiments/study.py second
python3 experiments/study.py score
```

要从完整语料重新抽样，可从[发布方](https://dbs.uni-leipzig.de/files/datasets/DBLP-ACM.zip)下载后解压，再执行下面的命令。参数应指向直接含有三个 CSV 的目录。也可使用[固定版本镜像](https://github.com/benseverndev-oss/goldenmatch/tree/52811889c5f025799e8c4044204d486496918288/scripts/suggest_quality/vendored/DBLP-ACM)。

```sh
python3 experiments/study.py prepare --data /path/to/DBLP-ACM
python3 experiments/study.py second
python3 experiments/study.py score
```

| 文件 | 原始字节 SHA-256 |
|---|---|
| ACM.csv | `32055f1dfa619a4fdca33e7de729c66686a2fb3c71589921a6a3bd3af389120e` |
| DBLP2.csv | `a74ced040108a9aea20345a8e21f763a03e284abc22b4b99d64b44e47a99485c` |
| DBLP-ACM_perfectMapping.csv | `d9d7c9feaba3d19a2e73ba8bd6ae08407d8b16082881f6e55abc2d703682d53a` |

## 抽样与真值

读取三个文件得到 2,616 条 DBLP 书目、2,294 条 ACM 书目和 2,224 对已知匹配。先用真实匹配关系构造连通分量，固定种子 20261119，按分量散列分开发集和测试集。同一分量仅属于其中一边，每个抽样集内每个分量最多使用一次。

正样本取自已知对应关系。对每条 DBLP 记录构造负样本候选时，至少共享一个在本分区 ACM 书目中出现不超过 100 次的题名词，去掉官方匹配后选题名 Dice 系数最高的 ACM 记录，平分时按 ACM ID 决定。正样本按题名 Dice 从低到高排序，负样本按 Dice 从高到低排序，各把头部 20% 定为困难层，其余作为另一个抽样层。每个分区的正负标签、两个难度层等额抽样，开发 8 对、测试 32 对。测试集准确率和 F1 描述这批有意平衡的候选样本。

## 判定器与流程

题名切分为去重的小写字母数字词集合。Dice 等于二倍交集大小除以两集合的元素个数之和。初始判定分为题名 Dice 减 0.78，只有已查询字段才能加分或扣分。若任何一侧字段为空，该项贡献为零。总分大于等于零判为同一论文。

| 字段 | 分值更新 |
|---|---|
| 作者 | 对按逗号、分号或 and 拆分的人名取末词，得两侧姓氏词集合。加上 0.32 ×（2 × 姓氏 Dice − 1） |
| 年份 | 相同加 0.12，不同减 0.22 |
| 来源 | 规范化后相同加 0.10，不同减 0.15。已知 SIGMOD、VLDB 的会议和期刊别名见源码 |

A 总是查作者、年份。B 在题名初始分绝对值达到 0.25 时停止，否则查作者。此时若分数绝对值达到 0.18 即停止，剩余情况按作者缺失查来源、作者齐全查年份。阈值是这次实验的预设参数。开发集只用来做流程核验。

C 只收到题名、已有观测、可选动作及固定的自然语言提示。它可以停止，也可以选择下一个仍可见的查询工具。控制器不接触标签、匹配总分或其权重。B 能使用确切分数和阈值，C 仅有定性说明；本实验比较这三种具体实现。论文元数据可公开检索，因此结果也无法排除大模型训练时已接触部分题名的可能性。

本次 C 的模型动作由 Codex 对话环境按批返回。主实验第一轮一批，待查询字段揭晓后第二轮一批。配对实验的完整、遮盖条件各用一个独立的新上下文及不同的匿名编号。每次输入的每一行都是独立样本。一批中的多个样本可在同一上下文中出现，因此与逐样本独立 API 调用存在差异。动作字符串、给模型看的输入及提示词均随仓库提供。重放已记录的动作可以精确复核分数，新模型推理可能产生不同动作。逻辑决策次数按每个样本所作选择计数。

## 配对重放

在作者完整的测试记录中，按初始分绝对值从小到大选择靠近判定边界的 8 对，第一步均查作者。对相同论文分别保留原始作者和遮盖 ACM 侧作者，真值始终沿用原始标注。三组各决定第二步，另对“立即停止”“查询年份”“查询来源”全部离线评分。两个版本和三种动作对应的 48 行重放来自同一批 8 对基础记录，不能当作 48 个独立样本。

## 文件导航

| 文件 | 用途 |
|---|---|
| `experiments/controller-prompt.txt` | C 的固定提示词 |
| `results/cases.json` | 原始来源 ID、字段、匹配真值、样本难度层和分区 |
| `results/blind-*.jsonl`、`results/actions-*.json` | 输入模型的匿名观测、实际选择 |
| `results/main-traces.json`、`main-summary.json` | 主实验逐对轨迹、混淆计数、F1 与查询量 |
| `results/paired-traces.json`、`paired-replay.json`、`paired-summary.json` | 配对实验实际动作、所有可选路径及汇总 |
| `results/dev-summary.json` | 开发集两种确定性策略的流程核验 |

数据提供者为 Universität Leipzig 数据库研究组。原作者为 Hanna Köpcke、Andreas Thor 和 Erhard Rahm，论文为 *Evaluation of Entity Resolution Approaches on Real-World Match Problems*, Proceedings of the VLDB Endowment, 3(1–2), 2010。书目文本与匹配标注来自该基准，本报告另行选样并对部分输入执行遮盖。[项目与数据集说明](https://dbs.uni-leipzig.de/research/projects/benchmark-datasets-for-entity-resolution) · [数据许可 CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

## 事后诊断：一种期刊缩写

T28 的两侧来源分别写成 `ACM Trans. Database Syst.` 和 `ACM Transactions on Database Systems (TODS)`，指向同一刊物。原规范化器未映射这组缩写。运行 `python3 experiments/audit_venue.py` 会固定原有主实验的全部选字段动作，仅将这两种名称视为同刊并重算分类，输出 `results/venue-audit.json`。这是查阅错误案例后增加的定向诊断，不能估计全面修复来源规范化后的性能。
