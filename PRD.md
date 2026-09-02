# FairHire AI 产品需求文档（PRD）

> Recruitment AI Assurance & Evidence Platform

| 项目 | 内容 |
|---|---|
| 文档版本 | v1.0 |
| 日期 | 2026-08-31 |
| 状态 | 可进入 MVP 评审 |
| 产品定位 | 面向招聘 AI 提供持续审计、风险控制与合规证据管理 |
| 目标区域 | EU 优先，后续扩展英国与美国州/城市级规则 |
| 免责声明 | 本产品提供技术评估和合规工作流，不提供法律意见或监管认证 |

## 1. 产品判断

### 1.1 结论

项目方向正确，且比开发“自动筛掉候选人”的招聘系统更有差异化和长期价值。招聘中的 CV 筛选、候选人排序、工作分配与绩效评估属于 EU AI Act 高风险使用场景；企业不仅需要一次性的公平性报告，还需要证明其在整个系统生命周期中持续进行风险管理、数据治理、日志留存、人类监督和上线后监控。

原始设计的不足在于，它更像一个“上传模型后生成几张算法报告”的检测工具。真正可购买、可落地的产品应升级为：

**招聘 AI 的持续控制与证据管理平台，而不是自动颁发“合规证书”的扫描器。**

平台的核心交付物不是一个总分，而是一套可复核的证据链：适用性判断、测试范围、数据来源、模型版本、指标与不确定性、风险、控制措施、责任人、审批记录、整改结果和持续监控记录。

### 1.2 对原始技术方案的调整

- 保留 FastAPI、PostgreSQL、Fairlearn、SHAP、Evidently。
- 增加异步任务队列、对象存储和隔离执行环境；公平性审计和 SHAP 计算不能阻塞 API。
- MVP 优先支持“候选数据 + 模型输出/决策结果”，而不是直接执行任意上传模型。这样能覆盖 SaaS 招聘模型、第三方供应商和黑盒 API，也避免反序列化恶意 pickle 的风险。
- 模型文件执行作为受控能力：首选 ONNX、安全格式或客户提供的容器/API；不直接加载不可信 `.pkl`、`.joblib`。
- LLM compliance assistant 放在证据层之上，用检索增强生成回答并逐条引用来源；它不能修改审计结果、给出无依据的法律结论或替代 DPO/法务审批。
- 增加“成对反事实测试”：对技能和经历完全相同的候选档案，只改变姓名、性别提示、年龄或国籍相关信号，检测输出是否发生不合理变化。

## 2. 背景与监管基线

截至本文日期，欧盟委员会将招聘 CV 排序等就业 AI 列为高风险场景。高风险系统的主要要求包括风险管理、数据质量与治理、技术文档、活动日志、向部署方提供信息、人类监督，以及准确性、稳健性和网络安全。Annex III 高风险规则现计划自 **2027 年 12 月 2 日**起适用。

平台必须同时考虑但不得混淆以下义务：

- **EU AI Act**：AI 系统分类、提供者/部署者角色、高风险系统控制、技术文档、日志和上市后监控。
- **GDPR**：合法性、目的限制、数据最小化、DPIA、数据主体权利，以及第 22 条对仅由自动化处理作出并产生法律或类似重大影响的决定的限制。
- **成员国劳动与反歧视法**：指标阈值、受保护群体及合法例外可能因司法辖区而不同。
- **组织内部治理**：采购审批、模型风险管理、供应商尽调、变更管理与事件响应。

重要设计约束：

1. “四分之五规则”或 disparate impact ratio 不是 EU AI Act 的统一合规阈值，只能作为可配置的风险信号，不能显示为自动法律判定。
2. 没有合法取得且质量足够的群体标签，就不能可靠计算群体公平性。平台不得通过姓名、照片或简历文本擅自推断真实候选人的种族、民族、性别或国籍。
3. 对特殊类别个人数据进行偏差检测必须经过适用性与必要性判断，并采取严格访问控制、假名化、复用限制和删除策略。系统需保留该必要性判断的证据。
4. SHAP 解释的是模型在给定数据上的行为，不等同于因果解释，也不证明模型公平或合法。

## 3. 产品目标与非目标

### 3.1 目标

