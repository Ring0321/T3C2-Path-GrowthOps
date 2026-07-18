# Research claims, evidence and falsification boundaries

## 1. What this repository can establish

本仓库可验证：数据契约是否阻止已知错误；公式是否具有预期方向；在已知生成机制的合成样本中，估计器能否恢复真值并正确报告失败诊断；同一输入是否可复现；越权、过期、冲突和高风险请求是否被门控。

## 2. What this repository cannot establish

本仓库不能证明：真实学生愿意长期使用；动态画像提高就业结果；Safe-VOI 优于专业顾问；华图服务产生因果效果；算法在不同高校、群体和赛道间公平；任何 ROI 推演已经实现。上述结论需要伦理审查、真实样本、预注册、对照条件、纵向随访和外部验证。

## 3. Evidence ladder

| Level | Evidence | Allowed claim | Prohibited upgrade |
|---|---|---|---|
| L0 | specification and unit test | mechanism is defined and executable | effective for students |
| L1 | synthetic known-truth validation | recovers injected properties under generator assumptions | real-world accurate |
| L2 | usability and no-harm study | users can understand and operate prototype | improves growth |
| L3 | preregistered wait-list pilot | effect in the enrolled pilot under stated conditions | universal effect |
| L4 | multi-site longitudinal validation | transportability across tested sites and periods | effect outside tested scope |

## 4. Falsification rules

- 如果证据更新不能优于等权平均或造成情境信息丢失，A 模块降级为证据账本。
- 如果路径孪生不能正确响应截止期、硬门槛和转轨，B 模块不得使用“数字孪生”称谓。
- 如果 Safe-VOI 不优于“最低负担优先”基线，C 模块保留简单规则。
- 如果 VA 对参照群体或模型规格方向不稳定，停止个人 VA 输出。
- 如果 SE 缺少重叠、稳定策略或可比对照，只报告描述性关联。
- 如果选择性拒答不能降低错误风险，重做置信度与门控，而不是提高阈值掩盖问题。

## 5. Reporting language

允许：“在固定种子的合成真值样本中，该实现满足预注册性质。”

禁止：“实验已经证明平台能提高学生就业率/证明企业服务有效。”

