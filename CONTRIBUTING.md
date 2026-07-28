# 贡献指南

TripPilot 使用短期功能分支、代码审查和 Conventional Commits 风格的提交信息。

## 开发流程

1. 从最新的 `main` 创建短期分支。
2. 每次提交只包含一个清晰、可说明的改动。
3. 提交前运行当前阶段要求的格式检查和测试。
4. 推送分支并通过 Pull Request 合并到 `main`。
5. 不提交密钥、真实用户数据或与当前任务无关的文件。

## 分支命名

使用小写英文和连字符：

```text
feature/travel-request-model
fix/budget-validation
docs/product-requirements
refactor/tool-registry
```

## 提交信息

基本格式：

```text
<type>(<scope>): <description>
```

`scope` 可选，冒号后保留一个空格。标题应简洁说明本次提交完成了什么。

常用类型：

| 类型 | 用途 |
| --- | --- |
| `feat` | 新增用户可感知的功能 |
| `fix` | 修复缺陷 |
| `docs` | 只修改文档 |
| `refactor` | 不改变外部行为的代码重构 |
| `test` | 新增或调整测试 |
| `perf` | 性能优化 |
| `build` | 构建系统或依赖变更 |
| `ci` | 持续集成配置变更 |
| `chore` | 其他维护性工作 |
| `revert` | 撤销已有提交 |

推荐示例：

```text
feat(planner): 支持按旅行偏好筛选景点
fix(budget): 修复零预算未被拒绝的问题
docs: 补充产品范围和非目标
test(tools): 增加天气工具超时测试
chore: 初始化项目仓库
```

不推荐示例：

```text
修改代码
fix bug
update
```

存在不兼容变更时，在类型后添加 `!`，并在正文中说明影响：

```text
feat(api)!: 调整旅行需求接口字段
```

## 提交前检查

至少确认：

- `git status` 中只有本次任务相关文件。
- 没有 `.env`、API Key、Token 或真实隐私数据。
- 新增行为具有对应测试或明确的验收方式。
- 文档与实际行为保持一致。

随着项目进入编码阶段，以上规则会加入本地检查和 CI 自动验证。