- 在 30 分钟内完成一个招聘 AI 系统的首次登记和可审计性预检。
- 在数据可用时，自动完成群体公平性、代理变量、年龄偏差、反事实一致性、模型表现和漂移测试。
- 将每一条风险关联到证据、控制措施、责任人、截止日期和复测结果。
- 生成版本化的 Explainability Report、Model Card、Risk Assessment、Audit Log Export 和供应商尽调材料。
- 为上线、重大版本变更和周期性复审提供可配置的审批门禁。
- 让法务、DPO、HR、模型团队和内审在同一证据链上协作。

### 3.2 非目标

- 不对候选人自动录用、拒绝或排序。
- 不为企业颁发监管意义上的“EU AI Act 合规认证”。
- 不以单一公平性分数取代法务、伦理或业务判断。
- 不推断真实候选人的敏感属性。
- 不保证检测到所有形式的歧视；统计关联、因果歧视与法律歧视不是同一概念。
- MVP 不覆盖视频面试情绪识别；工作场所情绪识别本身可能属于被禁止实践，应在登记阶段直接触发红色提示。

## 4. 用户与核心任务

| 用户角色 | 核心任务 | 主要痛点 |
|---|---|---|
| AI/ML 工程师 | 上传测试材料、修复模型、比较版本 | 不知道哪些指标与证据足够，报告难复现 |
| HR/TA 负责人 | 管理招聘流程风险、决定是否上线 | 技术指标难理解，无法定位业务影响 |
| Responsible AI / Model Risk | 制定测试策略、设置门禁、批准例外 | 工具分散，缺少整改闭环和版本证据 |
| 法务 / DPO | 判断角色、适用义务、数据处理边界 | 算法报告与法律问题脱节 |
| 内审 / 外部审计方 | 独立复核证据与审批记录 | 无法证明当时测了哪个版本和哪些数据 |
| 供应商管理 / 采购 | 对第三方招聘 AI 做尽调 | 只有供应商声明，缺少可验证的黑盒测试 |

核心 Jobs-to-be-Done：

> 当我们采购、开发、更新或使用一个招聘 AI 时，我需要知道它适用哪些规则、当前有哪些可验证风险、哪些证据仍缺失、谁应整改，以及是否满足组织设定的上线门槛。

## 5. 产品原则

1. **Evidence over score**：先展示证据和不确定性，再给风险等级。
2. **Version everything**：模型、数据、配置、代码、报告、法规映射和审批均版本化。
3. **Human accountable**：所有例外、上线和风险接受必须由具名人员审批。
4. **Privacy by design**：敏感属性与候选业务数据分域、最小化、短留存。
5. **No hidden inference**：不从姓名、头像等推断敏感属性。
6. **Reproducible by default**：每次结果包含数据指纹、测试配置、库版本和随机种子。
7. **Jurisdiction-aware**：规则、群体、阈值和报告模板由国家/地区及组织政策决定。

## 6. 产品范围

### 6.1 MVP（P0）

- 多租户组织、项目与 RBAC。
- AI 系统登记、提供者/部署者角色问卷和高风险适用性预检。
- CSV/Parquet 数据与预测结果导入；字段映射、质量检查、数据指纹。
- 二分类/排序型招聘模型的群体公平性审计。
- 性别/年龄/国籍相关信号的代理风险检测与成对反事实测试。
- SHAP 全局解释；对兼容模型提供局部解释。
- 数据、表现和公平性漂移基线。
- 风险登记册、整改任务、复测、审批门禁。
- Model Card、Explainability Report、Risk Assessment 和审计包导出。
- 不可追加修改的应用审计事件与哈希链校验。
- 有来源引用的 LLM compliance assistant。

### 6.2 P1

- ATS/MLOps 连接器；S3/Azure Blob/GCS 导入。
- 黑盒在线推理 API 和客户自带容器的隔离测试。
- 回归、Learning-to-Rank、LLM 简历评分和 RAG 场景测试。
- DPIA/FRIA 辅助工作流、供应商证据门户。
- Webhook、Slack/Teams/Email 通知。
- SSO/SAML、SCIM、EU 数据驻留选项。

### 6.3 P2

