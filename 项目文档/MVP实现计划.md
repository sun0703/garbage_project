# 校园生活垃圾智能分类识别系统 — 六阶段 MVP 实现计划

> **文档版本：** v2.0 (Web版)
> **创建日期：** 2026-05-21
> **更新日期：** 2026-05-21
> **项目代号：** EcoSort-Campus
> **技术栈：** FastAPI + YOLOv8m + Web SPA (HTML/CSS/JS或Vue3) + PostgreSQL + Redis

---

## 目录

1. [项目概述](#1-项目概述)
2. [现状盘点与技术资产](#2-现状盘点与技术资产)
3. [架构总览](#3-架构总览)
4. [阶段一：核心识别引擎完善（MVP-α）](#4-阶段一核心识别引擎完善mvp-α)
5. [阶段二：多模态识别 + 分类知识库（MVP-β）](#5-阶段二多模态识别--分类知识库mvp-β)
6. [阶段三：地图导航 + 社区互动基础（MVP-γ）](#6-阶段三地图导航--社区互动基础mvp-γ)
7. [阶段四：个人中心 + 数据可视化（MVP-δ）](#7-阶段四个人中心--数据可视化mvp-δ)
8. [阶段五：后台管理系统（MVP-ε）](#8-阶段五后台管理系统mvp-ε)
9. [阶段六：生产化部署 + 运营闭环（MVP-Final）](#9-阶段六生产化部署--运营闭环mvp-final)
10. [跨阶段公共基础设施](#10-跨阶段公共基础设施)
11. [验收标准与质量门禁](#11-验收标准与质量门禁)
12. [风险识别与应对策略](#12-风险识别与应对策略)

---

## 1. 项目概述

### 1.1 产品定位

面向校园场景的**网页端生活垃圾智能分类识别系统**，以 AI 图像识别为核心能力，逐步扩展语音识别、地图导航、社区互动、积分体系等功能，最终构建「识别 → 指导 → 行动 → 激励」的完整垃圾分类闭环。全站通过浏览器访问，支持 PC 和移动端。

### 1.2 目标用户

| 用户角色 | 核心诉求 | 使用频率 | 访问设备 |
|---------|---------|---------|---------|
| 在校学生 | 快速识别垃圾类别、学习分类知识 | 高（日常） | 手机浏览器 / PC |
| 教职工 | 准确投放、参与环保活动 | 中 | PC为主 / 手机 |
| 访客/家长 | 了解校园环保文化、体验功能 | 低 | PC / 手机 |
| 管理员/运营 | 数据监控、内容维护、活动管理 | 日常工作 | PC |

### 1.3 产品架构图（功能模块）

```
┌──────────────────────────────────────────────────────┐
│        校园生活垃圾智能分类识别系统 (Web)               │
├────────┬─────────┬──────────┬──────────┬─────────────┤
│智能识别 │分类指南  │校园社区   │个人中心   │后台管理     │
│模块    │模块     │模块      │模块      │模块         │
├────────┼─────────┼──────────┼──────────┼─────────────┤
│▶垃圾图像│▶校园垃圾│▶环保打卡 │▶环保积分 │▶用户管理    │
│ 分类识别 │ 分类标准 │ 分享    │ 记录     │ /数据分析    │
│▶语音识别│▶投放点  │▶知识问答│▶使用数据│▶模型迭代    │
│ 分类    │ 地图指引 │ 互动    │ 统计     │更新         │
│▶拍照/  │▶易错垃圾│▶环保活动│▶偏好设置│▶投放点信息  │
│相册导入 │ 查询    │ 发布    │          │维护         │
└────────┴─────────┴──────────┴──────────┴─────────────┘
```

### 1.4 六阶段路线图

```
阶段一 MVP-α  ████████████████████░░░░  核心识别引擎
阶段二 MVP-β  ░░░░░░░░░░░░░░░░░░░░░░  多模态+知识库
阶段三 MVP-γ  ░░░░░░░░░░░░░░░░░░░░░░  地图+社区基础
阶段四 MVP-δ  ░░░░░░░░░░░░░░░░░░░░░░  个人中心+数据
阶段五 MVP-ε  ░░░░░░░░░░░░░░░░░░░░░░  后台管理
阶段六 Final  ░░░░░░░░░░░░░░░░░░░░░░  部署+运营

依赖关系：
  阶段一 ← 阶段二 ← 阶段三 ← 阶段四
                  ↑         ↑
                  └─── 阶段五（并行开发）
                            └──→ 阶段六
```

---

## 2. 现状盘点与技术资产

### 2.1 已完成代码清单

| 文件路径 | 功能描述 | 代码行数 | 状态 |
|---------|---------|---------|------|
| `main.py` | FastAPI 主程序，含完整后端逻辑 | ~1420 行 | ✅ 可运行 |
| `index.html` | 单页 Web 前端 Demo（内联 HTML+CSS+JS） | ~行 | ✅ 可用 |
| `data/waste.json` | 垃圾分类词库（4类/100+物品） | 完整 | ✅ 已就绪 |
| `datasets/rubbish/` | YOLO 训练数据集（300+图片+标注） | 完整 | ✅ 已就绪 |
| `.github/linters/` | Python lint 配置 | 2个文件 | ✅ 已配置 |

### 2.2 main.py 现有能力矩阵

| 能力域 | 具体功能 | 实现位置 | 完成度 |
|-------|---------|---------|--------|
| **AI 推理引擎** | YOLOv8m PyTorch 模型加载与推理 | `VisionEngine._predict_pytorch()` | 100% |
| | ONNX 格式模型兼容推理 | `VisionEngine._predict_onnx()` | 100% |
| | 40类→中国4类映射 | `GARBAGE_40CLASSES` 字典 | 100% |
| | COCO 80类→中国4类映射 | `COCO_TO_WASTE` 字典 | 100% |
| **图像特征分析** | 颜色/亮度/透明度/形状分析 | `ImageFeatureAnalyzer` 类 | 100% |
| | 金属光泽检测（计分制 v3.0） | `_detect_metallic()` | 100% |
| | 启发式分类算法（形状优先 v2.1） | `classify_by_features()` | 100% |
| | 模拟置信度计算 | `calculate_confidence()` | 100% |
| **模糊搜索** | FuzzyWuzzy 文字模糊匹配 | `SearchEngine.search()` | 100% |
| | 物品类型智能匹配示例选择 | `get_smart_item()` | 100% |
| | 按 YOLO 标签/类别查找 | `get_by_yolo_label()` 等 | 100% |
| **API 接口** | POST `/api/predict` 图像预测 | 第1088行 | 100% |
| | GET `/api/search` 模糊搜索 | 第1252行 | 100% |
| | GET `/api/categories` 类别列表 | 第1276行 | 100% |
| | POST `/api/debug/analyze` 调试分析 | 第1303行 | 100% |
| | GET `/api/health` 健康检查 | 第1346行 | 100% |
| | GET `/` 首页 HTML 返回 | 第1076行 | 100% |

### 2.3 待补齐的能力缺口

| 缺失能力 | 影响阶段 | 优先级 | 说明 |
|---------|---------|--------|------|
| 批量识别 API | 一 | P0 | 当前仅支持单张图片 |
| 请求追踪/缓存层 | 一 | P0 | 无 request_id、无推理缓存 |
| 前端 SPA 多页面重构 | 一 | P0 | 当前 index.html 为单文件 Demo，需拆分为正式 SPA |
| 图片压缩上传 | 一 | P0 | 当前直接传原始 Base64，大图性能差 |
| 识别历史存储 | 一 | P2 | 无 localStorage 持久化 |
| 语音转文字链路（浏览器端） | 二 | P0 | 当前仅有 Web Speech API 简单集成，需增强录音 UI |
| 校园分类标准数据 | 二 | P0 | 仅 waste.json 词库，无结构化标准 |
| 易错物品对比数据 | 二 | P1 | 需从词库中提取并扩展 |
| 用户认证系统 | 三 | P0 | 完全缺失 |
| 地图服务集成（JS SDK） | 三 | P0 | 完全缺失 |
| 数据库持久层 | 三 | P0 | 当前无数据库，纯内存运行 |
| 积分系统 | 四 | P0 | 完全缺失 |
| 数据统计聚合 | 四 | P1 | 完全缺失 |
| 管理后台页面 | 五 | P0 | 完全缺失 |
| Docker/CI/CD | 六 | P0 | 完全缺失 |

---

## 3. 架构总览

### 3.1 最终目标架构（阶段六完成后）

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器 (Browser)                   │
│                                                             │
│   ┌─────────────────────────────────────────────────────┐   │
│   │              EcoSort Campus Web App (SPA)            │   │
│   │                                                     │   │
│   │  ┌─────────┬─────────┬─────────┬─────────┬────────┐ │   │
│   │  │ 识别首页 │ 分类指南 │ 社区互动 │ 个人中心 │ 管理   │ │   │
│   │  │ /        │ /guide  │ /community│ /profile│ /admin│ │   │
│   │  └─────────┴─────────┴─────────┴─────────┴────────┘ │   │
│   └──────────────────────┬──────────────────────────────┘   │
│                          │ HTTP (JSON)                      │
├──────────────────────────┼───────────────────────────────────┤
│                     Nginx 反向代理层                           │
│              (SSL终止 / 静态资源 / API转发 / gzip)             │
├──────────────────────────┼───────────────────────────────────┤
│                          ▼                                    │
│  ┌───────────────────────────────────────────────────────┐   │
│  │                  FastAPI 应用集群                        │   │
│  │                                                       │   │
│  │  ┌──────────┐  ┌──────────┐  ┌────────────────────┐  │   │
│  │  │ Web 服务  │  │ AI 推理  │  │ Admin 管理接口      │  │   │
│  │  │ :8001     │  │ :8002    │  │ (同进程/路由隔离)   │  │   │
│  │  └──────────┘  └──────────┘  └────────────────────┘  │   │
│  └──────────────────────┬────────────────────────────────┘   │
│                         │                                      │
├─────────────────────────┼──────────────────────────────────────┤
│                        基础设施层                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐   │
│  │PostgreSQL│  │  Redis   │  │ OSS/MinIO │  │Prometheus  │   │
│  │(主数据库) │  │(缓存/队列)│  │(图片存储) │  │+Grafana    │   │
│  └──────────┘  └──────────┘  └──────────┘  └────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

**关键设计决策：前端统一为单一 Web SPA**

不同于原方案中「小程序 + H5 + Admin 三端分离」，本方案采用**单一代码库 + 角色视图切换**模式：

| 用户角色 | 访问路径 | 视图差异 |
|---------|---------|---------|
| 普通用户 | `/`, `/guide`, `/community`, `/profile` | 完整功能界面 |
| 管理员 | `/admin/*` | 同一 SPA 内的管理面板视图（需登录鉴权） |
| 移动端用户 | 同 URL，响应式布局 | CSS Media Query 自适应 |

优势：
- 一套代码维护，无需多端同步
- 前后端共享同一套 API
- 部署简单（单个 Nginx 站点）
- 可渐进引入 Vue/React 框架重构（当前 Vanilla JS 可运行）

### 3.2 项目目录结构（最终形态）

```
垃圾识别/
├── backend/                         # 后端服务（从 main.py 重构而来）
│   ├── __init__.py
│   ├── main.py                     # FastAPI 入口，路由注册
│   ├── config.py                   # 配置管理（环境变量/常量）
│   ├── models/                     # 数据模型（SQLAlchemy ORM）
│   │   ├── __init__.py
│   │   ├── user.py                 # 用户模型
│   │   ├── waste.py                # 垃圾相关模型
│   │   ├── community.py            # 社区相关模型
│   │   └── admin.py                # 管理相关模型
│   ├── services/                   # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── vision_service.py       # 视觉推理服务（从 main.py 抽取）
│   │   ├── search_service.py       # 搜索服务（从 main.py 抽取）
│   │   ├── user_service.py         # 用户服务
│   │   ├── location_service.py     # 地图/投放点服务
│   │   ├── community_service.py    # 社区服务（打卡/问答/活动）
│   │   ├── point_service.py        # 积分服务
│   │   └── analytics_service.py    # 统计分析服务
│   ├── api/                        # API 路由层
│   │   ├── __init__.py
│   │   ├── predict.py              # 识别相关路由
│   │   ├── search.py               # 搜索相关路由
│   │   ├── guide.py                # 分类指南路由
│   │   ├── auth.py                 # 认证路由
│   │   ├── user.py                 # 用户路由
│   │   ├── community.py            # 社区路由
│   │   ├── map.py                  # 地图路由
│   │   └── admin/                  # 管理后台路由
│   │       ├── __init__.py
│   │       ├── users.py
│   │       ├── content.py
│   │       ├── model_mgmt.py
│   │       ├── stats.py
│   │       └── points_map.py
│   ├── core/                       # 核心工具
│   │   ├── __init__.py
│   │   ├── engine.py               # VisionEngine（从 main.py 抽取）
│   │   ├── analyzer.py             # ImageFeatureAnalyzer（抽取）
│   │   ├── search_engine.py        # SearchEngine（抽取）
│   │   ├── security.py             # Session/JWT 鉴权
│   │   ├── cache.py                # Redis 缓存封装
│   │   └── exceptions.py           # 自定义异常
│   ├── data/                       # 数据文件
│   │   ├── waste.json              # 垃圾词库（已有）
│   │   ├── guide_standard.json     # 校园分类标准（新建）
│   │   └── confusing_pairs.json    # 易错物品对（新建）
│   ├── database/                   # 数据库相关
│   │   ├── __init__.py
│   │   ├── session.py              # DB Session 工厂
│   │   └── init_db.py              # 建表脚本
│   ├── ai_models/                  # AI 模型目录（原 models/）
│   │   └── garbage_yolov8m_best.pt
│   ├── static/                     # 静态资源（CSS/JS/图片）
│   │   ├── css/
│   │   │   ├── main.css            # 主样式表
│   │   │   ├── components.css      # 组件样式
│   │   │   └── admin.css           # 管理后台样式
│   │   ├── js/
│   │   │   ├── app.js              # 主入口 / 路由管理器
│   │   │   ├── api.js              # API 封装（fetch wrapper）
│   │   │   ├── router.js           # Hash Router 或 History API 路由
│   │   │   ├── store.js            # 状态管理（简单的发布订阅或全局对象）
│   │   │   ├── utils/
│   │   │   │   ├── image.js        # 图片处理（压缩/裁剪/Base64）
│   │   │   │   ├── storage.js      # localStorage 封装
│   │   │   │   └── ui.js           # UI 工具函数（toast/loading/modal）
│   │   │   ├── pages/
│   │   │   │   ├── home.js         # 首页逻辑
│   │   │   │   ├── camera.js       # 拍照/上传页逻辑
│   │   │   │   ├── result.js       # 结果展示页逻辑
│   │   │   │   ├── search.js       # 搜索页逻辑
│   │   │   │   ├── guide.js        # 分类指南页逻辑
│   │   │   │   ├── map.js          # 地图导航页逻辑
│   │   │   │   ├── community/
│   │   │   │   │   ├── checkin.js  # 打卡页逻辑
│   │   │   │   │   ├── quiz.js     # 答题页逻辑
│   │   │   │   │   └── events.js   # 活动列表页逻辑
│   │   │   │   ├── profile/
│   │   │   │   │   ├── index.js    # 个人中心主页逻辑
│   │   │   │   │   ├── points.js   # 积分明细页逻辑
│   │   │   │   │   └── stats.js    # 数据统计页逻辑
│   │   │   │   └── admin/
│   │   │   │       ├── dashboard.js # 仪表盘逻辑
│   │   │   │       ├── users.js    # 用户管理逻辑
│   │   │   │       ├── content.js  # 内容管理逻辑
│   │   │   │       └── settings.js # 系统设置逻辑
│   │   │   └── components/         # UI 组件
│   │   │       ├── camera-btn.js   # 拍照按钮组件
│   │   │       ├── result-card.js  # 结果卡片组件
│   │   │       ├── category-tag.js # 分类标签组件
│   │   │       ├── point-badge.js  # 积分徽章组件
│   │   │       ├── nav-bar.js      # 导航栏组件
│   │   │       └── tab-bar.js      # 底部Tab栏组件（移动端）
│   │   └── images/                 # 图标/图片资源
│   ├── templates/                  # HTML 模板（Jinja2 或纯静态）
│   │   ├── base.html               # 基础模板（含 SPA 骨架）
│   │   ├── index.html              # 入口页（当前单文件可在此过渡）
│   │   └── admin.html              # 管理后台入口（可选独立页）
│   ├── tests/                      # 测试
│   │   ├── test_vision.py
│   │   ├── test_search.py
│   │   ├── test_api.py
│   │   └── conftest.py
│   └── requirements.txt
│
├── frontend/                       # （可选）如引入框架时的前端工程
│   ├── package.json                # 如使用 Vite + Vue3 构建
│   ├── vite.config.js
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/
│   │   ├── views/                  # 对应 static/ 下的各页面
│   │   ├── components/
│   │   ├── api/
│   │   ├── stores/                 # Pinia 状态管理
│   │   └── styles/
│   └── public/
│
├── deploy/                         # 部署配置
│   ├── Dockerfile                  # 应用镜像
│   ├── Dockerfile.ai               # AI 推理专用镜像
│   ├── docker-compose.yml          # 编排文件
│   ├── docker-compose.prod.yml     # 生产编排
│   ├── nginx.conf                  # Nginx 配置
│   ├── .env.example                # 环境变量模板
│   └── scripts/
│       ├── init-db.sh              # 数据库初始化
│       └── backup.sh               # 备份脚本
│
├── datasets/                       # 训练数据集（已有）
│   └── rubbish/
│
├── index.html                      # 当前 Web Demo 入口（重构前保留）
├── main.py                         # 当前主程序（重构前备份）
├── pyproject.toml                  # 项目配置
├── README.md
│
└── 项目文档/                       # 所有项目文档统一存放
    ├── MVP实现计划.md              # 本文档
    ├── MVP流程文档.md              # 详细交互流程
    ├── API接口文档.md
    ├── 数据库设计.md
    ├── 部署运维手册.md
    └── 测试报告模板.md
```

---

## 4. 阶段一：核心识别引擎完善（MVP-α）

### 4.1 阶段目标

打造可独立运行的垃圾图像分类识别核心能力，达到**「能拍照 → 能识别 → 能给出结果」**的最小闭环。本阶段完成后，产品具备可演示的 Web 应用。

### 4.2 功能需求清单

#### 4.2.1 F-1.1 图像识别 API 强化

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-1.1.1 | 为每次预测请求生成唯一 `request_id` | P0 | 响应中包含 UUID 格式的 request_id |
| F-1.1.2 | 新增批量识别接口 `POST /api/batch_predict` | P0 | 支持单次最多5张图片并行推理 |
| F-1.1.3 | 推理结果缓存（基于图像指纹） | P1 | 相同图片24h内不重复推理，直接返回缓存 |
| F-1.1.4 | 请求限流保护 | P1 | 单 IP 30次/分钟，超限返回 429 |
| F-1.1.5 | 推理耗时优化日志 | P2 | 记录预处理/推理/后处理各阶段耗时 |

#### 4.2.2 F-1.2 前端拍照/上传体验优化

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-1.2.1 | 上传区域优化（大尺寸突出，视觉引导清晰） | P0 | 点击唤起文件选择器（移动端调相机） |
| F-1.2.2 | 图片压缩上传（≤ 2MB） | P0 | 大于2MB的图片自动 Canvas 压缩后再上传 |
| F-1.2.3 | 图片预览与重新选择 | P0 | 上传前可预览确认，支持重新选择 |
| F-1.2.4 | 上传状态反馈（loading 动画） | P0 | 显示上传进度和识别中的动画 |
| F-1.2.5 | 拖拽上传支持（PC端） | P1 | PC端支持拖拽图片到指定区域 |
| F-1.2.6 | 粘贴上传支持（Ctrl+V） | P2 | 从剪贴板粘贴图片 |

#### 4.2.3 F-1.3 识别结果展示优化

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-1.3.1 | 结果卡片：类别名称 + 图标 + 颜色标识 | P0 | 四种颜色区分4类垃圾 |
| F-1.3.2 | 置信度进度条（百分比 + 动画） | P0 | 进度条带颜色渐变动画 |
| F-1.3.3 | 投放指引文案（如"请投入蓝色可回收物桶"） | P0 | 来自 waste.json 的 guidance 字段 |
| F-1.3.4 | 处理建议（如"请将液体倒尽后投放"） | P1 | 根据具体物品类型给出建议 |
| F-1.3.5 | 结果分享按钮（生成文字摘要/复制链接） | P2 | 可复制文本分享 |

#### 4.2.4 F-1.4 离线/弱网降级策略

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-1.4.1 | 网络异常检测与提示 | P0 | 请求失败时显示友好错误提示 |
| F-1.4.2 | 自动降级到特征分析演示模式 | P0 | 模型不可用时走 ImageFeatureAnalyzer |
| F-1.4.3 | 本地模型推理兜底方案设计 | P1 | 技术方案文档（WebAssembly/ONNX WASM 方向调研） |

#### 4.2.5 F-1.5 识别历史本地存储

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-1.5.1 | localStorage 存储最近50条记录 | P2 | 包含缩略图(DataURL)、类别、时间戳 |
| F-1.5.2 | 历史记录侧边栏/抽屉 | P2 | 支持查看历史、删除单条、清空全部 |
| F-1.5.3 | 历史记录点击回看详情 | P2 | 点击可重新展示该次识别的完整结果 |

### 4.3 技术实现方案

#### 4.3.1 后端改造（main.py 增强）

**新增/修改的 API 接口：**

```python
# ========== 新增：批量预测接口 ==========
@app.post("/api/batch_predict")
async def batch_predict_waste(request: BatchPredictRequest) -> JSONResponse:
    """
    批量图像预测接口（最多5张）
    - 并发执行多次推理
    - 返回结果数组，保持输入顺序
    """
    pass

# ========== 新增：预测历史查询 ==========
@app.get("/api/history")
async def get_history(limit: int = Query(20, ge=1, le=50)) -> JSONResponse:
    """获取当前会话的识别历史（内存缓存，TTL=24h）"""
    pass

# ========== 修改：原有 predict 接口增强 ==========
@app.post("/api/predict")
async def predict_waste(request: PredictRequest) -> JSONResponse:
    # 新增：
    # 1. 生成 request_id (uuid4)
    # 2. 计算图像指纹 (perceptual hash) 用于缓存 key
    # 3. 查缓存 → 命中则直接返回
    # 4. 未命中 → 推理 → 写缓存 → 返回
    # 5. 记录到历史
    pass
```

**新增中间件：**

```python
# 速率限制中间件
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # 基于 IP 的滑动窗口限流
    # 30次/分钟
    pass

# 请求ID注入中间件
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    # 生成 X-Request-ID 注入 header
    pass
```

**新增依赖包：**

```
# requirements.txt 新增
fastapi-limiter>=0.1.5    # 速率限制
imagehash>=4.3.1          # 感知哈希（图片去重缓存）
Pillow>=10.0.0            # 图片处理（已有）
```

#### 4.3.2 前端重构（index.html → SPA 结构）

**当前状态**：所有 HTML/CSS/JS 内联在单个 `index.html` 中，适合快速原型验证。
**目标状态**：拆分为模块化的 SPA 结构，支持多页面路由和组件复用。

**两种演进路径（按需选择）：**

**路径 A：保持轻量（Vanilla JS 模块化）**
- 将 `index.html` 中的 JS 拆分为多个 `.js` 文件
- 用 `<script type="module">` 引入
- 手写简易 Hash Router
- 适合单人开发、无构建工具依赖

**路径 B：引入框架（Vue3/Vite）**
- 用 Vue3 重写前端，获得响应式数据绑定和组件化能力
- Vite 构建，HMR 开发体验好
- 适合多人协作、长期维护

**阶段一推荐路径 A**（最小改动），后续可在阶段三~四平滑迁移到路径 B。

**页面结构重组（路径A）：**

```html
<!-- base.html - SPA 骨架 -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>🏫 校园垃圾分类智能识别</title>
    <link rel="stylesheet" href="/static/css/main.css">
    <link rel="stylesheet" href="/static/css/components.css">
</head>
<body>
    <!-- 导航栏 -->
    <nav id="navBar" class="nav-bar">...</nav>

    <!-- 主内容区域（SPA 视图容器） -->
    <main id="app">
        <!-- 页面1：首页（识别入口 + 搜索） -->
        <section id="page-home" class="page active">
            <div class="upload-area" id="uploadArea">
                <!-- 点击/拖拽/粘贴上传区域 -->
            </div>
            <div class="search-area">
                <input id="searchInput" placeholder="输入垃圾名称搜索...">
                <button id="voiceBtn">🎤</button>
            </div>
        </section>

        <!-- 页面2：预览确认 -->
        <section id="page-preview" class="page">
            <div class="image-preview">
                <img id="previewImg" src="" alt="预览">
            </div>
            <div class="preview-actions">
                <button onclick="retake()">重新选择</button>
                <button class="primary" onclick="startPredict()">开始识别</button>
            </div>
        </section>

        <!-- 页面3：识别结果 -->
        <section id="page-result" class="page">
            <div class="result-card" id="resultCard">
                <!-- 类别名称 + 图标 + 颜色条 -->
                <!-- 置信度进度条 -->
                <!-- 投放指引 -->
            </div>
            <div class="result-actions">
                <button onclick="shareResult()">📤 分享</button>
                <button onclick="goHome()">继续识别</button>
                <button onclick="showFeedback()">反馈错误</button>
            </div>
        </section>

        <!-- 页面4：搜索结果 -->
        <section id="page-search" class="page">
            <div id="searchResultList"></div>
        </section>

        <!-- 页面5：帮助/指南（阶段二补充） -->
        <section id="page-guide" class="page">...</section>

        <!-- 页面6：历史记录 -->
        <section id="page-history" class="page">
            <div class="history-list" id="historyList"></div>
        </section>
    </main>

    <!-- 底部 TabBar（移动端显示） -->
    <nav id="tabBar" class="tab-bar">
        <a href="#home" data-page="home" class="active">🏠</a>
        <a href="#guide" data-page="guide">📖</a>
        <a href="#history" data-page="history">📋</a>
        <a href="#profile" data-page="profile">👤</a>
    </nav>

    <!-- 全局遮罩：Loading / Modal / Toast -->
    <div id="loadingOverlay" class="overlay hidden">...</div>
    <div id="modalOverlay" class="overlay hidden">...</div>
    <div id="toast" class="toast hidden"></div>

    <!-- JS 模块（ES Module 方式加载） -->
    <script type="module" src="/static/js/app.js"></script>
</body>
</html>
```

**关键 JavaScript 模块：**

```javascript
// ========== static/js/utils/image.js ==========
/**
 * 图片处理工具模块
 * 负责压缩、Base64编码、格式校验等
 */
const ImageProcessor = {
    /**
     * 压缩图片至目标大小以下
     * 使用 Canvas API 进行客户端压缩，减少传输体积
     * @param {File} file - 原始图片文件
     * @param {number} maxSizeKB - 最大大小（KB），默认2048
     * @returns {Promise<Blob>} 压缩后的Blob
     */
    compress(file, maxSizeKB = 2048) {
        return new Promise((resolve) => {
            const canvas = document.createElement('canvas');
            const ctx = canvas.getContext('2d');
            const img = new Image();
            img.onload = () => {
                // 计算缩放比例，保持宽高比
                let { width, height } = img;
                const maxDim = 1280;
                if (width > height && width > maxDim) {
                    height = (height * maxDim) / width;
                    width = maxDim;
                } else if (height > maxDim) {
                    width = (width * maxDim) / height;
                    height = maxDim;
                }
                canvas.width = width;
                canvas.height = height;
                ctx.drawImage(img, 0, 0, width, height);
                // 逐步降低质量直到满足大小要求
                let quality = 0.85;
                const tryCompress = () => {
                    canvas.toBlob((blob) => {
                        if (blob.size <= maxSizeKB * 1024 || quality <= 0.3) {
                            resolve(blob);
                        } else {
                            quality -= 0.1;
                            tryCompress();
                        }
                    }, 'image/jpeg', quality);
                };
                tryCompress();
            };
            img.src = URL.createObjectURL(file);
        });
    },

    /** 转为 Base64 DataURL 用于上传 */
    toBase64(blob) {
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.readAsDataURL(blob);
        });
    },

    /** 校验图片格式和大小 */
    validate(file) {
        const MAX_SIZE = 5 * 1024 * 1024; // 5MB
        const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif'];
        if (!ALLOWED_TYPES.includes(file.type)) {
            return { valid: false, error: '请选择 JPG/PNG/WebP 格式的图片' };
        }
        if (file.size > MAX_SIZE) {
            return { valid: false, error: '图片过大，请选择 5MB 以内的图片' };
        }
        return { valid: true };
    }
};

// ========== static/js/api.js ==========
/**
 * API 客户端封装
 * 统一处理请求/响应、错误处理、Token 注入
 */
const ApiClient = {
    baseUrl: '',

    /** 通用请求方法 */
    async request(url, options = {}) {
        const defaultOptions = {
            headers: {
                'Content-Type': 'application/json',
                ...this._authHeaders()
            },
            ...options
        };

        try {
            const response = await fetch(`${this.baseUrl}${url}`, defaultOptions);

            // HTTP 错误处理
            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                throw new ApiError(
                    errorData.error?.code || `HTTP_${response.status}`,
                    errorData.error?.message || `请求失败 (${response.status})`,
                    response.status
                );
            }

            return await response.json();
        } catch (err) {
            if (err instanceof ApiError) throw err;
            // 网络层错误
            throw new ApiError('E005', '网络连接失败，请检查后端服务是否启动');
        }
    },

    async predict(imageBase64) {
        return this.request('/api/predict', {
            method: 'POST',
            body: JSON.stringify({ image: imageBase64 })
        });
    },

    async batchPredict(images) {
        return this.request('/api/batch_predict', {
            method: 'POST',
            body: JSON.stringify({ images })
        });
    },

    async search(query) {
        return this.request(`/api/search?query=${encodeURIComponent(query)}`);
    },

    _authHeaders() {
        const token = localStorage.getItem('ecosort_token');
        return token ? { 'Authorization': `Bearer ${token}` } : {};
    }
};

/** 自定义 API 错误类 */
class ApiError extends Error {
    constructor(code, message, status = 0) {
        super(message);
        this.code = code;
        this.status = status;
    }
}

// ========== static/js/utils/storage.js ==========
/**
 * 前端本地存储模块
 * 使用 localStorage 持久化识别历史等数据
 */
const Storage = {
    HISTORY_KEY: 'ecosort_history',
    MAX_HISTORY: 50,

    /** 保存一条识别记录到历史 */
    saveHistory(record) {
        const list = this.getHistory();
        list.unshift({
            ...record,
            timestamp: Date.now(),
            id: this._genId()
        });
        if (list.length > this.MAX_HISTORY) list.pop();
        localStorage.setItem(this.HISTORY_KEY, JSON.stringify(list));
    },

    /** 获取历史记录列表 */
    getHistory() {
        try {
            return JSON.parse(localStorage.getItem(this.HISTORY_KEY)) || [];
        } catch { return []; }
    },

    /** 清空历史 */
    clearHistory() {
        localStorage.removeItem(this.HISTORY_KEY);
    },

    _genId() {
        return Date.now().toString(36) + Math.random().toString(36).slice(2, 7);
    }
};
```

#### 4.3.3 缓存层设计

```python
# ========== 推理缓存（内存 + TTL）==========
from collections import OrderedDict
import time
import hashlib

class InferenceCache:
    """基于 LRU + TTL 的推理结果缓存"""

    def __init__(self, max_size: int = 500, ttl_seconds: int = 86400):
        self.cache: OrderedDict[str, dict] = OrderedDict()
        self.max_size = max_size
        self.ttl = ttl_seconds

    def _make_key(self, image_data: bytes) -> str:
        """使用感知哈希生成缓存键（相同内容的图片命中同一缓存）"""
        import imagehash
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data))
        phash = str(imagehash.phash(img, hash_size=16))
        return f"infer:{phash}"

    def get(self, key: str) -> Optional[dict]:
        if key not in self.cache:
            return None
        entry = self.cache[key]
        if time.time() - entry["ts"] > self.ttl:
            del self.cache[key]
            return None
        self.cache.move_to_end(key)
        return entry["data"]

    def set(self, key: str, data: dict) -> None:
        if key in self.cache:
            del self.cache[key]
        elif len(self.cache) >= self.max_size:
            self.cache.popitem(last=False)
        self.cache[key] = {"data": data, "ts": time.time()}
```

### 4.4 数据流时序图

```
用户操作              浏览器前端 (SPA)              后端 (FastAPI)           缓存/模型
  │                      │                          │                       │
  │ 点击上传区域          │                          │                       │
  │─────────────────────>│                          │                       │
  │                      │ 触发 <input file> click   │                       │
  │                      │──────────>               │                       │
  │ 选择/拍摄照片        │                          │                       │
  │<─────────────────────│                          │                       │
  │                      │ ImageProcessor.validate() │                       │
  │                      │ ImageProcessor.compress() │                       │
  │                      │ 显示预览(page-preview)    │                       │
  │                      │                          │                       │
  │ 点击「开始识别」      │                          │                       │
  │─────────────────────>│                          │                       │
  │                      │ showLoading()             │                       │
  │                      │ ImageProcessor.toBase64() │                       │
  │                      │                          │                       │
  │                      │ POST /api/predict        │                       │
  │                      │─────────────────────────>│                       │
  │                      │                          │ 计算图像指纹(pHash)    │
  │                      │                          │ 查缓存 ──────────────>│
  │                      │                          │<────────────── 命中?  │
  │                      │                          │                       │
  │                      │                          │ [未命中]              │
  │                      │                          │ VisionEngine.predict()│
  │                      │                          │─────────────────────>│
  │                      │                          │ YOLOv8m 推理          │
  │                      │                          │<─────────────────────│
  │                      │                          │ 写入缓存              │
  │                      │<─────────────────────────│                       │
  │ 渲染结果卡片          │                          │                       │
  │ (page-result)        │ hideLoading()             │                       │
  │<─────────────────────│ Storage.saveHistory()    │                       │
```

### 4.5 阶段一交付物清单

| 交付物 | 格式 | 说明 |
|-------|------|------|
| 增强版 `backend/` 目录 | Python | 含批量接口、缓存层、限流中间件的模块化代码 |
| SPA 版前端 `static/` 目录 | HTML/CSS/JS | 多页面路由、拍照组件、结果卡片、历史记录 |
| Web 应用可运行 | - | `python main.py` 启动即可访问 http://localhost:8001 |
| 阶段一测试报告 | Markdown | 功能测试 + 性能基准测试 |

### 4.6 阶段一验收标准

| 编号 | 验收项 | 通过标准 |
|-----|-------|---------|
| AC-1.1 | 单张图片识别 | 上传图片 → 2秒内返回结果（置信度>60%） |
| AC-1.2 | 批量识别 | 5张图片并发 → 5秒内全部返回 |
| AC-1.3 | 图片压缩 | 10MB原图 → 压缩后≤2MB，视觉质量无明显损失 |
| AC-1.4 | 缓存命中 | 同一张图片第二次请求 → 直接返回（<50ms） |
| AC-1.5 | 限流保护 | 超过30次/分钟 → 返回429 + Retry-After头 |
| AC-1.6 | 历史记录 | 识别后可在历史列表中回看 |
| AC-1.7 | 降级模式 | 模型卸载后仍可通过特征分析给出分类结果 |
| AC-1.8 | 移动端适配 | 手机浏览器打开正常，相机可调用（capture属性） |
| AC-1.9 | PC端拖拽 | Chrome/Edge 支持拖拽图片到上传区域 |

---

## 5. 阶段二：多模态识别 + 分类知识库（MVP-β）

### 5.1 阶段目标

扩展识别方式（语音 + 文字），构建校园垃圾分类标准知识库。本阶段完成后，用户可以通过**图像/语音/文字三种方式**查询垃圾分类信息。

### 5.2 功能需求清单

#### 5.2.1 F-2.1 语音识别分类

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-2.1.1 | 录音按钮 UI 组件（长按/点击录音） | P0 | 按住说话，松开结束，显示波形动画 |
| F-2.1.2 | 浏览器原生语音识别（Web Speech API） | P0 | Chrome/Edge/Safari 支持，实时转写文字 |
| F-2.1.3 | 语音转文字 → 搜索链路 | P0 | ASR 结果自动传入搜索接口 |
| F-2.1.4 | 不支持浏览器的降级提示 | P0 | Firefox 等不支持时提示用户使用 Chrome |
| F-2.1.5 | 录音文件备选方案（MediaRecorder API） | P1 | 当 Web Speech API 不可用时，录制音频上传后端 ASR |
| F-2.1.6 | 语音识别结果纠错 | P2 | 对常见ASR错误做后处理（如"奶茶杯"→"奶茶杯"） |

**技术选型（Web 语音方案）：**

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **Web Speech API** (SpeechRecognition) | 浏览器原生、免费、实时性好 | 仅Chrome/Edge/Safari支持；需联网；隐私顾虑 | **首选**，覆盖主流浏览器 |
| MediaRecorder + 后端ASR | 兼容性最好（所有现代浏览器） | 需要后端ASR服务；延迟较高 | 降级备选方案 |
| 第三方SDK（百度/讯飞JS SDK） | 中文准确率高 | 有调用费用；引入外部依赖 | 生产环境精度要求高时 |

**Web Speech API 核心实现：**

```javascript
// ========== static/js/components/voice-btn.js ==========
/**
 * 语音识别按钮组件
 * 基于 Web Speech API (SpeechRecognition)
 * 支持 Chrome / Edge / Safari
 */
class VoiceButton {
    constructor(options = {}) {
        this.btnEl = options.btnEl;           // 按钮 DOM 元素
        this.onResult = options.onResult;     // 识别结果回调
        this.isRecording = false;

        // 检测浏览器支持
        const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
        if (!SR) {
            console.warn('[VoiceButton] 当前浏览器不支持 Web Speech API');
            this.supported = false;
            return;
        }

        this.supported = true;
        this.recognition = new SR();

        // 配置识别参数
        this.recognition.continuous = false;     // 单次识别（非持续监听）
        this.recognition.interimResults = true;   // 返回临时结果
        this.recognition.lang = 'zh-CN';          // 中文普通话
        this.recognition.maxAlternatives = 1;     // 返回最佳结果

        // 绑定事件
        this.recognition.onstart = () => this._onStart();
        this.recognition.onend = () => this._onEnd();
        this.recognition.onresult = (event) => this._onResult(event);
        this.recognition.onerror = (event) => this._onError(event);

        // 绑定按钮交互
        this._bindEvents();
    }

    /** 开始/停止录音 */
    toggle() {
        if (!this.supported) {
            this._showUnsupportedTip();
            return;
        }
        if (this.isRecording) {
            this.recognition.stop();
        } else {
            // 每次重新创建实例避免状态问题
            this.recognition.start();
        }
    }

    _onStart() {
        this.isRecording = true;
        this.btnEl.classList.add('recording');
        this.btnEl.innerHTML = '🔴 停止';
    }

    _onEnd() {
        this.isRecording = false;
        this.btnEl.classList.remove('recording');
        this.btnEl.innerHTML = '🎤';
    }

    _onResult(event) {
        let finalTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; i++) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript;
            }
        }
        if (finalTranscript.trim()) {
            this.onResult?.(finalTranscript.trim());
        }
    }

    _onError(event) {
        console.warn('[VoiceButton] 识别错误:', event.error);
        this.isRecording = false;
        this.btnEl.classList.remove('recording');

        const tips = {
            'no-speech': '未检测到语音，请重试',
            'audio-capture': '找不到麦克风，请检查设备权限',
            'not-allowed': '麦克风权限被拒绝，请在浏览器设置中允许',
            'network': '网络错误，语音服务不可用'
        };
        this._showToast(tips[event.error] || '语音识别出错') ;
    }

    _showUnsupportedTip() {
        alert('您的浏览器不支持语音识别功能。\n建议使用 Chrome、Edge 或 Safari 浏览器。');
    }

    _bindEvents() {
        this.btnEl.addEventListener('click', () => this.toggle());
        // 也支持长按（移动端友好）
        let pressTimer;
        this.btnEl.addEventListener('touchstart', (e) => {
            pressTimer = setTimeout(() => this.toggle(), 300);
        });
        this.btnEl.addEventListener('touchend', () => clearTimeout(pressTimer));
    }
}
```

#### 5.2.2 F-2.2 文字搜索增强

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-2.2.1 | 拼音首字母搜索 | P0 | 输入"slp"可匹配"塑料瓶" |
| F-2.2.2 | 同义词扩展 | P0 | "可乐瓶"也能匹配到"饮料瓶" |
| F-2.2.3 | 搜索联想（输入时实时提示） | P1 | 输入2个字即触发下拉提示 |
| F-2.2.4 | 搜索历史记录 | P2 | localStorage 保存最近20条搜索词 |

**拼音搜索实现方案：**

```python
# 拼音转换工具（使用 pypinyin 库）
from pypinyin import lazy_pinyin, Style

def text_to_pinyin(text: str) -> str:
    """将中文转换为拼音首字母，如'塑料瓶'→'slp'"""
    return ''.join([py[0] for py in lazy_pinyin(text, style=Style.FIRST_LETTER)])

def build_pinyin_index(vocab: list[dict]) -> dict[str, list[dict]]:
    """构建拼音反向索引"""
    index = {}
    for item in vocab:
        py_key = text_to_pinyin(item['label'])
        if py_key not in index:
            index[py_key] = []
        index[py_key].append(item)
        # 同时索引别名
        for alias in item.get('aliases', []):
            alias_py = text_to_pinyin(alias)
            if alias_py not in index:
                index[alias_py] = []
            index[alias_py].append(item)
    return index
```

#### 5.2.3 F-2.3 校园垃圾分类标准页面

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-2.3.1 | 四类垃圾图文说明 | P0 | 每类含：名称、颜色标识、图标、定义、常见示例 |
| F-2.3.2 | 校园特有物品对照表 | P0 | 针对校园高频物品（外卖盒、奶茶杯、快递袋等） |
| F-2.3.3 | 投放注意事项 | P0 | 每类的特殊投放要求（如厨余需沥干） |
| F-2.3.4 | 可折叠/展开的卡片布局 | P1 | 默认折叠概览，点击展开详情 |

**数据结构设计（guide_standard.json）：**

```json
{
  "version": "1.0",
  "campus_name": "通用校园标准",
  "categories": [
    {
      "id": 0,
      "name": "厨余垃圾",
      "bin_color": "棕色",
      "color_code": "#8B4513",
      "icon": "🗑️",
      "definition": "易腐烂的食物残渣和有机废弃物",
      "disposal_tips": [
        "沥干水分后投放",
        "去除包装物（塑料袋、保鲜膜等）",
        "大骨头属于其他垃圾"
      ],
      "common_items": ["剩饭剩菜", "果皮果核", "茶叶渣", "蛋壳", "菜叶"],
      "campus_special_items": [
        {"name": "食堂剩饭", "tip": "倒入专用收集桶"},
        {"name": "水果皮核", "tip": "投入棕色垃圾桶"}
      ],
      "wrong_items": ["大骨头", "贝壳", "椰子壳"]
    },
    {
      "id": 1,
      "name": "可回收物",
      "bin_color": "蓝色",
      "color_code": "#007bff",
      "icon": "♻️",
      "definition": "可循环利用的废弃物",
      "disposal_tips": [
        "清空内容物（饮料瓶倒空液体）",
        "简单清洗（避免污染其他可回收物）",
        "压扁减少体积（塑料瓶、纸盒等）"
      ],
      "common_items": ["塑料瓶", "纸张", "玻璃瓶", "金属罐", "旧衣物"],
      "campus_special_items": [
        {"name": "快递纸箱", "tip": "拆开压扁后投放"},
        {"name": "教材课本", "tip": "整洁无污损的可回收"},
        {"name": "饮料瓶", "tip": "倒空洗净、压扁投放"}
      ],
      "wrong_items": ["受污染纸张", "一次性餐具", "复写纸"]
    },
    {
      "id": 2,
      "name": "其他垃圾",
      "bin_color": "灰色/黑色",
      "color_code": "#333333",
      "icon": "🗑️",
      "definition": "除以上三类之外的其他生活垃圾",
      "disposal_tips": [
        "尽量沥干水分",
        "难以判断的物品先归为此类"
      ],
      "common_items": ["卫生纸", "烟蒂", "陶瓷碎片", "一次性餐具"],
      "campus_special_items": [
        {"name": "外卖餐盒（脏）", "tip": "已污染的归为其他垃圾"},
        {"name": "奶茶杯（带珍珠）", "tip": "珍珠倒入厨余，杯子归其他"},
        {"name": "便利贴/胶带", "tip": "无法回收的小件"}
      ],
      "wrong_items": []
    },
    {
      "id": 3,
      "name": "有害垃圾",
      "bin_color": "红色",
      "color_code": "#dc3545",
      "icon": "☠️",
      "definition": "对人体健康或自然环境造成直接或潜在危害的废弃物",
      "disposal_tips": [
        "轻放、勿挤压",
        "电池需单独包装",
        "破损药品需密封"
      ],
      "common_items": ["废电池", "过期药品", "灯管", "油漆桶", "温度计"],
      "campus_special_items": [
        {"name": "废电池（5号/7号）", "tip": "投入红色有害垃圾桶"},
        {"name": "过期药品", "tip": "送至医务室或有害回收点"},
        {"name": "荧光灯管", "tip": "小心破碎，整根投放"}
      ],
      "wrong_items": []
    }
  ]
}
```

#### 5.2.4 F-2.4 易错垃圾专题

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-2.4.1 | 易错物品对比卡片 | P0 | 左右对比两张卡片，标明正确分类及原因 |
| F-2.4.2 | ≥ 30 组常见易混淆对 | P0 | 覆盖校园高频易错场景 |
| F-2.4.3 | 搜索时易错提示 | P1 | 搜到易错物品时额外展示对比信息 |

**易错对数据结构（confusing_pairs.json）：**

```json
{
  "pairs": [
    {
      "id": "cp001",
      "item_a": {
        "name": "奶茶杯（干净）",
        "category": "可回收物",
        "reason": "塑料材质、清洗干净后可回收利用"
      },
      "item_b": {
        "name": "奶茶杯（残留奶茶/珍珠）",
        "category": "其他垃圾",
        "reason": "被食物残渣污染，无法回收"
      },
      "key_difference": "是否清洗干净",
      "frequency": "high",
      "scene": "食堂/奶茶店"
    },
    {
      "id": "cp002",
      "item_a": {
        "name": "牛奶盒（利乐包）",
        "category": "可回收物",
        "reason": "冲洗干净、剪开后可回收"
      },
      "item_b": {
        "name": "牛奶盒（未清洗）",
        "category": "其他垃圾",
        "reason": "残留牛奶导致无法回收处理"
      },
      "key_difference": "是否冲洗干净",
      "frequency": "high",
      "scene": "宿舍/食堂"
    },
    {
      "id": "cp003",
      "item_a": {
        "name": "大骨头",
        "category": "其他垃圾",
        "reason": "质地坚硬，不易降解，可能损坏处理设备"
      },
      "item_b": {
        "name": "小骨头/鱼骨",
        "category": "厨余垃圾",
        "reason": "容易粉碎降解，可作为有机肥料"
      },
      "key_difference": "骨头的硬度/大小",
      "frequency": "medium",
      "scene": "食堂"
    },
    {
      "id": "cp004",
      "item_a": {
        "name": "用过的卫生纸",
        "category": "其他垃圾",
        "reason": "遇水溶解、已被污染、无法再生"
      },
      "item_b": {
        "name": "废报纸/书本",
        "category": "可回收物",
        "reason": "纸张纤维完整、未被严重污染"
      },
      "key_difference": "是否遇水溶解/是否可再利用",
      "frequency": "high",
      "scene": "宿舍/卫生间"
    },
    {
      "id": "cp005",
      "item_a": {
        "name": "普通干电池（碱性）",
        "category": "其他垃圾",
        "reason": "已实现无汞化，可按其他垃圾处理"
      },
      "item_b": {
        "name": "充电电池/纽扣电池",
        "category": "有害垃圾",
        "reason": "含有重金属（汞、镉、铅等），需专门回收"
      },
      "key_difference": "电池类型（一次性vs充电）",
      "frequency": "critical",
      "scene": "宿舍/教室"
    }
  ]
}
```

#### 5.2.5 F-2.5 投放指引详情

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-2.5.1 | 单物品详情页 | P0 | 展示名称、分类、处理步骤、注意事项 |
| F-2.5.2 | 处理步骤图文引导 | P1 | 如牛奶盒：倒空→冲洗→剪开→压扁→投放 |
| F-2.5.3 | 相关物品推荐 | P1 | 展示同类物品（如同属可回收物的其他物品） |

### 5.3 新增 API 设计

```
POST /api/voice/text          # 语音识别（备选：MediaRecorder 音频上传）
  请求体: { audio_base64: string, format: "mp3|wav|ogg|webm" }
  响应:   { text: string, items: [...] }  # ASR结果 + 搜索结果

GET  /api/guide/standard       # 获取完整分类标准
  响应:   { categories: [...] }

GET  /api/guide/category/:id   # 获取单类详情
  参数:   id = 0|1|2|3
  响应:   { category: {...}, items: [...] }

GET  /api/guide/confusing      # 易错物品列表
  参数:   ?limit=10&frequency=high
  响应:   { pairs: [...], total: N }

GET  /api/guide/confusing/:pair_id  # 易错对详情
  响应:   { pair: {...} }

GET  /api/guide/item/:keyword  # 物品详情
  响应:   { item: {...}, related_items: [...], confusing_with: [...] }

GET  /api/search/enhanced      # 增强搜索（含拼音+联想）
  参数:   ?q=关键词&include_pinyin=true
  响应:   { results: [...], suggestions: [...] }
```

### 5.4 阶段二交付物

| 交付物 | 格式 | 说明 |
|-------|------|------|
| 语音识别模块 | JS (Web Speech API) + Python(备选ASR) | 录音UI组件 + 实时转写 + 降级方案 |
| 增强搜索引擎 | Python | 拼音索引 + 同义词扩展 |
| guide_standard.json | JSON | 校园垃圾分类标准数据 |
| confusing_pairs.json | JSON | 30+ 组易错物品对比数据 |
| 分类指南页面 | HTML/CSS/JS | 四类标准展示 + 易错专题 + 物品详情 |

### 5.5 阶段二验收标准

| 编号 | 验收项 | 通过标准 |
|-----|-------|---------|
| AC-2.1 | 语音识别可用性 | Chrome/Edge/Safari 下点击麦克风 → 说出关键词 → 正确转写 |
| AC-2.2 | 语音→搜索闭环 | 说"这个是塑料瓶吗" → 自动填充搜索框 → 返回可回收物信息 |
| AC-2.3 | 拼音搜索 | 输入"slp" → 匹配"塑料瓶" |
| AC-2.4 | 分类标准完整性 | 4类垃圾各有完整的定义+示例+注意事项 |
| AC-2.5 | 易错对覆盖 | ≥30 组易混淆物品对比卡片 |
| AC-2.6 | 单物品详情 | 任意词库物品均可查看详细投放指引 |
| AC-2.7 | 不兼容浏览器降级 | Firefox 等不支持的浏览器显示友好提示 |

---

## 6. 阶段三：地图导航 + 社区互动基础（MVP-γ）

### 6.1 阶段目标

接入地理位置能力，建立用户系统和社区互动的基础框架。本阶段是**从工具型产品向平台型产品转型的关键节点**。

### 6.2 功能需求清单

#### 6.2.1 F-3.1 投放点地图指引

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-3.1.1 | 地图 JS SDK 集成 | P0 | 使用腾讯地图 JS SDK / 高德 JS SDK / Leaflet开源方案 |
| F-3.1.2 | 校园投放点标注 | P0 | 在地图上展示垃圾桶/回收位置 Marker |
| F-3.1.3 | 投放点详情弹窗 | P0 | 点击 Marker 显示：名称、类型、距离、开放时间 |
| F-3.1.4 | 导航跳转 | P0 | 点击"去这里"调起地图App导航（URL Scheme） |
| F-3.1.5 | 最近投放点推荐 | P1 | 根据用户当前位置排序，显示最近3个 |
| F-3.1.6 | 投放点筛选 | P2 | 按类型筛选（厨余/可回收/有害/其他） |

**地图技术选型（Web端）：**

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **Leaflet + OpenStreetMap** | 完全免费开源、轻量(~40KB)、自定义灵活 | 国内地图数据不如商业方案精确 | 开源优先、预算有限 |
| **腾讯地图 JS SDK** | 国内定位精准、校园场景友好 | 需申请 Key；有配额限制 | 国内部署首选 |
| **高德地图 JS SDK** | 国内路线规划能力强 | 同上 | 需要导航功能时首选 |

**推荐**：阶段三先用 Leaflet + OSM 快速验证，生产环境再切换到腾讯/高德 SDK。

**前端地图组件示例（Leaflet）：**

```javascript
// ========== static/js/pages/map.js ==========
/**
 * 地图页面逻辑
 * 使用 Leaflet 展示校园投放点
 */
function initMap(containerId) {
    // 初始化地图（默认中心：可配置为学校坐标）
    const map = L.map(containerId).setView([39.9042, 116.4074], 15); // 默认北京，需替换

    // 加载 OpenStreetMap 瓦片图层
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors',
        maxZoom: 19
    }).addTo(map);

    // 加载投放点数据并渲染 Marker
    fetch('/api/map/points')
        .then(r => r.json())
        .then(data => {
            data.points.forEach(point => {
                const marker = L.marker([point.latitude, point.longitude])
                    .addTo(map);

                // 弹出信息窗口
                marker.bindPopup(`
                    <strong>${point.name}</strong><br>
                    类型：${point.type}<br>
                    ${point.open_hours ? `开放：${point.open_hours}` : ''}
                    <br><a href="${getNavUrl(point)}" target="_blank">🧭 导航去这里</a>
                `);
            });
        });

    // 尝试获取用户当前位置
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
            pos => map.setView([pos.coords.latitude, pos.coords.longitude], 16),
            err => console.warn('定位失败:', err.message)
        );
    }

    return map;
}

/** 生成导航链接（调用外部地图App） */
function getNavUrl(point) {
    // 优先尝试高德/腾讯/Apple Maps
    const lat = point.latitude;
    const lng = point.longitude;
    const name = encodeURIComponent(point.name);

    // iOS → Apple Maps, Android → 高德/腾讯
    if (/iPhone|iPad|iPod/.test(navigator.userAgent)) {
        return `https://maps.apple.com/?daddr=${lat},${lng}`;
    }
    return `https://uri.amap.com/navigation?to=${lng},${lat},${name}&mode=car`;
}
```

**投放点数据结构：**

```python
# disposal_points 表结构
class DisposalPoint(Base):
    __tablename__ = "disposal_points"

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)          # 名称，如"教学楼A座一楼垃圾桶"
    point_type = Column(String(20), nullable=False)     # 类型: kitchen/recyclable/hazardous/other/mixed
    latitude = Column(Float, nullable=False)             # 纬度
    longitude = Column(Float, nullable=False)            # 经度
    campus_area = Column(String(50))                    # 所属区域: 教学楼/宿舍区/食堂/操场
    building = Column(String(100))                      # 关联建筑
    floor = Column(String(20))                          # 楼层
    status = Column(String(20), default="active")        # active/maintenance/removed
    capacity = Column(String(20))                       # 容量描述: 大/中/小
    open_hours = Column(String(100))                    # 开放时间
    description = Column(Text)                          # 补充说明
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, onupdate=datetime.utcnow)
```

#### 6.2.2 F-3.2 用户系统基础

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-3.2.1 | 注册/登录页面 | P0 | 用户名+密码注册登录（MVP阶段） |
| F-3.2.2 | 用户画像（角色） | P0 | 学生/教职工/访客 三种角色 |
| F-3.2.3 | 用户基本信息 | P0 | 昵称、头像（上传或默认）、注册时间 |
| F-3.2.4 | Session/Cookie 认证 | P0 | 登录后颁发 Session Token，后续请求携带 |
| F-3.2.5 | 自动登录（记住我） | P1 | Cookie 有效期7天，勾选"记住我"后免重复登录 |
| F-3.2.6 | OAuth第三方登录（预留） | P2 | 微信扫码/GitHub/Google 登录接口预留 |

**用户数据结构：**

```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)  # 用户名
    password_hash = Column(String(255), nullable=False)         # 密码哈希
    nickname = Column(String(50))                              # 昵称
    avatar_url = Column(String(255), default='/static/images/default-avatar.png')  # 头像
    role = Column(String(20), default="student")               # student/staff/visitor/admin
    points = Column(Integer, default=0)                        # 环保积分
    level = Column(Integer, default=1)                         # 环保等级
    total_predictions = Column(Integer, default=0)             # 累计识别次数
    total_checkins = Column(Integer, default=0)                # 累计打卡次数
    is_active = Column(Boolean, default=True)
    last_login_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
```

**登录流程（Web端）：**

```
浏览器                        后端 (FastAPI)              数据库
   │                              │                       │
   │ 填写用户名+密码               │                       │
   │ 点击登录                     │                       │
   │─────────────────────────────>│                       │
   │ POST /api/auth/login         │                       │
   │ { username, password }       │                       │
   │                              │                       │
   │                              │ 验证用户名密码          │
   │                              │ 查询 User 表 ──────────>│
   │                              │<────────────────────────│
   │                              │                       │
   │                              │ 生成 Session Token     │
   │                              │ 更新 last_login_at     │
   │                              │                       │
   │ { token, user_info }         │                       │
   │<─────────────────────────────│                       │
   │                              │                       │
   │ 存储 token 到 Cookie/localStorage                     │
   │                              │                       │
   │ 后续请求携带 Authorization Header                     │
```

#### 6.2.3 F-3.3 环保打卡分享

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-3.3.1 | 打卡入口 | P0 | 首页/地图页均有打卡入口 |
| F-3.3.2 | 拍照 + 定位校验 | P0 | 必须拍照且 GPS 距离投放点 ≤ 50米 |
| F-3.3.3 | 积分奖励 | P0 | 每次打卡 +5 积分 |
| F-3.3.4 | 打卡海报生成 | P1 | Canvas 生成打卡海报（含头像、日期、连续天数） |
| F-3.3.5 | 分享功能 | P1 | 复制链接 / Web Share API / 生成二维码 |

**打卡数据结构：**

```python
class CheckIn(Base):
    __tablename__ = "check_ins"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    point_id = Column(Integer, ForeignKey("disposal_points.id"))
    photo_url = Column(String(255))                    # 打卡照片（Base64或OSS路径）
    latitude = Column(Float)                            # 打卡时的纬度
    longitude = Column(Float)                           # 打卡时的经度
    points_earned = Column(Integer, default=5)          # 本次获得积分
    consecutive_days = Column(Integer, default=1)       # 连续打卡天数
    created_at = Column(DateTime, default=datetime.utcnow)
```

#### 6.2.4 F-3.4 知识问答互动

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-3.4.1 | 每日一题 | P0 | 从词库随机抽取题目，每天刷新 |
| F-3.4.2 | 四选一答题界面 | P0 | 显示问题 + 4个选项（A/B/C/D） |
| F-3.4.3 | 即时正误反馈 | P0 | 选完后立即显示正确答案 + 解析 |
| F-3.4.4 | 答题积分 | P0 | 答对 +3 积分，答错不扣分 |
| F-3.4.5 | 答题记录 | P1 | 记录答题历史，用于统计分析 |

**题目生成策略：**

```python
class QuizService:
    """每日答题服务"""

    def generate_daily_question(self, user_id: int) -> dict:
        """
        从词库生成每日题目
        策略：随机选一个物品作为正确答案，
        从其他3个不同类别各选一个作为干扰项
        """
        correct_item = self._random_item()
        wrong_items = self._pick_distractors(correct_item, count=3)
        options = self._shuffle([correct_item] + wrong_items)

        return {
            "question": f"「{correct_item['label']}」属于什么垃圾？",
            "options": [
                {"label": opt["label"], "category": opt["category_name"]}
                for opt in options
            ],
            "correct_index": options.index(correct_item),
            "explanation": correct_item.get("guidance", ""),
            "item_id": correct_item.get("id"),
        }
```

#### 6.2.5 F-3.5 环保活动发布

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-3.5.1 | 活动列表 | P2 | 展示进行中/即将开始/已结束的活动 |
| F-3.5.2 | 活动详情 | P2 | 时间、地点、人数上限、报名状态 |
| F-3.5.3 | 活动报名/取消 | P2 | 用户可报名参加活动 |
| F-3.5.4 | 活动签到核销 | P2 | 管理员扫码核销用户签到 |

### 6.3 新增 API 设计

```
# ===== 认证相关 =====
POST /api/auth/register          # 用户注册
  请求:   { username, password, nickname }
  响应:   { token, user: { id, nickname, role, points } }

POST /api/auth/login             # 用户登录
  请求:   { username, password }
  响应:   { token, user: {...} }

POST /api/auth/logout            # 登出（使Token失效）
GET  /api/auth/profile            # 获取当前用户信息
  Header: Authorization: Bearer xxx
  响应:   user 对象

# ===== 地图相关 =====
GET  /api/map/points              # 获取附近投放点
  参数:   ?lat=&lng=&type=kitchen&radius=1000
  响应:   { points: [{ id, name, type, lat, lng, distance_m }] }

GET  /api/map/points/:id         # 投放点详情
  响应:   { point: { ..., open_hours, description } }

# ===== 社区相关 =====
POST /api/community/checkin      # 提交打卡
  Header: Authorization
  请求:   { point_id, photo_base64, latitude, longitude }
  响应:   { checkin_id, points_earned, consecutive_days }

GET  /api/community/quiz/today   # 今日题目
  Header: Authorization
  响应:   { question, options, quiz_id }

POST /api/community/quiz/submit  # 提交答案
  Header: Authorization
  请求:   { quiz_id, answer_index }
  响应:   { is_correct, correct_answer, explanation, points_earned }

GET  /api/community/events        # 活动列表
  参数:   ?status=upcoming&limit=10
  响应:   { events: [...] }

POST /api/community/events/:id/signup  # 活动报名
  Header: Authorization
  响应:   { signup_id }
```

### 6.4 数据库设计（阶段三引入）

```sql
-- 用户表
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    nickname VARCHAR(50),
    avatar_url VARCHAR(255) DEFAULT '/static/images/default-avatar.png',
    role VARCHAR(20) DEFAULT 'student',
    points INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1,
    total_predictions INTEGER DEFAULT 0,
    total_checkins INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    last_login_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 投放点位表
CREATE TABLE disposal_points (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    point_type VARCHAR(20) NOT NULL,
    latitude FLOAT NOT NULL,
    longitude FLOAT NOT NULL,
    campus_area VARCHAR(50),
    building VARCHAR(100),
    floor VARCHAR(20),
    status VARCHAR(20) DEFAULT 'active',
    capacity VARCHAR(20),
    open_hours VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP
);

-- 打卡记录表
CREATE TABLE check_ins (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    point_id INTEGER REFERENCES disposal_points(id),
    photo_url VARCHAR(255),
    latitude FLOAT,
    longitude FLOAT,
    points_earned INTEGER DEFAULT 5,
    consecutive_days INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 答题记录表
CREATE TABLE quiz_records (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    question_text VARCHAR(200),
    correct_answer VARCHAR(100),
    user_answer VARCHAR(100),
    is_correct BOOLEAN,
    points_earned INTEGER DEFAULT 3,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 活动表
CREATE TABLE activities (
    id SERIAL PRIMARY KEY,
    title VARCHAR(100) NOT NULL,
    description TEXT,
    cover_image VARCHAR(255),
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    location VARCHAR(200),
    max_participants INTEGER,
    current_participants INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'draft',
    creator_id INTEGER REFERENCES users(id),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 活动报名表
CREATE TABLE activity_signups (
    id SERIAL PRIMARY KEY,
    activity_id INTEGER REFERENCES activities(id),
    user_id INTEGER REFERENCES users(id),
    status VARCHAR(20) DEFAULT 'signed_up',
    checked_in_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_points_location ON disposal_points(latitude, longitude);
CREATE INDEX idx_checkins_user ON check_ins(user_id, created_at DESC);
CREATE INDEX idx_quiz_user_date ON quiz_records(user_id, created_at);
```

### 6.5 阶段三交付物

| 交付物 | 格式 | 说明 |
|-------|------|------|
| 用户认证模块 | Python | 注册/登录/Session Token |
| 地图服务模块 | Python + JS | 投放点 CRUD + 距离计算 + Leaflet 前端 |
| 社区服务模块 | Python | 打卡 + 答题 + 活动 |
| SQLite/PostgreSQL 初始化脚本 | SQL | 建表 + 种子数据 |
| 登录/注册/地图/社区页面 | HTML/CSS/JS | 完整交互流程 |

### 6.6 阶段三验收标准

| 编号 | 验收项 | 通过标准 |
|-----|-------|---------|
| AC-3.1 | 用户注册登录 | 注册 → 登录 → 获得 Token → 进入个人中心 |
| AC-3.2 | 地图展示 | 加载地图 → 显示≥5个投放点 Marker |
| AC-3.3 | 导航功能 | 点击Marker → 查看详情 → 点击导航 → 跳转地图App |
| AC-3.4 | 打卡功能 | 拍照 → 定位校验 → 成功打卡 → 积分+5 |
| AC-3.5 | 答题功能 | 出题 → 选择 → 即时反馈 → 答对积分+3 |
| AC-3.6 | Token 有效期 | Token 过期后提示重新登录 |

---

## 7. 阶段四：个人中心 + 数据可视化（MVP-δ）

### 7.1 阶段目标

完善用户侧功能，通过数据驱动用户持续使用。本阶段聚焦**用户体验提升**和**用户粘性建设**。

### 7.2 功能需求清单

#### 7.2.1 F-4.1 个人中心页面

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-4.1.1 | 用户头像/昵称/角色标识 | P0 | 顶部个人信息卡片 |
| F-4.1.2 | 环保等级与进度条 | P0 | Lv.1~Lv.5，显示升级所需积分 |
| F-4.1.3 | 总积分展示 | P0 | 大字号突出显示 |
| F-4.1.4 | 快捷入口网格 | P0 | 我的积分/我的打卡/我的答题/设置 |
| F-4.1.5 | 环保成就徽章墙 | P2 | 展示已解锁的徽章图标 |

**等级体系设计：**

| 等级 | 所需积分 | 称号 | 徽章图标 |
|-----|---------|------|---------|
| Lv.1 | 0 | 环保新人 | 🌱 |
| Lv.2 | 50 | 分类达人 | 🌿 |
| Lv.3 | 200 | 绿色先锋 | 🌳 |
| Lv.4 | 500 | 环保卫士 | 🏆 |
| Lv.5 | 1000 | 校园环保大使 | 👑 |

#### 7.2.2 F-4.2 环保积分体系

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-4.2.1 | 积分规则引擎 | P0 | 可配置的赚取/消费规则 |
| F-4.2.2 | 积分明细流水 | P0 | 每笔变动的来源、数量、时间 |
| F-4.2.3 | 连续签到翻倍 | P0 | 连续打卡第N天获得 5×min(N,7) 积分 |
| F-4.2.4 | 积分商城概念 | P2 | 展示可兑换商品（暂不需真实交易） |

**积分规则配置：**

```python
# 积分规则配置（可热更新）
POINT_RULES = {
    "earn": {
        "prediction": 1,          # 每次识别
        "checkin_base": 5,        # 基础打卡
        "checkin_consecutive_multiplier": {  # 连续打卡翻倍
            1: 1, 2: 1, 3: 2, 4: 2, 5: 3, 6: 3, 7: 7  # 第7天7倍
        },
        "quiz_correct": 3,        # 答题正确
        "share_checkin": 2,       # 分享打卡
        "daily_first_login": 1,   # 每日首次登录
    },
    "spend": {
        # 阶段四暂不开放消费渠道，预留接口
    },
    "levels": [
        {"level": 1, "name": "环保新人", "threshold": 0},
        {"level": 2, "name": "分类达人", "threshold": 50},
        {"level": 3, "name": "绿色先锋", "threshold": 200},
        {"level": 4, "name": "环保卫士", "threshold": 500},
        {"level": 5, "name": "校园大使", "threshold": 1000},
    ]
}
```

**积分流水表：**

```sql
CREATE TABLE point_transactions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    amount INTEGER NOT NULL,           -- 正数为赚取，负数为消费
    type VARCHAR(30) NOT NULL,         -- prediction/checkin/quiz/share/...
    reference_id INTEGER,              -- 关联的业务ID（如check_in.id）
    description VARCHAR(200),
    balance_after INTEGER NOT NULL,     -- 变动后的余额
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_point_tx_user ON point_transactions(user_id, created_at DESC);
```

#### 7.2.3 F-4.3 使用数据统计

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-4.3.1 | 个人数据面板 | P0 | 累计识别、累计打卡、累计答题、总积分 |
| F-4.3.2 | 分类占比饼图 | P0 | 识别过的4类垃圾各自占比 |
| F-4.3.3 | 月度趋势折线图 | P1 | 近30天每日活跃度趋势 |
| F-4.3.4 | 排行榜 | P1 | 校园积分/打卡 Top 10 用户 |
| F-4.3.5 | 月度环保报告 | P2 | 每月生成个人环保数据报告（图片/HTML） |

**图表方案（Web端）：**

| 方案 | 优势 | 劣势 | 适用场景 |
|------|------|------|---------|
| **Chart.js** | 轻量(~60K)、零配置上手快 | 定制能力一般 | 饼图/折线图/柱状图 |
| **ECharts** | 功能强大、中文文档好 | 体积较大(~1MB) | 复杂图表/热力图/地理图 |
| **Canvas 手绘** | 完全可控、无依赖 | 开发成本高 | 特殊效果/动画 |

**推荐**：阶段四用 Chart.js 处理基础图表，后续升级 ECharts。

**统计聚合 API：**

```python
@router.get("/profile/stats")
async def get_user_stats(current_user: User = Depends(get_current_user)):
    """聚合用户统计数据"""
    user_id = current_user.id

    # 基础计数
    total_predictions = await db.scalar(
        select(func.count()).where(PredictionHistory.user_id == user_id)
    )
    total_checkins = await db.scalar(
        select(func.count()).where(CheckIn.user_id == user_id)
    )

    # 分类占比
    category_dist = await db.execute(
        select(
            PredictionHistory.category,
            func.count().label("count")
        ).where(PredictionHistory.user_id == user_id)
        .group_by(PredictionHistory.category)
    )

    # 近30天趋势
    trend_30d = await db.execute(
        select(
            date_trunc('day', CheckIn.created_at).label("date"),
            func.count().label("count")
        ).where(
            CheckIn.user_id == user_id,
            CheckIn.created_at >= datetime.utcnow() - timedelta(days=30)
        ).group_by(date_trunc('day', CheckIn.created_at))
        .order_by(date_trunc('day', CheckIn.created_at))
    )

    return {
        "total_predictions": total_predictions,
        "total_checkins": total_checkins,
        "total_quiz_correct": ...,
        "total_points": current_user.points,
        "level": current_user.level,
        "category_distribution": [dict(r) for r in category_dist],
        "trend_30d": [{"date": str(r.date), "count": r.count} for r in trend_30d],
    }
```

#### 7.2.4 F-4.4 偏好设置

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-4.4.1 | 默认识别模式 | P2 | 快速模式（仅结果）/ 详细模式（含分析过程） |
| F-4.4.2 | 通知开关 | P2 | 打卡提醒/答题提醒/活动通知（后续接Push/WebSocket） |
| F-4.4.3 | 隐私设置 | P2 | 是否在排行榜显示昵称 |

#### 7.2.5 F-4.5 成就系统

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-4.5.1 | 成就定义（≥10个） | P2 | 首次识别、连续打卡、答题全对等 |
| F-4.5.2 | 成就自动判定 | P2 | 触发条件满足时自动解锁 |
| F-4.5.3 | 成就解锁通知 | P2 | 弹窗/红点提示新成就 |

**成就定义：**

```json
{
  "achievements": [
    {
      "id": "first_predict",
      "name": "初识垃圾",
      "description": "完成第一次垃圾识别",
      "icon": "🔍",
      "condition": { "type": "count", "field": "total_predictions", "value": 1 },
      "points_reward": 10
    },
    {
      "id": "predict_10",
      "name": "识别新手",
      "description": "累计识别10次垃圾",
      "icon": "♻️",
      "condition": { "type": "count", "field": "total_predictions", "value": 10 },
      "points_reward": 15
    },
    {
      "id": "checkin_streak_7",
      "name": "周周坚持",
      "description": "连续打卡7天",
      "icon": "🔥",
      "condition": { "type": "streak", "field": "checkin", "value": 7 },
      "points_reward": 30
    },
    {
      "id": "quiz_perfect_5",
      "name": "答题达人",
      "description": "连续答对5道题",
      "icon": "🧠",
      "condition": { "type": "consecutive_correct", "field": "quiz", "value": 5 },
      "points_reward": 20
    },
    {
      "id": "points_100",
      "name": "百分百环保",
      "description": "累计获得100积分",
      "icon": "💯",
      "condition": { "type": "total_points", "value": 100 },
      "points_reward": 25
    },
    {
      "id": "all_categories",
      "name": "全能分类师",
      "description": "识别过所有4类垃圾",
      "icon": "🏅",
      "condition": { "type": "unique_categories", "value": 4 },
      "points_reward": 50
    }
  ]
}
```

### 7.3 阶段四交付物

| 交付物 | 格式 | 说明 |
|-------|------|------|
| 个人中心页面组 | HTML/CSS/JS | Profile 主页 + 积分明细 + 数据统计 |
| 积分服务 | Python | PointService（规则引擎+流水） |
| 统计分析服务 | Python | AnalyticsService（聚合查询） |
| 成就系统 | Python | AchievementService（判定+解锁） |
| Chart.js/ECharts 图表 | JS | 饼图+折线图 |

### 7.4 阶段四验收标准

| 编号 | 验收项 | 通过标准 |
|-----|-------|---------|
| AC-4.1 | 个人中心展示 | 头像/等级/积分/快捷入口完整呈现 |
| AC-4.2 | 积分流水 | 每笔变动有据可查，余额一致 |
| AC-4.3 | 数据图表 | 饼图+折线图在浏览器中正常渲染 |
| AC-4.4 | 等级晋升 | 积分达标后等级自动提升 |
| AC-4.5 | 成就解锁 | 满足条件后弹出成就通知 |

---

## 8. 阶段五：后台管理系统（MVP-ε）

### 8.1 阶段目标

为运营人员提供完整的管理控制台。本阶段可与**阶段三、四并行开发**，因为管理后台的数据依赖于前面阶段的业务积累。

**重要设计决策**：管理后台不作为独立项目，而是作为 Web SPA 的 **`/admin/*` 路由模块**，通过角色权限控制访问。这样：
- 无需额外部署一套前端
- 共享同一套 API 和认证体系
- 管理员可直接在浏览器中管理

### 8.2 技术选型

| 技术 | 版本 | 用途 | 选型理由 |
|------|------|------|---------|
| 原生 HTML/CSS/JS | - | 管理后台页面（阶段五初期） | 与主站保持一致，零学习成本 |
| **或** Vue3 + Element Plus | ^3.x | 管理后台（如决定引入框架） | 企业级组件丰富、表格/表单/弹窗开箱即用 |
| Chart.js / ECharts | ^4.x / ^5.x | 数据图表 | Dashboard 必备 |
| Axios / Fetch | - | HTTP 请求 | API 调用 |

### 8.3 功能需求清单

#### 8.3.1 F-5.1 用户管理

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-5.1.1 | 用户列表（表格+分页+搜索） | P0 | 支持按昵称/角色/注册时间搜索 |
| F-5.1.2 | 用户详情查看 | P0 | 查看完整画像、行为数据 |
| F-5.1.3 | 用户状态管理 | P0 | 禁用/启用账号 |
| F-5.1.4 | 角色分配 | P1 | 设置用户为学生/教职工/管理员 |
| F-5.1.5 | 批量导出 | P2 | 导出用户列表为 CSV/Excel |

#### 8.3.2 F-5.2 数据分析 Dashboard

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-5.2.1 | 总览指标卡片 | P0 | DAU、总用户数、今日识别量、今日打卡数 |
| F-5.2.2 | 趋势折线图 | P0 | 近30天识别量/打卡量/新用户趋势 |
| F-5.2.3 | 垃圾分类分布饼图 | P0 | 全局4类垃圾识别占比 |
| F-5.2.4 | 热门物品排行 | P1 | 识别频次 Top 20 牒品 |
| F-5.2.5 | 用户排行榜 | P1 | 积分/打卡 Top 10 用户 |
| F-5.2.6 | 地图热力图 | P2 | 打卡热点区域分布 |

#### 8.3.3 F-5.3 内容管理

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-5.3.1 | 词库 CRUD | P0 | 查看/编辑/添加/删除物品词条 |
| F-5.3.2 | 分类标准编辑 | P0 | 编辑4类垃圾的标准描述、投放提示 |
| F-5.3.3 | 易错物品管理 | P1 | 管理30+组易错物品对比数据 |
| F-5.3.4 | FAQ 管理 | P1 | 常见问题的增删改查 |

#### 8.3.4 F-5.4 模型迭代更新

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-5.4.1 | 模型版本列表 | P1 | 展示已部署的模型版本、状态 |
| F-5.4.2 | 模型切换（灰度/A-B） | P1 | 在线切换模型版本，支持按比例分流 |
| F-5.4.3 | Badcase 收集 | P1 | 用户标记"识别错误"的样本入库 |
| F-5.4.4 | 模型热加载 | P2 | 上传新模型文件后无需重启即生效 |

#### 8.3.5 F-5.5 投放点信息维护

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-5.5.1 | 投放点列表（地图+表格双视图） | P1 | 地图上展示所有点位 |
| F-5.5.2 | 投放点 CRUD | P1 | 新增/编辑/删除投放点 |
| F-5.5.3 | 状态管理 | P1 | 标记维修中/已移除等状态 |
| F-5.5.4 | 批量导入 | P2 | CSV/Excel 批量导入投放点数据 |

#### 8.3.6 F-5.6 活动管理

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-5.6.1 | 活动 CRUD | P2 | 创建/编辑/发布/下线活动 |
| F-5.6.2 | 报名管理 | P2 | 查看报名名单、审核、导出 |
| F-5.6.3 | 签到核销 | P2 | 管理员扫码核销用户签到 |

### 8.4 Admin 权限安全设计

```python
# 管理员 RBAC 权限模型
ADMIN_ROLES = {
    "super_admin": {
        "permissions": ["*"]  # 全部权限
    },
    "operator": {
        "permissions": [
            "users:read", "users:update_status",
            "content:crud",
            "map:crud",
            "community:review",
            "stats:read"
        ]
    },
    "viewer": {
        "permissions": [
            "users:read",
            "content:read",
            "stats:read",
            "map:read"
        ]
    }
}

# 管理员权限校验装饰器
def admin_required(permission: str = None):
    """管理员权限校验装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # 从 Session/Token 获取当前用户
            current_user = get_current_user()
            if current_user.role != "admin":
                raise HTTPException(403, "需要管理员权限")

            if permission and permission not in current_user.admin_permissions:
                raise HTTPException(403, "权限不足")

            return await func(*args, **kwargs)
        return wrapper
    return decorator
```

### 8.5 阶段五交付物

| 交付物 | 格式 | 说明 |
|-------|------|------|
| 管理后台页面组 | HTML/CSS/JS（或Vue3组件） | Dashboard/用户/内容/模型/地图/设置 |
| Admin API 路由 | Python | 管理员专用 RESTful API（/admin/*） |
| 管理员种子数据 | SQL | 预设管理员账户 |
| 操作审计日志 | Python | 记录所有管理操作 |

### 8.6 阶段五验收标准

| 编号 | 验收项 | 通过标准 |
|-----|-------|---------|
| AC-5.1 | 管理员登录 | 账密登录 → 进入 /admin/dashboard |
| AC-5.2 | Dashboard 加载 | ≤3秒内加载完所有图表和数据 |
| AC-5.3 | 用户管理 | 搜索/分页/状态变更均正常工作 |
| AC-5.4 | 词库编辑 | 修改物品信息后前端即时生效 |
| AC-5.5 | 权限控制 | operator 无法访问 super_admin 专属功能 |

---

## 9. 阶段六：生产化部署 + 运营闭环（MVP-Final）

### 9.1 阶段目标

全链路跑通，具备正式上线运营条件。

### 9.2 功能需求清单

#### 9.2.1 F-6.1 网站上线准备

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-6.1.1 | 域名解析与备案 | P0 | 域名指向服务器 IP |
| F-6.1.2 | HTTPS 配置 | P0 | 全站 HTTPS，SSL 证书有效（Let's Encrypt 免费） |
| F-6.1.3 | SEO 基础优化 | P1 | Meta标签、Sitemap、语义化HTML |
| F-6.1.4 | favicon 和 PWA 基础 | P1 | 网站图标 + manifest.json（可添加到主屏幕） |
| F-6.1.5 | 友情链接/二维码 | P2 | 便于推广传播 |

#### 9.2.2 F-6.2 服务端部署

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-6.2.1 | Docker 容器化 | P0 | 应用打包为 Docker 镜像 |
| F-6.2.2 | Docker Compose 编排 | P0 | 一键启动全部服务（Web + DB + Redis） |
| F-6.2.3 | Nginx 反向代理 | P0 | SSL终止 + 静态资源 + API转发 + Gzip压缩 |
| F-6.2.4 | CI/CD 流水线 | P0 | GitHub Actions 自动测试+构建+部署 |

**Docker Compose 编排：**

```yaml
# docker-compose.yml
version: "3.8"

services:
  # Web 应用服务
  web:
    build:
      context: .
      dockerfile: deploy/Dockerfile
    ports:
      - "8001:8001"
    environment:
      - DATABASE_URL=postgresql://user:pass@db:5432/ecosort
      - REDIS_URL=redis://redis:6379/0
      - MODEL_PATH=/app/ai_models/garbage_yolov8m_best.pt
    volumes:
      - ./ai_models:/app/ai_models:ro
      - ./uploads:/app/uploads
    depends_on:
      - db
      - redis
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/api/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  # PostgreSQL 数据库
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: user
      POSTGRES_PASSWORD: pass
      POSTGRES_DB: ecosort
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./deploy/init.sql:/docker-entrypoint-initdb.d/init.sql
    ports:
      - "5432:5432"
    restart: unless-stopped

  # Redis 缓存
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:-ecosort2024}
    volumes:
      - redisdata:/data
    ports:
      - "6379:6379"
    restart: unless-stopped

  # Nginx 反向代理
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./deploy/ssl:/etc/nginx/ssl:ro
      - ./uploads:/usr/share/nginx/uploads:ro
    depends_on:
      - web
    restart: unless-stopped

volumes:
  pgdata:
  redisdata:
```

**Dockerfile：**

```dockerfile
# deploy/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN adduser --disabled-password --gecos '' appuser && \
    chown -R appuser:appuser /app
USER appuser

EXPOSE 8001

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
```

#### 9.2.3 F-6.3 数据库迁移

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-6.3.1 | SQLite → PostgreSQL 迁移 | P0 | 数据无损迁移 |
| F-6.3.2 | Alembic 迁移工具 | P0 | 支持 versioned migration |
| F-6.3.3 | 数据备份脚本 | P0 | 定时自动备份（每日全量+增量） |

#### 9.2.4 F-6.4 监控告警

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-6.4.1 | Prometheus 指标采集 | P1 | 自定义业务指标暴露 |
| F-6.4.2 | Grafana 监控大盘 | P1 | CPU/内存/延迟/QPS 等指标面板 |
| F-6.4.3 | 错误追踪 | P1 | 异常自动上报和聚合（Sentry 或自建日志） |
| F-6.4.4 | 日志集中（结构化JSON） | P1 | 文件输出 + ELK 或轻量替代方案 |

#### 9.2.5 F-6.5 性能优化

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-6.5.1 | 静态资源 CDN/缓存 | P1 | Nginx 缓存静态资源，设置合理 Cache-Control |
| F-6.5.2 | 推理缓存（Redis） | P1 | 热门图片推理结果缓存 |
| F-6.5.3 | API 限流增强 | P1 | 多维度限流（IP/User/全局） |
| F-6.5.4 | 前端资源优化 | P1 | JS/CSS 压缩、图片懒加载、代码分割 |
| F-6.5.5 | 数据库索引优化 | P1 | 慢查询分析与索引补齐 |

#### 9.2.6 F-6.6 运营工具

| 需求项 | 描述 | 优先级 | 验收标准 |
|-------|------|--------|---------|
| F-6.6.1 | 分享功能增强 | P2 | 生成分享卡片图片 / Web Share API |
| F-6.6.2 | 数据导出（CSV/Excel） | P2 | 管理后台支持各类数据导出 |
| F-6.6.3 | 运营周报自动生成 | P2 | 每周一自动发送上周数据摘要邮件 |

### 9.3 CI/CD 流水线

```yaml
# .github/workflows/deploy.yml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test-and-build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt -r requirements-dev.txt

      - name: Run linter
        run: ruff check .

      - name: Run tests
        run: pytest tests/ -v --cov=backend

      - name: Build Docker image
        run: docker build -t ecosort:${{ github.sha }} -f deploy/Dockerfile .

      - name: Push to registry
        run: |
          echo ${{ secrets.DOCKER_PASSWORD }} | docker login -u ${{ secrets.DOCKER_USERNAME }} --password-stdin
          docker tag ecosort:${{ github.sha }} ${{ secrets.DOCKER_REGISTRY }}/ecosort:latest
          docker push ${{ secrets.DOCKER_REGISTRY }}/ecosort:latest

  deploy:
    needs: test-and-build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1
        with:
          host: ${{ secrets.SERVER_HOST }}
          username: ${{ secrets.SERVER_USER }}
          key: ${{ secrets.SSH_PRIVATE_KEY }}
          script: |
            cd /opt/ecosort
            docker compose pull
            docker compose up -d
            docker image prune -f
```

### 9.4 阶段六交付物

| 交付物 | 格式 | 说明 |
|-------|------|------|
| Docker 镜像 | Docker Image | 生产级容器镜像 |
| docker-compose.yml | YAML | 一键启动全部服务 |
| Nginx 配置 | conf | SSL + 反向代理 + Gzip + 缓存 |
| CI/CD Pipeline | GitHub Actions | 自动测试+构建+部署 |
| 监控大盘 | Grafana JSON | 运维监控面板 |
| 部署运维手册 | Markdown | 详细操作指南 |
| 线上可访问网站 | URL | 公网可访问 |

### 9.5 阶段六验收标准

| 编号 | 验收项 | 通过标准 |
|-----|-------|---------|
| AC-6.1 | 网站公网可访问 | 域名/DNS 解析正常，HTTPS 绿锁 |
| AC-6.2 | 一键部署 | `docker compose up -d` 后全部服务正常运行 |
| AC-6.3 | 自动化发布 | push main → 自动测试→构建→部署 |
| AC-6.4 | 监控告警 | 服务异常时5分钟内收到告警通知 |
| AC-6.5 | 数据备份 | 每日自动备份，恢复验证通过 |
| AC-6.6 | 性能达标 | P99 延迟 ≤ 1.5s（含网络），并发 ≥ 50 QPS |

---

## 10. 跨阶段公共基础设施

以下基础设施需要在**阶段三之前**搭建完成，后续各阶段共用：

### 10.1 配置管理（config.py）

```python
"""应用配置管理 - 支持环境变量覆盖"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """全局配置项"""

    # ===== 应用基础 =====
    app_name: str = "EcoSort Campus"
    app_version: str = "1.0.0"
    debug: bool = False
    secret_key: str = "change-me-in-production"

    # ===== 服务器 =====
    host: str = "0.0.0.0"
    port: int = 8001
    workers: int = 2

    # ===== 数据库 =====
    database_url: str = "sqlite:///./ecosort.db"  # 开发默认SQLite
    # 生产: postgresql://user:pass@host:5432/ecosort

    # ===== Redis =====
    redis_url: str = "redis://localhost:6379/0"

    # ===== AI 模型 =====
    model_path: str = "models/garbage_yolov8m_best.pt"
    use_pt_model: bool = True
    inference_timeout: float = 10.0  # 推理超时秒数

    # ===== 地图 =====
    map_provider: str = "leaflet"  # leaflet/tencent/amap
    tencent_map_key: str = ""     # 腾讯地图Key（如使用）
    amap_web_key: str = ""        # 高德地图Key（如使用）

    # ===== 限流 =====
    rate_limit_per_minute: int = 30

    # ===== 文件上传 =====
    upload_max_size_mb: int = 10
    upload_dir: str = "./uploads"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """单例获取配置（带缓存）"""
    return Settings()
```

### 10.2 统一响应格式

```python
"""统一 API 响应格式"""

from fastapi.responses import JSONResponse
from typing import Any, Optional
from datetime import datetime


class ApiResponse(JSONResponse):
    """标准化 API 响应"""

    def __init__(
        self,
        data: Any = None,
        message: str = "success",
        code: int = 0,
        status_code: int = 200,
        **kwargs
    ):
        body = {
            "code": code,
            "message": message,
            "data": data,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            **kwargs
        }
        super().__init__(status_code=status_code, content=body)


class PaginatedResponse(ApiResponse):
    """分页响应"""

    def __init__(self, items: list, total: int, page: int, page_size: int, **kwargs):
        data = {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size,
            }
        }
        super().__init__(data=data, **kwargs)


class ErrorResponse(JSONResponse):
    """错误响应"""

    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: Optional[dict] = None
    ):
        body = {
            "code": error_code,
            "message": message,
            "details": details,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        super().__init__(status_code=status_code, content=body)


# 错误码规范
ERROR_CODES = {
    # 通用错误 1xxx
    "E1001": ("参数错误", 400),
    "E1002": ("未授权", 401),
    "E1003": ("权限不足", 403),
    "E1004": ("资源不存在", 404),
    "E1005": ("请求过于频繁", 429),
    "E1006": ("服务器内部错误", 500),

    # 业务错误 2xxx
    "E2001": ("用户不存在", 404),
    "E2002": ("模型未加载", 503),
    "E2003": ("推理失败", 500),
    "E2004": ("词库未加载", 503),

    # 认证错误 3xxx
    "E3001": ("登录失败", 401),
    "E3002": ("Token 已过期", 401),
    "E3003": ("Token 无效", 401),
}
```

### 10.3 全局异常处理

```python
"""全局异常处理器"""

from fastapi import Request
from fastapi.exceptions import RequestValidationError


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """参数校验异常"""
    errors = []
    for err in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in err["loc"][1:]),
            "message": err["msg"],
            "type": err["type"],
        })
    return ErrorResponse("E1001", "参数校验失败", details={"errors": errors})


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """未捕获异常兜底"""
    logger.error(f"未处理异常: {exc}", exc_info=True)
    return ErrorResponse("E1006", f"服务器内部错误: {str(exc)}", status_code=500)
```

### 10.4 日志规范

```python
"""结构化 JSON 日志配置"""

import logging


class SimpleJsonFormatter(logging.Formatter):
    """轻量 JSON 日志格式化器（无需额外依赖）"""

    def format(self, record):
        log_entry = {
            "time": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "module": record.module,
            "message": record.getMessage(),
        }
        # 可选：附加 request_id
        request_id = getattr(record, "request_id", None)
        if request_id:
            log_entry["request_id"] = request_id

        import json
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging():
    """配置全局日志"""
    formatter = SimpleJsonFormatter()

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)

    # 降低第三方库日志级别
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
```

---

## 11. 验收标准与质量门禁

### 11.1 各阶段质量门禁

| 门禁项 | 阶段一 | 阶段二 | 阶段三 | 阶段四 | 阶段五 | 阶段六 |
|-------|--------|--------|--------|--------|--------|--------|
| **单元测试覆盖率** | ≥60% | ≥65% | ≥70% | ≥75% | ≥70% | ≥80% |
| **Lint 通过** | ✅ ruff | ✅ | ✅ | ✅ | ✅ | ✅ |
| **API 文档完整** | OpenAPI | 更新 | 更新 | 更新 | 完整 | 完整 |
| **浏览器兼容** | Chrome/Edge | 完善 | Firefox兼容 | 全面 | 全面 | 全面 |
| **移动端适配** | 基础响应式 | 完善 | Touch友好 | 完美 | - | 上线 |
| **安全扫描** | - | - | 基础鉴权(SQL注入/XSS防护) | 完善 | RBAC | 渗透测试 |
| **性能基准** | P99<3s | P99<3s | P99<2s | P99<2s | P99<2s | P99<1.5s |
| **数据备份** | - | - | SQLite | 定期 | 自动 | 双机热备 |

### 11.2 核心技术指标（最终目标）

| 指标 | 目标值 | 测量方法 |
|------|-------|---------|
| 图像识别 P99 延迟 | ≤ 1500ms | 服务端计时（不含网络） |
| 识别准确率（40类模型） | ≥ 90% | 测试集评估 |
| API 可用性 | ≥ 99.5% | Prometheus uptime |
| 首屏加载（FCP） | ≤ 2s | Lighthouse / Performance API |
| 并发支持 | ≥ 50 QPS | 压测工具（wrk/locust） |
| 数据丢失率 | 0 | 备份恢复验证 |

---

## 12. 风险识别与应对策略

### 12.1 技术风险

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|---------|
| YOLOv8 模型在边缘案例表现差 | 中 | 高 | 特征分析演示模式兜底；持续收集 Badcase 迭代模型 |
| Web Speech API 浏览器兼容性差 | 低 | 中 | 提供 MediaRecorder + 后端ASR 降级方案 |
| 地图 SDK 配额/费用超预期 | 低 | 中 | 优先使用 Leaflet + OSM（免费开源）；商业SDK留作备选 |
| PostgreSQL 迁移数据丢失 | 低 | 高 | 完整迁移脚本 + 回滚方案 + 迁移前后校验 |
| 大流量下性能瓶颈 | 中 | 中 | Redis 缓存 + Nginx 负载均衡 + 水平扩容 |

### 12.2 产品风险

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|---------|
| 用户活跃度低 | 中 | 高 | 积分激励体系；社交裂变（打卡分享）；校园推广合作 |
| 识别结果不准确引发投诉 | 中 | 中 | 明确标注演示模式；提供纠错反馈通道；快速迭代 |
| 内容维护成本高 | 中 | 低 | 管理后台自助；UGC 部分内容（如打卡照片） |
| 竞品出现 | 低 | 中 | 聚焦校园垂直场景深度；建立数据和社区壁垒 |

### 12.3 资源风险

| 风险 | 概率 | 影响 | 应对策略 |
|------|------|------|---------|
| 开发人力不足 | 中 | 高 | 严格按优先级排期；MVP 先做减法；核心功能优先 |
| 服务器成本超预算 | 低 | 中 | 初期云服务器最低配置；按需扩容；学生优惠申请 |
| 第三方 API 变更 | 低 | 中 | 封装抽象层降低耦合；关注官方 changelog |

---

## 附录 A：依赖清单（汇总）

### A.1 Python 后端依赖

```
# requirements.txt（生产）
fastapi>=0.110.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
sqlalchemy>=2.0.0
alembic>=1.13.0
asyncpg>=0.29.0              # PostgreSQL 异步驱动（生产）
aiosqlite>=0.19.0            # SQLite 异步驱动（开发）
redis>=5.0.0
httpx>=0.26.0                # 异步HTTP客户端
python-multipart>=0.0.6       # 文件上传
passlib[bcrypt]>=1.7.4        # 密码哈希
python-jose[cryptography]>=3.3.0  # JWT（可选，Session也可）
Pillow>=10.0.0                # 图片处理
numpy>=1.26.0
opencv-python-headless>=4.9.0
onnxruntime>=1.17.0           # ONNX 推理
ultralytics>=8.1.0            # YOLOv8 PyTorch
fuzzywuzzy>=0.18.0
python-Levenshtein>=0.22.0    # fuzzywuzzy 加速
imagehash>=4.3.1              # 感知哈希
pypinyin>=0.51.0              # 拼音转换
slowapi>=0.1.9                # 速率限制

# requirements-dev.txt（开发）
pytest>=8.0.0
pytest-asyncio>=0.23.0
pytest-cov>=4.1.0
httpx>=0.26.0                 # TestClient
ruff>=0.3.0                   # Linter
```

### A.2 前端依赖（Vanilla JS 方案 — 零构建依赖）

```
# 阶段一~三：纯原生，无 npm 依赖
# 所有功能通过浏览器原生 API 实现：
#   - Fetch API (HTTP请求)
#   - FileReader/FileReaderSync (文件读取)
#   - Canvas API (图片压缩)
#   - Web Speech API (语音识别)
#   - Geolocation API (定位)
#   - LocalStorage (本地存储)
#   - Clipboard API (复制分享)

# 外部 CDN（可选引入）：
#   - Chart.js ^4.4  (图表，~60KB)
#   - Leaflet ^1.9  (地图，~40KB)
#   - highlight.js (代码高亮，管理后台用)
```

### A.3 前端依赖（Vue3 方案 — 如阶段五引入框架）

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "element-plus": "^2.5.0",
    "@element-plus/icons-vue": "^2.3.0",
    "echarts": "^5.5.0",
    "axios": "^1.6.0",
    "dayjs": "^1.11.0"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.1.0",
    "sass": "^1.71.0"
  }
}
```

---

## 附录 B：术语表

| 术语 | 英文 | 解释 |
|------|------|------|
| MVP | Minimum Viable Product | 最小可行产品 |
| SPA | Single Page Application | 单页应用（通过JS切换视图，不刷新页面） |
| ASR | Automatic Speech Recognition | 自动语音识别（Web端用 Web Speech API） |
| OCR | Optical Character Recognition | 光学字符识别 |
| JWT | JSON Web Token | JSON 网络令牌（认证凭证） |
| RBAC | Role-Based Access Control | 基于角色的访问控制 |
| pHash | Perceptual Hash | 感知哈希（图片指纹） |
| LRU | Least Recently Used | 最近最少使用（缓存淘汰策略） |
| QPS | Queries Per Second | 每秒查询数 |
| DAU | Daily Active Users | 日活跃用户数 |
| P99 | 99th Percentile | 99分位延迟 |
| SDK | Software Development Kit | 软件开发工具包 |
| CI/CD | Continuous Integration/Deployment | 持续集成/持续部署 |
| PWA | Progressive Web Application | 渐进式Web应用（可安装到桌面） |
| HMR | Hot Module Replacement | 热模块替换（开发时保存即生效） |

---

## 附录 C：Web vs 小程序关键技术映射

| 功能域 | 原方案（小程序） | 新方案（Web） | 备注 |
|--------|---------------|--------------|------|
| 前端框架 | Taro / 原生WXML | Vanilla JS / Vue3 | 可渐进迁移 |
| 拍照/相册 | wx.chooseMedia() | `<input type="file" capture>` | HTML5 原生能力 |
| 语音识别 | 微信同声传译插件 | Web Speech API | Chrome/Edge/Safari 支持 |
| 地图 | 微信地图SDK | Leaflet / 腾讯JS SDK | Leaflet 免费开源 |
| 用户登录 | wx.login() → openid | 用户名密码 / OAuth | 更通用 |
| 分享 | wx.shareAppMessage | Web Share API / navigator.clipboard | 复制链接更通用 |
| 存储 | wx.setStorage() | localStorage / IndexedDB | 浏览器标准API |
| 推送 | 微信模板消息 | WebSocket / Server-Sent Events | 需自行实现 |
| 支付 | 微信支付 | 支付宝/微信H5支付 | 需商户资质 |
| 扫码 | wx.scanCode() | 不支持（需原生App） | Web端限制 |

---

> **文档维护说明：** 本文档随项目进展同步更新，每个阶段结束后更新对应章节的状态和验收结论。
>
> **下一步行动：** 建议从**阶段一（MVP-α）**开始实施，首先将 `index.html` 重构为 SPA 模块化结构，同时增强 `main.py` 的 API 能力（批量识别、缓存、限流）。
