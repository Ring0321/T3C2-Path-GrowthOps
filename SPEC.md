# Specification: T³-C² Path GrowthOps v0.2.0

## 1. Objective

构建一个可运行、可测试、可审计的教育成长规划研发基线，把已有《T3-C2算法研究设计》和《数据与算法验证样本包》中的计算主张转化为稳定代码契约。系统面向学生、顾问、研究人员和运营管理者，输出“带证据和边界的下一步行动”，而不是录取概率、命运标签或自动高利害决策。

## 2. Assumptions

1. v0.2.0 只处理合成或去标识化研究数据，不接入真实个人信息、华图内部系统或飞书生产租户。
2. Python 3.11+ 是算法与服务端基线；Pydantic 用于边界验证，FastAPI 作为可选 REST 适配层。
3. 透明、确定性算法优先；大模型只允许在受控结构化结果之上生成解释草稿，不得修改数值、规则或因果等级。
4. MVP 的 VA 是形成性估计；SE 只在群体级、识别条件满足时允许因果措辞。
5. 所有路径规则均需显式 `valid_from`、`valid_to` 与来源版本；仓库不内置当前招录事实。
6. 用户已经批准此前开题报告、算法研究设计和验证样本包作为本规格的上游研究依据。

## 3. Functional Requirements

### 3.1 Data contracts

实现不可变、可版本化的 `ConsentRecord`、`EvidenceRecord`、`ProfileSnapshot`、`KnowledgeRule`、`PathPlan`、`TaskCard`、`ServiceExposure`、`ValueAddedReport`、`AgentDecisionLog` 和 `ReviewTicket`。未知值必须使用 `None` 或明确状态，不得填零；所有推断必须回指证据 ID。

### 3.2 Algorithm A: evidence state

- 以可靠性、年龄半衰期和重复来源惩罚构造有效观测方差。
- 输出后验均值、标准差、区间、证据贡献、情境冲突与复测提示。
- 无有效授权、量规不可比或严重冲突时不得强行聚合。

### 3.3 Algorithm B: path digital twin

- 路径由时间节点、硬约束、资源负担、可迁移资产和转轨成本构成。
- 蒙特卡洛输出准备度分布和可行概率，不伪装成录取概率。
- 过期硬规则使路径进入 `NEEDS_VERIFICATION`，不能被软分覆盖。
- 输出 Pareto 非支配集合和条件性解释，不强制单一排序。

### 3.4 Algorithm C: Safe-VOI

- 候选任务先经过授权、可退出、规则有效和高利害四项安全门。
- 通过后再按预期成长、信息增益、迁移性、时间价值、负担和风险计算价值。
- 有更低成本且信息增益不低的替代任务时，阻断高成本商业行动。

### 3.5 Algorithm D: student value-added

- `VA = observed_readiness - expected_readiness_given_baseline_and_context`。
- 输出区间、参照条件、模型版本与不确定结论；禁止个人排名或惩罚。
- 测量不等值、样本不足或区间过宽时降级到分维度变化。

### 3.6 Algorithm E: service effect

- 将目标试验资格、分配、时间零点、策略版本、结局和缺失规则结构化。
- 优先返回随机等待组 ITT；观察性数据仅在重叠、稳定版本和协变量条件满足时运行 AIPW。
- 返回影响函数区间、重叠诊断和声明等级；不满足时只能描述关联或拒绝估计。

### 3.7 Algorithm F: publication gate

- 检查授权、证据覆盖、规则有效期、校准、公平、风险、工作负担与用途。
- 返回 `PUBLISH`、`QUALIFIED`、`DEFER`、`HUMAN_REVIEW` 或 `BLOCK`，并提供原因码和补证动作。
- 高利害用途不能自动发布。

### 3.8 Agent orchestration and interfaces

- 证据、路径、任务、评价、治理智能体各自具有输入/输出契约和最小权限。
- 编排器以事务方式冻结输入版本，输出决策包并追加不可变审计日志。
- 提供 CLI 演示与 `/v1/decisions/evaluate` REST 接口；所有错误使用统一结构。

## 4. Commands

```bash
python -m pip install -e ".[dev,api,research]"
pytest -q
pytest --cov=t3c2_path --cov-report=term-missing
ruff check .
mypy src
python -m t3c2_path demo
uvicorn t3c2_path.api:app --reload
```

## 5. Project Structure

```text
src/t3c2_path/        domain, algorithms, agents, audit, API and CLI
tests/                unit, integration, contract and red-team tests
examples/             synthetic requests and deterministic outputs
research/             synthetic generators, estimators and reports
docs/                 architecture, protocols, data/model cards and ADRs
.github/workflows/    reproducible quality gates
```

## 6. Code Style

```python
def evaluate(candidate: CandidateDecision, policy: GatePolicy) -> GateResult:
    """Return a typed gate decision; never mutate the candidate."""
    if candidate.is_high_stakes:
        return GateResult.human_review("HIGH_STAKES_REQUIRES_HUMAN")
    return GateResult.publish()
```

- 类型优先、不可变模型、纯函数算法；I/O 与计算分离。
- 公共名称和协议字段使用英文，文档、解释和原因信息可中英双语。
- 所有随机过程必须接收显式种子；所有输出携带算法、知识与数据版本。

## 7. Testing Strategy

- 单元测试：公式方向性、边界、缺失、时效、硬约束与拒答。
- 性质测试：更可靠证据不得获得更低权重；过期规则不得发布；低成本支配任务应阻断高成本任务。
- 合成真值：VA/SE 估计器在已知生成机制下验证偏差、覆盖与失效诊断。
- 合约测试：Pydantic 模型、API 错误形状、枚举和版本不可变。
- 红队测试：越权、提示注入、重复证据、规则过期、版本混合、因果措辞升级。
- 每个生产行为遵循测试先行；main 只接受全绿增量。

## 8. Boundaries

### Always

- 验证所有外部输入；显式处理缺失、冲突、时效和用途授权。
- 报告区间、诊断、失败条件和声明等级。
- 每个可验证增量在本地通过测试后独立提交并推送。

### Ask before production integration

- 接入真实学生 PII、生产飞书、高校系统、华图 CRM 或外部大模型。
- 更改身份认证、CORS、数据保留期或高利害用途。
- 把研究阈值替换为生产阈值。

### Never

- 将未知填零、将大模型自报置信度当统计置信度、将 VA 当 SE。
- 自动决定录取、淘汰、收费资格、就业机会或学生排名。
- 提交密钥、真实个人数据、未授权材料或伪造实验结果。

## 9. Success Criteria

1. 六个算法模块均有公开契约、可执行实现和失败测试。
2. 端到端决策在同一输入与种子下可复现，审计记录可回指所有版本和证据。
3. 过期规则、高利害用途、撤回授权、低覆盖、无因果重叠等红队输入必定降级或阻断。
4. 合成实验输出同时包含观测值、预期性质和声明边界。
5. CI 在 Python 3.11—3.13 上运行 lint、type check、tests、coverage、build 和 security audit。
6. 公开仓库包含许可证、贡献指南、行为准则、安全策略、模型卡、数据卡、变更日志和引用信息。

## 10. Non-goals for v0.2.0

- 不训练端到端强化学习策略，不实现真实推荐商业转化，不提供录取概率。
- 不声称算法优于顾问、通用大模型或竞品，除非真实预注册研究支持。
- 不实现生产认证、数据库、多租户、消息队列或飞书凭证集成。
