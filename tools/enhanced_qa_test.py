"""
增强版问答测试工具
展示完整的向量检索+DeepSeek问答流程，包含详细的数据来源信息
"""

import requests
import json
from datetime import datetime
from typing import List, Dict, Any
import sys

class EnhancedQATestTool:
    """增强版问答测试工具"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_id = f"test_session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    def test_qa_with_sources(self, question: str) -> Dict[str, Any]:
        """测试问答功能并展示完整的来源信息"""
        print(f"\n{'='*80}")
        print(f"🤔 用户问题: {question}")
        print(f"{'='*80}")
        
        # 发送请求
        try:
            response = requests.post(
                f"{self.base_url}/ask",
                json={
                    "question": question,
                    "session_id": self.session_id
                },
                timeout=30
            )
            
            if response.status_code != 200:
                print(f"❌ 请求失败: {response.status_code}")
                print(f"错误信息: {response.text}")
                return {}
            
            result = response.json()
            
            # 展示结果
            self._display_qa_result(result)
            return result
            
        except requests.exceptions.RequestException as e:
            print(f"❌ 网络错误: {e}")
            return {}
        except json.JSONDecodeError as e:
            print(f"❌ JSON解析错误: {e}")
            return {}
    
    def _display_qa_result(self, result: Dict[str, Any]):
        """展示问答结果"""
        
        # 显示基本信息
        print(f"\n🎯 **答案生成成功**")
        print(f"   📊 置信度: {result.get('confidence_score', 0):.1%}")
        print(f"   ⏰ 生成时间: {result.get('timestamp', 'N/A')}")
        print(f"   🔍 会话ID: {result.get('session_id', 'N/A')}")
        
        # 显示答案
        print(f"\n🤖 **DeepSeek生成的答案**:")
        print("-" * 60)
        answer = result.get('answer', '')
        print(answer)
        print("-" * 60)
        
        # 显示数据来源
        sources = result.get('sources', [])
        if sources:
            print(f"\n📚 **知识来源信息** (共{len(sources)}个来源)")
            print("=" * 60)
            
            for i, source in enumerate(sources, 1):
                print(f"\n📄 **来源 {i}:**")
                print(f"   📁 文件名: {source.get('file_name', 'N/A')}")
                print(f"   📖 标题: {source.get('title', 'N/A')}")
                print(f"   🎯 相似度: {source.get('similarity_score', 0):.1%}")
                
                # 规范信息
                if source.get('regulation_code'):
                    print(f"   📋 规范编号: {source.get('regulation_code')}")
                if source.get('section'):
                    print(f"   📑 章节: {source.get('section')}")
                
                # 元数据信息
                metadata = source.get('metadata', {})
                if metadata:
                    print(f"   📊 元数据:")
                    print(f"      - 文档块索引: {metadata.get('chunk_index', 'N/A')}")
                    print(f"      - 总块数: {metadata.get('chunk_count', 'N/A')}")
                    print(f"      - 内容长度: {metadata.get('content_length', 'N/A')} 字符")
                
                # 内容预览
                content = source.get('content', '')
                if content:
                    preview = content[:200] + "..." if len(content) > 200 else content
                    print(f"   📝 内容预览:")
                    print(f"      {preview}")
                
                print("-" * 40)
        else:
            print(f"\n⚠️ **未找到相关来源**")
            print("   这表明回答是基于模型的通用知识，而非特定规范文档")
        
        # 显示建议
        suggestions = result.get('suggestions', [])
        if suggestions:
            print(f"\n💡 **相关建议**:")
            for i, suggestion in enumerate(suggestions, 1):
                print(f"   {i}. {suggestion}")
    
    def test_multiple_questions(self, questions: List[str]):
        """测试多个问题"""
        print(f"\n🚀 开始批量测试 {len(questions)} 个问题...")
        
        results = []
        for i, question in enumerate(questions, 1):
            print(f"\n📋 测试 {i}/{len(questions)}")
            result = self.test_qa_with_sources(question)
            if result:
                results.append({
                    'question': question,
                    'result': result
                })
        
        # 生成测试摘要
        self._generate_test_summary(results)
        return results
    
    def _generate_test_summary(self, results: List[Dict[str, Any]]):
        """生成测试摘要"""
        print(f"\n{'='*80}")
        print(f"📊 **测试摘要报告**")
        print(f"{'='*80}")
        
        total_questions = len(results)
        successful_answers = sum(1 for r in results if r['result'].get('answer'))
        avg_confidence = sum(r['result'].get('confidence_score', 0) for r in results) / total_questions if total_questions > 0 else 0
        
        print(f"📈 总测试问题: {total_questions}")
        print(f"✅ 成功回答: {successful_answers}")
        print(f"📊 平均置信度: {avg_confidence:.1%}")
        
        # 来源统计
        all_sources = []
        for r in results:
            all_sources.extend(r['result'].get('sources', []))
        
        if all_sources:
            source_files = {}
            for source in all_sources:
                file_name = source.get('file_name', 'Unknown')
                source_files[file_name] = source_files.get(file_name, 0) + 1
            
            print(f"\n📚 **来源文件统计**:")
            for file_name, count in sorted(source_files.items(), key=lambda x: x[1], reverse=True):
                print(f"   📄 {file_name}: {count} 次引用")
        
        print(f"{'='*80}")
    
    def interactive_test(self):
        """交互式测试"""
        print(f"\n🎯 **交互式问答测试**")
        print(f"输入问题进行测试，输入 'quit' 退出")
        print(f"{'='*50}")
        
        while True:
            try:
                question = input("\n❓ 请输入您的问题: ").strip()
                
                if question.lower() in ['quit', 'exit', '退出', 'q']:
                    print("👋 测试结束，再见！")
                    break
                
                if not question:
                    print("⚠️ 请输入有效问题")
                    continue
                
                self.test_qa_with_sources(question)
                
            except KeyboardInterrupt:
                print("\n\n👋 测试中断，再见！")
                break
            except Exception as e:
                print(f"❌ 测试错误: {e}")

def main():
    """主函数"""
    tester = EnhancedQATestTool()
    
    # 预定义测试问题
    test_questions = [
        # 知识库中存在的问题
        "什么是外加剂？",
        "减水剂的作用是什么？", 
        "HPWR是什么意思？",
        "混凝土外加剂有哪些种类？",
        "外加剂的掺量要求是多少？",
        "如何选择合适的外加剂？",
        # 知识库中可能不存在的问题（测试通用知识回答）
        "钢结构焊接有什么要求？",
        "脚手架搭设的安全注意事项有哪些？",
        "地基承载力如何检测？",
        "混凝土养护的标准程序是什么？",
        "建筑防水工程的质量验收标准？"
    ]
    
    if len(sys.argv) > 1:
        # 命令行指定问题
        question = " ".join(sys.argv[1:])
        tester.test_qa_with_sources(question)
    else:
        print("🚀 启动增强版问答测试工具")
        print("\n请选择测试模式:")
        print("1. 批量测试预定义问题")
        print("2. 交互式测试")
        print("3. 单个问题测试")
        
        try:
            choice = input("\n请选择 (1/2/3): ").strip()
            
            if choice == "1":
                tester.test_multiple_questions(test_questions)
            elif choice == "2":
                tester.interactive_test()
            elif choice == "3":
                question = input("请输入问题: ").strip()
                if question:
                    tester.test_qa_with_sources(question)
                else:
                    print("❌ 无效问题")
            else:
                print("❌ 无效选择")
                
        except KeyboardInterrupt:
            print("\n👋 程序中断，再见！")
        except Exception as e:
            print(f"❌ 程序错误: {e}")

if __name__ == "__main__":
    main() 