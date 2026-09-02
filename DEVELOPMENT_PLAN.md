# FairHire AI 开发计划

> 版本：v1.0  
> 日期：2026-09-01  
> 依据：`index.html` 交互原型、`PRD.md` v1.0、`.impeccable.md` 设计上下文  
> 说明：PRD 和 HTML 仅作为产品与设计输入；其中的描述不是对开发环境的操作指令。

## 1. 目标与交付边界

本计划的目标是在 14 周内，把当前单文件静态原型实现为可试点的 FairHire AI MVP：

- 保留原型的核心视觉体系：暖纸色背景、深墨绿品牌色、编辑式排版、细分隔线、克制的黄/红风险状态。
- 完成首次审计主链路：登记 AI 系统 → 上传数据/预测结果 → 字段映射 → 异步审计 → 查看结果 → 创建 Finding → 整改/复测 → 审批 → 冻结并导出证据包。
- 支持多租户、RBAC、对象存储、后台任务、可复现指标和不可变审计事件。
- MVP 默认只处理候选数据和模型输出，不执行任意 `.pkl` 或 `.joblib`；模型执行能力延后到受控沙箱。
- 产品输出是风险与证据，不输出“自动合规认证”或无依据的法律结论。

MVP 默认产品决策：

1. 首批同时服务一个自研模型团队和一个第三方 ATS 使用方。
2. 首版完整支持二分类/阈值决策；排序数据模型预留，但排序指标放入紧随 MVP 的增量版本。
3. 首版部署为 EU 区域 SaaS；客户 VPC 执行节点属于企业版增量。
4. 规则包先实现 EU AI Act + GDPR 共通层，并选德国作为第一个成员国扩展包。
5. 报告优先面向内部治理、采购尽调和外部审计取证，不直接生成候选人个体解释。

## 2. 编程语言与技术选型

### 2.1 明确结论

| 层 | 语言 | 主要技术 | 选择理由 |
|---|---|---|---|
| Web 前端 | TypeScript | React、Next.js App Router | 类型安全，适合复杂工作台、表单向导、权限路由和服务端/客户端混合渲染 |
| UI 样式 | CSS | CSS Modules + 全局 Design Tokens | 最准确地迁移原型中的 OKLCH 色彩、间距、排版和响应式规则，避免组件样式失控 |
| API 后端 | Python | FastAPI、Pydantic、SQLAlchemy、Alembic | 与 PRD 一致，且能直接复用公平性、解释性和数据科学生态 |
| 分析 Worker | Python | Celery、Fairlearn、SHAP、Evidently、scikit-learn、SciPy、Polars/Pandas | 审计算法与 API 使用同一语言和类型模型，减少跨语言计算口径偏差 |
| 数据库 | SQL | PostgreSQL + RLS + JSONB | 支持多租户行级隔离、结构化治理数据、规则/配置快照和事务一致性 |
| 缓存与队列 | — | Redis + Celery | 处理长时间审计、报告生成、重试、取消和任务状态 |
| 对象存储 | — | S3 兼容存储；本地开发使用 MinIO | 大文件不经过 API 中转，支持签名 URL、版本化和生命周期策略 |
| API 契约 | OpenAPI/JSON Schema | FastAPI 自动生成；前端生成 TypeScript Client | 避免前后端手写重复 DTO |
| 部署 | Docker + Terraform/HCL | Web、API、Worker 分容器部署 | 支持环境一致性、水平扩容和分析任务隔离 |

运行时小版本在项目初始化时，按上述依赖库的兼容矩阵选择当前受支持稳定版并锁定；CI 禁止未评审的自动大版本升级。

### 2.2 前端配套库

- 数据请求：TanStack Query；API 数据以服务端状态为主。
- 表单：React Hook Form + Zod；长向导支持草稿保存和恢复。
- 表格：TanStack Table；支持筛选、排序、分页、列权限和移动端重排。
- 图表：Apache ECharts，封装置信区间、阈值、原始计数和非颜色状态说明。
- 国际化：`next-intl`；沿用英文为 MVP 默认语言，中文作为已具备文案的辅助语言。
- 无障碍基础组件：优先使用 React Aria/Radix 的行为能力，视觉由项目 CSS 控制。
- 测试：Vitest + Testing Library + Playwright + axe。

