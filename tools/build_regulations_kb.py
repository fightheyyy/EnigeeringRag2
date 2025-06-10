#!/usr/bin/env python3
"""
构建法律法规知识库
专门用于处理法律法规文档，建立法规库集合
"""

import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.bigmodel_knowledge_base import BigModelKnowledgeBase
from core.config import Config

class RegulationsKnowledgeBuilder:
    """法规知识库构建器"""
    
    def __init__(self, api_key: str = None):
        """初始化构建器"""
        self.config = Config()
        self.api_key = api_key or self.config.bigmodel_api_key
        self.collection_name = "regulations"  # 法规库集合名
        
        if not self.api_key:
            raise ValueError("请设置BigModel API密钥")
        
        # 初始化知识库
        self.kb = BigModelKnowledgeBase(self.api_key, self.collection_name)
        
        print(f"🏛️ 法规知识库构建器初始化成功")
        print(f"   集合名称: {self.collection_name}")
        print(f"   API密钥: {self.api_key[:10]}...")
        
        # 法规文档的特殊处理参数
        self.regulation_chunk_size = 600  # 法规条文通常较短，使用较小的块
        self.regulation_chunk_overlap = 150  # 更多重叠确保条文连贯性
    
    def add_regulation_file(self, file_path: str, regulation_info: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        添加法规文件到知识库
        
        Args:
            file_path: 文件路径
            regulation_info: 法规信息（法规名称、发布机构、生效日期等）
            
        Returns:
            添加结果
        """
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")
        
        # 默认法规信息
        if regulation_info is None:
            regulation_info = {}
        
        print(f"📖 读取法规文件: {file_path}")
        
        # 读取文件内容
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except UnicodeDecodeError:
            # 尝试其他编码
            with open(file_path, 'r', encoding='gbk') as f:
                content = f.read()
        
        print(f"   文件大小: {len(content):,} 字符")
        
        # 智能识别法规结构
        regulation_type = self._identify_regulation_type(content, file_path.name)
        print(f"   法规类型: {regulation_type}")
        
        # 使用适合的分割策略
        chunks = self._smart_split_regulation(content, regulation_type)
        print(f"   智能分割为 {len(chunks)} 个条文块")
        
        # 准备元数据
        metadatas = []
        for i, chunk in enumerate(chunks):
            # 尝试提取条文编号
            article_number = self._extract_article_number(chunk)
            
            metadata = {
                "source_file": file_path.name,
                "file_path": str(file_path),
                "chunk_index": i,
                "chunk_count": len(chunks),
                "regulation_type": regulation_type,
                "add_time": datetime.now().isoformat(),
                "content_length": len(chunk),
                "document_type": "regulation",
                "article_number": article_number,
                "regulation_name": regulation_info.get("name", self._extract_regulation_name(content)),
                "issuing_authority": regulation_info.get("authority", ""),
                "effective_date": regulation_info.get("effective_date", ""),
                "regulation_number": regulation_info.get("number", ""),
                "category": regulation_info.get("category", "法律法规")
            }
            metadatas.append(metadata)
        
        # 批量添加
        print(f"🔄 添加到法规知识库...")
        doc_ids = self.kb.add_documents_batch(chunks, metadatas)
        
        result = {
            "file_path": str(file_path),
            "regulation_type": regulation_type,
            "chunks_added": len(doc_ids),
            "document_ids": doc_ids,
            "regulation_info": regulation_info,
            "success": True
        }
        
        print(f"✅ 成功添加法规: {file_path.name}")
        print(f"   添加了 {len(doc_ids)} 个条文块")
        
        return result
    
    def _identify_regulation_type(self, content: str, filename: str) -> str:
        """智能识别法规类型"""
        content_lower = content.lower()
        filename_lower = filename.lower()
        
        # 法律
        if any(keyword in content_lower for keyword in ["中华人民共和国", "法", "全国人大", "人大常委会"]):
            if any(keyword in filename_lower for keyword in ["法", "law"]):
                return "法律"
        
        # 行政法规
        if any(keyword in content_lower for keyword in ["国务院", "条例", "规定", "办法"]):
            if any(keyword in filename_lower for keyword in ["条例", "规定", "办法"]):
                return "行政法规"
        
        # 部门规章
        if any(keyword in content_lower for keyword in ["部", "委", "局", "署"]):
            return "部门规章"
        
        # 地方法规
        if any(keyword in content_lower for keyword in ["省", "市", "县", "区"]):
            return "地方法规"
        
        # 技术规范
        if any(keyword in content_lower for keyword in ["技术规范", "标准", "gb", "jgj", "cjj"]):
            return "技术规范"
        
        return "其他法规"
    
    def _smart_split_regulation(self, content: str, regulation_type: str) -> List[str]:
        """智能分割法规内容"""
        # 根据法规类型调整分割策略
        if regulation_type in ["法律", "行政法规"]:
            return self._split_by_articles(content)
        elif regulation_type == "技术规范":
            return self._split_by_sections(content)
        else:
            # 默认分割
            return self.kb.split_document(content, self.regulation_chunk_size, self.regulation_chunk_overlap)
    
    def _split_by_articles(self, content: str) -> List[str]:
        """按条文分割法规"""
        import re
        
        # 查找条文标记
        article_pattern = r'第[一二三四五六七八九十百千万\d]+条[：\s]'
        articles = re.split(article_pattern, content)
        
        if len(articles) > 1:
            # 重新组合，保留条文标号
            matches = re.findall(article_pattern, content)
            chunks = []
            
            for i, article_content in enumerate(articles[1:]):  # 跳过第一个空元素
                if i < len(matches):
                    chunk = matches[i] + article_content.strip()
                    if len(chunk) > 50:  # 过滤太短的内容
                        chunks.append(chunk)
            
            print(f"   按条文分割: {len(chunks)} 条")
            return chunks
        
        # 如果没有找到条文标记，使用默认分割
        return self.kb.split_document(content, self.regulation_chunk_size, self.regulation_chunk_overlap)
    
    def _split_by_sections(self, content: str) -> List[str]:
        """按章节分割技术规范"""
        import re
        
        # 查找章节标记
        section_patterns = [
            r'\d+\.\d+\s+[^\r\n]+',  # 如: 3.1 总则
            r'第[一二三四五六七八九十]+章[：\s]',  # 如: 第三章
            r'\d+\s+[^\r\n]+(?=\n)',  # 如: 3 基本规定
        ]
        
        for pattern in section_patterns:
            sections = re.split(pattern, content)
            if len(sections) > 2:  # 至少要有3个部分才算有效分割
                matches = re.findall(pattern, content)
                chunks = []
                
                for i, section_content in enumerate(sections[1:]):
                    if i < len(matches):
                        chunk = matches[i] + section_content.strip()
                        if len(chunk) > 100:  # 过滤太短的内容
                            chunks.append(chunk)
                
                if chunks:
                    print(f"   按章节分割: {len(chunks)} 节")
                    return chunks
        
        # 如果没有找到章节标记，使用默认分割
        return self.kb.split_document(content, self.regulation_chunk_size, self.regulation_chunk_overlap)
    
    def _extract_article_number(self, content: str) -> str:
        """提取条文编号"""
        import re
        
        # 查找条文编号
        patterns = [
            r'第([一二三四五六七八九十百千万\d]+)条',
            r'(\d+\.\d+(?:\.\d+)?)',  # 如: 3.1.1
            r'第([一二三四五六七八九十]+)章',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, content[:100])  # 只在前100字符中查找
            if match:
                return match.group(1)
        
        return ""
    
    def _extract_regulation_name(self, content: str) -> str:
        """从内容中提取法规名称"""
        import re
        
        # 常见的法规名称模式
        patterns = [
            r'《([^》]+)》',  # 《法规名称》格式
            r'([^（\n\r]+)(?:（[^）]*）)?(?:法|条例|规定|办法|标准)',  # 以法、条例等结尾
        ]
        
        first_lines = content[:500]  # 在前500字符中查找
        
        for pattern in patterns:
            matches = re.findall(pattern, first_lines)
            if matches:
                name = matches[0].strip()
                if len(name) < 100 and len(name) > 3:  # 合理的名称长度
                    return name
        
        return "未知法规"
    
    def build_from_directory(self, dir_path: str, recursive: bool = True) -> Dict[str, Any]:
        """
        从目录构建法规库
        
        Args:
            dir_path: 目录路径
            recursive: 是否递归处理子目录
            
        Returns:
            构建结果
        """
        dir_path = Path(dir_path)
        
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"目录不存在或不是目录: {dir_path}")
        
        print(f"📁 构建法规库，处理目录: {dir_path}")
        
        # 查找法规文件
        supported_types = ['.txt', '.md']
        files = []
        
        if recursive:
            for ext in supported_types:
                files.extend(dir_path.rglob(f"*{ext}"))
        else:
            for ext in supported_types:
                files.extend(dir_path.glob(f"*{ext}"))
        
        # 按文件名排序，优先处理法律文件
        def sort_key(file_path):
            name = file_path.name.lower()
            if '法' in name:
                return 0  # 法律优先
            elif '条例' in name or '规定' in name:
                return 1  # 行政法规次之
            elif '办法' in name:
                return 2  # 部门规章
            else:
                return 3  # 其他
        
        files.sort(key=sort_key)
        print(f"   找到 {len(files)} 个法规文件")
        
        if not files:
            return {"success": False, "message": "未找到法规文件"}
        
        results = []
        total_chunks = 0
        successful_files = 0
        
        for file_path in files:
            try:
                print(f"\n处理法规文件: {file_path.name}")
                
                # 根据文件名推断法规信息
                regulation_info = self._infer_regulation_info(file_path.name)
                
                result = self.add_regulation_file(file_path, regulation_info)
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
            "collection_name": self.collection_name,
            "total_files": len(files),
            "successful_files": successful_files,
            "total_chunks": total_chunks,
            "results": results,
            "success": successful_files > 0
        }
        
        print(f"\n📊 法规库构建完成:")
        print(f"   成功处理: {successful_files}/{len(files)} 个文件")
        print(f"   总条文块: {total_chunks}")
        print(f"   知识库集合: {self.collection_name}")
        
        return summary
    
    def _infer_regulation_info(self, filename: str) -> Dict[str, Any]:
        """根据文件名推断法规信息"""
        info = {
            "name": "",
            "authority": "",
            "category": "法律法规",
            "number": "",
            "effective_date": ""
        }
        
        filename_lower = filename.lower()
        
        # 推断法规类型和发布机构
        if '建筑法' in filename or '城市规划法' in filename:
            info["authority"] = "全国人大常委会"
            info["category"] = "法律"
        elif '建设工程' in filename and '条例' in filename:
            info["authority"] = "国务院"
            info["category"] = "行政法规"
        elif '住建部' in filename or '建设部' in filename:
            info["authority"] = "住房和城乡建设部"
            info["category"] = "部门规章"
        elif 'gb' in filename_lower:
            info["authority"] = "国家标准化管理委员会"
            info["category"] = "国家标准"
        
        # 提取法规名称（去除文件扩展名）
        name_without_ext = Path(filename).stem
        info["name"] = name_without_ext
        
        return info
    
    def get_regulations_stats(self) -> Dict[str, Any]:
        """获取法规库统计信息"""
        basic_stats = self.kb.get_knowledge_base_stats()
        
        # 获取法规分类统计
        try:
            # 这里可以扩展，查询不同类型法规的数量
            regulations_by_type = {
                "法律": 0,
                "行政法规": 0,
                "部门规章": 0,
                "地方法规": 0,
                "技术规范": 0,
                "其他": 0
            }
            
            return {
                **basic_stats,
                "regulations_by_type": regulations_by_type,
                "collection_description": "法律法规专门知识库"
            }
        except Exception:
            return basic_stats

def main():
    """主函数"""
    print("🏛️ 法规知识库构建工具")
    print("=" * 50)
    
    try:
        # 从配置文件获取API密钥
        config = Config()
        api_key = config.bigmodel_api_key
        if not api_key:
            print("❌ 配置文件中未找到BigModel API密钥，请在config.py中设置bigmodel_api_key")
            return
        
        print(f"🔑 使用配置文件中的API密钥: {api_key[:10]}...")
        
        # 初始化构建器
        builder = RegulationsKnowledgeBuilder(api_key)
        
        # 检查法规文档目录
        regulations_dir = Path("./regulations")
        if not regulations_dir.exists():
            print(f"📁 创建法规文档目录: {regulations_dir}")
            regulations_dir.mkdir(exist_ok=True)
            print(f"请将法规文档（.txt 或 .md 格式）放入 {regulations_dir} 目录")
            return
        
        # 检查集合状态
        current_stats = builder.get_regulations_stats()
        current_count = current_stats.get("total_chunks", 0)
        
        if current_count > 0:
            print(f"📚 当前法规库已有 {current_count} 个文档块")
            choice = input("是否清空现有数据重新构建？(y/N): ").strip().lower()
            if choice == 'y':
                builder.kb.clear_collection()
                print("🗑️ 已清空现有法规数据")
        
        # 构建法规库
        print(f"\n🔄 开始构建法规知识库...")
        result = builder.build_from_directory(regulations_dir, recursive=True)
        
        if result["success"]:
            print(f"\n🎉 法规库构建成功！")
            
            # 显示最终统计
            final_stats = builder.get_regulations_stats()
            print(f"\n📊 法规库统计:")
            print(f"   集合名称: {final_stats['collection_name']}")
            print(f"   文档总数: {final_stats['total_chunks']}")
            print(f"   向量模型: {final_stats['embedding_model']}")
            print(f"   向量维度: {final_stats['embedding_dimension']}")
            
            # 测试搜索功能
            print(f"\n🧪 测试法规库搜索功能...")
            test_queries = [
                "建筑工程质量管理",
                "工程监理职责",
                "施工许可证",
                "安全生产责任",
                "工程竣工验收"
            ]
            
            for query in test_queries:
                print(f"\n🔍 搜索测试: '{query}'")
                results = builder.kb.search(query, n_results=2)
                
                if results["results"]:
                    for i, result in enumerate(results["results"]):
                        similarity = result.get('similarity', 0)
                        regulation_name = result['metadata'].get('regulation_name', '未知法规')
                        article_number = result['metadata'].get('article_number', '')
                        
                        print(f"   结果{i+1}: 相似度={similarity:.3f}")
                        print(f"   法规: {regulation_name}")
                        if article_number:
                            print(f"   条文: 第{article_number}条")
                        print(f"   内容: {result['content'][:100]}...")
                else:
                    print("   未找到相关结果")
            
            print(f"\n✅ 法规库已准备就绪，现在可以切换到法规库进行问答！")
            print(f"   使用命令: 在Web界面中选择切换到「法律法规库」")
        else:
            print(f"\n❌ 法规库构建失败: {result.get('message', '未知错误')}")
    
    except Exception as e:
        print(f"❌ 构建失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main() 