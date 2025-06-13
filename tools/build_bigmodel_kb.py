"""
使用BigModel embedding-2模型重新构建知识库
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bigmodel_knowledge_base import BigModelKnowledgeBase
from core.config import Config

def main():
    """主函数"""
    print("🚀 BigModel知识库构建工具")
    print("=" * 50)
    
    # 从配置文件获取API密钥
    config = Config()
    api_key = config.BIGMODEL_API_KEY
    if not api_key:
        print("❌ 配置文件中未找到BigModel API密钥，请在config.py中设置BIGMODEL_API_KEY")
        return
    
    print(f"🔑 使用配置文件中的API密钥: {api_key[:10]}...")
    
    # 检查文档文件
    doc_file = "GB+8076-2008.txt"
    if not os.path.exists(doc_file):
        print(f"❌ 文档文件不存在: {doc_file}")
        return
    
    try:
        # 初始化知识库
        print(f"\n📚 初始化BigModel知识库...")
        kb = BigModelKnowledgeBase(api_key, "engineering_knowledge_bigmodel")
        
        # 清空现有数据（可选）
        current_count = kb.get_collection_info()["count"]
        if current_count > 0:
            choice = input(f"集合中已有 {current_count} 个文档，是否清空？(y/N): ").strip().lower()
            if choice == 'y':
                kb.clear_collection()
                print("🗑️ 已清空现有数据")
        
        # 读取文档
        print(f"\n📖 读取文档: {doc_file}")
        with open(doc_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        print(f"   文档大小: {len(content):,} 字符")
        
        # 分割文档
        print(f"\n✂️ 分割文档...")
        chunks = kb.split_document(content, chunk_size=800, chunk_overlap=100)
        print(f"   分割为 {len(chunks)} 个块")
        
        # 显示前几个块的预览
        print(f"\n📄 文档块预览:")
        for i, chunk in enumerate(chunks[:3]):
            print(f"   块 {i+1}: {chunk[:100]}...")
        
        # 准备元数据
        print(f"\n🏷️ 准备元数据...")
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source_file": doc_file,
                "chunk_index": i,
                "chunk_count": len(chunks),
                "content_preview": chunk[:50] + "..." if len(chunk) > 50 else chunk
            }
            metadatas.append(metadata)
        
        # 批量添加到知识库
        print(f"\n🔄 开始添加文档到知识库...")
        print(f"   这可能需要几分钟时间，请耐心等待...")
        
        doc_ids = kb.add_documents_batch(chunks, metadatas)
        
        print(f"✅ 成功添加 {len(doc_ids)} 个文档块")
        
        # 显示最终统计
        info = kb.get_collection_info()
        print(f"\n📊 知识库统计:")
        print(f"   集合名称: {info['name']}")
        print(f"   文档数量: {info['count']}")
        print(f"   向量模型: {info['embedding_model']}")
        print(f"   向量维度: {info['embedding_dimension']}")
        
        # 测试搜索功能
        print(f"\n🧪 测试搜索功能...")
        test_queries = [
            "外加剂的定义",
            "减水剂",
            "HPWR",
            "高性能减水剂",
            "混凝土外加剂"
        ]
        
        for query in test_queries:
            print(f"\n🔍 搜索: '{query}'")
            results = kb.search(query, n_results=2)
            
            if results["results"]:
                for i, result in enumerate(results["results"]):
                    similarity = result.get('similarity', 0)
                    print(f"   结果{i+1}: 相似度={similarity:.3f}")
                    print(f"   内容: {result['content'][:150]}...")
                    print(f"   来源: 块{result['metadata']['chunk_index']}")
            else:
                print("   未找到相关结果")
        
        print(f"\n🎉 知识库构建完成！")
        print(f"   现在可以使用BigModel embedding模型进行问答了")
        
    except Exception as e:
        print(f"❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 