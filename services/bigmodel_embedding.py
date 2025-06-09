"""
BigModel Embedding Service
使用智谱AI的embedding-2模型进行文本向量化
"""

import requests
import json
import numpy as np
from typing import List, Union
import os
from core.config import Config

class BigModelEmbedding:
    """BigModel embedding-2模型服务"""
    
    def __init__(self, api_key: str = None):
        """
        初始化BigModel embedding服务
        
        Args:
            api_key: BigModel API密钥
        """
        self.api_key = api_key or Config.bigmodel_api_key
        self.base_url = Config.bigmodel_base_url
        self.model = Config.bigmodel_embedding_model
        
        if not self.api_key:
            raise ValueError("请设置BigModel API密钥")
        
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        
        print(f"✅ BigModel Embedding服务初始化成功")
        print(f"   模型: {self.model}")
        print(f"   维度: 1024")
    
    def encode(self, texts: Union[str, List[str]]) -> np.ndarray:
        """
        将文本编码为向量
        
        Args:
            texts: 单个文本或文本列表
            
        Returns:
            向量数组
        """
        if isinstance(texts, str):
            texts = [texts]
        
        embeddings = []
        
        for text in texts:
            embedding = self._get_embedding(text)
            embeddings.append(embedding)
        
        return np.array(embeddings)
    
    def _get_embedding(self, text: str) -> List[float]:
        """
        获取单个文本的向量表示
        
        Args:
            text: 输入文本
            
        Returns:
            向量列表
        """
        url = f"{self.base_url}/embeddings"
        
        data = {
            "model": self.model,
            "input": text
        }
        
        try:
            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if 'data' in result and len(result['data']) > 0:
                return result['data'][0]['embedding']
            else:
                raise ValueError(f"API返回格式错误: {result}")
                
        except requests.exceptions.RequestException as e:
            print(f"❌ BigModel API请求失败: {e}")
            raise
        except Exception as e:
            print(f"❌ 处理响应时出错: {e}")
            raise
    
    def get_embedding_dimension(self) -> int:
        """获取向量维度"""
        return 1024  # embedding-2模型的维度

if __name__ == "__main__":
    # 测试代码
    try:
        # 需要设置API密钥
        api_key = input("请输入BigModel API密钥: ").strip()
        if not api_key:
            print("❌ 未提供API密钥")
            exit(1)
        
        embedding_service = BigModelEmbedding(api_key)
        
        # 测试文本
        test_texts = [
            "外加剂的定义是什么？",
            "减水剂的作用机理",
            "HPWR代表什么意思？"
        ]
        
        print("\n🧪 测试BigModel embedding...")
        embeddings = embedding_service.encode(test_texts)
        
        print(f"✅ 成功获取 {len(embeddings)} 个向量")
        print(f"   向量维度: {embeddings.shape[1]}")
        print(f"   向量示例 (前5个值): {embeddings[0][:5].tolist()}")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}") 