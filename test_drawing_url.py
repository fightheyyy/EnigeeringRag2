#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试图纸URL功能
"""

import requests
import json

def test_drawing_url_functionality():
    """测试图纸URL功能"""
    
    # 测试问题 - 包含图纸相关内容
    test_question = """
    根据1号住宅楼墙柱大样图纸（1号住宅楼_13_10_5_000_59_000m墙柱大样_第1版），不同编号墙柱的配筋信息如下：

    1. GBZ1
    - 标高5.000~56.000m：
    - 纵筋：8Φ16+4Φ10(空心)
    - 箍筋：Φ8@200(4肢)/Φ6@200(拉筋)
    
    请问这个配筋设计是否符合规范要求？
    """
    
    # 发送请求
    url = "http://localhost:8000/ask"
    payload = {
        "question": test_question,
        "session_id": "test_drawing_url"
    }
    
    try:
        print("🔍 发送测试问题...")
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 请求成功")
            print(f"答案: {result.get('answer', '无答案')}")
            print(f"可信度: {result.get('confidence_score', 0)}")
            
            # 检查答案中是否包含图纸URL
            answer = result.get('answer', '')
            if '相关工程图纸' in answer:
                print("✅ 检测到图纸信息部分")
                if '[查看图纸文档]' in answer:
                    print("✅ 包含图纸URL链接")
                else:
                    print("❌ 未找到图纸URL链接")
            else:
                print("❌ 未检测到图纸信息部分")
                
        else:
            print(f"❌ 请求失败: {response.status_code}")
            print(f"错误信息: {response.text}")
            
    except Exception as e:
        print(f"❌ 测试失败: {e}")

if __name__ == "__main__":
    test_drawing_url_functionality() 