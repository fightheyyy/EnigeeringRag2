import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

class Config:
    # DeepSeek API配置 - 从环境变量读取
    OPENAI_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
    OPENAI_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    MODEL_NAME = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    
    # 向量数据库配置
    CHROMA_PERSIST_DIRECTORY = "./data/chroma_db"
    # 注意：实际使用的是BigModel的embedding-2模型，下面的配置为遗留配置
    EMBEDDING_MODEL = "paraphrase-MiniLM-L6-v2"  # 已弃用，保留作为备选
    
    # BigModel配置 - 从环境变量读取
    bigmodel_api_key = os.getenv("BIGMODEL_API_KEY", "")
    bigmodel_base_url = os.getenv("BIGMODEL_BASE_URL", "https://open.bigmodel.cn/api/paas/v4")
    bigmodel_embedding_model = os.getenv("BIGMODEL_MODEL", "embedding-2")
    
    # MySQL配置 - 从环境变量读取
    MYSQL_HOST = os.getenv("MYSQL_HOST", "")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "")
    
    # MinIO配置 - 从环境变量读取
    MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "")
    MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "")
    MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "")
    MINIO_BUCKET_NAME = os.getenv("MINIO_BUCKET_NAME", "engineering-drawings")
    
    # OpenRouter API配置 - 从环境变量读取
    OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
    
    # 检索配置
    SIMILARITY_THRESHOLD = 0.24  # 进一步降低阈值以包含燃气调压器流速要求(相似度0.2437)
    MAX_RETRIEVAL_RESULTS = 15  # 增加检索结果数量以确保包含目标文档块
    
    # 服务器配置
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    
    # 知识库配置
    KNOWLEDGE_BASE_PATH = "./knowledge_base"
    SUPPORTED_FILE_TYPES = [".txt", ".md", ".pdf", ".docx"]
    
    # 数据库配置
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./engineering_rag.db")
    
    # 系统配置
    MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", "10485760"))  # 10MB
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000,*").split(",")
    
    # 日志配置
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE = os.getenv("LOG_FILE", "./logs/app.log")
    
    # DeepSeek模型特定配置
    MAX_TOKENS = 2000
    TEMPERATURE = 0.1
    TOP_P = 0.9
    
    # 工程监理专用配置
    SYSTEM_PROMPT = """你是一个专业的工程监理智能助手，专门帮助现场监理工程师查询工程建设规范、标准和设计图纸信息。

请遵循以下原则：
1. 基于提供的知识库内容回答问题，确保答案准确可靠
2. 每个答案都必须提供明确的来源引用（规范编号、条款号、图纸编号等）
3. 如果无法找到确切答案，请明确告知，不要猜测
4. 使用专业但易懂的语言回答
5. 支持追问和进一步澄清
6. 重点关注混凝土结构、脚手架、外墙保温等工程监理常见问题

回答格式要求：
- 直接回答问题
- 使用清晰的分节结构，**分节标题必须加粗**（如：**材料要求：**、**安装技术要求：**、**验收要求：**等）
- 提供详细的技术要求和具体数值
- 标明信息来源和依据
- 如有必要，提供相关的注意事项和监理要点
- **不要添加"注："或其他补充说明**，直接回答问题即可

请用中文回答所有问题，确保分节标题使用加粗格式，不要添加额外的注释。
"""

    # ChromaDB配置
    CHROMA_CONFIG = {
        "persist_directory": CHROMA_PERSIST_DIRECTORY,
        "anonymized_telemetry": False,
        "allow_reset": True
    }
    
    # 文档处理配置
    DOCUMENT_CONFIG = {
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "max_chunks_per_document": 50
    }
    
    # 检索配置详细设置
    RETRIEVAL_CONFIG = {
        "similarity_threshold": SIMILARITY_THRESHOLD,
        "max_results": MAX_RETRIEVAL_RESULTS,
        "rerank_top_k": 3,
        "include_metadata": True
    }
    
    # 工程领域配置
    ENGINEERING_DOMAINS = {
        "混凝土": {
            "keywords": ["强度等级", "配合比", "保护层", "钢筋", "浇筑", "养护", "抗压强度"],
            "regulations": ["GB 50010", "GB 50204", "JGJ 55"]
        },
        "钢结构": {
            "keywords": ["焊接", "螺栓连接", "防腐涂装", "变形", "承载力", "稳定性"],
            "regulations": ["GB 50017", "GB 50205", "JGJ 81"]
        },
        "脚手架": {
            "keywords": ["立杆", "横杆", "连墙件", "剪刀撑", "安全网", "荷载"],
            "regulations": ["GB 51210", "JGJ 130", "JGJ 162"]
        },
        "地基基础": {
            "keywords": ["承载力", "沉降", "桩基", "地基处理", "基坑支护"],
            "regulations": ["GB 50007", "GB 50202", "JGJ 94"]
        },
        "防水工程": {
            "keywords": ["防水材料", "防水层", "渗漏", "防水卷材", "防水涂料"],
            "regulations": ["GB 50208", "GB 50207", "JGJ 298"]
        },
        "保温工程": {
            "keywords": ["保温材料", "导热系数", "保温层", "热桥", "节能"],
            "regulations": ["GB 50176", "JGJ 144", "JGJ 26"]
        }
    }
    
    # DeepSeek API配置详细设置
    DEEPSEEK_CONFIG = {
        "api_key": OPENAI_API_KEY,
        "base_url": OPENAI_BASE_URL,
        "model": MODEL_NAME,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "stream": False,
        "timeout": 30,
        "max_retries": 3
    }
    
    @classmethod
    def get_deepseek_config(cls):
        """获取DeepSeek配置"""
        return cls.DEEPSEEK_CONFIG
    
    @classmethod
    def get_mysql_config(cls):
        """获取MySQL配置"""
        return {
            "host": cls.MYSQL_HOST,
            "port": cls.MYSQL_PORT,
            "user": cls.MYSQL_USER,
            "password": cls.MYSQL_PASSWORD,
            "database": cls.MYSQL_DATABASE
        }
    
    @classmethod
    def get_minio_config(cls):
        """获取MinIO配置"""
        return {
            "endpoint": cls.MINIO_ENDPOINT,
            "access_key": cls.MINIO_ACCESS_KEY,
            "secret_key": cls.MINIO_SECRET_KEY,
            "bucket_name": cls.MINIO_BUCKET_NAME
        }
    
    @classmethod
    def get_engineering_domain_config(cls, domain: str):
        """获取工程领域配置"""
        return cls.ENGINEERING_DOMAINS.get(domain, {})
    
    @classmethod
    def validate_config(cls):
        """验证配置有效性"""
        missing_configs = []
        
        if not cls.OPENAI_API_KEY:
            missing_configs.append("DEEPSEEK_API_KEY")
        
        if not cls.bigmodel_api_key:
            missing_configs.append("BIGMODEL_API_KEY")
        
        if not cls.MYSQL_PASSWORD:
            missing_configs.append("MYSQL_PASSWORD")
            
        if missing_configs:
            print(f"⚠️  警告：以下配置项未设置: {', '.join(missing_configs)}")
            print("   请检查.env文件或环境变量设置")
            return False
        
        print("✅ 配置验证通过")
        print(f"   DeepSeek API: {cls.OPENAI_BASE_URL}")
        print(f"   模型: {cls.MODEL_NAME}")
        print(f"   BigModel API: {cls.bigmodel_base_url}")
        print(f"   MySQL: {cls.MYSQL_HOST}:{cls.MYSQL_PORT}")
        
        return True 