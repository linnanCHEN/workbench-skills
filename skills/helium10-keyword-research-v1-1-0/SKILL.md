---
name: helium10-keyword-research-v1-1-0
description: 当用户要求用 Helium 10 插件对 2–5 个 Amazon ASIN 做 Cerebro 反向关键词调研、以自然排名为核心生成彩色 Excel 汇总表时使用。先收集同一站点的 ASIN 和变体口径，再通过插件只读取数，保留至少一个 ASIN 自然排名前 24 的关键词；广告排名仅作可选辅助。不用于单 ASIN 拓词、Listing 写作、广告账户修改、排名追踪写入或缺少 Helium 10 插件时伪造数据。
---

# Helium 10 关键词调研

## 业务背景

这个 Skill 把 2–5 个竞品或目标 ASIN 的 Helium 10 Cerebro 关键词合并到一张可筛选的 Excel 表，重点横向比较同一关键词下各 ASIN 的自然排名；广告排名存在时作为辅助信息保留。它只通过已安装的 Helium 10 插件做第三方公开市场数据的只读取数、确定性过滤和表格导出，不生成广告动作，也不修改 Helium 10 或 Amazon 账户。

## 当前工作流（人工版）

人工做法通常是逐个 ASIN 在 Cerebro 导出关键词，再在 Excel 中统一关键词、复制排名、排序、删除没有自然首页表现的词，并手工设置颜色。主要痛点是字段容易错位、重复词口径不一致、漏删不满足前 24 条件的行，以及多 ASIN 列难以追溯。

## 输入要求

运行前必须取得：

1. 2–5 个互不重复、同一 Amazon 站点的 10 位 ASIN。
2. marketplace：`US`、`CA`、`MX`、`DE`、`ES`、`IT`、`FR`、`UK`、`IN`、`NL`、`AU`、`JP`、`AE`、`BR` 或 `SA`。
3. 变体口径二选一：
   - `parent_and_variations`：父体与全部子变体聚合，对应 `exclude_variations=false`。
   - `exact_asin`：只看输入的精准 ASIN，对应 `exclude_variations=true`。
4. 可选输出目录；未指定时在当前任务的 `output/` 下新建任务目录，文件名固定为 `关键词汇总.xlsx`。

如果用户只说“做 Helium 10 关键词调研”但没有给 ASIN，第一条回复只需用简短表单补齐以下信息，不调用工具：

```text
请提供同一站点的 2–5 个目标 ASIN（每行一个）：
站点代码：
变体口径：父体合并全部变体 / 仅精准 ASIN
```

不要推断、搜索或编造 ASIN。少于 2 个或多于 5 个时，先让用户修正。

## Skill 工作流（自动版）

### 0. 上下文与 Token 效率门（非业务阻断项）

- 如果当前对话已经包含上一轮 Helium 10 调研、大段工具日志/JSON/CSV，或大量无关项目历史，先用一句话建议用户在**新对话**中运行本次任务。新对话只携带本次 Skill 名称、ASIN、站点、变体口径和可选输出目录，避免每次模型调用重复处理旧上下文。
- 这是成本与速度建议，不是数据完整性门禁。用户要求继续当前对话时直接执行，不得因此标记 `BLOCKED`，也不得反复劝说。
- 不得擅自创建、迁移或分叉线程。只有用户明确要求“帮我新建线程/任务并运行”时，才可使用线程创建能力；否则仅提供下面的最小启动模板：

```text
使用 $helium10-keyword-research-v1-1-0
ASIN：（每行一个，共 2–5 个）
站点：
变体口径：父体合并全部变体 / 仅精准 ASIN
```

- 新对话不得继承上一轮 ASIN、站点、临时文件、下载链接或结论；每次运行使用独立任务目录。当前对话内也不得读取或关联其他业务 Skill，除非本 Skill 明确声明为必要依赖。
- 同一次运行只读取本 Skill 及必要引用一次；不要为了复述规则重复打开 `SKILL.md`。详细的工具往返、落盘和用量报告规则见 `references/context-efficiency.md`。

### 1. 校验请求

- ASIN 使用正则 `^[A-Z0-9]{10}$`，统一转大写并去重。
- 2–5 个 ASIN 必须属于同一 marketplace；跨站点任务必须拆开运行，禁止合并搜索量或排名。
- 记录输入顺序；Excel 中 ASIN 列按该顺序排列。
- 用户没有明确变体口径时必须补问，不能沿用工具默认值。

### 2. 调用 Helium 10 插件

使用已安装的 Helium 10 插件中的 ASIN 反向关键词能力 `get_keywords_by_asin`。不要另接 Helium 10 MCP，也不要调用其他供应商。`compare_asin_keywords` 只提供多 ASIN 对比摘要，不能替代逐个 ASIN 的自然排名明细。

