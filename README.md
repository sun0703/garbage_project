# 校园生活垃圾智能分类识别系统

## 项目简介

基于深度学习的校园垃圾分类 AI 助手,支持**拍照识别 + 语音/文字搜索 + 智能分类**。系统采用 YOLOv8m 目标检测模型,结合多模态融合推理(YOLOv8 + SAHI 切片推理 + 双层级联分类),覆盖中国标准的四大垃圾类别(厨余垃圾、可回收物、其他垃圾、有害垃圾),共 40 种常见校园垃圾物品。

### 核心特性

- **多模态融合推理**: YOLOv8 + SAHI 切片推理 + 双层级联分类器,提升小目标检测和复杂场景识别准确率
- **智能搜索**: 支持中文模糊匹配、拼音首字母缩写搜索(如输入 `slp` 查找"塑料瓶")、别名扩展
- **图像缓存**: 基于 LRU + TTL 的推理结果缓存,感知哈希去重,避免重复推理
- **降级处理**: 当模型不可用时,自动降级到基于 12 维图像特征(颜色/纹理/形状/金属光泽)的启发式分类
- **前端 SPA**: 原生 JavaScript 模块化架构,Hash 路由 + 发布订阅状态管理
- **限流保护**: IP 级滑动窗口限流,路径分级限流(预测接口 15 次/分钟,搜索 30 次/分钟)
- **用户系统**: 注册/登录/注销、OAuth 第三方登录(微信 + GitHub)、Session 管理

---

## 技术栈

| 层级 | 技术选型 | 说明 |
|------|----------|------|
| **后端框架** | FastAPI + Uvicorn | 高性能异步 Web 框架 |
| **AI 推理** | Ultralytics YOLOv8 | 目标检测 + 分类 |
| **图像处理** | Pillow + OpenCV + imagehash | 图像预处理、特征提取 |
| **搜索引擎** | FuzzyWuzzy + pypinyin | 模糊匹配、拼音首字母索引 |
| **数据库** | SQLite (WAL 模式) | 本地文件数据库,支持事务和索引 |
| **配置管理** | pydantic-settings + python-dotenv | 环境变量 + .env 文件加载 |
| **前端** | 原生 JavaScript SPA | Hash 路由 + 发布订阅状态管理 |
| **数据格式** | JSON | 词库/指南/步骤/易混淆对 |
| **测试** | pytest + httpx | API 集成测试 |
| **部署** | Docker + docker-compose | 容器化部署 |
| **CI/CD** | GitHub Actions | Lint + 构建 |

---

## 系统架构

项目采用**三层分层架构**,代码按职责划分为独立的包:

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

### 核心模块说明

#### 1. 路由层 (routers/)

| 文件 | 功能 | API 端点 |
|------|------|----------|
| `predict.py` | 图像识别、批量识别、多模态融合 | `/api/predict`, `/api/batch_predict`, `/api/predict/multimodal` |
| `search.py` | 搜索、分类列表、增强搜索 | `/api/search`, `/api/search/enhanced` |
| `guide.py` | 分类指南、物品详情、易混淆对比 | `/api/categories`, `/api/guide/*` |
| `history.py` | 识别历史记录管理 | `/api/history` |
| `feedback.py` | 用户反馈收集 | `/api/feedback` |
| `voice.py` | 语音纠偏校正 | `/api/voice/correct` |
| `debug.py` | 图像特征分析 | `/api/debug/analyze` |
| `auth.py` | 用户认证(OAuth) | `/api/auth/*` |
| `map.py` | 校园地图、投放点 | `/api/map/*` |
| `quiz.py` | 知识问答 | `/api/quiz/*` |
| `activities.py` | 环保活动管理 | `/api/activities/*` |

#### 2. 服务层 (services/)

| 文件 | 功能 | 核心实现 |
|------|------|----------|
| `vision_engine.py` | 视觉推理引擎 | PyTorch/ONNX 双引擎、置信度校准 |
| `search_engine.py` | 模糊搜索引擎 | FuzzyWuzzy + 拼音首字母索引 + 别名映射 |
| `inference_cache.py` | 推理缓存 | LRU + TTL + 感知哈希去重 |
| `rate_limiter.py` | 限流器 | 滑动窗口算法 + 路径分级限流 |
| `history_store.py` | 历史记录存储 | SQLite + 备份机制 |
| `feedback_store.py` | 反馈存储 | SQLite + 按类别统计 |
| `image_analyzer.py` | 图像特征分析 | 12 维特征(颜色/纹理/边缘/金属光泽) |
| `garbage_utils.py` | 垃圾分类工具 | 类别映射、置信度校准、投放指引 |
| `asr_correction.py` | 语音纠偏 | ASR 结果修正 + 上下文联想 |