- 上线流量持续监控、自动基线更新审批。
- 多司法辖区规则包。
- 第三方审计只读空间与电子签署。
- 证据 API 和 GRC 平台集成。
- 隐私增强统计、联邦评估和自托管执行节点。

## 7. 核心用户流程

### 7.1 首次审计

1. 创建 AI 系统，填写用途、候选群体、决策影响、使用地区、供应商和人类参与方式。
2. 平台输出角色与风险分类建议，标注依据、待法务确认项和禁止实践红旗。
3. 创建审计运行，选择模型版本、数据时间窗和司法辖区规则包。
4. 上传数据/预测结果或连接推理端点。
5. 完成字段映射、合法依据与敏感属性必要性确认。
6. 运行数据质量、公平性、代理变量、解释性、稳健性和漂移测试。
7. 平台生成 Findings；用户确认严重度、指定责任人和整改期限。
8. 上传修复版本并复测，对比风险是否改善及准确性是否被过度牺牲。
9. Responsible AI、HR、法务/DPO 按政策审批。
10. 冻结证据包并生成可验证导出。

### 7.2 持续监控

1. 定时或事件触发获取生产统计与决策样本。
2. 与已批准基线比较数据、表现、公平性和解释漂移。
3. 超过阈值时创建 Incident/Finding 并通知责任人。
4. 严重风险可将系统状态切换为 `Review required`，由外部部署系统决定是否暂停。
5. 完成调查、整改、复测和关闭；全过程写入审计日志。

## 8. 功能需求与验收标准

### FR-01 AI 系统登记与适用性判断

**需求**

- 记录 intended purpose、实际用途、用户、受影响人群、地域、决策类型、是否 profiling、是否仅自动决策、模型来源和生命周期状态。
- 区分 provider、deployer、importer、distributor 等角色；同一组织可在不同系统中承担不同角色。
- 识别就业高风险场景、潜在禁止实践、可能的 Article 6(3) 例外及其书面论证需求。
- 生成“适用性建议”，明确标记 `需法务确认`，不输出“已合规”。

**验收**

- 未完成 intended purpose、地域和决策影响时，不允许进入正式审计。
- 每个判断均显示规则版本、依据链接、回答人和时间。
- 规则包升级不会静默改写历史结论；必须创建新的 assessment version。

### FR-02 数据与模型接入

**需求**

- MVP 支持 CSV、Parquet 和 JSONL；必填字段至少包括匿名候选 ID、模型输出或决策、时间戳，可选真实结果与群体字段。
- 自动识别 schema，但必须由用户确认字段角色：feature、protected attribute、label、prediction、decision、metadata。
- 生成内容哈希、schema 版本、行数、缺失率、时间范围和来源证明。
- 支持直接上传模型输出，从而在无法访问第三方模型时完成黑盒结果审计。
- 模型文件只接受白名单格式；任何代码执行在无外网、限 CPU/内存/时间、只读文件系统的隔离环境中进行。

**验收**

- 原始候选标识不可作为报告中的明文维度。
- 不可信 pickle 被拒绝并给出安全替代方式。
- 数据集、模型和配置三者任一变化，都产生新的 audit run ID。

### FR-03 数据质量与代表性

**需求**

- 检测缺失、重复、异常值、标签泄漏、样本量、群体覆盖、时间覆盖和训练/测试重叠。
- 展示每个群体的样本量和置信区间；低样本量时抑制强结论。
- 记录数据来源、收集目的、许可范围、保留期限和代表性说明。
- 敏感属性进入逻辑隔离的 Audit Attribute Vault；默认不提供给被审模型。

**验收**

- 群体样本低于组织配置下限时，结果显示 `Insufficient evidence`，而不是 Pass。
- 未记录数据来源和处理目的时，报告标记 Evidence Gap。

### FR-04 公平性评估

**需求**

- 支持 selection rate、demographic parity difference/ratio、true/false positive rate、equal opportunity、equalized odds、precision、calibration 和 error rate。
- 支持性别、年龄段、国籍/公民身份等客户合法提供的维度，以及交叉群体分析。
- 支持业务阈值分析：不同候选评分阈值下，公平性与效用的变化。
- 使用 bootstrap 或适当统计方法给出置信区间；同时报告原始计数。
- 阈值由组织政策/司法辖区规则包配置，UI 不把单一比率表述为法律事实。