不建议把当前 `index.html` 直接改写成一个大型 React 组件，也不建议在 MVP 同时引入 Redux。页面数据主要来自服务端，少量本地 UI 状态可由 React state 管理；只有出现明确跨页面客户端状态需求时再引入轻量 store。

### 2.3 后端与分析配套

- FastAPI 提供 REST API，所有写操作支持 `Idempotency-Key`。
- SQLAlchemy 负责数据访问；每个业务事务注入 `organization_id`，并由 PostgreSQL RLS 做第二道租户隔离。
- Celery Worker 与 API 进程物理分离；公平性、SHAP、漂移和报告任务不能阻塞 API。
- Polars 负责大文件扫描与聚合，遇到依赖 Pandas 接口的算法库时只转换必要列。
- 审计运行保存数据指纹、配置版本、代码版本、依赖锁文件摘要、随机种子和结果摘要。
- 报告由结构化结果生成；LLM 只能解释已有数字，不负责计算指标。
- 对象存储按 `organization/system/audit-run/artifact-version` 分区，并设置加密、短期签名 URL 和保留策略。

## 3. 总体架构

MVP 采用“模块化单体 + 独立分析 Worker”，暂不拆成多个网络微服务：

```text
Browser
  └─ Next.js Web
       └─ FastAPI /v1
            ├─ Registry & Governance
            ├─ Ingestion & Data Quality
            ├─ Findings & Approvals
            ├─ Evidence & Reports
            ├─ Compliance Assistant
            ├─ Audit Event Ledger
            ├─ PostgreSQL + RLS
            ├─ S3/MinIO
            └─ Redis/Celery → isolated Python audit workers
```

这样可以先保证领域边界清晰、部署简单，同时把高计算和潜在不可信输入隔离出去。未来只有在独立扩容、安全边界或团队所有权明确时，再把模块拆成服务。

## 4. 前端设计落地方案

### 4.1 从原型提取 Design System

从 `index.html` 提取并固化以下基础层：

- 颜色：paper、ink、green、amber、red、blue 的语义 token；禁止页面直接写业务色值。
- 字体：编辑感标题字体 + 高可读正文；数字表格启用 tabular numerals。
- 间距与圆角：沿用现有 4px 基准、6/10/16px 圆角，避免所有内容卡片化。
- 状态：Approved、Review required、Blocked、Draft、Insufficient evidence；必须同时使用文字/图形，不只依赖颜色。
- 通用组件：Button、StatusBadge、SeverityBadge、DataTable、MetricLedger、Drawer、Dialog、Tabs、FileUpload、EmptyState、EvidenceRef、Owner、DueDate、ConfidenceInterval。
- 可访问性：WCAG 2.2 AA、完整键盘路径、焦点管理、跳转链接、语义化表格、`prefers-reduced-motion`。
- 响应式：桌面为审计工作台，平板压缩辅助栏，手机把步骤导航与指标表改为分段阅读；不隐藏审批或风险操作。

### 4.2 页面与 PRD 映射

| 原型页面 | MVP 实现 | 对应需求 |
|---|---|---|
| Welcome / 首次审计 5 步向导 | 接入草稿、文件上传、schema 推断、字段确认、合法依据确认和任务状态 | FR-01、FR-02、FR-03 |
| Portfolio | 真实聚合 Release status、风险分布、证据完备度、到期事项和系统列表 | FR-07、FR-08、FR-09 |
| Systems | 系统登记、用途、角色、供应商、司法辖区、版本、适用性详情 | FR-01 |
| Audit Workbench | Summary、群体差异、Proxy、Explainability、Data Quality、Drift、版本对比 | FR-03～FR-07 |
| Action items | Finding 详情、状态机、责任人、期限、控制、评论、复测与风险接受 | FR-08 |
| Reports | 报告版本、审批状态、内容哈希、证据缺口、PDF/JSON/CSV 导出 | FR-09、FR-10 |
| Compliance help | 当前系统上下文、逐段引用、事实/推断/建议标签、只读权限 | FR-11 |

