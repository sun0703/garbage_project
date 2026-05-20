# CI/CD 与自动化配置说明
# 本文件详细说明了项目中集成的 GitHub Actions 工作流

## 📋 工作流概览

本项目配置了 **3 个主要自动化工作流**，用于确保代码质量和团队协作效率：

```
┌─────────────────────────────────────────────────────────────┐
│                  GitHub Actions 自动化矩阵                    │
├─────────────────┬──────────────────┬────────────────────────┤
│   工作流名称     │    触发条件       │       主要功能          │
├─────────────────┼──────────────────┼────────────────────────┤
│ ci-cd.yml       │ Push / PR        │ 测试、构建、安全扫描     │
│ code-quality.yml │ PR 创建/更新      │ 代码质量、复杂度分析     │
│ automation.yml   │ Issue/PR 创建    │ 欢迎消息、自动标签      │
└─────────────────┴──────────────────┴────────────────────────┘
```

---

## 🚀 1. CI/CD Pipeline (ci-cd.yml)

### 触发时机
- ✅ 推送到 `main` 或 `develop` 分支
- ✅ 创建或更新 Pull Request
- ✅ 手动触发（`workflow_dispatch`）

### 包含的任务（Jobs）

#### 🔍 任务 1: Code Style Check (Lint)
- **Flake8**: Python 代码规范检查
- **Black**: 代码格式化检查
- **isort**: 导入排序检查
- **运行时间**: ~2 分钟

#### 🔎 任务 2: Type Checking (类型检查)
- **MyPy**: 静态类型检查
- **运行时间**: ~3 分钟

#### 🧪 任务 3: Unit Tests (单元测试)
- **多版本测试**: Python 3.9, 3.10, 3.11, 3.12
- **覆盖率报告**: 使用 pytest-cov
- **上传制品**: 保留 7 天的测试报告
- **运行时间**: ~5-10 分钟

#### 🔒 任务 4: Security Scan (安全扫描)
- **Safety**: 依赖漏洞检查
- **Bandit**: 安全问题扫描
- **运行时间**: ~2 分钟

#### 🏗️ 任务 5: Build Verification (构建验证)
- **应用启动测试**: 验证 FastAPI 应用可正常加载
- **API 基础访问测试**
- **运行时间**: ~1 分钟

### 状态徽章使用

在你的 README.md 中添加：

```markdown
![CI](https://github.com/sun0703/garbage_project/actions/workflows/ci-cd.yml/badge.svg)
```

---

## 📊 2. Code Quality (code-quality.yml)

### 触发时机
- PR 被创建、更新或重新打开时自动运行

### 主要功能

