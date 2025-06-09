"""
构建国家标准知识库
专门处理国家标准库目录下的标准文档，存储到"standards"集合
"""

import os
import glob
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bigmodel_knowledge_base import BigModelKnowledgeBase
from core.config import Config

def main():
    """主函数：构建国家标准知识库"""
    print("🏗️ 开始构建国家标准知识库...")
    print("=" * 60)
    
    # 配置
    config = Config()
    standards_dir = "./data/国家标准库"
    collection_name = "standards"  # 专门用于国家标准的集合
    
    print(f"📁 标准文档目录: {standards_dir}")
    print(f"📚 目标集合名称: {collection_name}")
    
    # 检查目录是否存在
    if not os.path.exists(standards_dir):
        print(f"❌ 错误: 目录 {standards_dir} 不存在")
        return False
    
    try:
        # 初始化知识库管理器（使用standards集合）
        print(f"\n🔧 初始化知识库管理器...")
        kb = BigModelKnowledgeBase(
            api_key=config.bigmodel_api_key,
            collection_name=collection_name
        )
        
        # 文档处理配置
        print(f"📄 准备文档处理...")
        
        # 获取所有txt文件
        txt_files = glob.glob(os.path.join(standards_dir, "*.txt"))
        print(f"\n📋 找到 {len(txt_files)} 个标准文档")
        
        if not txt_files:
            print("❌ 没有找到任何txt文件")
            return False
        
        # 显示文件列表
        print("\n📄 标准文档列表:")
        for i, file_path in enumerate(txt_files, 1):
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path) / 1024  # KB
            print(f"   {i:2d}. {file_name} ({file_size:.1f}KB)")
        
        # 清空现有集合（如果存在）
        print(f"\n🗑️ 清空现有的 '{collection_name}' 集合...")
        try:
            kb.clear_collection()
        except Exception as e:
            print(f"   注意: {e}")
        
        # 处理每个文档
        total_chunks = 0
        successful_files = 0
        
        for i, file_path in enumerate(txt_files, 1):
            file_name = os.path.basename(file_path)
            print(f"\n📖 处理文件 {i}/{len(txt_files)}: {file_name}")
            
            try:
                # 读取文件内容
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read().strip()
                
                if not content:
                    print(f"   ⚠️ 跳过空文件: {file_name}")
                    continue
                
                print(f"   📝 文档长度: {len(content)} 字符")
                
                # 分割文档
                chunks = kb.split_document(
                    content, 
                    chunk_size=config.DOCUMENT_CONFIG["chunk_size"],
                    chunk_overlap=config.DOCUMENT_CONFIG["chunk_overlap"]
                )
                
                print(f"   ✂️ 分割为 {len(chunks)} 个块")
                
                # 准备元数据
                metadatas = []
                for j, chunk in enumerate(chunks):
                    # 从文件名提取标准信息
                    standard_number = file_name.replace('.txt', '').replace('+', ' ')
                    
                    metadata = {
                        "source_file": file_name,
                        "standard_number": standard_number,
                        "document_type": "national_standard",
                        "chunk_index": j,
                        "chunk_count": len(chunks),
                        "file_size": len(content),
                        "content_preview": chunk[:100] + "..." if len(chunk) > 100 else chunk
                    }
                    metadatas.append(metadata)
                
                # 批量添加到知识库
                print(f"   🔄 添加到知识库...")
                doc_ids = kb.add_documents_batch(chunks, metadatas)
                
                print(f"   ✅ 成功添加 {len(doc_ids)} 个文档块")
                total_chunks += len(chunks)
                successful_files += 1
                
            except Exception as e:
                print(f"   ❌ 处理文件失败: {e}")
                continue
        
        # 显示最终统计
        print(f"\n" + "=" * 60)
        print(f"🎉 国家标准知识库构建完成!")
        print(f"📊 处理统计:")
        print(f"   - 成功处理文件: {successful_files}/{len(txt_files)}")
        print(f"   - 总文档块数: {total_chunks}")
        
        # 获取集合信息
        info = kb.get_collection_info()
        print(f"\n📚 知识库信息:")
        print(f"   - 集合名称: {info['name']}")
        print(f"   - 文档总数: {info['count']}")
        print(f"   - 向量模型: {info['embedding_model']}")
        print(f"   - 向量维度: {info['embedding_dimension']}")
        
        # 测试搜索功能
        print(f"\n🧪 测试搜索功能...")
        test_queries = [
            "混凝土外加剂",
            "水泥",
            "建筑材料",
            "质量标准",
            "技术要求"
        ]
        
        for query in test_queries:
            print(f"\n🔍 搜索: '{query}'")
            try:
                results = kb.search(query, n_results=3)
                
                if results["results"]:
                    for j, result in enumerate(results["results"]):
                        similarity = result.get('similarity', 0)
                        source = result['metadata'].get('standard_number', '未知标准')
                        print(f"   结果{j+1}: {source} (相似度={similarity:.3f})")
                        print(f"   内容: {result['content'][:80]}...")
                else:
                    print("   未找到相关结果")
                    
            except Exception as e:
                print(f"   搜索失败: {e}")
        
        print(f"\n✨ 国家标准知识库已准备就绪！")
        print(f"💡 您现在可以通过集合名称 '{collection_name}' 访问这个知识库")
        
        return True
        
    except Exception as e:
        print(f"❌ 构建知识库失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def get_standards_collection_info():
    """获取标准知识库信息"""
    try:
        config = Config()
        kb = BigModelKnowledgeBase(
            api_key=config.bigmodel_api_key,
            collection_name="standards"
        )
        return kb.get_collection_info()
    except Exception as e:
        print(f"获取信息失败: {e}")
        return None

if __name__ == "__main__":
    print("🏗️ 国家标准知识库构建工具")
    print("=" * 60)
    
    success = main()
    
    if success:
        print(f"\n🎯 下一步建议:")
        print(f"   1. 可以创建'regulations'集合用于法律法规")
        print(f"   2. 可以创建'drawings'集合用于项目图纸")
        print(f"   3. 在主系统中选择使用'standards'集合")
    else:
        print(f"\n❌ 构建失败，请检查错误信息并重试") 