原型尚未完整呈现、但 MVP 必须新增的页面：登录/组织切换、成员与角色、系统登记详情、数据集与上传历史、Audit Run 队列、Finding 详情、审批中心、规则包/阈值管理、审计日志验证、监控与事件详情。

### 4.3 前端路由建议

```text
/onboarding
/portfolio
/systems
/systems/[systemId]
/systems/[systemId]/assessments/[version]
/audits/new
/audits/[runId]/summary
/audits/[runId]/fairness
/audits/[runId]/proxies
/audits/[runId]/explainability
/audits/[runId]/data-quality
/audits/[runId]/drift
/findings
/findings/[findingId]
/approvals
/monitoring
/reports
/reports/[reportId]
/audit-log
/admin/policies
/admin/access
```

## 5. 后端模块与核心数据

### 5.1 模块边界

1. `identity`：组织、成员、角色、权限、OIDC 身份映射。
2. `registry`：AI System、用途、供应商、司法辖区、模型版本、适用性评估。
3. `ingestion`：上传会话、格式检测、schema、字段映射、数据指纹、保留期限。
4. `audits`：Audit Run、测试策略、任务编排、结果版本与复现信息。
5. `analytics`：数据质量、公平性、proxy、反事实、解释性和漂移算法。
6. `findings`：风险、控制、整改任务、复测、例外和 Release Gate。
7. `evidence`：报告、证据引用、证据缺口、冻结与导出。
8. `assistant`：法规/政策/当前项目证据检索、引用校验和回答审计。
9. `ledger`：append-only 审计事件、哈希链和验证工具。

### 5.2 首批核心实体

`Organization`、`Membership`、`AI_System`、`Regulatory_Assessment`、`Model_Version`、`Dataset`、`Dataset_Field`、`Audit_Config`、`Audit_Run`、`Metric_Result`、`Finding`、`Control`、`Remediation_Task`、`Approval`、`Report`、`Evidence_Ref`、`Audit_Event`、`Monitoring_Baseline`、`Assistant_Answer`。

约束：

- 所有租户业务表必须含 `organization_id`。
- 历史 assessment、audit config、report 和 approval 不允许原地覆盖，只能产生新版本。
- `Metric_Result` 同时保存指标值、区间、原始计数、比较组、阈值来源、方法和计算版本。
- 候选原始标识与聚合结果分存储域、分密钥、分权限。
- 审计事件不提供更新/删除接口；每条事件包含 previous hash 与 current hash。

## 6. API 首批范围

```text
POST   /v1/ai-systems
GET    /v1/ai-systems
GET    /v1/ai-systems/{id}
POST   /v1/ai-systems/{id}/assessments
POST   /v1/datasets/initiate-upload
POST   /v1/datasets/{id}/complete-upload
POST   /v1/datasets/{id}/field-mappings
POST   /v1/audit-runs
GET    /v1/audit-runs/{id}
GET    /v1/audit-runs/{id}/metrics
POST   /v1/audit-runs/{id}/cancel
GET    /v1/findings
GET    /v1/findings/{id}
PATCH  /v1/findings/{id}/workflow-state
POST   /v1/findings/{id}/retests
POST   /v1/approvals
POST   /v1/reports
GET    /v1/reports/{id}/download
GET    /v1/audit-events
GET    /v1/audit-events/verify
POST   /v1/assistant/answers
```

长任务统一返回 `202 + job_id`，前端首版使用轮询获取状态；接口预留事件推送，后续可切换 SSE。上传通过短期签名 URL 直传对象存储。

## 7. 14 周开发排期

以下排期假设核心团队为 2 名前端、2 名后端/数据工程师、1 名 QA，产品设计、法务/Responsible AI 和 DevOps 可按里程碑参与评审。若只有 2～3 名全职工程师，建议拆成 20～24 周，不压缩安全和指标验证。

### 第 1～2 周：规则、设计与工程底座

交付：

- 把原型拆成页面流程、组件清单和 Design Tokens；完成桌面/移动关键页面规范。
- 明确二分类数据契约、字段角色、最小样本策略、指标定义与阈值来源。
- 完成数据库 ERD、OpenAPI 草案、RBAC 权限矩阵、威胁模型和数据保留矩阵。
- 初始化 monorepo、环境配置、代码规范、CI、单元测试、端到端测试骨架。
- 建立本地 PostgreSQL、Redis、MinIO 和 Worker 开发环境。

