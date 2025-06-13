"""
符合ChromaDB接口的BigModel Embedding函数
"""

from typing import List
from chromadb.api.types import EmbeddingFunction, Embeddings
from services.bigmodel_embedding import BigModelEmbedding

class BigModelEmbeddingFunction(EmbeddingFunction):
    """符合ChromaDB接口的BigModel embedding函数"""
    
    def __init__(self, api_key: str):
        """初始化embedding函数"""
        self.embedding_service = BigModelEmbedding(api_key)
    
    def __call__(self, input: List[str]) -> Embeddings:
        """
        实现ChromaDB要求的embedding函数接口
        
        Args:
            input: 文本列表
            
        Returns:
            向量列表
        """
        embeddings = self.embedding_service.encode(input)
        return embeddings.tolist() 