每个 ASIN 的首个请求参数：

```yaml
asin: 用户提供的 ASIN
marketplace: 用户确认的站点
exclude_variations: 由变体口径映射
limit: 10000
response_format: download
export_format: csv
time_period: null
context: 拉取目标 ASIN 的当前 Cerebro 关键词、搜索量和自然排名，用于只读 Excel 汇总；广告排名存在时一并保留
```

- 第一次只对输入顺序中的第一个 ASIN 调用 Helium 10 插件且不传 `session_id`；收到插件返回的会话标识后，后续所有 Helium 10 插件调用必须原样复用，不向用户展示。
- 取得 `session_id` 后，在运行时与插件允许的前提下，把其余 ASIN 的首屏请求放进同一个并行工具批次，避免一个 ASIN 消耗一个完整模型往返。插件要求串行、出现限流或共享会话不支持并发时，退回串行并记录限制，不牺牲完整性换速度。
- 所有 ASIN 都必须处理。每次只提取并检查 `error`、`results_summary`、`pagination.has_more`、`pagination.next_cursor`、`pagination.truncated`、`truncation_reason`、`notice.message` 和下载文件元数据；不要把无关响应正文复制进会话。
- `has_more=true` 时继续用同一查询参数和返回的 cursor 拉下一页。不得把第一页误报为完整数据。
- 多个 ASIN 同时存在 `next_cursor` 时，在插件允许的前提下把续页请求合并为同一个并行工具批次；任何单个请求失败都单独记录并按完整性规则处理。
- 下载链接有时效，收到后立即保存到本次任务的临时目录；不要在回复或日志中展示完整链接。
- 如果出现 `traversal_bound`、无法续页、下载过期或任一 ASIN 失败，不伪造完整结果。能安全形成表格时标记 `PARTIAL` 并列出受影响 ASIN；否则标记 `BLOCKED`。
- `phrase`、`search_volume` 和 `organic_rank` 是核心字段；`sponsored_rank` 是可选辅助字段。仅缺广告排名时继续生成表格并留空，不得因此阻断自然排名汇总。
- 保留工具返回的 `notice.message` 原文并在最终回复中转告用户。

### 3. 生成 Excel

全部分页文件落盘后，统一做一次有界检查：只汇总文件名、字段名、行数、文件大小和缺失字段，不把 CSV 正文读入会话。整次任务只加载一次 Codex 工作区依赖以取得 bundled Python，然后只运行一次工作簿构建命令：

```powershell
python scripts/build_keyword_workbook.py `
  --source ASIN1=page-1.csv `
  --source ASIN2=page-1.csv `
  --output output/关键词汇总.xlsx `
  --receipt output/关键词汇总收据.json
```

按实际数量继续添加 `--source`，最多 5 个不同 ASIN；同一 ASIN 有多页时重复传入同一个 `ASIN=文件路径`。脚本依赖 `openpyxl`；依赖不可用时停止并说明，不全局安装或污染用户环境。

### 4. 读回验证

脚本成功后只做一次聚合读回验证；输出紧凑 JSON 或等价摘要，不逐行回传工作簿内容。至少确认：

- 工作表名为 `关键词汇总`，只有一张业务表。
- A 列是关键词，B 列是搜索量；随后每个 ASIN 固定两列：自然排名、广告排名。
- 2–5 个 ASIN 使用对应数量的不同颜色；同一 ASIN 保持同一色系，自然排名列突出显示，广告排名列使用较浅色。
- 搜索量按数值从大到小；相同搜索量按关键词升序，缺失搜索量排最后。
- 每个保留行至少有一个 ASIN 的自然排名为 1–24。
- 没有自然排名前 24 的关键词全部删除；广告排名不能让一行通过过滤。
- 缺失排名保持空白，不填 0；缺少 `sponsored_rank` 列或值时只留空，不影响自然排名结果。
- 收据中的输入行数、去重词数、保留数、删除数与工作簿一致。

## 合并与过滤规则

1. 关键词去重键为：去首尾空格、连续空白折叠、Unicode `casefold`。展示值使用输入 ASIN 顺序中首次出现的清洗后词组。
2. 同一 ASIN 同一关键词重复出现时，自然排名取最小正整数，表示检测到的最佳位置；存在广告排名时也按相同方式合并。
3. 同一关键词出现多个非空搜索量时，不做平均。脚本取最大值用于确定性排序，同时在 Excel 单元格批注和收据中记录所有观测值；存在冲突时最终状态不得高于 `PASS_WITH_LIMITS`。
4. 过滤条件固定为 `任一 ASIN 的 1 <= organic_rank <= 24`。无论输入 2、3、4 还是 5 个 ASIN，只要全部缺失自然排名、排名为 0、负数或全部大于 24，就删除整行。
5. 排名缺失与排名为 0 均不能解释为“第 0 名”；按未排名处理。
6. Search Volume 是 Helium 10 的月度估算，不得表述为 Amazon 官方精确值。

