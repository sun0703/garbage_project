# 校园生活垃圾智能分类识别系统

## 项目简介

基于深度学习的校园垃圾分类 AI 助手，支持**拍照识别 + 语音/文字搜索 + 智能分类**。
系统采用 YOLOv8m 目标检测模型，结合多模态融合推理（YOLOv8 + SAHI 切片推理 + 双层级联分类），
覆盖中国标准的四大垃圾类别（厨余垃圾、可回收物、其他垃圾、有害垃圾），共 40 种常见校园垃圾物品。

## 技术栈

| 层级 | 技术选型 |
|------|----------|
| 后端框架 | FastAPI + Uvicorn |
| AI 推理 | Ultralytics YOLOv8（PyTorch 推理，可选 ONNX Runtime） |
| 图像处理 | Pillow + OpenCV + imagehash |
| 搜索引擎 | FuzzyWuzzy + pypinyin（首字母拼音搜索） |
| 数据库 | SQLite（WAL 模式，原生 sqlite3） |
| 配置管理 | pydantic-settings + python-dotenv |
| 前端 | 原生 JavaScript SPA（Hash 路由 + 发布订阅状态管理） |
| 数据格式 | JSON（词库/指南/步骤/易混淆对） |
| 测试 | pytest + httpx（API 集成测试）+ Playwright（可选 E2E） |
| 部署 | Docker + docker-compose |
| CI/CD | GitHub Actions（lint + 构建） |

## 系统架构

项目采用**三层分层架构**，代码按职责划分为独立的包：

```
┌─────────────────────────────────────────────────┐
│                 路由层 (routers/)                  │
│  预测 · 搜索 · 指南 · 历史 · 反馈 · 语音 · 调试    │
│   认证 · 地图 · 问答 · 活动                      │
├─────────────────────────────────────────────────┤
│                 服务层 (services/)                 │
│  视觉引擎 · 搜索引擎 · 缓存 · 限流 · 存储 · 语音   │
├─────────────────────────────────────────────────┤
│               数据访问层 (repositories/)            │
│  用户 · 会话 · 打卡 · 活动 · 问答 · 投放点         │
├─────────────────────────────────────────────────┤
│            核心层 (app/) + 工具层 (utils/)          │
│  配置 · 数据库 · 模型 · 多模态融合 · 后端状态管理    │
│  响应工厂 · JSON加载器 · 图像处理工具              │
└─────────────────────────────────────────────────┘
```

## 核心功能

### 图像识别
- 上传/拍照进行垃圾分类识别
- 多模态融合推理（YOLOv8 + SAHI 切片推理 + 双层级联分类）
- 基于 LRU + TTL 的推理结果缓存（感知哈希去重，默认 500 条/24 小时）
- 演示模式：无专用模型时基于图像特征（颜色/纹理/形状/金属光泽等 12 维特征）的启发式分类

### 智能搜索
- 中文关键词模糊匹配（FuzzyWuzzy + Levenshtein）
- 拼音首字母缩写搜索（如输入 `slp` 查找"塑料瓶"）
- 别名索引扩展搜索覆盖率
- 搜索联想下拉 + 搜索历史缓存
- 语音搜索入口

### 分类指南
- 四大垃圾类别标准说明卡片
- 常见物品示例 + 校园特有物品指南
- 易混淆物品对比（20+ 组常见错误）
- 物品详情页（处理步骤 + 投放提示）

### 校园地图
- 投放点分布地图展示
- 按区域/分类筛选过滤
- 用户定位 + 导航

### 环保社区
- 每日打卡积分系统
- 每日环保知识问答
- 环保活动管理与报名
- 打卡分享海报生成（Canvas API）

### 用户系统
- 注册/登录/注销（密码哈希存储）
- OAuth 第三方登录（微信 + GitHub）
- Session 管理（服务端存储）
- 签到记录与排行榜

### 系统能力
- IP 级滑动窗口限流（路径分级限流）
- CORS 跨域支持
- 用户反馈收集
- 健康检查接口
- 模型诊断工具集

## API 接口总览（共 43 个）

### 主页 & 健康检查

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 服务 SPA 首页 |
| GET | `/api/health` | 健康检查 |

### 图像识别

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/predict` | 单张图片垃圾分类识别 |
| POST | `/api/predict/multimodal` | 多模态融合推理 |
| POST | `/api/batch_predict` | 批量识别（最多 5 张） |

### 智能搜索

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search` | 模糊搜索（支持中文/拼音） |
| GET | `/api/search/enhanced` | 增强搜索（含联想推荐） |

