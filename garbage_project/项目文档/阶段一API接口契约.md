# 阶段一 API 接口契约 (MVP-α)

> 前后端协作约定文档，双方以此为准，格式不可单方面修改

---

## 通用约定

- 基础路径：`http://localhost:8001`
- Content-Type：`application/json`
- 编码：UTF-8
- 图片格式：Base64 编码字符串，含 `data:image/jpeg;base64,` 前缀

---

## 1. POST /api/predict（已有，不得修改响应字段名）

### 请求

```json
{
  "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image | string | 是 | Base64 图片，含 MIME 前缀 |

### 响应（成功）

```json
{
  "success": true,
  "result": {
    "category": "可回收物",
    "category_id": 1,
    "bin_color": "#007bff",
    "bin_icon": "♻️",
    "label_cn": "塑料瓶",
    "confidence": 0.92,
    "guidance": "请将塑料瓶清空内容物、简单冲洗、压扁后投入蓝色可回收物垃圾桶",
    "is_demo_mode": false,
    "reasoning": "40类模型检测: 饮料瓶/塑料瓶"
  },
  "inference_time_ms": 234,
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| success | boolean | 是否成功 |
| result.category | string | 4类中文名：厨余垃圾/可回收物/其他垃圾/有害垃圾 |
| result.category_id | int | 0=厨余, 1=可回收, 2=其他, 3=有害 |
| result.bin_color | string | 垃圾桶颜色 Hex |
| result.bin_icon | string | 分类图标 emoji |
| result.label_cn | string | 具体物品中文名 |
| result.confidence | float | 置信度 0.0~1.0 |
| result.guidance | string | 投放指引文案 |
| result.is_demo_mode | boolean | 是否为降级演示模式 |
| result.reasoning | string | 分类依据说明 |
| inference_time_ms | int | 推理耗时（毫秒） |
| request_id | string | 本次请求唯一 ID |

### 响应（失败）

```json
{
  "success": false,
  "error": {
    "code": "E002",
    "message": "模型未就绪"
  }
}
```

错误码：`E001` 图片格式无效, `E002` 模型未就绪, `E006` 服务器内部错误

---

## 2. POST /api/batch_predict（新增）

### 请求

```json
{
  "images": [
    "data:image/jpeg;base64,/9j/4AAQ...",
    "data:image/jpeg;base64,/9j/4AAQ..."
  ]
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| images | string[] | 是 | Base64 图片数组，最多 5 张 |

### 响应（成功）

```json
{
  "success": true,
  "results": [
    {
      "index": 0,
      "category": "可回收物",
      "category_id": 1,
      "bin_color": "#007bff",
      "bin_icon": "♻️",
      "label_cn": "塑料瓶",
      "confidence": 0.92,
      "guidance": "请将塑料瓶清空后投入蓝色可回收物垃圾桶",
      "is_demo_mode": false,
      "inference_time_ms": 234
    },
    {
      "index": 1,
      "category": "厨余垃圾",
      "category_id": 0,
      "bin_color": "#8B4513",
      "bin_icon": "🗑️",
      "label_cn": "香蕉皮",
      "confidence": 0.88,
      "guidance": "请将香蕉皮投入棕色厨余垃圾桶",
      "is_demo_mode": false,
      "inference_time_ms": 198
    }
  ],
  "total_time_ms": 512,
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| results[].index | int | 与请求数组对应的序号 |
| results[].category | string | 4类中文名 |
| results[].category_id | int | 0-3 |
| results[].bin_color | string | 颜色 Hex |
| results[].label_cn | string | 物品中文名 |
| results[].confidence | float | 置信度 |
| results[].guidance | string | 投放指引 |
| results[].is_demo_mode | boolean | 是否降级模式 |
| results[].inference_time_ms | int | 单张耗时 |
| total_time_ms | int | 总耗时 |
| request_id | string | 请求唯一 ID |

### 响应（失败）

```json
{
  "success": false,
  "error": {
    "code": "E001",
    "message": "批量识别最多支持5张图片"
  }
}
```

---

## 3. GET /api/history（新增）

### 请求

```
GET /api/history?page=1&page_size=20
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| page | int | 否 | 1 | 页码 |
| page_size | int | 否 | 20 | 每页条数，最大 50 |

### 响应（成功）

```json
{
  "success": true,
  "data": [
    {
      "id": "m2n3o4p5",
      "category": "可回收物",
      "category_id": 1,
      "label_cn": "塑料瓶",
      "bin_color": "#007bff",
      "confidence": 0.92,
      "guidance": "请将塑料瓶清空后投入蓝色可回收物垃圾桶",
      "created_at": "2026-05-21T20:30:00Z"
    }
  ],
  "pagination": {
    "total": 47,
    "page": 1,
    "page_size": 20,
    "total_pages": 3
  },
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| data[].id | string | 记录唯一 ID |
| data[].category | string | 4类中文名 |
| data[].category_id | int | 0-3 |
| data[].label_cn | string | 物品中文名 |
| data[].bin_color | string | 颜色 Hex |
| data[].confidence | float | 置信度 |
| data[].guidance | string | 投放指引 |
| data[].created_at | string | ISO 8601 时间 |
| pagination.total | int | 总记录数 |
| pagination.page | int | 当前页码 |
| pagination.page_size | int | 每页条数 |
| pagination.total_pages | int | 总页数 |

### 响应（空）

```json
{
  "success": true,
  "data": [],
  "pagination": { "total": 0, "page": 1, "page_size": 20, "total_pages": 0 }
}
```

---

## 4. DELETE /api/history/{id}（新增）

### 请求

```
DELETE /api/history/m2n3o4p5
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| id | string (path) | 是 | 记录 ID |

### 响应（成功）

```json
{
  "success": true,
  "message": "已删除"
}
```

### 响应（未找到）

```json
{
  "success": false,
  "error": { "code": "E004", "message": "记录不存在" }
}
```

---

## 5. POST /api/feedback（新增）

### 请求

```json
{
  "image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
  "predicted_category_id": 1,
  "correct_category_id": 0,
  "comment": "这是苹果核，应该是厨余垃圾"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| image_base64 | string | 是 | 原始图片 Base64 |
| predicted_category_id | int | 是 | 模型预测的类别 0-3 |
| correct_category_id | int | 是 | 用户认为的正确类别 0-3 |
| comment | string | 否 | 用户备注 |

### 响应（成功）

```json
{
  "success": true,
  "message": "反馈已提交，感谢您的帮助",
  "feedback_id": "fb_abc123"
}
```

### 响应（失败）

```json
{
  "success": false,
  "error": { "code": "E001", "message": "correct_category_id 必须为 0-3" }
}
```

---

## 6. GET /api/categories（已有，不做修改）

### 请求

```
GET /api/categories
```

### 响应

```json
{
  "success": true,
  "categories": [
    { "id": 0, "name": "厨余垃圾", "color": "#8B4513", "icon": "🗑️", "bin_color": "棕色", "description": "易腐烂的食物残渣和有机废弃物" },
    { "id": 1, "name": "可回收物", "color": "#007bff", "icon": "♻️", "bin_color": "蓝色", "description": "可循环利用的废弃物" },
    { "id": 2, "name": "其他垃圾", "color": "#333333", "icon": "🗑️", "bin_color": "灰色/黑色", "description": "除以上三类之外的其他生活垃圾" },
    { "id": 3, "name": "有害垃圾", "color": "#dc3545", "icon": "☠️", "bin_color": "红色", "description": "对人体健康或自然环境造成直接或潜在危害的废弃物" }
  ]
}
```

---

## 7. GET /api/search（已有，不做修改）

### 请求

```
GET /api/search?query=塑料瓶
```

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| query | string | 是 | 搜索关键词 |

### 响应

```json
{
  "success": true,
  "query": "塑料瓶",
  "results": [
    {
      "yolo_label": "plastic_bottle",
      "label": "塑料瓶",
      "aliases": ["瓶子", "饮料瓶", "矿泉水瓶"],
      "category_id": 1,
      "category": "可回收物",
      "bin_color": "#007bff",
      "bin_icon": "♻️",
      "guidance": "请将塑料瓶清空内容物、简单冲洗、压扁后投入蓝色可回收物垃圾桶",
      "similarity_score": 100
    }
  ]
}
```

---

## 统一错误码

| code | HTTP状态码 | 含义 |
|------|-----------|------|
| E001 | 400 | 参数错误 |
| E002 | 503 | 模型未就绪 |
| E003 | 401 | 未授权（阶段三启用） |
| E004 | 404 | 资源不存在 |
| E005 | 429 | 请求过于频繁 |
| E006 | 500 | 服务器内部错误 |

---

## 变更记录

| 日期 | 变更 | 发起方 |
|------|------|--------|
| 2026-05-21 | 初版，含 predict/search/categories/batch/history/feedback | 后端 |