**验收**

- 每个指标显示定义、参考群体、比较群体、样本量、区间、阈值来源和计算版本。
- 有真实结果标签与无标签时使用不同测试集，并清楚提示可得结论的边界。
- 任何 `Pass` 都必须对应预先批准的测试策略；临时修改阈值会触发重新审批。

### FR-05 代理变量与年龄偏差检测

**需求**

- 通过关联/互信息、受保护属性可预测性、特征重要性、消融测试和语义风险词典识别潜在 proxy。
- 分析邮编、学校、语言、姓名相关字段、职业空窗期等高风险特征，但只将其标记为调查线索。
- 年龄分析同时支持连续年龄趋势、业务定义年龄段和阈值附近不连续性。
- 支持 matched-pair/counterfactual 测试：在资历一致时只改变一个受保护特征或可疑代理。

**验收**

- Proxy finding 必须展示“与受保护属性相关”及“影响模型输出”两类证据，缺一不可时降低置信度。
- 平台不得把姓名分类器的推断结果写回候选人档案。
- 用户必须能够查看和复现实验中的唯一变量变化。

### FR-06 Explainability

**需求**

- 对兼容模型输出全局 SHAP、群体分层特征贡献、特征依赖和关键错误案例。
- 局部解释默认只面向授权审计人员；候选人可见解释需使用独立模板和人工复核。
- 展示解释稳定性；对高度相关特征提示 attribution 可能被分摊。
- 生成自然语言摘要时，所有数字从结构化结果读取，不由 LLM 自行计算。

**验收**

- 解释报告包含模型/数据/配置版本、background dataset 和随机种子。
- 不支持的模型不能伪造 SHAP 结果，应降级为 permutation importance 或黑盒敏感性测试，并明确方法。

### FR-07 漂移与持续监控

**需求**

- 数据漂移：PSI、Jensen-Shannon、Wasserstein/K-S 等按数据类型选择。
- 表现漂移：accuracy、precision、recall、AUC 或排序指标。
- 公平性漂移：按群体追踪 selection/error/calibration 的变化。
- 解释漂移：关键特征排序和贡献分布变化。
- 阈值支持 warning/critical 两级，并允许季节性基线。

**验收**

- 监控结果必须区分“分布变化”和“有害性能下降”。
- 基线变更需要理由和审批，不能用新基线自动掩盖历史告警。

### FR-08 风险、控制与整改闭环

**需求**

- Finding 包含来源测试、证据、影响群体、严重度、置信度、建议控制、责任人和期限。
- 风险状态：`Open → Triaged → Mitigating → Ready for retest → Resolved / Accepted`。
- `Accepted` 必须填写残余风险、有效期和审批人，到期自动重开。
- 控制映射到适用法规条款和组织政策；一个控制可关联多个证据。

**验收**

- Critical finding 未解决或未获有效例外时，Release Gate 不能通过。
- 所有风险状态变化均进入审计日志。

### FR-09 报告与证据包

**需求**

- 输出：Executive Summary、Fairness Report、Explainability Report、Model Card、Risk Assessment、Audit Log、Evidence Gap List。
- 报告有 Draft/Approved/Superseded 状态、版本号、生成时间、批准人和内容哈希。
- 支持 PDF、JSON 和 CSV 导出；JSON 便于 GRC/MLOps 集成。
- 区分“系统卡/模型卡”：合规对象是完整 AI 系统及其使用情境，不只是模型。

**验收**

- 报告中的每个图表和结论可追溯到 audit run 和 metric result。
- 历史报告不可覆盖；修订产生新版本并保留差异。

### FR-10 审计日志

**需求**

- 记录登录、数据访问、配置变更、运行、结果审批、报告导出、风险接受、助手引用和管理员操作。
- 事件包含 actor、tenant、action、resource、timestamp、reason、前后值摘要和 correlation ID。
- 采用 append-only 存储与哈希链；企业版可导出到 WORM/SIEM。

**验收**

- 管理员也不能通过产品界面删除或修改事件。
- 校验工具能发现事件缺失或哈希链断裂。

### FR-11 LLM Compliance Assistant

**需求**

