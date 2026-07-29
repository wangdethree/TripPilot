# TripPilot

TripPilot 是一个面向国内城市自由行场景的旅行规划 Agent。项目将按照接近企业实践的软件开发流程推进，重点覆盖需求分析、架构设计、工具调用、状态管理、Agent 评测、测试、部署与可观测性。

## 当前状态

- 阶段：Sprint 1（工程基础与领域建模）
- 需求状态：Requirements Baseline v1.0（Accepted）
- 架构状态：Architecture Baseline v1.0（Accepted）
- 第一版目标：为国内城市 1～3 日自由行生成可检查、可调整的个性化行程

## 第一版范围

- 接收城市、日期、人数、预算、兴趣偏好和旅行节奏
- 查询或读取景点、天气、路线和费用信息
- 生成多日旅行计划
- 检查预算、时间、距离和天气等约束
- 根据用户反馈局部调整行程

## 暂不包含

- 真实机票、酒店或门票交易
- 自动支付
- 无人工确认的高风险外部操作

## 文档

- [产品简介](docs/product-brief.md)
- [用户故事与优先级](docs/user-stories.md)
- [需求规格](docs/requirements.md)
- [业务用例](docs/use-cases.md)
- [业务规则](docs/business-rules.md)
- [数据字典](docs/data-dictionary.md)
- [非功能需求](docs/non-functional-requirements.md)
- [验收标准](docs/acceptance-criteria.md)
- [验收场景](docs/acceptance-scenarios.md)
- [Agent 评测需求](docs/evaluation-requirements.md)
- [需求追踪矩阵](docs/traceability.md)
- [需求评审清单](docs/requirements-review.md)
- [架构设计](docs/architecture/README.md)
- [架构决策记录](docs/decisions/README.md)
- [开发路线图与 Sprint 1](docs/development-plan.md)
- [贡献与提交规范](CONTRIBUTING.md)

## 本地开发

项目使用 Python 3.12 和 uv。首次安装 uv 后执行：

```bash
uv sync --locked
uv run pytest
```

完整本地质量检查：

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
uv build
```

依赖只能通过 `pyproject.toml` 和 `uv.lock` 管理，不维护独立的 `requirements.txt`。
