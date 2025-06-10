"""
BigModel知识库管理器
使用智谱AI的embedding-2模型和ChromaDB构建知识库
"""

import chromadb
from chromadb.config import Settings
import os
import re
from typing import List, Dict, Any, Optional
import numpy as np
from services.bigmodel_embedding import BigModelEmbedding
from services.bigmodel_embedding_function import BigModelEmbeddingFunction
from core.config import Config

class BigModelKnowledgeBase:
    """使用BigModel embedding的知识库管理器"""
    
    def __init__(self, api_key: str = None, collection_name: str = "engineering_knowledge_bigmodel"):
        """
        初始化知识库管理器
        
        Args:
            api_key: BigModel API密钥
            collection_name: 集合名称
        """
        self.api_key = api_key
        self.collection_name = collection_name
        
        # 初始化BigModel embedding服务
        self.embedding_service = BigModelEmbedding(api_key)
        self.embedding_function = BigModelEmbeddingFunction(api_key)
        
        # 初始化ChromaDB客户端
        self.client = chromadb.PersistentClient(
            path=Config.CHROMA_PERSIST_DIRECTORY,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # 创建或获取集合
        self.collection = self._get_or_create_collection()
        
        print(f"✅ BigModel知识库管理器初始化成功")
        print(f"   集合名称: {self.collection_name}")
        print(f"   数据库路径: {Config.CHROMA_PERSIST_DIRECTORY}")
    
    def _get_or_create_collection(self):
        """获取或创建集合"""
        try:
            # 尝试获取现有集合
            collection = self.client.get_collection(name=self.collection_name)
            print(f"📚 使用现有集合: {self.collection_name}")
        except Exception:
            # 创建新集合，使用自定义嵌入函数
            collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_function,
                metadata={"description": "工程监理知识库 - BigModel版"}
            )
            print(f"📚 创建新集合: {self.collection_name}")
        
        return collection
    
    def _embedding_function(self, input: List[str]) -> List[List[float]]:
        """
        ChromaDB使用的嵌入函数
        
        Args:
            input: 文本列表
            
        Returns:
            嵌入向量列表
        """
        embeddings = self.embedding_service.encode(input)
        return embeddings.tolist()
    
    def add_document(self, content: str, metadata: Dict[str, Any] = None) -> str:
        """
        添加单个文档到知识库
        
        Args:
            content: 文档内容
            metadata: 文档元数据
            
        Returns:
            文档ID
        """
        # 生成文档ID
        doc_id = f"doc_{hash(content) % 1000000}"
        
        # 默认元数据
        if metadata is None:
            metadata = {}
        
        metadata.update({
            "content_length": len(content),
            "type": "document"
        })
        
        # 获取向量表示
        embedding = self.embedding_service.encode([content])[0].tolist()
        
        # 添加到集合
        self.collection.add(
            documents=[content],
            embeddings=[embedding],
            metadatas=[metadata],
            ids=[doc_id]
        )
        
        print(f"✅ 添加文档: {doc_id}")
        return doc_id
    
    def add_documents_batch(self, documents: List[str], metadatas: List[Dict[str, Any]] = None) -> List[str]:
        """
        批量添加文档
        
        Args:
            documents: 文档列表
            metadatas: 元数据列表
            
        Returns:
            文档ID列表
        """
        if not documents:
            return []
        
        # 生成文档ID
        doc_ids = [f"doc_{hash(doc) % 1000000}_{i}" for i, doc in enumerate(documents)]
        
        # 处理元数据
        if metadatas is None:
            metadatas = [{} for _ in documents]
        
        # 为每个文档添加基本元数据
        for i, metadata in enumerate(metadatas):
            metadata.update({
                "content_length": len(documents[i]),
                "type": "document",
                "batch_index": i
            })
        
        # 获取向量表示
        print(f"🔄 正在获取 {len(documents)} 个文档的向量表示...")
        embeddings = self.embedding_service.encode(documents)
        
        # 批量添加到集合
        self.collection.add(
            documents=documents,
            embeddings=embeddings.tolist(),
            metadatas=metadatas,
            ids=doc_ids
        )
        
        print(f"✅ 批量添加了 {len(documents)} 个文档")
        return doc_ids
    
    def search(self, query: str, n_results: int = 5, include_distances: bool = True) -> Dict[str, Any]:
        """
        搜索相关文档
        
        Args:
            query: 查询文本
            n_results: 返回结果数量
            include_distances: 是否包含距离信息
            
        Returns:
            搜索结果
        """
        # 获取查询向量
        query_embedding = self.embedding_service.encode([query])[0].tolist()
        
        # 执行搜索
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            include=['documents', 'metadatas', 'distances']
        )
        
        # 格式化结果
        formatted_results = {
            "query": query,
            "results": []
        }
        
        if results['documents'][0]:  # 检查是否有结果
            for i in range(len(results['documents'][0])):
                result_item = {
                    "id": results['ids'][0][i],
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                }
                
                if include_distances and 'distances' in results:
                    # ChromaDB返回的是距离，转换为相似度（1 - 归一化距离）
                    distance = results['distances'][0][i]
                    similarity = max(0, 1 - distance / 2)  # 简单的距离到相似度转换
                    result_item["similarity"] = similarity
                    result_item["distance"] = distance
                
                formatted_results["results"].append(result_item)
        
        print(f"🔍 查询: '{query}' - 找到 {len(formatted_results['results'])} 个结果")
        return formatted_results
    
    def get_collection_info(self) -> Dict[str, Any]:
        """获取集合信息"""
        count = self.collection.count()
        
        return {
            "name": self.collection_name,
            "count": count,
            "embedding_model": self.embedding_service.model,
            "embedding_dimension": self.embedding_service.get_embedding_dimension()
        }
    
    def get_knowledge_base_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        count = self.collection.count()
        
        return {
            "total_chunks": count,
            "collection_name": self.collection_name,
            "embedding_model": self.embedding_service.model,
            "embedding_dimension": self.embedding_service.get_embedding_dimension()
        }
    
    def search_documents(self, query: str, top_k: int = 5, similarity_threshold: float = 0.3):
        """
        搜索文档（兼容接口）
        
        Args:
            query: 查询文本
            top_k: 返回结果数量
            similarity_threshold: 相似度阈值，低于此值的结果将被过滤
            
        Returns:
            文档源列表，如果没有超过阈值的结果则返回空列表
        """
        from core.models import DocumentSource
        
        # 使用现有的search方法，获取更多结果以便过滤
        results = self.search(query, n_results=min(top_k * 2, 20), include_distances=True)
        
        # 转换为DocumentSource格式并应用相似度阈值过滤
        sources = []
        for result in results["results"]:
            similarity_score = result.get("similarity", 0.0)
            
            # 只保留相似度超过阈值的结果
            if similarity_score >= similarity_threshold:
                source = DocumentSource(
                    title=result["metadata"].get("source_file", "未知文档"),
                    content=result["content"],
                    source=result["metadata"].get("source_file", "未知来源"),
                    similarity=similarity_score,
                    metadata=result["metadata"],
                    file_name=result["metadata"].get("source_file", "未知文档"),
                    regulation_code=result["metadata"].get("regulation_code"),
                    section=result["metadata"].get("section"),
                    similarity_score=similarity_score
                )
                sources.append(source)
        
        # 按相似度排序并返回前top_k个结果
        sources.sort(key=lambda x: x.similarity_score, reverse=True)
        filtered_sources = sources[:top_k]
        
        # 记录过滤信息
        total_found = len(results["results"])
        filtered_count = len(filtered_sources)
        print(f"🔍 查询: '{query}' - 总共找到 {total_found} 个结果，过滤后保留 {filtered_count} 个结果（阈值: {similarity_threshold:.2f}）")
        
        return filtered_sources
    
    def clear_collection(self):
        """清空集合"""
        try:
            self.client.delete_collection(name=self.collection_name)
            self.collection = self._get_or_create_collection()
            print(f"🗑️ 已清空集合: {self.collection_name}")
        except Exception as e:
            print(f"❌ 清空集合失败: {e}")
    
    def remove_documents_by_source(self, source_file: str) -> int:
        """
        根据来源文件删除文档
        
        Args:
            source_file: 来源文件名
            
        Returns:
            删除的文档数量
        """
        try:
            # 先查询要删除的文档
            results = self.collection.get(
                where={"source_file": source_file}
            )
            
            if not results['ids']:
                print(f"⚠️ 未找到来源为 '{source_file}' 的文档")
                return 0
            
            # 删除文档
            self.collection.delete(
                where={"source_file": source_file}
            )
            
            removed_count = len(results['ids'])
            print(f"🗑️ 成功删除 {removed_count} 个文档块（来源: {source_file}）")
            return removed_count
            
        except Exception as e:
            print(f"❌ 删除文档失败: {e}")
            raise
    
    def remove_documents_by_ids(self, doc_ids: List[str]) -> int:
        """
        根据文档ID删除文档
        
        Args:
            doc_ids: 文档ID列表
            
        Returns:
            删除的文档数量
        """
        try:
            if not doc_ids:
                return 0
            
            self.collection.delete(ids=doc_ids)
            
            print(f"🗑️ 成功删除 {len(doc_ids)} 个文档块")
            return len(doc_ids)
            
        except Exception as e:
            print(f"❌ 删除文档失败: {e}")
            raise
    
    def update_document(self, content: str, metadata: Dict[str, Any] = None, doc_id: str = None) -> str:
        """
        更新文档（先删除再添加）
        
        Args:
            content: 新的文档内容
            metadata: 新的元数据
            doc_id: 要更新的文档ID，如果为None则根据content生成
            
        Returns:
            更新后的文档ID
        """
        if doc_id is None:
            doc_id = f"doc_{hash(content) % 1000000}"
        
        try:
            # 先删除现有文档
            self.collection.delete(ids=[doc_id])
            print(f"🔄 删除旧文档: {doc_id}")
        except Exception:
            # 如果文档不存在，继续添加新文档
            pass
        
        # 添加新文档
        return self.add_document(content, metadata)
    
    def get_documents_by_source(self, source_file: str) -> List[Dict[str, Any]]:
        """
        获取指定来源的所有文档
        
        Args:
            source_file: 来源文件名
            
        Returns:
            文档列表
        """
        try:
            results = self.collection.get(
                where={"source_file": source_file},
                include=['documents', 'metadatas', 'ids']
            )
            
            documents = []
            if results['ids']:
                for i, doc_id in enumerate(results['ids']):
                    documents.append({
                        "id": doc_id,
                        "content": results['documents'][i],
                        "metadata": results['metadatas'][i]
                    })
            
            print(f"📋 找到 {len(documents)} 个文档（来源: {source_file}）")
            return documents
            
        except Exception as e:
            print(f"❌ 获取文档失败: {e}")
            return []
    
    def split_document(self, content: str, chunk_size: int = 1000, chunk_overlap: int = 200) -> List[str]:
        """
        分割文档为小块
        
        Args:
            content: 文档内容
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            
        Returns:
            文档块列表
        """
        if len(content) <= chunk_size:
            return [content]
        
        chunks = []
        start = 0
        
        while start < len(content):
            # 确定结束位置
            end = start + chunk_size
            
            # 如果不是最后一块，尝试在句号或换行符处分割
            if end < len(content):
                # 寻找最近的句号或换行符
                for i in range(end, start + chunk_size - 100, -1):
                    if content[i] in '。\n':
                        end = i + 1
                        break
            
            chunk = content[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            # 设置下一个开始位置（考虑重叠）
            start = end - chunk_overlap
            if start >= len(content):
                break
        
        return chunks

def build_knowledge_base_from_file(file_path: str, api_key: str) -> BigModelKnowledgeBase:
    """
    从文件构建知识库
    
    Args:
        file_path: 文件路径
        api_key: BigModel API密钥
        
    Returns:
        知识库管理器
    """
    # 初始化知识库
    kb = BigModelKnowledgeBase(api_key)
    
    # 读取文件
    print(f"📖 读取文件: {file_path}")
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 分割文档
    print(f"✂️ 分割文档...")
    chunks = kb.split_document(content)
    print(f"   分割为 {len(chunks)} 个块")
    
    # 准备元数据
    metadatas = []
    for i, chunk in enumerate(chunks):
        metadata = {
            "source_file": os.path.basename(file_path),
            "chunk_index": i,
            "chunk_count": len(chunks)
        }
        metadatas.append(metadata)
    
    # 批量添加到知识库
    kb.add_documents_batch(chunks, metadatas)
    
    return kb

if __name__ == "__main__":
    # 测试代码
    try:
        # 获取API密钥
        api_key = input("请输入BigModel API密钥: ").strip()
        if not api_key:
            print("❌ 未提供API密钥")
            exit(1)
        
        # 测试知识库
        print("\n🧪 测试BigModel知识库...")
        kb = BigModelKnowledgeBase(api_key, "test_collection")
        
        # 添加测试文档
        test_docs = [
            "外加剂是指在混凝土搅拌过程中掺入的用于改善混凝土性能的化学物质。",
            "减水剂的主要作用是减少混凝土拌合用水量，提高工作性能。",
            "HPWR是高性能减水剂的英文缩写，全称为High Performance Water Reducer。"
        ]
        
        kb.add_documents_batch(test_docs)
        
        # 测试搜索
        test_queries = ["什么是外加剂", "减水剂的作用", "HPWR代表什么"]
        
        for query in test_queries:
            print(f"\n🔍 搜索: {query}")
            results = kb.search(query, n_results=2)
            
            for i, result in enumerate(results["results"]):
                print(f"   结果{i+1}: 相似度={result.get('similarity', 0):.3f}")
                print(f"   内容: {result['content'][:100]}...")
        
        # 显示集合信息
        info = kb.get_collection_info()
        print(f"\n📊 集合信息:")
        print(f"   文档数量: {info['count']}")
        print(f"   向量维度: {info['embedding_dimension']}")
        
        print("\n✅ 测试完成")
        
    except Exception as e:
        print(f"❌ 测试失败: {e}") 