### 分类指南

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/categories` | 获取分类列表 |
| GET | `/api/guide/standard` | 分类标准数据 |
| GET | `/api/guide/category/{category_id}` | 单类详细指南 |
| GET | `/api/guide/confusing` | 易混淆物品列表 |
| GET | `/api/guide/confusing/{pair_id}` | 单组对比详情 |
| GET | `/api/guide/item/{keyword}` | 物品详细指引 |

### 识别历史

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/history` | 识别历史列表（分页） |
| DELETE | `/api/history/{record_id}` | 删除单条记录 |
| DELETE | `/api/history` | 清空所有记录 |

### 用户反馈

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/feedback` | 提交识别反馈 |

### 语音纠偏

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/voice/correct` | 语音纠偏校正 |

### 模型调试

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/debug/analyze` | 图像特征分析 |

### 用户认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录 |
| POST | `/api/auth/logout` | 用户登出 |
| GET | `/api/auth/oauth/providers` | OAuth 提供商列表 |
| GET | `/api/auth/oauth/{provider}` | OAuth 授权跳转 |
| POST | `/api/auth/oauth/{provider}/callback` | OAuth 回调 |
| GET | `/api/auth/me` | 当前用户信息 |

### 校园地图

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/map/points` | 投放点列表 |
| GET | `/api/map/point/{point_id}` | 单一投放点详情 |

### 环保打卡

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/checkin` | 提交打卡 |
| GET | `/api/checkin/today` | 今日打卡状态 |
| GET | `/api/checkin/history` | 打卡历史 |
| GET | `/api/checkin/poster` | 打卡海报数据 |

### 知识问答

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/quiz/daily` | 每日问答题目 |
| POST | `/api/quiz/answer` | 提交答案 |

