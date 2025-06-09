import os

class Config:
    # DeepSeek API配置
    OPENAI_API_KEY = "sk-6617ec8529ec49f8a632b7532d2c8760"
    OPENAI_BASE_URL = "https://api.deepseek.com/v1"
    MODEL_NAME = "deepseek-chat"
    
    # 向量数据库配置
    CHROMA_PERSIST_DIRECTORY = "./data/chroma_db"
    # 注意：实际使用的是BigModel的embedding-2模型，下面的配置为遗留配置
    EMBEDDING_MODEL = "paraphrase-MiniLM-L6-v2"  # 已弃用，保留作为备选
    
    # BigModel配置
    bigmodel_api_key = "cc4a411638ce41deacc6977ccc584d67.f9W593o2F3JVcouv"  # BigModel API密钥
    bigmodel_base_url = "https://open.bigmodel.cn/api/paas/v4"
    bigmodel_embedding_model = "embedding-2"
    
    # 检索配置
    SIMILARITY_THRESHOLD = 0.24  # 进一步降低阈值以包含燃气调压器流速要求(相似度0.2437)
    MAX_RETRIEVAL_RESULTS = 15  # 增加检索结果数量以确保包含目标文档块
    
    # 服务器配置
    DEBUG = False
    HOST = "0.0.0.0"
    PORT = 8000
    
    # 知识库配置
    KNOWLEDGE_BASE_PATH = "./knowledge_base"
    SUPPORTED_FILE_TYPES = [".txt", ".md", ".pdf", ".docx"]
    
    # 数据库配置
    DATABASE_URL = "sqlite:///./engineering_rag.db"
    
    # 系统配置
    MAX_UPLOAD_SIZE = 10485760  # 10MB
    ALLOWED_ORIGINS = ["http://localhost:3000", "http://localhost:8000", "*"]
    
    # 日志配置
    LOG_LEVEL = "INFO"
    LOG_FILE = "./logs/app.log"
    
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

回答格式：
- 直接回答问题
- 提供详细的技术要求
- 标明信息来源和依据
- 如有必要，提供相关的注意事项

请用中文回答所有问题。
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
    def get_engineering_domain_config(cls, domain: str):
        """获取工程领域配置"""
        return cls.ENGINEERING_DOMAINS.get(domain, {})
    
    @classmethod
    def validate_config(cls):
        """验证配置有效性"""
        if not cls.OPENAI_API_KEY:
            raise ValueError("DeepSeek API密钥未配置")
        
        if not cls.OPENAI_BASE_URL:
            raise ValueError("DeepSeek API地址未配置")
        
        if not cls.MODEL_NAME:
            raise ValueError("模型名称未配置")
        
        print("✅ 配置验证通过")
        print(f"   DeepSeek API: {cls.OPENAI_BASE_URL}")
        print(f"   模型: {cls.MODEL_NAME}")
        print(f"   向量模型: {cls.EMBEDDING_MODEL}")
        
        return True 