## Helium 10 插件与数据合同

```yaml
integration: Helium 10 plugin
capability: get_keywords_by_asin
scenario: 同一站点 2–5 ASIN Cerebro 关键词横向汇总
required_fields:
  - phrase
  - search_volume
  - organic_rank
optional_fields:
  - sponsored_rank
source_requirement: PUBLIC_MARKET_ALLOWED
read_only_or_write_action: read_only
schema_checked_at: 2026-10-13
route_status: ROUTE_SCHEMA_VERIFIED
stop_conditions:
  - Helium 10 连接不可用或无权限
  - 请求与返回站点不一致
  - 必需字段缺失且无法解释
  - pagination 无法完成且用户要求完整结果
```

这是用户明确指定的插件，不调用 Helium 10 MCP，也不自动换成 SellerSprite、SIF、Sorftime 或网页抓取。Schema 可见只证明插件工具合同可用，不代表真实 ASIN 数据已经验证；Schema、字段或站点枚举变化时重新核对。

## 核心原则 / 踩坑规避

- 全程只读；只使用 Helium 10 插件的 ASIN 关键词读取能力，禁止调用新增跟踪、删除关键词、广告管理或其他写入工具。
- 自然排名是核心指标；不把 `amazon_recommended_rank`、竞争平均排名、CPS 或广告排名当成自然排名。
- 广告排名仅作辅助，缺失时留空；不跨站点合并搜索量，不把缺失值补 0。
- 不把下载成功等同于数据完整；分页、总行数和截断状态都必须验证。
- 不在会话里粘贴大 CSV、完整 JSON 或时效下载链接；原始文件落入任务临时目录，只汇报统计和产物路径。
- 不使用子 Agent 拆分本流程；这会复制上下文并增加协调成本。通过同一轮并行工具批次减少往返，不得为了省 Token 跳过分页、字段或读回验证。
- 不为统计 Token 额外扫描整段会话日志。运行环境直接提供本轮 `usage` 时才报告输入、缓存输入、输出和总量，并标注为 best-effort；否则写 `TOKEN_USAGE=NOT_AVAILABLE`，不得估算或把账户额度百分比冒充本轮 Token。
- Excel 关键词以文本写入，防止以 `=` 开头的词组被解释成公式。
- 本 Skill 是数据导出流程，不是分析报告，不触发 Amazon HTML 报告渲染器。

## 触发场景

- “用 Helium 10 插件查这 3 个 ASIN 的关键词，按搜索量做一张自然排名汇总表。”
- “把 5 个竞品的 Cerebro 词合并成 Excel，重点对比自然位。”
- “只保留至少一个 ASIN 自然排名前 24 的关键词，并按 ASIN 分颜色。”
- “做 2–5 个 ASIN 的 Helium 10 关键词调研表，广告位有就带上。”

## 不适用场景

- 用户只要单个 ASIN 的原始 Cerebro 导出，或要求同时处理超过 5 个 ASIN。
- 用户提供的是 Walmart Item ID、SKU、广告 Campaign 或 Search Term 报表。
- 用户要求写 Listing、给广告出价/否词建议、修改 Keyword Tracker 或上传到 Amazon。
- 用户要跨站点比较，或要求用其他第三方数据源替代 Helium 10。

## 输出规范

- 主产物：`关键词汇总.xlsx`。
- 审计收据：`关键词汇总收据.json`，记录输入 ASIN、源文件、行数、过滤数量、搜索量冲突和工作簿 SHA-256。
- 完成信号必须包含：状态 `PASS`、`PASS_WITH_LIMITS`、`PARTIAL` 或 `BLOCKED`；Excel 绝对路径；保留关键词数；删除关键词数；数据完整性限制。
- 完成信号追加一行运行效率收据：`execution_scope=new_thread|current_thread`、`raw_rows_in_model_context=0`，以及可获得时的 `TOKEN_USAGE`；不可获得时明确写 `NOT_AVAILABLE`。
- 不生成 HTML，不上传 Seller Central，不发送到外部系统。

## 引用文件

- `references/context-efficiency.md`：新线程建议、工具批处理、原始数据落盘和 Token 收据规则。
- `scripts/build_keyword_workbook.py`：确定性合并、过滤、排序、着色与收据生成。
- `tests/test_build_keyword_workbook.py`：2–5 ASIN、自然排名过滤、可选广告列、冲突、缺列和公式安全回归。
- `evals/trigger-evals.json`：触发与反触发基准。