#### 3. 核心层 (app/)

| 文件 | 功能 | 说明 |
|------|------|------|
| `main.py` | FastAPI 应用入口 | 中间件注册、路由注册、启动事件 |
| `config.py` | 配置管理 | pydantic-settings、环境变量加载 |
| `constants.py` | 全局常量 | 路径、配置项、类别映射 |
| `backend_state.py` | 后端状态管理 | 全局单例注入、依赖注入 |
| `models.py` | Pydantic 模型定义 | 请求/响应数据结构 |
| `db.py` | SQLite 数据库管理 | 连接、迁移、索引、种子数据 |
| `multimodal_fusion.py` | 多模态融合分类器 | YOLO + SAHI + 双层级联 |

#### 4. 多模态融合架构

```
Layer 1: YOLOv8 (目标检测) → 粗定位 + 大类分类
Layer 2: SAHI (切片推理) → 小目标增强检测
Layer 3: 双层级联 (粗分类→路由→专用子模型) → 精细识别
Fusion: 加权投票 + 置信度校准 → 最终决策
```

**核心优势**:
- **YOLO**: 快速目标检测,适合大中型物体
- **SAHI**: 切片推理解决小目标漏检问题(垃圾通常较小)
- **双层级联**: 先分 4 大类再精细化,类别越少准确率越高
- **融合决策**: 多视角交叉验证,大幅提升准确率

---

## 核心功能

### 图像识别

- **单张图片识别**: 上传/拍照进行垃圾分类识别
- **批量识别**: 最多 5 张图片并行推理
- **多模态融合推理**: YOLO + SAHI + 双层级联,提升准确率
- **智能缓存**: 基于 LRU + TTL 的推理结果缓存(默认 500 条/24 小时)
- **演示模式**: 无专用模型时基于图像特征(颜色/纹理/形状/金属光泽等 12 维特征)的启发式分类

### 智能搜索

- **中文模糊匹配**: FuzzyWuzzy + Levenshtein 距离
- **拼音首字母缩写搜索**: 输入 `slp` 查找"塑料瓶"
- **别名索引扩展**: 覆盖 150+ 垃圾分类高频汉字
- **搜索联想下拉**: 实时推荐
- **语音搜索入口**: Web Speech API + ASR 纠错

### 分类指南

- **四大类标准说明**: 厨余垃圾/可回收物/其他垃圾/有害垃圾
- **常见物品示例**: 覆盖 40+ 物品
- **校园特有物品**: 食堂剩饭、外卖餐盒等
- **易混淆物品对比**: 20+ 组常见错误
- **物品详情页**: 处理步骤 + 投放提示

### 校园地图

- **投放点分布地图**: 展示校园内所有投放点
- **按区域/分类筛选**: 支持按区域(东区/西区/中心区)和分类筛选
- **用户定位**: 调用浏览器定位 API
- **导航功能**: 跳转外部地图应用

### 环保社区

- **每日打卡积分系统**: 每次识别/打卡获得积分
- **每日环保知识问答**: 15+ 道题目
- **环保活动管理**: 活动发布、报名、签到
- **打卡分享海报**: Canvas API 生成海报

### 用户系统

- **注册/登录/注销**: 密码哈希存储(SHA-256)
- **OAuth 第三方登录**: 微信 + GitHub
- **Session 管理**: 服务端存储,有效期 7 天
- **签到记录与排行榜**: 每日签到 + 积分排行

### 系统能力

- **IP 级滑动窗口限流**: 按路径分级限流
- **CORS 跨域支持**: 允许跨域请求
- **用户反馈收集**: 支持按类别统计
- **健康检查接口**: `/api/health` 检查模型和服务状态
- **模型诊断工具集**: 图像特征分析、置信度校准

---

## API 接口总览(共 43 个)

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
| POST | `/api/batch_predict` | 批量识别(最多 5 张) |

