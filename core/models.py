from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class QuestionRequest(BaseModel):
    """问题请求模型"""
    question: str
    session_id: Optional[str] = None
    context: Optional[str] = None

class DocumentSource(BaseModel):
    """文档来源模型"""
    title: str
    content: str
    source: str
    similarity: float = 0.0
    metadata: Dict[str, Any] = {}
    file_name: Optional[str] = None
    regulation_code: Optional[str] = None
    section: Optional[str] = None
    similarity_score: float = 0.0

class AnswerResponse(BaseModel):
    """回答响应模型"""
    question: str
    answer: str
    sources: List[DocumentSource] = []
    confidence_score: float = 0.0
    timestamp: datetime
    has_definitive_answer: bool = False
    suggestions: List[str] = []
    session_id: Optional[str] = None

class KnowledgeDocument(BaseModel):
    """知识文档模型"""
    id: str
    title: str
    content: str
    file_path: str
    file_type: str
    document_type: str = "regulation"  # regulation, drawing, manual
    regulation_info: Optional[Dict[str, Any]] = None
    upload_time: datetime
    last_updated: datetime

class SystemStatus(BaseModel):
    """系统状态模型"""
    status: str
    knowledge_base_stats: Dict[str, Any]
    llm_service_status: str
    uptime: str 