### 环保活动

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/activities` | 活动列表 |
| GET | `/api/activities/{activity_id}` | 活动详情 |
| POST | `/api/activities/signup` | 报名活动 |
| GET | `/api/activities/{activity_id}/signed` | 检查签到状态 |
| POST | `/api/activities/{activity_id}/checkin/{user_id}` | 活动签到 |
| POST | `/api/activities` | 创建活动 |
| PUT | `/api/activities/{activity_id}` | 更新活动 |
| DELETE | `/api/activities/{activity_id}` | 删除活动 |
| POST | `/api/activities/{activity_id}/cancel` | 取消报名 |

## 项目结构

```
垃圾识别/
├── app/                          # 核心应用层
│   ├── __init__.py               # app 包初始化
│   ├── main.py                   # FastAPI 应用入口（中间件/启动事件/路由注册）
│   ├── config.py                 # 应用配置管理（pydantic-settings）
│   ├── constants.py              # 全局常量定义（路径/配置项）
│   ├── backend_state.py          # 后端状态管理（全局单例注入）
│   ├── db.py                     # SQLite 数据库管理（连接/迁移/种子数据）
│   ├── models.py                 # 数据表模型定义
│   └── multimodal_fusion.py      # 多模态融合分类器（YOLOv8 + SAHI + 级联）
│
├── services/                     # 服务逻辑层
│   ├── __init__.py
│   ├── vision_engine.py          # 视觉引擎（YOLOv8 模型加载/推理/图像预处理）
│   ├── search_engine.py          # 搜索引擎（模糊匹配/拼音索引/别名扩展）
│   ├── inference_cache.py        # 推理缓存（LRU + TTL + 感知哈希去重）
│   ├── rate_limiter.py           # 滑动窗口限流器（IP 级/路径分级）
│   ├── history_store.py          # 识别历史记录存储
│   ├── feedback_store.py         # 用户反馈存储
│   ├── image_analyzer.py         # 图像特征分析（颜色/纹理/边缘/金属光泽）
│   ├── garbage_utils.py          # 垃圾分类数据工具函数
│   └── asr_correction.py         # 语音纠偏校正（ASR 结果修正）
│
├── repositories/                 # 数据访问层
│   ├── __init__.py
│   ├── user_repo.py              # 用户数据操作
│   ├── session_repo.py           # 会话管理
│   ├── checkin_repo.py           # 打卡数据操作
│   ├── activity_repo.py          # 活动数据操作
│   ├── quiz_repo.py              # 问答数据操作
│   └── disposal_point_repo.py    # 投放点数据操作
│
├── routers/                      # API 路由层
│   ├── __init__.py
│   ├── predict.py                # 图像识别路由（上传/批量/多模态）
│   ├── search.py                 # 搜索路由（模糊搜索/分类列表）
│   ├── guide.py                  # 分类指南路由（标准/类别/易混淆/物品详情）
│   ├── history.py                # 识别历史路由（列表/删除/清空）
│   ├── feedback.py               # 反馈路由
│   ├── voice.py                  # 语音纠偏路由
│   ├── debug.py                  # 模型调试路由
│   ├── auth.py                   # 用户认证路由（注册/登录/OAuth/信息）
│   ├── map.py                    # 地图路由（投放点/打卡）
│   ├── quiz.py                   # 知识问答路由
│   └── activities.py             # 活动管理路由（CRUD/报名/签到）
│
├── utils/                        # Python 工具模块
│   ├── __init__.py               # 工具包初始化
│   ├── response.py               # 统一 API 响应工厂（success/error 格式）
│   ├── json_loader.py            # JSON 文件缓存加载器
│   └── image.py                  # 图像处理（Base64 编解码/尺寸校验）
│
├── models/                       # 模型目录
│   └── garbage_yolov8m_best.pt   # 40 类垃圾分类 YOLOv8m 模型
│
├── data/                         # 数据目录
│   ├── waste.json                # 垃圾分类词库（40+ 物品/别名/拼音映射）
│   ├── guide_standard.json       # 四大类分类标准数据
│   ├── confusing_pairs.json      # 易混淆物品对比数据（20+ 组）
│   ├── disposal_steps.json       # 物品处理步骤（25 条）
│   ├── history.json              # 识别历史备份（运行时自动生成）
│   ├── feedback.json             # 用户反馈备份（运行时自动生成）
│   └── app.db                    # SQLite 业务数据库（首次启动自动创建）
│
├── static/                       # 前端静态资源
│   ├── index.html                # SPA 主页面
│   ├── css/
│   │   ├── main.css              # 主样式表（设计令牌/毛玻璃/响应式）
│   │   └── components.css        # 组件样式
│   ├── js/
│   │   ├── app.js                # 应用入口（SPA 引导 + 初始化）
│   │   ├── router.js             # Hash 路由器（hashchange + 正则匹配）
│   │   ├── store.js              # 发布订阅状态管理（细粒度 key 订阅）
│   │   ├── api.js                # API 客户端（Fetch 封装/超时/错误码映射）
│   │   ├── pages/                # 页面视图
│   │   │   ├── home.js           # 首页（上传 + 搜索）
│   │   │   ├── camera.js         # 预览确认页
│   │   │   ├── result.js         # 识别结果页
│   │   │   ├── search.js         # 搜索结果页
│   │   │   ├── guide.js          # 分类指南页
│   │   │   ├── history.js        # 历史记录页
│   │   │   ├── item-detail.js    # 物品详情页
│   │   │   ├── community.js      # 环保社区页
│   │   │   ├── map.js            # 投放点地图页
│   │   │   └── profile.js        # 个人中心页
│   │   ├── components/           # UI 组件
│   │   │   ├── nav-bar.js        # 顶部导航栏
│   │   │   ├── tab-bar.js        # 底部标签栏
│   │   │   ├── result-card.js    # 结果卡片
│   │   │   ├── category-tag.js   # 分类标签
│   │   │   ├── voice-btn.js      # 语音按钮
│   │   │   ├── search-suggest.js # 搜索联想下拉
│   │   │   └── confusing-pair-card.js # 易混淆对比卡片
│   │   └── utils/
│   │       ├── image.js          # 图像处理工具（压缩/旋转/预览）
│   │       ├── storage.js        # 本地存储工具（localStorage 封装）
│   │       ├── ui.js             # UI 工具函数（消息/加载/动画）
│   │       └── escape.js         # 转义工具（防 XSS）
│   ├── data/                     # （预留）前端数据目录
│   └── images/                   # （预留）前端图片资源
│
├── docker/                       # Docker 部署配置
│   ├── Dockerfile                # 多阶段构建镜像（Python 3.12+）
│   └── docker-compose.yml        # 容器编排（端口映射/卷挂载/环境变量）
│
├── tests/                        # 测试套件
│   ├── __init__.py
│   ├── conftest.py               # pytest 全局配置（Fixture/钩子）
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── client.py             # 测试客户端 Fixture（httpx.AsyncClient）
│   ├── test_api.py               # API 接口集成测试
│   └── e2e/
│       └── package.json          # Playwright E2E 测试依赖（可选）
│
├── 模型训练/                      # 模型训练资源
│   ├── diagnose_model.py         # 模型诊断工具
│   ├── deep_diagnose.py          # 深度模型诊断
│   └── datasets/rubbish/         # 训练数据集
│       ├── data.yaml             # 数据集配置文件
│       ├── images/               # 训练图片
│       ├── labels/               # YOLO 标注文件
│       └── README.md             # 数据集说明
│
├── 项目文档/                      # 项目文档
│   ├── 需求文档.md
│   ├── 设计架构文档.md
│   ├── MVP实现计划.md
│   ├── 阶段一任务清单.md
│   ├── 阶段一API接口契约.md
│   ├── 模型下载说明.md
│   └── CI-CD配置说明.md
│
├── .github/                      # GitHub 配置
│   ├── workflows/
│   │   └── ci.yml                # CI 工作流
│   └── linters/                  # Linter 配置
│       ├── .python-lint          # pylint 配置
│       └── .python-black         # black 配置
│
├── .env.example                  # 环境变量模板
├── .gitignore                    # Git 忽略规则
├── pyproject.toml                # Python 项目配置
├── requirements.txt              # Python 依赖
└── package.json                  # Node.js 依赖（可选，E2E 测试用）
```

## 快速开始

### 环境准备

```bash
# 1. 创建并激活虚拟环境（推荐）
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 2. 安装 Python 依赖
pip install -r requirements.txt
```

### 模型准备

将训练好的 YOLOv8 模型放入 `models/` 目录：

- `models/garbage_yolov8m_best.pt` — 40 类垃圾分类专用模型（必需）
- `models/yolov8n.pt` — YOLOv8n 预训练权重（自动降级备用，可选）

模型下载说明详见 [模型下载说明.md](file:///c:/000/code/垃圾识别/项目文档/模型下载说明.md)。

### 启动服务

```bash
python -m app.main
```

默认监听 `http://localhost:8001`，可通过环境变量 `PORT` 或修改 [app/config.py](file:///c:/000/code/垃圾识别/app/config.py) 自定义端口。

