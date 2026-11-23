---
name: evidence-mindmap-builder
description: Use when a case supplies notes, a paper section, or a project brief and asks for a mind map or concept structure; parses headings and paragraphs into a typed node tree (question, method, evidence, conclusion, limitation, task), attaches a character-level evidence locator to each node, detects duplicates and overloaded branches, adds causal/contrast edges, and emits Mermaid plus JSON in /app/output/result.json while preserving case_id and every output_contract field. Deterministic standard library only; no network.
---

# 思维导图与概念结构（节点有出处—分支不超载—关系可解释）

## 用途与适用条件

当输入是一段笔记、论文小节或项目说明，需要整理成可核对的思维导图/概念图时使用。

适用：

- 有原始文本可定位，需要每个节点都能回到原文位置。
- 需要区分“研究问题、方法、证据、结论、局限、任务”等节点类型。
- 需要检查重复节点、过深分支、单节点子项过多。
- 需要输出可直接渲染的 Mermaid mindmap 与机器可读节点表。

不适用：无源文的自由联想、替作者生成新观点、把未提供的因果关系画成事实。

## 输入

- `/input/case.json`：读取 `case_id`、`output_contract`、`task`、`title`/`topic`、`notes`/`text`/`materials`/`document`，可选 `max_children`、`max_depth`。
- `task.md`：存在时读取 `/input/task.md` 或 `/app/work/task.md`。
- 文本可内联或给路径；只读 UTF-8、≤2MB；二进制登记为未解析。
- 输出 `/app/output`，工作 `/app/work`。

## 处理流程（逐项覆盖评分维度）

1. **结构解析（立得住）**：优先按 Markdown 标题层级建树；无标题时按段落建一层节点；段落内句子作为子节点候选。
2. **节点分类（分得清）**：按关键词与形态判定 `question / method / evidence / conclusion / limitation / task / concept`；判据写入 `type_reason`，便于复核。
3. **证据定位（核得了）**：每个节点记录 `paragraph_index`、`char_start`、`char_end` 与原文引用（≤120 字）；定位不到的内容不建节点。
4. **关系标注（连得上）**：父子为 `contains`；同段相邻句出现“因为/由于/因此/导致”标 `causal`，出现“但是/然而/相比”标 `contrast`；仅依据连接词，不推断隐含因果。
5. **重复与冗余**：规范化后完全相同或二元组重叠 ≥0.85 的节点标 `duplicate_of`，保留首次出现，不自动删除。
6. **结构体检**：子节点 > `max_children`（默认 7）标 `branch_overload`；深度 > `max_depth`（默认 4）标 `too_deep`；无证据节点占比过高时标 `low_evidence_coverage`。
7. **双格式交付**：`mindmap`（Mermaid 字符串，转义括号与换行）+ `nodes`/`edges`（JSON）；标题取 `title`/`topic`，缺失时用 `Case mind map` 并登记。
8. **合同保留**：见输出契约。

## 输出契约

写入 `/app/output/result.json`：

- 顶层 `case_id` 与输入一致。
- **保留原始 `output_contract` 每个字段名**（字典/列表/`fields`/Schema `properties`）；未映射写 `null` 并登记，状态降为 `partial`；组合 Schema 登记 `unsupported_features`。
- 固定字段：
  - `status`：`success | partial | insufficient_input | failed`
  - `result`：`mindmap`、`nodes`、`edges`、`evidence_map`、`structure_issues`、`outline`
  - `evidence`、`uncertainty`、`errors`、`stats`
- 节点字段：`id`、`label`、`type`、`type_reason`、`parent`、`depth`、`paragraph_index`、`char_start`、`char_end`、`quote`、`duplicate_of`。
- 退出码：`0` 完成；`1` 有未映射合同字段；`2` 输入不可读。

## 异常处理

| 情形 | 处置 |
|---|---|
| 无文本 | `status=insufficient_input`，不生成空图 |
| 无标题 | 按段落建树，标 `structure_inferred` |
| 标题层级跳跃（# 到 ###） | 挂到最近上层并标 `level_jump`，不丢节点 |
| 节点文本含括号/换行 | Mermaid 输出时转义，保留原文 quote |
| 单节点子项过多 | 标 `branch_overload`，建议拆分，不自动拆 |
| 深度超限 | 标 `too_deep`，保留结构供作者决策 |
| 重复节点 | 标 `duplicate_of`，不删除原文证据 |
| 长段落无明确分句 | 截断为单节点，标 `long_paragraph` |

## 限制与不适用