- 回答“为什么该风险被标记”“缺哪些证据”“某条款与本系统如何关联”“如何生成整改计划”等问题。
- 检索范围包括官方法规/指南、组织政策和当前项目证据；回答逐段引用来源并显示规则日期。
- 严格区分事实、系统推断与建议；无法支持的结论必须回答“不足以判断”。
- 助手只读审计结果；创建任务或修改风险需要用户明确确认并记录操作。
- 在聊天界面持续显示“AI 助手，不构成法律意见”。

**验收**

- 无来源的法律结论不得展示为确定性答案。
- 文档中存在提示注入文本时，不得改变系统权限或泄露其他租户数据。
- 每个回答保留所用文档版本、检索片段 ID 和模型版本。

## 9. 风险判定模型

平台不提供一个掩盖细节的“合规百分比”。首页采用三层状态：

- **Release status**：Approved / Review required / Blocked。
- **Risk distribution**：Critical / High / Medium / Low 的数量与趋势。
- **Evidence readiness**：Required / Present / Approved / Expired，按控制域展示覆盖率。

Finding 严重度由以下维度计算并允许人工调整：

`Severity = impact × exposure × likelihood × evidence confidence × control weakness`

人工调整必须填写理由；公平性指标越过内部阈值只会创建 Finding，不会直接宣称违法。

## 10. 信息架构

- **Portfolio**：组织内全部 AI 系统、风险与到期事项。
- **AI Systems**：系统登记、用途、角色、供应商、版本和适用性。
- **Audits**：数据、配置、运行、指标、解释和版本比较。
- **Findings & Controls**：风险登记、整改、复测、例外和审批。
- **Monitoring**：数据/性能/公平性/解释漂移与事件。
- **Evidence & Reports**：模型卡、系统卡、风险评估、日志和导出。
- **Assistant**：基于当前系统上下文的合规问答。
- **Admin**：规则包、阈值、RBAC、保留策略、连接器和密钥。

## 11. 关键数据模型

| 实体 | 关键字段 |
|---|---|
| Organization | id, region, policy_pack, retention_policy |
| AI_System | intended_purpose, owner, lifecycle_state, vendor, jurisdictions |
| Regulatory_Assessment | role, risk_class, applicable_rules, answers, reviewer, version |
| Model_Version | artifact_ref, hash, framework, schema, release_state |
| Dataset | source, fingerprint, schema, time_range, lawful_basis_ref, retention_until |
| Audit_Run | model_version, dataset_version, config_version, code_version, status |
| Metric_Result | metric, groups, value, interval, threshold, raw_counts, method |
| Finding | severity, confidence, affected_group, evidence_refs, owner, due_date, status |
| Control | framework_ref, implementation, test_procedure, owner, review_date |
| Approval | object_ref, decision, approver, role, reason, expires_at |
| Report | type, version, status, content_hash, artifact_ref |
| Audit_Event | actor, action, resource, timestamp, diff_digest, previous_hash, hash |
| Monitoring_Baseline | feature/metric, reference_window, threshold, approved_by |

所有租户业务表必须包含 `organization_id`，并在数据库层启用行级安全策略；候选原始 PII 与分析结果使用不同存储域和密钥。

## 12. 技术架构建议

### 12.1 组件

- **Web**：React/Next.js + TypeScript，负责工作台、报告和审计配置。
- **API**：FastAPI + Pydantic，OpenAPI-first。
- **数据库**：PostgreSQL，结构化业务数据、RLS、JSONB 规则快照。
- **对象存储**：S3 兼容 EU 区域存储，保存加密数据集、报告和证据。
- **任务系统**：Celery/Dramatiq + Redis 或托管队列，处理审计与报告任务。
- **分析运行器**：独立 Python workers；Fairlearn、SHAP、Evidently、scikit-learn、SciPy、Polars/Pandas。
- **隔离执行**：短生命周期容器/微虚拟机，无外网、最小权限、资源限额。
- **LLM 层**：规则与证据检索、结构化工具调用、引用校验、输出策略检查。
- **可观测性**：OpenTelemetry + 集中日志/指标/trace。

### 12.2 服务边界

1. Registry & Governance Service
2. Ingestion & Data Quality Service
3. Audit Orchestrator
4. Fairness/Explainability/Drift Workers
5. Findings & Approval Service
6. Evidence & Reporting Service
7. Compliance Knowledge/Assistant Service
8. Immutable Audit Event Service

