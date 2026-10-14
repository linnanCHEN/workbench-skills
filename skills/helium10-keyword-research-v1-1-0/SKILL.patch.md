# 变更记录

## 1.1.1

- 新增非阻断式“新对话建议”：长对话或已有上一轮 Helium 10 历史时，只建议一次使用最小启动模板；用户选择继续时必须照常执行。
- 第一个 ASIN 建立插件会话后，在插件允许时批量并行其余首屏与续页请求，减少完整模型往返。
- 明确大 CSV/JSON 直接落盘，整次任务只做一次字段与行数聚合、一次构建、一次读回验证。
- 新增运行效率收据；只有运行环境直接提供 usage 时报告 Token，否则输出 `TOKEN_USAGE=NOT_AVAILABLE`，不额外扫描 rollout 或主观估算。
- 新增长线程、拒绝另开线程和 usage 不可用三条回归样例。

### 回滚

- 回滚包：`work/helium10-skill-update/rollback-v1.1.0.zip`
- SHA-256：`4E0ABDAFDAB8B0D59540A357415D5526EBDE54EE4BC93EDE17B373B33A342D00`

## 1.1.0

- 将输入数量从固定 4 个 ASIN 调整为 2–5 个 ASIN。
- 保持过滤门槛不变：每个保留关键词必须至少有一个 ASIN 的自然排名在 1–24 位。
- 数据源明确为已安装的 Helium 10 插件，不另接或降级到 Helium 10 MCP。
- 将 `organic_rank` 设为核心必需字段；`sponsored_rank` 降为可选辅助字段，缺失时留空且不阻断出表。
- Excel 中自然排名列加粗并使用主色，广告排名列使用同色系浅色。
- 新增 2–5 个 ASIN、缺广告排名列、数量越界和 CLI 端到端回归。

### 回滚

- 回滚包：`work/helium10-skill-update/rollback-v1.0.0.zip`
- SHA-256：`F8A597A78EC3FB6D5902FB22D3BE17097507192D5C20CBB24BB682F9CEC3C00C`