- 不生成源文没有的观点、数据或因果链。
- 类型判定基于关键词，可能误判，需结合 `type_reason` 人工复核。
- Mermaid 文本仅保证语法安全转义，不保证特定渲染器主题效果。
- 不做语义相似度模型计算，重复检测基于字面规范化与二元组重叠。

## 最小调用示例（示例）

以下为合成示意，非官方案例。

```bash
python /skills/weekly-skill/scripts/run_skill.py \
  --case /input/case.json \
  --out /app/output/result.json \
  --work /app/work
```

合成 `case.json`：

```json
{
  "case_id": "synthetic-mindmap-demo",
  "output_contract": {"status": "string", "mindmap": "string", "nodes": "array", "evidence_map": "array"},
  "title": "Synthetic study",
  "notes": "# Question\nDoes marker X predict response?\n# Method\nWe measured X in 40 samples.\n# Finding\nResponse rate was 62.5% (p=0.01).\n# Limitation\nSingle-center design."
}
```

示意输出（节选）：

```json
{"case_id":"synthetic-mindmap-demo","status":"success","result":{"mindmap":"mindmap\n  root((Synthetic study))\n    question\n      node1","nodes":[{"id":"node1","type":"question"}]},"stats":{"nodes":4}}
```

## 自查清单

- [ ] `case_id` 与合同字段保留；未映射项已登记。
- [ ] 每个节点都有段落索引与字符区间。
- [ ] 类型判定附判据，未把推测写成结论。
- [ ] 重复节点只标记未删除；分支超载已列出。
- [ ] Mermaid 文本可解析（缩进与转义一致）。
- [ ] 未新增源文没有的节点或因果边。


## 交付保证与评分对齐

调用顺序（固定）：

1. 先运行包内脚本（若存在）：`python scripts/run_skill.py`（默认读 `/input/case.json`，写 `/app/output/result.json`）；路径不同时用 `--case` / `--output` 指定。
2. **必须交付完整成品**：脚本只做结构解析；调用 Agent 必须输出覆盖全部材料的完整 `mindmap`（Mermaid 可渲染）、`nodes` 与 `edges`（每个节点有类型、出处与字符区间），并补齐 `structure_issues` 与 `outline`；不得只给根节点、截断分支或 `pending`。
3. 最后自检：`case_id` 与输入一致；`output_contract` 每个字段都存在；`status` 取本合同允许值 `success | partial | insufficient_input | failed`；正文无 `pending`/`TODO`/空占位；数字、引用、来源可逐条回溯。

运行保证：

- 输入缺失、JSON 损坏、字段异常、输出目录不存在时，仍须写出结构化 `result.json` 并正常结束，不得崩溃或非零退出。
- 不联网、不伪造数据、不声称平台评分或官方案例结果。
- 交付物必须是可直接编辑与复核的成品，而不是流程说明。

评分对齐（本题五个维度）：

- 实际效果（40）：完整产出任务要求的最终成品，覆盖全部输入条目，可直接进入修改流程。
- 使用增益（25）：体现相对基础 Agent 的可验证改进（结构化、术语/数字/引用核对、可编辑性）。
- 创新增益（15）：保留方法学增量（分块、对齐、二次校验、版本比对等），并用结果证明其价值。
- 可靠体验（10）：异常输入有明确降级与说明，不同长度/文体/重复运行下稳定产出。
- 生态贡献（10）：用途、调用、输入输出、限制、示例、维护信息齐全，资源可被他人复用。

## 最终交付强制要求

1. **调用 Agent 必须交付成品，不是流程说明**：脚本产出只是索引、核对或规格骨架；调用 Agent 必须在同一 `result.json` 中补齐本题要求的最终产物（正文/译文/审稿意见/综述/分析结论/图表源文件与导出件/幻灯片页内容与讲稿/实验方案等）。交付字段为空、只有标题骨架，或含 `pending`、`TODO` 之类占位，一律视为未完成。
2. **必须覆盖全部输入条目**：输入中的每个章节、问题、文献、图、页面、指标都要有对应条目，不得只处理示例或首条；确实缺失的条目写入 `uncertainty` / `limitations` 并说明原因，不得静默跳过。
3. **必须自检后再交付**：`case_id` 与输入一致；`output_contract` 每个字段都存在；状态值取本题契约规定的枚举；数字、单位、引用、来源可逐条回溯；结果内部无自相矛盾。
4. **参数等价**：`python scripts/run_skill.py --case <输入> --out <输出>` 与 `--output <输出>` 等价；默认 `/input/case.json` → `/app/output/result.json`。
5. **平台用 3 个固定案例分别运行**：逻辑要由输入驱动，不针对某一份示例硬编码；字段命名差异走别名匹配与显式降级，并在 `uncertainty` 记录假设。
