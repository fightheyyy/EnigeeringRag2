# 向量数据库增量添加使用指南

## 概述

本系统的向量数据库基于 **ChromaDB** 和 **智谱AI的embedding-2模型** 构建，完全支持**增量添加**向量数据。您可以通过多种方式动态添加、更新和管理知识库中的数据。

## 技术架构

- **向量数据库**: ChromaDB (支持持久化存储)
- **向量模型**: 智谱AI embedding-2 (1024维)
- **存储位置**: `./data/chroma_db`
- **支持格式**: .txt, .md, .pdf, .docx

## 支持的操作

### ✅ 完全支持的功能

1. **增量添加文档** - 新文档会自动添加到现有知识库
2. **批量上传文件** - 支持一次性上传多个文件
3. **直接添加文本** - 无需文件，直接添加文本内容
4. **更新文档** - 先删除旧版本，再添加新版本
5. **删除文档** - 根据来源文件删除指定文档
6. **搜索测试** - 实时测试知识库检索效果

## 使用方法

### 1. Web管理界面 (推荐)

访问管理页面：`http://localhost:8000/admin`

#### 功能特性：
- 📊 实时显示知识库统计信息
- 📝 直接添加文本内容
- 📁 批量上传文件（拖拽支持）
- 🗑️ 删除指定来源的文档
- 🔍 搜索功能测试
- 📈 上传进度显示

#### 操作步骤：
1. **添加文本**：在"添加文本"卡片中输入标题和内容
2. **批量上传**：拖拽文件到上传区域或点击选择文件
3. **设置参数**：调整块大小(chunk_size)和重叠大小(chunk_overlap)
4. **删除文档**：输入文件名删除对应的所有文档块

### 2. API接口

#### 添加文本
```bash
curl -X POST "http://localhost:8000/add-text" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "新增规范",
    "content": "这里是文档内容...",
    "chunk_size": 800,
    "chunk_overlap": 100
  }'
```

#### 批量上传文件
```bash
curl -X POST "http://localhost:8000/upload-batch" \
  -F "files=@document1.txt" \
  -F "files=@document2.txt" \
  -F "chunk_size=800" \
  -F "chunk_overlap=100"
```

#### 删除文档
```bash
curl -X DELETE "http://localhost:8000/remove-documents?source_file=document1.txt"
```

#### 搜索测试
```bash
curl "http://localhost:8000/search?query=外加剂&top_k=5"
```

### 3. 命令行工具

使用 `tools/incremental_add.py` 进行批量操作：

#### 添加单个文件
```bash
python tools/incremental_add.py add-file --path "新文档.txt"
```

#### 添加整个目录
```bash
python tools/incremental_add.py add-dir --path "./documents" --recursive
```

#### 添加文本内容
```bash
python tools/incremental_add.py add-text --text "文档内容" --title "标题"
```

#### 更新文件
```bash
python tools/incremental_add.py update-file --path "updated_document.txt"
```

#### 删除文件
```bash
python tools/incremental_add.py remove-file --filename "document.txt"
```

#### 查看统计信息
```bash
python tools/incremental_add.py stats
```

#### 搜索测试
```bash
python tools/incremental_add.py search --query "外加剂" --top-k 5
```

## 参数配置

### 文档分割参数

| 参数 | 默认值 | 说明 | 推荐范围 |
|------|--------|------|----------|
| `chunk_size` | 800 | 每个文档块的字符数 | 500-2000 |
| `chunk_overlap` | 100 | 文档块之间的重叠字符数 | 50-500 |

### 搜索参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `similarity_threshold` | 0.24 | 相似度阈值，低于此值的结果会被过滤 |
| `top_k` | 5 | 返回的搜索结果数量 |

## 最佳实践

### 1. 文档分割策略
- **技术文档**: chunk_size=800, chunk_overlap=100
- **法规标准**: chunk_size=600, chunk_overlap=150  
- **长篇文档**: chunk_size=1000, chunk_overlap=200

### 2. 增量添加策略
- **定期更新**: 使用 `update-file` 替换已有文档
- **新增内容**: 使用 `add-file` 或 `add-text` 追加内容
- **批量导入**: 使用 `add-dir` 处理整个文档目录

### 3. 元数据管理
系统自动为每个文档块添加以下元数据：
- `source_file`: 来源文件名
- `chunk_index`: 块索引
- `chunk_count`: 总块数
- `add_time`: 添加时间
- `content_length`: 内容长度

## 监控和维护

### 查看知识库状态
```bash
# 通过API
curl "http://localhost:8000/status"

# 通过命令行
python tools/incremental_add.py stats
```

### 性能监控
- **文档总数**: 当前知识库中的文档块数量
- **向量维度**: 1024维 (embedding-2模型)
- **存储大小**: ChromaDB数据库文件大小
- **响应时间**: 搜索和添加操作的耗时

### 备份和恢复
```bash
# 备份知识库
cp -r ./data/chroma_db ./backup/chroma_db_$(date +%Y%m%d)

# 恢复知识库  
cp -r ./backup/chroma_db_20241201 ./data/chroma_db
```

## 错误处理

### 常见问题解决

1. **文件编码错误**
   - 工具会自动尝试 UTF-8 和 GBK 编码
   - 建议使用 UTF-8 编码保存文档

2. **API密钥错误**
   - 检查 `core/config.py` 中的 `bigmodel_api_key`
   - 确保密钥有效且有足够的调用次数

3. **文档格式不支持**
   - 目前支持: .txt, .md, .pdf, .docx
   - PDF和DOCX需要额外的解析库

4. **向量维度不匹配**
   - 确保使用相同的embedding模型
   - 不要混用不同的向量模型

## 性能优化建议

### 1. 批量操作
- 优先使用批量API而不是单个文档API
- 大量文档建议分批处理，每批20个文件以内

### 2. 合理的块大小
- 太小：语义信息不完整
- 太大：检索精度下降
- 建议根据文档类型调整

### 3. 索引优化
- ChromaDB会自动创建向量索引
- 大量数据建议定期检查索引状态

## 示例脚本

### 批量更新目录
```bash
#!/bin/bash
# 更新整个标准文档目录
python tools/incremental_add.py add-dir \
  --path "./standards" \
  --recursive \
  --chunk-size 600 \
  --chunk-overlap 150
```

### 定期备份
```bash
#!/bin/bash
# 定期备份知识库
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf "./backup/knowledge_base_$DATE.tar.gz" ./data/chroma_db
echo "✅ 知识库已备份到: knowledge_base_$DATE.tar.gz"
```

## 总结

✅ **向量数据库完全支持增量添加**
- 实时添加新文档而不影响现有数据
- 支持多种添加方式：Web界面、API、命令行
- 自动处理文档分割和向量化
- 提供完整的管理和监控功能

通过合理使用这些功能，您可以轻松维护一个动态更新的智能问答知识库！ 