### 访问

浏览器打开 `http://localhost:8001` 即可使用 SPA 前端界面。

### Docker 部署

```bash
cd docker
docker-compose up --build
```

## AI 分类策略

系统按优先级依次尝试以下分类策略：

1. **YOLOv8 40 类模型** — 最高优先级，直接检测 40 种校园常见垃圾
2. **多模态融合** — YOLOv8 + SAHI 切片推理 + 双层级联，适用于小目标和复杂场景
3. **COCO 80 类映射** — 使用 COCO 预训练模型并映射到中国 4 类标准（备用）
4. **启发式分类（演示模式）** — 基于 12 维图像特征（颜色/纹理/边缘/金属光泽等）的加权投票系统

## 前端架构

SPA 单页应用，采用原生 JavaScript 模块化架构：

- **Hash 路由**：基于 `hashchange` 事件 + 正则匹配的路由分发
- **状态管理**：发布订阅模式（`Store`），细粒度按 key 订阅
- **API 客户端**：Fetch 封装（超时/错误码映射/降级处理）
- **UI 组件**：类模式（`new Component().render()`），独立生命周期
- **设计风格**：Soft UI Evolution（环保生态/毛玻璃效果/Mobile-First）

## 功能特性详情

### 识别流程状态机

```
上传 → 压缩 → 上传中 → 识别中 → 结果展示
  │                                  │
  └── 网络异常检测 → 自动降级重试 ────┘
```

### 限流策略

- 滑动窗口算法，IP 级限流
- 路径分级：预测接口 15 次/分钟，搜索 30 次/分钟，登录 10 次/分钟
- 白名单机制（开发环境 IP 自动跳过）
- 响应头携带完整限流状态（`X-RateLimit-*`）

### 缓存策略

- LRU 淘汰 + TTL 过期（默认 500 条/24 小时）
- 图像感知哈希（phash）去重
- 支持相同图片复用缓存结果

### 拼音搜索

- 纯字母输入自动触发拼音首字母搜索
- 内置手动拼音映射表（覆盖 150+ 垃圾分类高频汉字）
- pypinyin 库优先，自动降级

## 测试

```bash
# API 接口测试（pytest）
python -m pytest tests/ -v

# 运行指定测试文件
python -m pytest tests/test_api.py -v

# 模型诊断
python 模型训练/diagnose_model.py
python 模型训练/deep_diagnose.py

# Playwright E2E 测试（需要额外安装）
cd tests/e2e
npm install
npx playwright test
```

## 依赖清单

| 依赖 | 版本 | 用途 |
|------|------|------|
| fastapi | >=0.100.0 | Web 框架 |
| uvicorn | >=0.23.0 | ASGI 服务器 |
| pydantic-settings | >=2.0.0 | 配置管理 |
| python-dotenv | >=1.0.0 | .env 文件加载 |
| Pillow | >=10.0.0 | 图像处理 |
| python-multipart | >=0.0.6 | 文件上传 |
| fuzzywuzzy | >=0.18.0 | 模糊搜索 |
| python-Levenshtein | >=0.23.0 | Levenshtein 距离加速 |
| pypinyin | >=0.50.0 | 拼音转换 |
| numpy | >=1.24.0 | 数值计算 |
| ultralytics | >=8.0.0 | YOLOv8 推理 |
| opencv-python | (隐式依赖) | 图像特征分析 |
| httpx | (测试依赖) | API 测试客户端 |
| pytest | (测试依赖) | 测试框架 |