#### 🎯 Super-Lint
使用 [GitHub Super-Linter](https://github.com/github/super-linter) 进行全面检查：
- Python: Black, Flake8, isort, Pylint
- JSON, YAML, Markdown 格式验证
- Shell 脚本检查

#### 📊 Complexity Analysis (复杂度分析)
- **圈复杂度** (Cyclomatic Complexity): A(优秀) → D(需重构)
- **维护性指数** (Maintainability Index): 0-100 分
- 结果输出到 GitHub Step Summary

#### 📚 Documentation Check (文档检查)
- 统计函数/类的 docstring 覆盖率
- 低于 50% 会发出警告

#### 🔍 Change Impact Analysis (变更影响分析)
- 统计 PR 的变更文件数和代码行数
- 大型 PR (>10 文件或 >500 行) 会发出警告
- 列出所有变更的文件列表

---

## 🤖 3. Automation (automation.yml)

### 自动化功能

#### 👋 Welcome First-Time Contributors
- **触发**: 首次提交 PR 或 Issue 的贡献者
- **动作**: 
  - 发送欢迎消息
  - 添加 `good first contribution` 标签
  - 提供项目参与指南

#### 🏷️ Auto Labeling (自动标签)
根据 Issue 内容自动添加标签：
| 关键词 | 自动标签 |
|--------|----------|
| Bug, 错误, 崩溃 | `bug` |
| 新功能, 建议, 希望 | `enhancement` |
| 文档, 说明, 教程 | `documentation` |
| 如何, 怎么, 帮助 | `question` |

#### 📝 Issue Auto Response (Issue 自动回复)
- 发送确认收到消息
- 显示当前状态和处理流程
- 提供后续步骤指引

#### 📊 PR Status Update (PR 状态更新)
- 快速评估 PR 规模（小/中/大）
- 显示变更统计信息
- 提供预计审查时间

---

## ⚙️ 配置与自定义

### 修改 Python 版本

编辑 `.github/workflows/ci-cd.yml`：

```yaml
env:
  PYTHON_VERSION: "3.11"  # 修改为你需要的版本
```

或在 test job 中修改 matrix：

```yaml
strategy:
  matrix:
    python-version: ['3.9', '3.10', '3.11', '3.12']  # 添加或删除版本
```

### 添加环境变量

在仓库设置中：
1. Settings → Secrets and variables → Actions
2. 点击 "New repository secret"
3. 添加变量名和值

常用变量示例：
- `DATABASE_URL`: 数据库连接字符串
- `API_KEY`: 第三方 API 密钥
- `SLACK_WEBHOOK`: Slack 通知 Webhook

### 启用 Codecov（可选）

1. 注册 [Codecov](https://codecov.io) 账号
2. 授权 GitHub 仓库
3. 在 Actions 中会自动上传覆盖率报告

### 添加通知渠道

在 `ci-cd.yml` 的最后添加通知步骤：

```yaml
- name: 发送 Slack 通知
  if: always()
  uses: slackapi/slack-github-action@v1
  with:
    payload: |
      {
        "text": "CI/CD ${{ job.status }}: ${{ github.event.head_commit.message }}"
      }
  env:
    SLACK_WEBHOOK_URL: ${{ secrets.SLACK_WEBHOOK }}
```

---

## 🔧 本地调试工作流

### 使用 act 工具本地运行

```bash
# 安装 act (需要 Docker)
# macOS/Linux:
brew install act

# Windows (通过 scoop):
scoop install act

# 运行特定工作流
act -j lint          # 运行 lint 任务
act -j test          # 运行测试任务
act                  # 运行所有任务
```

### 手动触发工作流

```bash
# 通过 gh CLI
gh workflow run ci-cd.yml --ref main

# 或者访问 GitHub Actions 页面手动点击 Run workflow
```

---

## 📈 监控与优化

### 查看运行日志

1. 进入仓库的 Actions 页面
2. 点击具体的工作流运行
3. 查看每个任务的详细日志

### 优化建议

#### 加速 CI 运行
- ✅ 使用缓存（pip 缓存已启用）
- ✅ 并行执行独立任务
- ✅ 减少不必要的依赖安装
- ✅ 只在必要时运行完整测试

#### 降低失败率
- ✅ 确保 `requirements.txt` 完整且版本固定
- ✅ 添加容错处理 (`continue-on-error: true`)
- ✅ 设置合理的超时时间
- ✅ 定期更新 Actions 版本

---

## ❌ 常见问题排查

### 问题 1：CI 一直失败

**可能原因**：
- 依赖安装失败
- 代码不符合规范
- 测试用例有错误

**解决方案**：
1. 查看 Actions 日志中的错误信息
2. 本地复现并修复
3. 推送修复后的代码

### 问题 2：Super-Linter 报错过多

**解决方案**：
1. 先运行 Black 格式化代码：
   ```bash
   black .
   isort .
   ```
2. 提交后再触发 CI

### 问题 3：安全扫描误报

**解决方案**：
1. 在代码中添加注释忽略特定规则：
   ```python
   # nosec  # 忽略 bandit 检查
   ```
2. 或调整 Bandit 配置

---

## 🔄 更新工作流

当需要更新 Actions 版本时：

```bash
# 1. 查看可用更新
dependabot 会自动创建 PR 来更新 Actions 版本

# 2. 手动更新
# 将 v4 改为最新版本号
uses: actions/checkout@v4  # → uses: actions/checkout@v5

# 3. 测试更新后是否正常工作
gh workflow run ci-cd.yml
```

---

## 📚 相关资源

- [GitHub Actions 文档](https://docs.github.com/en/actions)
- [Super-Linter 配置](https://github.com/github/super-linter)
- [pytest 最佳实践](https://docs.pytest.org/)
- [Bandit 安全规则](https://bandit.readthedocs.io/)

---

**最后更新**: 2026-05-20  
**维护者**: @sun0703
