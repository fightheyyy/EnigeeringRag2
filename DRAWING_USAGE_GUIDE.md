# 项目图纸上传功能使用指南

## 功能概述

项目图纸上传功能允许用户上传PDF格式的工程图纸，系统会自动：
1. 将文件上传到MinIO对象存储
2. 使用Gemini AI提取图纸中的文本信息
3. 将提取的文本向量化并存储到专用知识库
4. 记录图纸信息到MySQL数据库
5. 支持在智能问答中检索图纸内容

## 使用步骤

### 方式一：对话窗口上传（推荐）

访问主页面：`http://your-domain/`

**点击上传按钮：**
1. 点击输入框旁的 📋 按钮
2. 选择PDF图纸文件
3. 填写项目信息（可选）
4. 点击"上传处理"按钮
5. 在聊天窗口中查看上传进度和结果

**拖拽上传：**
1. 直接将PDF文件拖拽到聊天窗口
2. 系统自动显示上传面板
3. 填写项目信息（可选）
4. 点击"上传处理"按钮

### 方式二：专用上传页面

访问 `/static/drawing_upload.html` 页面：

```
http://your-domain/static/drawing_upload.html
```

1. 填写图纸信息
   - **项目名称**: 例如"XX大厦工程"
   - **图纸类型**: 建筑/结构/给排水/电气/暖通/装修/其他
   - **设计阶段**: 方案设计/初步设计/施工图设计/竣工图
   - **上传者**: 您的姓名

2. 选择PDF文件
   - 点击上传区域选择PDF文件
   - 支持拖拽上传
   - 文件大小限制：100MB

3. 上传处理
   点击"开始上传和处理"按钮，系统将：
   - 上传文件到MinIO
   - 使用Gemini提取文本
   - 向量化并存储到知识库
   - 返回处理结果

## API接口

### 上传图纸
```http
POST /upload-drawing
Content-Type: multipart/form-data

file: PDF文件
project_name: 项目名称（可选）
drawing_type: 图纸类型（可选）
drawing_phase: 设计阶段（可选）
created_by: 上传者（可选）
```

### 获取图纸列表
```http
GET /drawings?project_name=项目名称&drawing_type=图纸类型&limit=50
```

### 搜索图纸
```http
GET /search-drawings?query=关键词&top_k=5&project_name=项目名称&drawing_type=图纸类型
```

### 获取统计信息
```http
GET /drawings-stats
```

## 响应示例

### 成功上传响应
```json
{
    "message": "图纸上传和处理成功",
    "drawing_id": 123,
    "drawing_name": "建筑平面图",
    "original_filename": "建筑平面图.pdf",
    "minio_url": "http://localhost:9000/drawings/建筑平面图_12345678.pdf",
    "vector_chunks_count": 15,
    "process_status": "completed",
    "vector_status": "completed",
    "file_size_mb": 5.2,
    "knowledge_base": "drawings"
}
```

### 图纸列表响应
```json
{
    "message": "获取图纸列表成功",
    "count": 3,
    "drawings": [
        {
            "id": 123,
            "drawing_name": "建筑平面图",
            "original_filename": "建筑平面图.pdf",
            "file_size": 5452832,
            "minio_url": "http://localhost:9000/drawings/建筑平面图_12345678.pdf",
            "project_name": "XX大厦工程",
            "drawing_type": "建筑",
            "drawing_phase": "施工图设计",
            "process_status": "completed",
            "vector_status": "completed",
            "vector_chunks_count": 15,
            "upload_time": "2024-01-15T10:30:00",
            "created_by": "张工程师"
        }
    ]
}
```

## 数据库表结构

### project_drawings 表
```sql
CREATE TABLE project_drawings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    drawing_name VARCHAR(255) NOT NULL COMMENT '图纸名称',
    original_filename VARCHAR(255) NOT NULL COMMENT '原始文件名',
    file_size BIGINT NOT NULL COMMENT '文件大小(字节)',
    minio_url VARCHAR(512) NOT NULL COMMENT 'MinIO存储URL',
    minio_object_name VARCHAR(255) NOT NULL COMMENT 'MinIO对象名',
    extracted_text_path VARCHAR(512) COMMENT '提取的文本文件路径',
    project_name VARCHAR(255) COMMENT '项目名称',
    drawing_type VARCHAR(100) COMMENT '图纸类型',
    drawing_phase VARCHAR(100) COMMENT '设计阶段',
    upload_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '上传时间',
    process_status ENUM('uploaded', 'processing', 'completed', 'failed') DEFAULT 'uploaded',
    vector_status ENUM('pending', 'processing', 'completed', 'failed') DEFAULT 'pending',
    vector_chunks_count INT DEFAULT 0 COMMENT '向量化文档块数量',
    error_message TEXT COMMENT '错误信息',
    created_by VARCHAR(100) COMMENT '上传者',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);
```

## 向量知识库

### 知识库名称
- `drawings` - 专用于项目图纸的向量知识库

### 元数据结构
每个向量化的文档块包含以下元数据：
```json
{
    "source_file": "图纸名称",
    "original_filename": "原始文件名",
    "project_name": "项目名称",
    "drawing_type": "图纸类型",
    "drawing_phase": "设计阶段",
    "chunk_index": 0,
    "chunk_count": 15,
    "document_type": "project_drawing",
    "upload_time": "2024-01-15T10:30:00",
    "drawing_id": 123,
    "minio_url": "存储URL"
}
```

## 智能问答集成

图纸知识库已集成到主要的智能问答系统中。当用户提问时，系统会同时搜索：
1. 国家标准知识库
2. 法规知识库
3. 项目图纸知识库

## 配置说明

### MinIO配置
```python
MINIO_ENDPOINT = "localhost:9000"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_BUCKET_NAME = "drawings"
MINIO_SECURE = False
```

### Gemini API配置
```python
OPENROUTER_API_KEY = "sk-or-v1-xxx"
BASE_URL = "https://openrouter.ai/api/v1"
MODEL_NAME = "google/gemini-2.5-pro-preview"
```

### 文本提取配置
- 块大小：800字符
- 块重叠：100字符
- 最大文件大小：100MB

## 故障排除

### 1. 上传失败
- 检查文件格式是否为PDF
- 检查文件大小是否超过100MB
- 检查MinIO服务是否正常运行

### 2. 文本提取失败
- 检查OpenRouter API密钥是否有效
- 检查网络连接是否正常
- 查看服务器日志获取详细错误信息

### 3. 向量化失败
- 检查BigModel API配置
- 确认向量数据库连接正常
- 检查文本内容是否有效

### 4. 数据库错误
- 检查MySQL连接配置
- 确认数据库表已正确创建
- 查看MySQL错误日志

## 监控和日志

系统会记录详细的处理日志：
- ✅ 成功操作
- ❌ 错误操作
- ⏳ 处理中状态
- 📋 图纸相关操作
- 🔍 搜索操作

通过日志可以跟踪每个图纸的处理状态和可能的错误信息。 