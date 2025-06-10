#!/usr/bin/env python3
"""
增量添加向量数据工具
支持添加新文档、更新现有文档、删除文档等操作
"""

import os
import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bigmodel_knowledge_base import BigModelKnowledgeBase
from core.config import Config

class IncrementalDataManager:
    """增量数据管理器"""
    
    def __init__(self, api_key: str = None, collection_name: str = None):
        """初始化管理器"""
        self.config = Config()
        self.api_key = api_key or self.config.bigmodel_api_key
        self.collection_name = collection_name or "engineering_knowledge_bigmodel"
        
        if not self.api_key:
            raise ValueError("请设置BigModel API密钥")
        
        # 初始化知识库
        self.kb = BigModelKnowledgeBase(self.api_key, self.collection_name)
        
        print(f"✅ 增量数据管理器初始化成功")
        print(f"   集合名称: {self.collection_name}")
        print(f"   API密钥: {self.api_key[:10]}...")
    
    def add_file(self, file_path: str, chunk_size: int = 800, chunk_overlap: int = 100) -> Dict[str, Any]:
        """
        添加单个文件到知识库
        
        Args:
            file_path: 文件路径
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            
        Returns:
            添加结果
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 检查文件类型
        supported_types = ['.txt', '.md']
        if file_path.suffix.lower() not in supported_types:
            raise ValueError(f"不支持的文件类型: {file_path.suffix}")
        
        print(f"📖 读取文件: {file_path}")
        
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
        
        print(f"   文件大小: {len(content):,} 字符")
        
        # 分割文档
        chunks = self.kb.split_document(content, chunk_size, chunk_overlap)
        print(f"   分割为 {len(chunks)} 个块")
        
        # 准备元数据
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source_file": file_path.name,
                "file_path": str(file_path),
                "chunk_index": i,
                "chunk_count": len(chunks),
                "add_time": datetime.now().isoformat(),
                "content_length": len(chunk),
                "file_size": len(content)
            }
            metadatas.append(metadata)
        
        # 批量添加
        print(f"🔄 添加到知识库...")
        doc_ids = self.kb.add_documents_batch(chunks, metadatas)
        
        result = {
            "file_path": str(file_path),
            "chunks_added": len(doc_ids),
            "document_ids": doc_ids,
            "success": True
        }
        
        print(f"✅ 成功添加文件: {file_path.name}")
        print(f"   添加了 {len(doc_ids)} 个文档块")
        
        return result
    
    def add_directory(self, dir_path: str, recursive: bool = True, 
                     chunk_size: int = 800, chunk_overlap: int = 100) -> Dict[str, Any]:
        """
        添加目录中的所有文件
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归处理子目录
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            
        Returns:
            添加结果
        """
        dir_path = Path(dir_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"目录不存在或不是目录: {dir_path}")
        
        print(f"📁 处理目录: {dir_path}")
        
        # 查找支持的文件
        supported_types = ['.txt', '.md']
        files = []
        
        if recursive:
            for ext in supported_types:
                files.extend(dir_path.rglob(f"*{ext}"))
        else:
            for ext in supported_types:
                files.extend(dir_path.glob(f"*{ext}"))
        
        print(f"   找到 {len(files)} 个支持的文件")
        
        if not files:
            return {"success": False, "message": "未找到支持的文件"}
        
        results = []
        total_chunks = 0
        successful_files = 0
        
        for file_path in files:
            try:
                print(f"\n处理文件: {file_path.name}")
                result = self.add_file(file_path, chunk_size, chunk_overlap)
                results.append(result)
                total_chunks += result["chunks_added"]
                successful_files += 1
                
            except Exception as e:
                print(f"❌ 处理文件失败: {file_path.name} - {e}")
                results.append({
                    "file_path": str(file_path),
                    "success": False,
                    "error": str(e)
                })
        
        summary = {
            "directory": str(dir_path),
            "total_files": len(files),
            "successful_files": successful_files,
            "total_chunks": total_chunks,
            "results": results,
            "success": successful_files > 0
        }
        
        print(f"\n📊 目录处理完成:")
        print(f"   成功处理: {successful_files}/{len(files)} 个文件")
        print(f"   总文档块: {total_chunks}")
        
        return summary
    
    def add_text(self, text: str, title: str = "手动添加", 
                chunk_size: int = 800, chunk_overlap: int = 100) -> Dict[str, Any]:
        """
        直接添加文本内容
        
        Args:
            text: 文本内容
            title: 文档标题
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            
        Returns:
            添加结果
        """
        if not text.strip():
            raise ValueError("文本内容不能为空")
        
        print(f"📝 添加文本: {title}")
        print(f"   文本长度: {len(text):,} 字符")
        
        # 分割文档
        chunks = self.kb.split_document(text, chunk_size, chunk_overlap)
        print(f"   分割为 {len(chunks)} 个块")
        
        # 准备元数据
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source_file": title,
                "chunk_index": i,
                "chunk_count": len(chunks),
                "document_type": "manual",
                "add_time": datetime.now().isoformat(),
                "content_length": len(chunk)
            }
            metadatas.append(metadata)
        
        # 批量添加
        print(f"🔄 添加到知识库...")
        doc_ids = self.kb.add_documents_batch(chunks, metadatas)
        
        result = {
            "title": title,
            "chunks_added": len(doc_ids),
            "document_ids": doc_ids,
            "success": True
        }
        
        print(f"✅ 成功添加文本")
        print(f"   添加了 {len(doc_ids)} 个文档块")
        
        return result
    
    def update_file(self, file_path: str, chunk_size: int = 800, chunk_overlap: int = 100) -> Dict[str, Any]:
        """
        更新文件（先删除旧版本，再添加新版本）
        
        Args:
            file_path: 文件路径
            chunk_size: 块大小
            chunk_overlap: 重叠大小
            
        Returns:
            更新结果
        """
        file_path = Path(file_path)
        filename = file_path.name
        
        print(f"🔄 更新文件: {filename}")
        
        # 先删除现有文档
        try:
            removed_count = self.kb.remove_documents_by_source(filename)
            print(f"   删除了 {removed_count} 个旧文档块")
        except Exception as e:
            print(f"   删除旧文档时出现警告: {e}")
        
        # 添加新文档
        result = self.add_file(file_path, chunk_size, chunk_overlap)
        result["removed_count"] = removed_count if 'removed_count' in locals() else 0
        result["operation"] = "update"
        
        print(f"✅ 文件更新完成: {filename}")
        
        return result
    
    def remove_file(self, filename: str) -> Dict[str, Any]:
        """
        删除指定文件的所有文档
        
        Args:
            filename: 文件名
            
        Returns:
            删除结果
        """
        print(f"🗑️ 删除文件: {filename}")
        
        try:
            removed_count = self.kb.remove_documents_by_source(filename)
            
            result = {
                "filename": filename,
                "removed_count": removed_count,
                "success": removed_count > 0
            }
            
            if removed_count > 0:
                print(f"✅ 成功删除 {removed_count} 个文档块")
            else:
                print(f"⚠️ 未找到相关文档")
            
            return result
            
        except Exception as e:
            print(f"❌ 删除失败: {e}")
            return {
                "filename": filename,
                "success": False,
                "error": str(e)
            }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        return self.kb.get_knowledge_base_stats()
    
    def search_test(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """测试搜索功能"""
        print(f"🔍 搜索测试: {query}")
        
        results = self.kb.search(query, n_results=top_k, include_distances=True)
        
        print(f"   找到 {len(results['results'])} 个结果")
        
        for i, result in enumerate(results["results"]):
            similarity = result.get('similarity', 0)
            print(f"   结果{i+1}: 相似度={similarity:.3f}")
            print(f"   来源: {result['metadata'].get('source_file', '未知')}")
            print(f"   内容: {result['content'][:100]}...")
        
        return results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="增量添加向量数据工具")
    parser.add_argument("action", choices=[
        "add-file", "add-dir", "add-text", "update-file", 
        "remove-file", "stats", "search"
    ], help="操作类型")
    
    parser.add_argument("--path", help="文件或目录路径")
    parser.add_argument("--text", help="要添加的文本内容")
    parser.add_argument("--title", default="手动添加", help="文本标题")
    parser.add_argument("--filename", help="文件名（用于删除）")
    parser.add_argument("--query", help="搜索查询")
    
    parser.add_argument("--collection", default="engineering_knowledge_bigmodel", help="集合名称")
    parser.add_argument("--chunk-size", type=int, default=800, help="块大小")
    parser.add_argument("--chunk-overlap", type=int, default=100, help="重叠大小")
    parser.add_argument("--recursive", action="store_true", help="递归处理子目录")
    parser.add_argument("--top-k", type=int, default=5, help="搜索返回结果数量")
    
    args = parser.parse_args()
    
    try:
        # 初始化管理器
        manager = IncrementalDataManager(collection_name=args.collection)
        
        # 执行操作
        if args.action == "add-file":
            if not args.path:
                print("❌ 请使用 --path 指定文件路径")
                sys.exit(1)
            result = manager.add_file(args.path, args.chunk_size, args.chunk_overlap)
            
        elif args.action == "add-dir":
            if not args.path:
                print("❌ 请使用 --path 指定目录路径")
                sys.exit(1)
            result = manager.add_directory(args.path, args.recursive, args.chunk_size, args.chunk_overlap)
            
        elif args.action == "add-text":
            if not args.text:
                print("❌ 请使用 --text 指定要添加的文本内容")
                sys.exit(1)
            result = manager.add_text(args.text, args.title, args.chunk_size, args.chunk_overlap)
            
        elif args.action == "update-file":
            if not args.path:
                print("❌ 请使用 --path 指定文件路径")
                sys.exit(1)
            result = manager.update_file(args.path, args.chunk_size, args.chunk_overlap)
            
        elif args.action == "remove-file":
            if not args.filename:
                print("❌ 请使用 --filename 指定要删除的文件名")
                sys.exit(1)
            result = manager.remove_file(args.filename)
            
        elif args.action == "stats":
            result = manager.get_stats()
            print(f"\n📊 知识库统计:")
            print(f"   集合名称: {result['collection_name']}")
            print(f"   文档总数: {result['total_chunks']}")
            print(f"   向量模型: {result['embedding_model']}")
            print(f"   向量维度: {result['embedding_dimension']}")
            
        elif args.action == "search":
            if not args.query:
                print("❌ 请使用 --query 指定搜索查询")
                sys.exit(1)
            result = manager.search_test(args.query, args.top_k)
        
        # 保存结果（除了stats和search）
        if args.action not in ["stats", "search"]:
            result_file = f"incremental_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(result_file, 'w', encoding='utf-8') as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            print(f"\n💾 结果已保存到: {result_file}")
        
        print(f"\n🎉 操作完成!")
        
    except Exception as e:
        print(f"❌ 操作失败: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main() 