---
name: evidence-mindmap-builder
description: Use when a case supplies notes, a paper section, or a project brief and asks for a mind map or concept structure; parses headings and paragraphs into a typed node tree (question, method, evidence, conclusion, risk, limitation, task), attaches a source- and character-level evidence locator to each node, reports per-material coverage, detects duplicates and overloaded branches, adds causal/contrast edges, and emits Mermaid plus JSON in /app/output/result.json while preserving case_id and every output_contract field. Deterministic standard library only; no network.
---

# 思维导图与概念结构（节点有出处—分支不超载—关系可解释）

## 用途与适用条件

当输入是一段笔记、论文小节或项目说明，需要整理成可核对的思维导图/概念图时使用。

适用：

- 有原始文本可定位，需要每个节点都能回到原文位置。
- 需要区分“研究问题、方法、证据、结论、风险、局限、任务”等节点类型。
- 需要检查重复节点、过深分支、单节点子项过多。
- 需要输出可直接渲染的 Mermaid mindmap 与机器可读节点表。

不适用：无源文的自由联想、替作者生成新观点、把未提供的因果关系画成事实。

## 输入

- `/input/case.json`：读取 `case_id`、`output_contract`、`task`、`title`/`topic`、`notes`/`text`/`materials`/`document`，可选 `max_children`、`max_depth`。
- `task.md`：存在时读取 `/input/task.md` 或 `/app/work/task.md`。
- 文本可内联或给路径；只读 UTF-8、≤2MB；不可解码的文件不建节点，由调用方在 `coverage` 标 `parsed:false`。
- 输出 `/app/output`，工作 `/app/work`。

## 处理流程（逐项覆盖评分维度）

1. **结构解析（立得住）**：优先按 Markdown 标题层级建树；无标题时按段落建一层节点；段落内句子作为子节点候选。多份可读材料全部合并建树（不取最长一份），每个节点用 `source` 指明来源；不可解码的文件在 `coverage` 中标 `parsed:false` 与原因，不静默丢弃。
2. **节点分类（分得清）**：按关键词与形态判定 `question / method / evidence / conclusion / risk / limitation / task / concept`；判据写入 `type_reason`，便于复核。
3. **证据定位（核得了）**：每个节点记录 `source`、`page`（材料有页码时）、`paragraph_index`、`char_start`、`char_end` 与原文引用（≤120 字）；定位不到的内容不建节点。
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
  - `result`：`mindmap`、`nodes`、`edges`、`evidence_map`、`structure_issues`、`outline`、`sources`、`coverage`、`review_queue`
  - `evidence`、`uncertainty`、`errors`、`stats`
- 节点字段：`id`、`label`、`type`、`type_reason`、`parent`、`depth`、`source`、`page`、`paragraph_index`、`char_start`、`char_end`、`quote`、`duplicate_of`。
- `coverage[]`：每份材料一项 `{label, path, chars, char_offset, parsed, reason}`；`parsed:false` 时 `reason` 写格式或权限原因，`review_queue` 列出待人工读取项。
- `review_queue[]`：需人工确认的项 `{item, kind, question, locator}`，kind 取 `conflict`/`missing`/`ambiguous`。
- 退出码：脚本恒以 `0` 结束；以 `status` 与 `contract_status.unmapped_fields` 判断是否完整，不依赖退出码。

## 异常处理

| 情形 | 处置 |
|---|---|
| 无文本 | `status=insufficient_input`，不生成空图 |
| 文件为 PDF/二进制或编码不可读 | 不建节点；`coverage` 标 `parsed:false` + `reason`，`review_queue` 列入待人工读取 |
| 多份材料互相矛盾 | 两方节点都保留并标 `conflict`，`review_queue` 提问，不替作者裁决 |
| 材料缺章节或表格 | 写入 `coverage.reason` 或 `uncertainty`，不补写内容 |
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

## 调用与自检

```bash
python /skills/weekly-skill/scripts/run_skill.py --case /input/case.json --out /app/output/result.json
```

`--out` 与 `--output` 等价；默认 `/input/case.json` → `/app/output/result.json`。脚本只做结构解析；`coverage`、`review_queue` 与完整分支由调用 Agent 在同一 `result.json` 中补齐，不得只交根节点或 `pending`。

- [ ] `case_id` 与输入一致；`output_contract` 每字段存在（未映射为 `null` 并登记）。
- [ ] 每份材料都在 `coverage` 中：可读的进节点，不可读的写 `parsed:false` + `reason`。
- [ ] 每个节点有 `id`、`type`、`type_reason`、`source`、`paragraph_index`、`char_start`/`char_end` 与 `quote`。
- [ ] 冲突与缺口进 `review_queue`，未冒充事实。
- [ ] `mindmap` 缩进与转义一致，可在 Mermaid 中直接渲染；重复节点只标记不删除。
- [ ] 未新增源文没有的节点、数字或因果边；未声称平台评分。