### 智能搜索

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search` | 模糊搜索(支持中文/拼音) |
| GET | `/api/search/enhanced` | 增强搜索(含联想推荐) |

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
| GET | `/api/history` | 识别历史列表(分页) |
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

---

## 项目结构

```
垃圾识别/
├── app/                          # 核心应用层
│   ├── __init__.py               # app 包初始化
│   ├── main.py                   # FastAPI 应用入口(中间件/启动事件/路由注册)
│   ├── config.py                 # 应用配置管理(pydantic-settings)
│   ├── constants.py              # 全局常量定义(路径/配置项)
│   ├── backend_state.py          # 后端状态管理(全局单例注入)
│   ├── db.py                     # SQLite 数据库管理(连接/迁移/种子数据)
│   ├── models.py                 # 数据表模型定义
│   └── multimodal_fusion.py      # 多模态融合分类器(YOLO + SAHI + 级联)
│
├── services/                     # 服务逻辑层
│   ├── __init__.py
│   ├── vision_engine.py          # 视觉引擎(YOLOv8 模型加载/推理/图像预处理)
│   ├── search_engine.py          # 搜索引擎(模糊匹配/拼音索引/别名扩展)
│   ├── inference_cache.py        # 推理缓存(LRU + TTL + 感知哈希去重)
│   ├── rate_limiter.py           # 滑动窗口限流器(IP 级/路径分级)
│   ├── history_store.py          # 识别历史记录存储
│   ├── feedback_store.py         # 用户反馈存储
│   ├── image_analyzer.py         # 图像特征分析(颜色/纹理/边缘/金属光泽)
│   ├── garbage_utils.py          # 垃圾分类数据工具函数
│   └── asr_correction.py         # 语音纠偏校正(ASR 结果修正)
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
│   ├── predict.py                # 图像识别路由(上传/批量/多模态)
│   ├── search.py                 # 搜索路由(模糊搜索/分类列表)
│   ├── guide.py                  # 分类指南路由(标准/类别/易混淆/物品详情)
│   ├── history.py                # 识别历史路由(列表/删除/清空)
│   ├── feedback.py               # 反馈路由
│   ├── voice.py                  # 语音纠偏路由
│   ├── debug.py                  # 模型调试路由
│   ├── auth.py                   # 用户认证路由(注册/登录/OAuth/信息)
│   ├── map.py                    # 地图路由(投放点/打卡)
│   ├── quiz.py                   # 知识问答路由
│   └── activities.py             # 活动管理路由(CRUD/报名/签到)
│
├── utils/                        # Python 工具模块
│   ├── __init__.py               # 工具包初始化
│   ├── response.py               # 统一 API 响应工厂(success/error 格式)
│   ├── json_loader.py            # JSON 文件缓存加载器
│   └── image.py                  # 图像处理(Base64 编解码/尺寸校验)
│
├── models/                       # 模型目录
│   └── garbage_yolov8m_best.pt   # 40 类垃圾分类 YOLOv8m 模型
│
├── data/                         # 数据目录
│   ├── waste.json                # 垃圾分类词库(40+ 物品/别名/拼音映射)
│   ├── guide_standard.json       # 四大类分类标准数据
│   ├── confusing_pairs.json      # 易混淆物品对比数据(20+ 组)
│   ├── disposal_steps.json       # 物品处理步骤(25 条)
│   ├── history.json              # 识别历史备份(运行时自动生成)
│   ├── feedback.json             # 用户反馈备份(运行时自动生成)
│   └── app.db                    # SQLite 业务数据库(首次启动自动创建)
│
├── static/                       # 前端静态资源
│   ├── index.html                # SPA 主页面
│   ├── css/
│   │   ├── main.css              # 主样式表(设计令牌/毛玻璃/响应式)
│   │   └── components.css        # 组件样式
│   ├── js/
│   │   ├── app.js                # 应用入口(SPA 引导 + 初始化)
│   │   ├── router.js             # Hash 路由器(hashchange + 正则匹配)
│   │   ├── store.js              # 发布订阅状态管理(细粒度 key 订阅)
│   │   ├── api.js                # API 客户端(Fetch 封装/超时/错误码映射)
│   │   ├── pages/                # 页面视图
│   │   │   ├── home.js           # 首页(上传 + 搜索)
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
│   │       ├── image.js          # 图像处理工具(压缩/旋转/预览)
│   │       ├── storage.js        # 本地存储工具(localStorage 封装)
│   │       ├── ui.js             # UI 工具函数(消息/加载/动画)
│   │       └── escape.js         # 转义工具(防 XSS)
│   ├── data/                     # (预留)前端数据目录
│   └── images/                   # (预留)前端图片资源
│
├── docker/                       # Docker 部署配置
│   ├── Dockerfile                # 多阶段构建镜像(Python 3.12+)
│   └── docker-compose.yml        # 容器编排(端口映射/卷挂载/环境变量)
│
├── tests/                        # 测试套件
│   ├── __init__.py
│   ├── conftest.py               # pytest 全局配置(Fixture/钩子)
│   ├── fixtures/
│   │   ├── __init__.py
│   │   └── client.py             # 测试客户端 Fixture(httpx.AsyncClient)
│   ├── test_api.py               # API 接口集成测试
│   └── e2e/
│       └── package.json          # Playwright E2E 测试依赖(可选)
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
└── package.json                  # Node.js 依赖(可选,E2E 测试用)
```

---

## 前端架构

### 技术栈

- **路由**: Hash 路由(`hashchange` 事件 + 正则匹配)
- **状态管理**: 发布订阅模式(`Store`),细粒度按 key 订阅
- **API 客户端**: Fetch 封装(超时/错误码映射/降级处理)
- **UI 组件**: 类组件模式(`new Component().render()`),独立生命周期
- **设计风格**: Soft UI Evolution(环保生态/毛玻璃效果/Mobile-First)

### 核心模块

| 模块 | 文件 | 功能 |
|------|------|------|
| **应用入口** | `app.js` | SPA 启动引导、全局初始化、路由注册 |
| **路由器** | `router.js` | Hash 路由管理、页面视图切换、参数解析 |
| **状态管理** | `store.js` | 发布订阅模式、细粒度订阅、不可变更新 |
| **API 客户端** | `api.js` | 统一 HTTP 请求、错误处理、业务方法封装 |
| **页面视图** | `pages/*.js` | 各页面业务逻辑(10 个页面) |
| **UI 组件** | `components/*.js` | 7 个可复用组件 |

### 路由结构

```
#/home           # 首页:拍照上传 + 搜索入口
#/preview         # 预览确认页:图片裁剪/确认
#/result          # 结果展示页:AI识别结果
#/search          # 搜索结果页:关键词匹配列表
#/guide           # 分类指南页:四类垃圾说明
#/history         # 历史记录页:过往识别记录
#/item/:keyword   # 物品详情页:处理步骤+易混淆对比
#/map             # 投放点地图页
#/community       # 社区活动页
#/profile         # 个人中心页
```

### 页面生命周期

每个页面类必须实现:
- `init()`: 初始化逻辑
- `destroy()`: 清理逻辑(移除事件监听、释放资源)

---

## 数据文件说明

### waste.json (垃圾分类词库)

```json
{
  "version": "1.0",
  "categories": [
    {
      "id": 0,
      "name": "厨余垃圾",
      "color": "#8B4513",
      "icon": "🗑️",
      "bin_color": "棕色"
    },
    {
      "id": 1,
      "name": "可回收物",
      "color": "#007bff",
      "icon": "♻️",
      "bin_color": "蓝色"
    },
    {
      "id": 2,
      "name": "其他垃圾",
      "color": "#333333",
      "icon": "🗑️",
      "bin_color": "灰色/黑色"
    },
    {
      "id": 3,
      "name": "有害垃圾",
      "color": "#dc3545",
      "icon": "☠️",
      "bin_color": "红色"
    }
  ],
  "items": [
    {
      "yolo_label": "apple",
      "label": "苹果核",
      "aliases": ["苹果", "苹果皮", "苹果核"],
      "category_id": 0,
      "category_name": "厨余垃圾",
      "bin_color": "棕色",
      "guidance": "请将果皮果核投入棕色厨余垃圾桶..."
    }
  ]
}
```

**数据量**: 40+ 物品,150+ 别名,覆盖 4 大类

### guide_standard.json (分类标准数据)

**数据量**: 4 大类,每类包含:
- 定义与说明
- 投放提示(6-8 条)
- 常见物品示例(8-10 条)
- 校园特有物品(5-8 条)
- 易错物品对比(4-6 条)

### confusing_pairs.json (易混淆物品对比)

**数据量**: 20+ 组对比,每组包含:
- 物品 A(名称、类别、原因、提示)
- 物品 B(名称、类别、原因、提示)
- 关键差异点
- 频率(高/中/低)
- 场景(食堂/宿舍/教室等)
- 标签(用于搜索过滤)

---

## 快速开始

### 环境准备

```bash
# 1. 创建并激活虚拟环境(推荐)
python -m venv venv
# Windows
venv\Scripts\activate
# Linux/macOS
source venv/bin/activate

# 2. 安装 Python 依赖
pip install -r requirements.txt
```

### 模型准备

将训练好的 YOLOv8 模型放入 `models/` 目录:

- `models/garbage_yolov8m_best.pt` — 40 类垃圾分类专用模型(必需)
- `models/yolov8n.pt` — YOLOv8n 预训练权重(自动降级备用,可选)

模型下载说明详见 [模型下载说明.md](项目文档/模型下载说明.md)。

### 启动服务

```bash
python -m app.main
```

默认监听 `http://localhost:8001`,可通过环境变量 `PORT` 或修改 [app/config.py](app/config.py) 自定义端口。

### 访问

浏览器打开 `http://localhost:8001` 即可使用 SPA 前端界面。

### Docker 部署

```bash
cd docker
docker-compose up --build
```

---

## AI 分类策略

系统按优先级依次尝试以下分类策略:

1. **YOLOv8 40 类模型** — 最高优先级,直接检测 40 种校园常见垃圾
2. **多模态融合** — YOLOv8 + SAHI 切片推理 + 双层级联,适用于小目标和复杂场景
3. **COCO 80 类映射** — 使用 COCO 预训练模型并映射到中国 4 类标准(备用)
4. **启发式分类(演示模式)** — 基于 12 维图像特征(颜色/纹理/形状/金属光泽等)的加权投票系统

### 12 维图像特征

1. 绿色像素比例(植物/食物)
2. 红色像素比例(危险品/食物)
3. 棕色像素比例(土壤/腐烂)
4. 高亮像素比例(透明/金属)
5. 灰暗像素比例(脏污/其他)
6. 亮度均值
7. 对比度(标准差)
8. 长宽比
9. 圆形度
10. 边缘密度
11. 金属光泽
12. 纹理复杂度

---

## 限流策略

- **滑动窗口算法**: IP 级限流,精确控制请求频率
- **路径分级限流**:
  - `/api/predict`: 15 次/分钟(计算密集型)
  - `/api/batch_predict`: 10 次/分钟
  - `/api/search`: 30 次/分钟
  - `/api/auth/`: 10 次/分钟(防暴力破解)
- **白名单机制**: 开发环境 IP 自动跳过
- **响应头携带**: 完整限流状态(`X-RateLimit-*`)

### 响应头示例

```http
X-RateLimit-Limit: 15
X-RateLimit-Remaining: 12
X-RateLimit-Reset: 1716796800
X-RateLimit-Policy: 15;w=60
Retry-After: 3
```

---

## 缓存策略

- **LRU 淘汰**: 最近最少使用,超过最大容量时淘汰最久未使用的条目
- **TTL 过期**: 默认 24 小时,过期自动删除
- **感知哈希去重**: 使用 `imagehash` 库的 `phash` 算法,识别相似图片
- **最大容量**: 默认 500 条

### 缓存命中场景

- 相同图片短时间内多次上传(用户重复操作)
- 批量处理时包含重复图片
- 演示/测试环境减少模型调用次数

---

## 拼音搜索

### 实现方式

1. **优先使用 pypinyin 库**: 自动转换中文为拼音首字母
2. **Fallback 手动映射表**: 覆盖 150+ 垃圾分类高频汉字
3. **前缀匹配**: 支持精确匹配和前缀匹配(如 `sl` 匹配 `slp`、`sld`)

### 示例

| 输入 | 匹配结果 |
|------|----------|
| `slp` | 塑料瓶、塑料袋、塑料杯 |
| `sl` | 塑料瓶、塑料袋、塑料杯、塑料碗、塑料盒 |
| `pp` | 垃圾桶、塑料瓶、苹果 |

---

## 测试

### API 接口测试

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行指定测试文件
python -m pytest tests/test_api.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=app --cov=services --cov=routers --cov=utils --cov-report=html
```

### 模型诊断

```bash
# 基础模型诊断
python 模型训练/diagnose_model.py

# 深度诊断
python 模型训练/deep_diagnose.py
```

### Playwright E2E 测试

```bash
cd tests/e2e
npm install
npx playwright test
```

---

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

---

## 开发指南

### 代码规范

- **注释**: 全中文注释,函数/类必写 docstring
- **质量**: 减少冗余对象复制,用提前返回替代多层嵌套
- **结构**: 代码超 20 行必须抽象为独立函数/模块
- **坏味道**: 禁用无意义命名,消除重复代码

### 添加新路由

1. 在 `routers/` 创建新文件
2. 定义 `router = APIRouter(tags=["标签"])`
3. 在 `app/main.py` 注册路由: `app.include_router(router)`
4. 在 `utils/response.py` 添加统一响应格式

### 添加新页面

1. 在 `static/js/pages/` 创建新文件
2. 实现 `init()` 和 `destroy()` 生命周期方法
3. 在 `app.js` 注册路由: `router.register('/path', createPageHandler('pageName', './pages/xxx.js'))`

### 添加新数据

1. 在 `data/` 创建或修改 JSON 文件
2. 在对应服务层添加加载逻辑
3. 在路由层添加 API 端点

---

## 部署指南

### 本地部署

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 放置模型文件
# 将 garbage_yolov8m_best.pt 放入 models/ 目录

# 3. 启动服务
python -m app.main

# 4. 访问
# 浏览器打开 http://localhost:8001
```

### Docker 部署

```bash
# 1. 构建 Docker 镜像
cd docker
docker-compose build

# 2. 启动容器
docker-compose up -d

# 3. 查看日志
docker-compose logs -f

# 4. 停止容器
docker-compose down
```

### 环境变量配置

创建 `.env` 文件:

```env
HOST=0.0.0.0
PORT=8001
LOG_LEVEL=info
DATABASE_PATH=data/app.db
MODEL_PATH=models/garbage_yolov8m_best.pt
USE_YOLO_PT_MODEL=true
YOLO_INPUT_SIZE=640
CONFIDENCE_THRESHOLD=0.25
CACHE_MAX_ITEMS=500
CACHE_TTL_HOURS=24
```

---

## 常见问题

### Q1: 模型加载失败怎么办?

**A**: 检查以下几点:
1. 模型文件是否存在: `models/garbage_yolov8m_best.pt`
2. 依赖是否安装: `pip install -r requirements.txt`
3. 模型路径是否正确: 检查 `.env` 文件中的 `MODEL_PATH`

### Q2: 图片识别不准确怎么办?

**A**: 尝试以下方法:
1. 使用多模态融合接口: `/api/predict/multimodal`
2. 确保图片清晰,光线充足
3. 垃圾物品尽量完整,不要遮挡
4. 查看识别日志,分析置信度

### Q3: 搜索功能不工作怎么办?

**A**: 检查:
1. 词库文件是否存在: `data/waste.json`
2. 搜索关键词是否正确
3. 浏览器控制台是否有错误

### Q4: 如何添加新的垃圾分类物品?

**A**:
1. 在 `data/waste.json` 的 `items` 数组中添加新条目
2. 设置正确的 `category_id` 和 `aliases`
3. 重启服务或重新加载词库

### Q5: 如何调整限流策略?

**A**: 修改 `services/rate_limiter.py` 中的 `PATH_LIMITS` 字典:

```python
PATH_LIMITS = {
    "/api/predict": (30, 60),  # 调整为 30 次/分钟
    "/api/search": (60, 60),   # 调整为 60 次/分钟
    # ...
}
```

---

## 许可证

MIT License

---

## 贡献指南

欢迎提交 Issue 和 Pull Request!

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 联系方式

如有问题或建议,欢迎通过以下方式联系:

- 提交 Issue
- 发送邮件
- 加入技术交流群

---

## 更新日志

### v1.1.0 (2025-05-25)

- ✨ 新增多模态融合推理接口
- ✨ 新增语音纠偏校正功能
- ✨ 新增投放点地图功能
- ✨ 新增环保社区打卡功能
- ✨ 优化图像缓存策略(感知哈希去重)
- ✨ 优化拼音搜索(前缀匹配)
- 🐛 修复 YOLO 置信度校准问题
- 🐛 修复批量识别内存泄漏问题

### v1.0.0 (2025-05-20)

- ✅ 初始版本发布
- ✅ 支持 YOLOv8 图像识别
- ✅ 支持中文模糊搜索
- ✅ 支持拼音首字母搜索
- ✅ 支持批量识别
- ✅ 支持识别历史记录
- ✅ 支持用户反馈收集
- ✅ 支持用户认证(OAuth)

---

## 致谢

感谢以下开源项目:

- [Ultralytics YOLOv8](https://github.com/ultralytics/ultralytics) - YOLO 目标检测框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代 Web 框架
- [FuzzyWuzzy](https://github.com/seatgeek/fuzzywuzzy) - 模糊字符串匹配
- [Pillow](https://pillow.readthedocs.io/) - Python 图像处理库