MVP 可作为模块化单体部署，但分析 worker 与模型执行沙箱必须物理隔离，避免高计算任务和不可信代码影响主 API。

### 12.3 API 示例

- `POST /v1/ai-systems`
- `POST /v1/ai-systems/{id}/assessments`
- `POST /v1/datasets/initiate-upload`
- `POST /v1/audit-runs`
- `GET /v1/audit-runs/{id}/metrics`
- `POST /v1/findings/{id}/retests`
- `POST /v1/approvals`
- `POST /v1/reports`
- `GET /v1/audit-events/verify`
- `POST /v1/assistant/answers`

所有写操作要求 idempotency key；长任务返回 job ID；外部 API 使用短期签名 URL，不经 API 进程转发大文件。

## 13. 安全与隐私要求

- EU 区域数据驻留；传输与静态加密，企业客户支持客户管理密钥。
- SSO/MFA、最小权限 RBAC、敏感属性单独权限、季度访问复核。
- 上传文件恶意软件扫描、格式校验、大小限制和内容嗅探。
- 禁止主服务反序列化客户模型；沙箱无生产凭据、无外网、自动销毁。
- 数据默认短保留；客户可配置删除，备份同步过期；证据保留与原始 PII 保留分开。
- 生成报告前执行 k-anonymity/最小单元格抑制，避免小群体被重新识别。
- LLM 默认不接收原始简历；仅使用脱敏聚合结果。若使用外部模型供应商，必须明确数据处理与不训练承诺。
- 支持 DSAR、legal hold、删除证明、处理活动记录和子处理者清单。
- 建立安全事件响应、漏洞管理、依赖/SBOM、密钥轮换和渗透测试流程。

## 14. 非功能需求

| 类别 | MVP 目标 |
|---|---|
| 可用性 | 月度 99.5%，计划维护除外 |
| API 性能 | 非分析型 API P95 < 500ms |
| 审计性能 | 100 万行、50 特征的基础公平性审计 < 20 分钟 |
| 可复现性 | 相同输入和版本化配置的确定性指标完全一致 |
| 可扩展性 | 单租户任务限额与队列隔离，支持水平扩展 worker |
| 可访问性 | Web 核心流程达到 WCAG 2.2 AA |
| 国际化 | MVP 英文；架构支持多语言、时区与本地数字格式 |
| 恢复 | RPO ≤ 24h，RTO ≤ 8h；企业版后续提高 |
| 审计性 | 所有高权限与证据变更操作 100% 写入不可变日志 |

## 15. 关键页面

### 15.1 Portfolio 首页

- 顶部：Blocked / Review required / Approved 系统数。
- 中部：到期审批、Critical findings、证据缺口和漂移趋势。
- 底部：按用途、供应商、司法辖区和负责人筛选的系统列表。

### 15.2 Audit Workbench

- 左侧：审计步骤与完成状态。
- 主区：按群体展示原始计数、指标、置信区间、阈值和趋势。
- 右侧：方法说明、适用边界、关联条款和证据。
- 版本对比：准确性、公平性、风险和数据变化并列，不只显示“改善/恶化”。

### 15.3 Finding 详情

- 风险陈述、受影响对象、证据、严重度/置信度。
- 根因假设、控制建议、任务、讨论和复测历史。
- 风险接受与审批区；清楚显示有效期和残余风险。

## 16. 成功指标

### 北极星指标

**每月完成闭环的高风险 AI 控制数量**：有证据、有责任人、经审批并在有效期内的控制。

### 产品指标

- 首次系统登记完成时间中位数 < 30 分钟。
- 从数据就绪到首份审计报告时间中位数 < 60 分钟。
- Critical/High finding 在 SLA 内完成 triage 的比例 ≥ 90%。
- 报告结论可追溯到结构化证据的比例 = 100%。
- 已批准系统按期复审率 ≥ 95%。
- Assistant 带有效来源引用的回答比例 = 100%。

### 反指标

- 因缺少数据仍被显示为 Pass 的审计数量。
- 被用户误解为法律认证的报告比例。
- 被偷偷重设基线后消失的告警数量。
- 原始敏感数据进入 LLM 日志或分析报告的事件数量。

