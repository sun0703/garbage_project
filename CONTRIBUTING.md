# 贡献指南 (Contributing Guide)

感谢你对 **垃圾识别项目 (Garbage Classification)** 的关注！我们非常欢迎各种形式的贡献，无论是代码、文档、Bug 修复还是新功能建议。

---

## 📋 目录

- [🤝 贡献方式](#-贡献方式)
- [🛠️ 开发环境搭建](#️-开发环境搭建)
- [📝 工作流程](#-工作流程)
- [💻 代码规范](#-代码规范)
- [🧪 测试要求](#-测试要求)
- [📖 提交规范](#-提交规范)
- [🔀 Pull Request 流程](#-pull-request-流程)
- [❌ 问题报告](#-问题报告)

---

## 🤝 贡献方式

### 你可以通过以下方式参与：

1. **🐛 报告 Bug** - 发现问题？请提 Issue
2. **💡 建议功能** - 有好想法？告诉我们
3. **✍️ 改进文档** - 文档不够清晰？帮忙完善
4. **💻 提交代码** - 修复 Bug 或开发新功能
5. **🔍 Code Review** - 帮助审查他人的 PR

### 贡献者行为准则

- ✅ 尊重他人，保持友善和专业
- ✅ 接受建设性批评
- ✅ 专注于对社区最有利的事情
- ✅ 对其他社区成员表示同理心

---

## 🛠️ 开发环境搭建

### 环境要求

- **Python**: >= 3.9
- **Git**: 最新版本
- **操作系统**: Windows / macOS / Linux

### 快速开始

```bash
# 1. Fork 并克隆仓库
git clone https://github.com/YOUR_USERNAME/garbage_project.git
cd garbage_project

# 2. 创建虚拟环境（强烈推荐）
python -m venv venv

# Windows 激活
venv\Scripts\activate

# macOS/Linux 激活
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 运行服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 5. 打开浏览器访问
# http://localhost:8000
```

### 项目结构说明

```
garbage_project/
├── main.py                 # FastAPI 主应用入口
├── index.html              # 前端界面
├── requirements.txt        # Python 依赖列表
├── data/
│   └── waste.json         # 垃圾分类数据配置
├── utils/
│   └── export_model.py    # 模型导出工具
├── .github/
│   ├── workflows/          # CI/CD 自动化流程
│   └── ISSUE_TEMPLATE/     # Issue 模板
├── 项目文档/               # 项目相关文档
└── scripts/                # 辅助脚本
```

---

## 📝 工作流程

### 标准贡献流程图

```
Fork  → Clone → Branch → Commit → Push → PR → Review → Merge
 ↓      ↓       ↓        ↓       ↓      ↓       ↓        ↓
你的仓库 本地  功能分支  代码提交  推送   发起PR  审查通过  合并到主分支
```

### 详细步骤

#### 1️⃣ Fork 仓库

点击 GitHub 页面右上角的 **Fork** 按钮，将仓库复制到你的账号下。

#### 2️⃣ 克隆到本地

```bash
git clone https://github.com/YOUR_USERNAME/garbage_project.git
cd garbage_project

# 添加上游仓库（方便后续同步）
git remote add upstream https://github.com/sun0703/garbage_project.git
```

#### 3️⃣ 创建功能分支

```bash
# 同步最新代码（重要！）
git fetch upstream
git checkout main
git merge upstream/main

# 创建分支（命名规范见下方）
git checkout -b feature/your-feature-name
# 或者修复 Bug
git checkout -b fix/bug-description
```

**分支命名规范**：

| 类型 | 前缀 | 示例 |
|------|------|------|
| 新功能 | `feature/` | `feature/add-recycle-detection` |
| Bug 修复 | `fix/` | `fix/image-upload-error` |
| 文档更新 | `docs/` | `docs/update-readme-install` |
| 重构 | `refactor/` | `refactor/optimize-model-loading` |
| 测试 | `test/` | `test/add-unit-tests-for-api` |
| 紧急修复 | `hotfix/` | `hotfix/critical-security-fix` |

#### 4️⃣ 编写代码并提交

```bash
# 查看修改的文件
git status

# 添加文件到暂存区
git add .

# 提交（遵循提交信息规范）
git commit -m "type(scope): description"
```

#### 5️⃣ 推送并创建 PR

```bash
# 推送到你的 Fork
git push origin feature/your-feature-name

# 创建 Pull Request（会打开浏览器）
gh pr create --base main --head feature/your-feature-name
```

---

## 💻 代码规范

### Python 代码风格

- 遵循 **PEP 8** 规范
- 使用 **类型注解**（Type Hints）
- 函数和类必须有 **docstring**
- 注释使用 **中文**（技术术语保留英文）

#### 示例代码

```python
from fastapi import FastAPI, UploadFile, File
from typing import Optional
import uvicorn

def classify_garbage(image_bytes: bytes) -> dict:
    """
    对上传的垃圾图片进行分类识别
    
    Args:
        image_bytes: 图片的二进制数据
        
    Returns:
        包含分类结果和置信度的字典
        
    Example:
        >>> result = classify_garbage(image_data)
        >>> print(result['category'])
        '可回收垃圾'
    """
    # TODO: 实现模型推理逻辑
    pass
```

### 注释规范

```python
# 单行注释：解释"为什么"，而不是"什么"
if user.is_admin:  # 管理员可以跳过审核流程
    approve_automatically()

# TODO: 待办事项（需要后续处理）
# FIXME: 已知问题（需要尽快修复）
# HACK: 临时方案（需要重构）
# NOTE: 重要提示
```

### 文件命名

- Python 文件：`snake_case.py` （如 `export_model.py`）
- HTML/CSS 文件：`kebab-case.html`
- 配置文件：全小写或 `UPPER_CASE`

---

## 🧪 测试要求

### 在提交前必须确保：

- [ ] 代码可以在本地正常运行
- [ ] 没有语法错误或导入错误
- [ ] 新功能有对应的单元测试（如有）
- [ ] 没有引入新的安全漏洞
- [ ] 敏感信息未硬编码在代码中

### 运行测试（如果有）

```bash
# 运行所有测试
pytest tests/

# 运行特定测试文件
pytest tests/test_api.py -v

# 生成覆盖率报告
pytest tests/ --cov=. --cov-report=html
```

---

## 📖 提交规范

我们使用 **Conventional Commits** 规范：

```
<type>(<scope>): <subject>

<body>

<footer>
```

### 类型 (Type)

| 类型 | 说明 |
|------|------|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `docs` | 文档变更 |
| `style` | 代码格式（不影响功能）|
| `refactor` | 重构（不是新功能也不是修复）|
| `perf` | 性能优化 |
| `test` | 添加或修改测试 |
| `chore` | 构建过程或辅助工具的变动 |

### 示例

```bash
# 好的提交信息
feat(api): add batch image upload endpoint
支持一次上传多张图片进行批量识别

- 添加 POST /api/batch-classify 接口
- 支持最多 10 张图片同时处理
- 返回 JSON 格式的批量结果

Closes #123

# 不好的提交信息
update code
fix bug
asdf
```

---

## 🔀 Pull Request 流程

### PR 标题格式

- **功能**: `feat: add new feature description`
- **修复**: `fix: resolve specific bug description`
- **文档**: `docs: update installation guide`

### PR 描述模板

创建 PR 时请填写以下信息（我们有预设模板）：

1. **变更描述** - 这个 PR 做了什么
2. **变更类型** - 选择合适的类型标签
3. **技术细节** - 实现思路和技术选型
4. **测试计划** - 如何验证这个 PR
5. **检查清单** - 提交前的确认项
6. **关联 Issue** - 解决了哪个 Issue

### PR 审查流程

1. **自动化检查** - CI 会自动运行测试和代码检查
2. **人工审查** - 至少需要 1 位维护者审查通过
3. **修改反馈** - 根据 review 意见修改代码
4. **合并** - 审查通过后由维护者合并

### 合并策略

本项目采用 **Squash Merge**（压缩合并）：
- 将多个 commit 压缩成一个
- 保持主分支历史整洁
- 自动生成清晰的合并提交信息

---

## ❌ 问题报告

### 报告 Bug 前

1. **搜索现有 Issue** - 避免重复报告
2. **确认版本信息** - 使用的是哪个版本
3. **复现步骤** - 清晰描述如何复现

### Issue 模板

使用我们的 [Bug Report Template](https://github.com/sun0703/garbage_project/issues/new?template=bug_report.md) 或 [Feature Request Template](https://github.com/sun0703/garbage_project/issues/new?template=feature_request.md)。

### 必须包含的信息

- **环境信息**：操作系统、Python 版本、浏览器版本
- **复现步骤**：详细到可以一步步重现
- **预期行为**：你期望的正确结果
- **实际行为**：实际发生了什么
- **截图/日志**：错误信息或截图

---

## 🎯 优先处理的问题

我们优先关注以下类型的贡献：

### 🔴 高优先级

- 🔒 安全漏洞修复
- 🐛 导致程序崩溃的 Bug
- ⚡ 性能严重下降的问题

### 🟡 中优先级

- ✨ 核心功能增强
- 🧪 测试覆盖率提升
- 📚 关键文档完善

### 🟢 低优先级

- 🎨 UI/UX 改进
- 📖 一般文档优化
- 🔧 代码重构

---

## 💡 贡献小贴士

### 对新手的建议

1. **从小的 Issue 开始** - 寻找标记为 `good first issue` 的问题
2. **先观察再动手** - 多看看已有的 PR 是怎么做的
3. **不怕问问题** - 如果不清楚，直接在 Issue 中提问
4. **接受反馈** - Code Review 是学习的好机会

### 提高接受率的技巧

- ✅ 先讨论再编码（避免做无用功）
- ✅ 保持 PR 小而聚焦（一个 PR 只做一件事）
- ✅ 编写清晰的描述和注释
- ✅ 及时响应审查意见
- ✅ 遵循现有的代码风格

---

## 🏆 贡献者认可

所有贡献者都会被添加到：
- **CONTRIBUTORS.md** - 贡献者列表
- **Release Notes** - 版本发布说明
- **GitHub Stats** - 项目统计页面

---

## 📞 需要帮助？

如果你有任何问题：

- 📧 **提 Issue** - [GitHub Issues](https://github.com/sun0703/garbage_project/issues)
- 💬 ** Discussions** - [GitHub Discussions](https://github.com/sun0703/garbage_project/discussions)（如果启用）
- 📖 **查看文档** - [项目文档目录](./项目文档/)
- 👥 **联系维护者** - 通过 Issue @ 相关人员

---

## 📄 许可证

通过向本项目贡献代码，你同意你的贡献将在与项目相同的许可证下发布。

---

**再次感谢你的贡献！让我们一起让垃圾分类变得更智能！♻️🤖**
