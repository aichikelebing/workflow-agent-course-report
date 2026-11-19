# 论文去重时，下一步查什么？

数据挖掘课程实验报告 · Workflow 与 Agent 决策边界的对照实验

[报告 PDF](report/report.pdf)　·　[直接阅读正文](report/report.md)　·　[LaTeX 源文件](report/report.tex)　·　[完整 AI 协作记录（Markdown）](conversations/01-planning.md)

面对同一对疑似重复的论文，如果作者字段缺失，规则和模型都可能改查年份。我们把“由谁选择下一步”落实到一次字段查询，将控制器换成固定顺序、条件分支或受两次查询预算约束的模型，最后交给同一个判定器。数据来自 DBLP–ACM 基准，开发集 8 对，测试集 32 对；其中 8 对另做作者字段遮盖与替代动作重放。

| 测试集策略 | F1 | 判对数 | 字段查询总数 |
|---|---:|---:|---:|
| A 固定顺序 | 0.8649 | 27/32 | 64 |
| B 条件分支 | 0.8108 | 25/32 | 23 |
| C 有限自主 Agent | 0.8333 | 26/32 | 11 |

C 相比 B 多判对的唯一一例是 T28。期刊全称和缩写在原判定器中被当成不同来源。固定全部动作、只修正这个别名后，两组对 32 对记录的预测一致。这项事后诊断及其输入与主实验分别留档。

## 核查入口

| 想核查的内容 | 对应文件 |
|---|---|
| 选题、实验设计、调整和交付过程 | [逐条对话原文](conversations/01-planning.md) |
| 数据来源、采样、提示词、评分步骤 | [实验复核说明](experiments/README.md) · [代码](experiments/study.py) · [模型选字段指令](experiments/controller-prompt.txt) |
| 32 对测试结果能否复算 | [原始样本和真值](results/cases.json) · [实际动作及逐例结果](results/main-traces.json) · [总表](results/main-summary.json) |
| 遮盖作者后，还有哪些可能的结果 | [成对轨迹](results/paired-traces.json) · [三种动作的全部 48 条重放](results/paired-replay.json) |
| 一条期刊缩写改变了哪一例 | [诊断代码](experiments/audit_venue.py) · [修正前后变化](results/venue-audit.json) |

在仓库根目录执行以下命令，可用 Python 标准库和已归档的模型动作重算结果。

```sh
python3 experiments/study.py second
python3 experiments/study.py score
python3 experiments/audit_venue.py
```

报告 PDF 和可编辑的 XeLaTeX 源文件使用同一份正文。发布版 PDF 采用本机中文排版生成。封面身份栏留空，便于在提交版本中填写。记录中的当前成绩和全部判断均可用上述命令复核。