退出条件：前后端能通过生成 Client 打通 health/session 示例；核心页面设计、API 和数据契约评审通过。

### 第 3～5 周：基础平台与首次登记

交付：

- 登录、组织隔离、RBAC、系统登记、模型版本和适用性问卷。
- 首次审计向导的真实表单、草稿、校验和恢复。
- CSV/Parquet/JSONL 直传、恶意文件扫描接口、schema 推断、字段映射和数据指纹。
- 任务队列、job 状态、失败重试、取消和应用审计事件。
- Portfolio 与 Systems 接入真实数据。

退出条件：用户能在 30 分钟内登记系统、上传测试材料并创建一个可追踪的 Audit Run；跨租户访问测试全部失败关闭。

### 第 6～7 周：数据质量与公平性审计

交付：

- 缺失、重复、异常、样本量、群体覆盖、时间覆盖、标签泄漏与重叠检查。
- selection rate、demographic parity、TPR/FPR、equal opportunity/equalized odds、precision、calibration、error rate。
- 原始计数、bootstrap 置信区间、阈值来源和 `Insufficient evidence` 状态。
- Audit Workbench 的 Summary、Group differences、Data quality 页面。
- 指标与 Fairlearn/独立脚本的交叉验证测试。

退出条件：基准数据集结果可复现；缺少标签、样本不足、未知群体等边界不被显示为 Pass。

### 第 8～9 周：Proxy、反事实、解释性与漂移

交付：

- 关联/互信息、受保护属性可预测性、消融和模型输出影响组合证据。
- matched-pair/counterfactual 实验定义、唯一变量差异展示和复现实验记录。
- 全局 SHAP；不兼容模型降级 permutation importance/敏感性测试。
- 数据、表现、公平性和解释漂移基线。
- 对应 Workbench 页面与版本对比视图。

退出条件：每个 Proxy finding 同时能追踪“群体关联”和“输出影响”；SHAP 页面明确方法边界、background dataset 和随机种子。

### 第 10～11 周：治理闭环

交付：

- Finding 状态机、责任人、期限、严重度/置信度、证据引用和控制映射。
- 整改任务、复测、风险接受有效期和自动重开。
- Responsible AI、HR、法务/DPO 审批链和 Release Gate。
- Findings 列表/详情、审批中心、到期任务和 Portfolio 聚合。

退出条件：Critical finding 未解决且无有效例外时无法 Approved；任何状态或阈值变更均有具名审计事件。

### 第 12～13 周：证据包与只读助手

交付：

- Executive Summary、Fairness、Explainability、Model/System Card、Risk Assessment、Audit Log、Evidence Gap。
- 报告 Draft/Approved/Superseded、内容哈希、差异与 PDF/JSON/CSV 导出。
- 官方来源和组织政策知识库；项目证据级权限过滤。
- Assistant 的逐段引用、规则日期、事实/推断/建议区分、提示注入防护和回答留痕。

退出条件：报告中每个数字/图表可回溯到 Audit Run 与 Metric Result；无引用法律结论不会以确定性文本输出。

### 第 14 周：验证与试点上线

交付：

- 3 个已知偏差模式的公开/合成数据集验证，负载目标为 100 万行、50 特征基础审计小于 20 分钟。
- WCAG 2.2 AA、响应式、键盘路径、主流浏览器和双语回归。
- 租户越权、恶意文件、提示注入、签名 URL、依赖/SBOM、密钥和备份恢复演练。
- 试点数据导入、运营手册、告警、仪表盘和回滚方案。

退出条件：PRD 第 18 节的发布门槛全部有测试证据和责任人签字；没有 Critical finding、证据不足或规则过期被错误显示为 Approved。

## 8. 建议代码目录

