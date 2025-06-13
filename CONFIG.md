# 环境配置说明

本项目使用 `.env` 文件管理所有的API密钥和敏感配置信息。

## 🔧 设置步骤

### 1. 复制环境变量模板
```bash
cp .env.example .env
```

### 2. 编辑 .env 文件，填入您的实际配置信息

```env
# DeepSeek API配置
DEEPSEEK_API_KEY=your_actual_deepseek_api_key
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1
DEEPSEEK_MODEL=deepseek-chat

# BigModel API配置  
BIGMODEL_API_KEY=your_actual_bigmodel_api_key
BIGMODEL_BASE_URL=https://open.bigmodel.cn/api/paas/v4
BIGMODEL_MODEL=embedding-2

# MySQL数据库配置
MYSQL_HOST=your_mysql_host
MYSQL_PORT=3306
MYSQL_USER=your_mysql_user
MYSQL_PASSWORD=your_mysql_password
MYSQL_DATABASE=your_database_name

# MinIO配置
MINIO_ENDPOINT=your_minio_endpoint:9000
MINIO_ACCESS_KEY=your_minio_access_key
MINIO_SECRET_KEY=your_minio_secret_key
MINIO_BUCKET_NAME=engineering-drawings

# OpenRouter API配置 (用于Gemini)
OPENROUTER_API_KEY=your_openrouter_api_key
```

### 3. 验证配置
```bash
python -c "from core.config import Config; Config.validate_config()"
```

如果配置正确，您将看到：
```
✅ 配置验证通过
   DeepSeek API: https://api.deepseek.com/v1
   模型: deepseek-chat
   BigModel API: https://open.bigmodel.cn/api/paas/v4
   MySQL: your_mysql_host:3306
```

## 🔑 API密钥获取方式

### DeepSeek API
1. 访问 [DeepSeek官网](https://platform.deepseek.com/)
2. 注册并登录账户
3. 在API密钥页面生成新的密钥

### BigModel API (智谱AI)
1. 访问 [智谱AI开放平台](https://open.bigmodel.cn/)
2. 注册并登录账户
3. 在API密钥管理页面创建新密钥

### OpenRouter API (用于Gemini)
1. 访问 [OpenRouter](https://openrouter.ai/)
2. 注册并登录账户
3. 在API Keys页面生成新密钥

## 🛡️ 安全提示

1. **不要提交 `.env` 文件到版本控制**
   - `.env` 文件已添加到 `.gitignore`
   - 仅提交 `.env.example` 作为模板

2. **定期更换API密钥**
   - 定期轮换密钥以提高安全性
   - 如果密钥泄露，立即更换

3. **使用环境变量**
   - 在生产环境中，推荐直接设置系统环境变量
   - 避免在服务器上存储明文密钥文件

## 🚀 运行项目

配置完成后，可以正常启动项目：
```bash
python main.py
```

## ❓ 常见问题

### Q: 配置验证失败怎么办？
A: 检查以下项目：
- `.env` 文件是否存在
- API密钥是否正确填写
- 网络连接是否正常

### Q: 如何在Docker中使用？
A: 使用Docker时，可以通过环境变量或挂载 `.env` 文件：
```bash
docker run -v $(pwd)/.env:/app/.env your-image
# 或者
docker run -e DEEPSEEK_API_KEY=your_key your-image  
```

### Q: 生产环境部署建议？
A: 
- 使用系统环境变量而不是 `.env` 文件
- 使用密钥管理服务（如AWS Secrets Manager）
- 定期轮换所有API密钥 