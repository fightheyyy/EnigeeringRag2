#!/usr/bin/env python3
"""
测试知识库回退机制
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from services.llm_service import LLMService
from core.config import Config

def test_fallback_mechanism():
    """测试回退机制"""
    print("🧪 测试知识库回退机制...")
    
    # 初始化服务
    config = Config()
    llm_service = LLMService()
    
    print("✅ 服务初始化完成")
    
    # 测试问题
    test_questions = [
        "钢筋锚固长度如何计算？",
        "脚手架连墙件最大间距要求？",
        "混凝土抗压强度试验方法？"
    ]
    
    for question in test_questions:
        print(f"\n📋 测试问题: {question}")
        print("=" * 50)
        
        try:
            # 直接测试generate_answer_without_context方法
            response = llm_service.generate_answer_without_context(question)
            
            print(f"✅ 回答生成成功")
            print(f"📊 置信度: {response.confidence_score}")
            print(f"🎯 确定性答案: {response.has_definitive_answer}")
            print(f"📝 答案预览:")
            
            # 显示答案的前300字符
            answer_preview = response.answer[:300] + "..." if len(response.answer) > 300 else response.answer
            print(answer_preview)
            
            # 检查是否包含标准标注
            if "[使用标准:" in response.answer:
                print("✅ 包含标准标注")
            else:
                print("❌ 缺少标准标注")
                
        except Exception as e:
            print(f"❌ 错误: {e}")
            import traceback
            traceback.print_exc()
    
    print("\n🏁 测试完成")

def test_content_relevance_check():
    """测试内容相关性检查"""
    print("\n🧪 测试内容相关性检查...")
    
    # 模拟不相关的回答
    test_answers = [
        "根据提供的规范文档内容，未检索到关于钢筋锚固长度计算的具体公式。",
        "文档中主要涉及混凝土结构施工，但未包含钢筋锚固长度的计算方法。",
        "建议补充提供GB 50010规范文档以便准确查询。",
        "[使用标准: 无]",
        "正常的专业回答，包含具体的技术要求。[使用标准: GB 50010-2010]"
    ]
    
    irrelevant_keywords = [
        "未检索到", "未找到", "没有找到", "无法找到", "不能找到",
        "建议补充提供", "建议查阅", "需要查阅",
        "根据提供的规范文档内容，未",
        "[使用标准: 无]"
    ]
    
    compound_conditions = [
        ("文档中主要涉及", "但未包含"),
        ("文档中主要涉及", "但未明确提及"),
        ("文档中主要涉及", "未包含"),
        ("根据提供的", "未检索到")
    ]
    
    for i, answer in enumerate(test_answers):
        print(f"\n📝 测试答案 {i+1}: {answer[:50]}...")
        
        # 检查简单关键词
        simple_match = any(keyword in answer for keyword in irrelevant_keywords)
        
        # 检查复合条件
        compound_match = any(
            (cond[0] in answer and cond[1] in answer) 
            for cond in compound_conditions
        )
        
        is_irrelevant = simple_match or compound_match
        
        if is_irrelevant:
            print("❌ 判定为不相关答案，应该回退")
        else:
            print("✅ 判定为相关答案，正常返回")

if __name__ == "__main__":
    try:
        test_content_relevance_check()
        test_fallback_mechanism()
    except KeyboardInterrupt:
        print("\n用户中断测试")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc() 