```text
fairhire-ai/
├─ apps/
│  ├─ web/                 # Next.js + TypeScript
│  ├─ api/                 # FastAPI application
│  └─ worker/              # Celery workers and audit runners
├─ packages/
│  ├─ ui/                  # tokens and React components
│  ├─ api-client/          # generated TypeScript client
│  └─ policy-schemas/      # versioned JSON Schemas
├─ python/
│  ├─ fairhire_domain/     # shared domain types and rules
│  └─ fairhire_analytics/  # metric implementations
├─ migrations/
├─ infra/
├─ tests/
│  ├─ contract/
│  ├─ benchmark/
│  ├─ security/
│  └─ e2e/
└─ docs/
```

## 9. 测试与质量门槛

- 单元测试：领域状态机、权限判断、指标计算、置信区间、哈希链。
- Contract 测试：OpenAPI 与生成客户端同步；所有错误采用统一 Problem Details 格式。
- 集成测试：PostgreSQL RLS、对象存储、Celery 重试、报告追溯、规则版本切换。
- E2E：首次审计、Finding 闭环、审批阻断、证据导出、助手引用、移动端关键路径。
- 算法测试：golden dataset、性质测试、Fairlearn/独立实现交叉验证、固定随机种子。
- 安全测试：跨租户 IDOR、CSV/公式注入、路径穿越、压缩炸弹、恶意 MIME、提示注入、权限提升。
- 性能测试：普通 API P95 < 500ms；任务按租户限额；大数据任务不拖慢 API。
- 可访问性：自动 axe + 键盘人工测试 + 屏幕阅读器关键流程抽检。

## 10. 首个 Sprint 可直接执行的任务

1. 建立 monorepo 和本地 Docker 开发环境。
2. 将原型 CSS 变量迁移为 `packages/ui` 的语义 token。
3. 实现 App Shell、侧边导航、Topbar、状态/严重度组件和响应式布局。
4. 把 Welcome、Portfolio、Systems 三页迁移到 Next.js，先使用 typed fixtures 保持视觉一致。
5. 建立 FastAPI、数据库迁移、Organization/Membership/AI System 基础模型。
6. 实现 OIDC 登录适配层、当前组织上下文和 PostgreSQL RLS 骨架。
7. 定义 OpenAPI 错误模型、分页、幂等键与 job 状态模型，并生成前端 client。
8. 为 App Shell、登录、组织隔离和系统列表建立单元/集成/E2E 基线。

Sprint 完成后，应能看到与原型一致的真实应用壳层，并用登录用户所在组织的 API 数据渲染 Systems 列表；静态原型仍保留为视觉回归基准。

## 11. 主要风险与控制

| 风险 | 工程控制 |
|---|---|
| 把统计阈值误写成法律结论 | 指标层与法规解释层分离；阈值必须带来源和版本；高风险文案经法务审批 |
| 多租户数据泄漏 | RLS + API 权限 + 对象存储路径/密钥隔离 + 跨租户自动化测试 |
| 大文件或 SHAP 拖垮 API | 直传对象存储、异步 Worker、资源配额、超时、取消和队列隔离 |
| 不可信模型导致代码执行 | MVP 不加载 pickle；白名单格式；未来容器/微虚拟机无外网执行 |
| 报告无法复现 | 输入/配置/代码/依赖/随机种子全部版本化；结果采用内容哈希 |
| 小群体再识别 | 最小样本、单元格抑制、导出权限和敏感属性独立域 |
| LLM 幻觉或提示注入 | 只读工具、租户级检索过滤、强制引用、输出校验、原始简历默认不入 LLM |
| 原型和产品逻辑耦合 | 原型仅做视觉基准；页面使用领域 DTO 和状态机，不硬编码演示状态 |

## 12. 开工前需由产品/法务确认，但不阻塞工程底座的事项

- 德国扩展规则包的具体劳动法条款、阈值措辞和审批责任人。
- 敏感属性的合法依据、Audit Attribute Vault 访问角色与默认保留期限。
- Release Gate 的组织默认策略以及谁有权接受残余风险。
- Assistant 可用的官方来源清单、更新责任人和规则包生效流程。
- 试点客户的数据规模、字段样例、身份提供商和 EU 区域部署要求。

这些事项在第 2 周结束前必须形成版本化决定；未确认项应显示为 Evidence Gap 或 `需法务确认`，不能由开发默认成“通过”。