## 17. MVP 里程碑（14 周建议）

| 阶段 | 周期 | 交付 |
|---|---:|---|
| 0. 规则与设计 | 1–2 周 | 角色问卷、指标策略、数据契约、威胁模型、页面原型 |
| 1. 基础平台 | 3–5 周 | 租户/RBAC、系统登记、数据上传、任务框架、审计事件 |
| 2. 审计引擎 | 6–9 周 | 数据质量、公平性、proxy、反事实、SHAP、漂移基线 |
| 3. 治理闭环 | 10–11 周 | Findings、整改、复测、审批、Release Gate |
| 4. 证据与助手 | 12–13 周 | 报告、模型卡、证据包、带引用的只读助手 |
| 5. 验证 | 14 周 | 安全测试、基准数据集验证、可用性测试、试点上线 |

MVP 试点建议选择 2 类客户：一个自研招聘评分模型团队、一个采购第三方 ATS AI 的企业。前者验证白盒解释和修复闭环，后者验证黑盒输出审计和供应商证据流程。

## 18. 发布门槛

MVP 上线前必须满足：

- 使用至少 3 个已知偏差模式的合成/公开基准集验证指标方向和置信区间。
- 指标计算与 Fairlearn/独立脚本交叉验证。
- 任意历史 audit run 能在锁定依赖环境下复现。
- 租户隔离、越权访问、恶意文件、提示注入和模型沙箱完成安全测试。
- Critical finding、证据不足、规则过期三类场景无法被错误显示为 Approved。
- 法务审核所有对外产品措辞，移除“自动认证”“保证合规”等承诺。

## 19. 主要风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| 客户没有敏感属性数据 | 无法做可靠群体审计 | 支持证据缺口状态、成对测试、合法数据收集方案；不做隐式推断 |
| 统计指标被当作法律结论 | 错误决策与责任风险 | 指标/法律层分离、阈值来源、人工审批、免责声明 |
| 直接上传模型造成供应链风险 | RCE、数据泄漏 | 默认审计输出；格式白名单；隔离沙箱 |
| SHAP 被误解为因果解释 | 错误根因判断 | 方法边界提示、消融/反事实交叉验证 |
| LLM 幻觉法规或整改要求 | 合规误导 | 官方来源优先、引用强制、规则日期、只读默认、人工确认 |
| 法规/指南变化 | 旧判断失效 | 规则包版本化、变更通知、重新评估队列 |
| 公平优化损害模型效用或其他群体 | 风险转移 | 多指标版本对比、交叉群体测试、残余风险审批 |
| 小群体报表再识别 | 隐私泄漏 | 单元格抑制、最小样本、权限与导出策略 |

## 20. 待确认产品决策

1. 首批客户是自研模型团队，还是采购第三方招聘 AI 的大型雇主？这决定白盒/黑盒能力的优先级。
2. MVP 是否只支持二分类与阈值决策，还是必须支持候选人排序？建议先支持二分类，同时把排序数据模型设计好。
3. 是否提供 SaaS、单租户 EU 云和客户 VPC 三种部署？建议 MVP 为 EU SaaS，首个企业版增加客户 VPC 执行节点。
4. 首个规则包覆盖哪些国家？建议以 EU AI Act + GDPR 的共同层为主，选一个成员国做劳动法深度适配。
5. 报告面向内部治理、供应商尽调还是外部审计？建议 MVP 优先内部治理与外部审计证据导出，不面向候选人直接生成个体解释。

## 21. 官方依据与参考

- [European Commission：AI Act 风险分类、招聘高风险示例、主要义务与时间线](https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai)
- [EUR-Lex：Regulation (EU) 2024/1689 最新合并文本](https://eur-lex.europa.eu/eli/reg/2024/1689)
- [European Commission：2026 AI Omnibus 生效与更新后的时间线](https://digital-strategy.ec.europa.eu/en/news/ai-omnibus-enters-force)
- [EUR-Lex：GDPR Regulation (EU) 2016/679，第 22 条自动化决策](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:32016R0679)

> 注：法规适用性取决于系统用途、角色、司法辖区和事实情境。PRD 中的监管映射用于产品设计，不替代具备资质的法律意见。
