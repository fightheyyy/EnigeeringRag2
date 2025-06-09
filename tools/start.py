#!/usr/bin/env python3
"""
工程监理智能问答系统启动脚本
自动检查环境和配置，启动Web服务
"""

import os
import sys
import subprocess
import importlib.util
from pathlib import Path

def check_python_version():
    """检查Python版本"""
    if sys.version_info < (3, 8):
        print("❌ Python版本过低，需要Python 3.8+")
        print(f"   当前版本: {sys.version}")
        return False
    print(f"✅ Python版本检查通过: {sys.version.split()[0]}")
    return True

def check_dependencies():
    """检查依赖包"""
    required_packages = [
        'fastapi',
        'uvicorn', 
        'chromadb',
        'requests',
        'pydantic',
        'pandas',
        'numpy',
        'matplotlib'
    ]
    
    missing_packages = []
    for package in required_packages:
        spec = importlib.util.find_spec(package)
        if spec is None:
            missing_packages.append(package)
    
    if missing_packages:
        print(f"❌ 缺少依赖包: {', '.join(missing_packages)}")
        print("请运行: pip install -r requirements.txt")
        return False
    
    print("✅ 依赖包检查通过")
    return True

def check_config():
    """检查配置文件"""
    try:
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from core.config import Config
        
        # 检查API密钥
        if not Config.OPENAI_API_KEY or Config.OPENAI_API_KEY == "your_deepseek_api_key":
            print("⚠️ 未配置DeepSeek API密钥")
            print("请在config.py中配置OPENAI_API_KEY")
            return False
        
        if not Config.bigmodel_api_key or Config.bigmodel_api_key == "your_bigmodel_api_key":
            print("⚠️ 未配置BigModel API密钥")
            print("请在config.py中配置bigmodel_api_key")
            return False
        
        print("✅ API密钥配置检查通过")
        return True
        
    except Exception as e:
        print(f"❌ 配置检查失败: {e}")
        return False

def check_knowledge_base():
    """检查知识库"""
    chroma_db_path = Path("./chroma_db")
    if not chroma_db_path.exists():
        print("⚠️ 知识库不存在，正在构建...")
        try:
            subprocess.run([sys.executable, "build_bigmodel_kb.py"], check=True)
            print("✅ 知识库构建完成")
        except subprocess.CalledProcessError:
            print("❌ 知识库构建失败")
            print("请手动运行: python build_bigmodel_kb.py")
            return False
    else:
        print("✅ 知识库检查通过")
    
    return True

def start_service():
    """启动服务"""
    print("\n🚀 启动工程监理智能问答系统...")
    print("   访问地址: http://localhost:8000")
    print("   API文档: http://localhost:8000/docs")
    print("   按 Ctrl+C 停止服务\n")
    
    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 服务已停止")
    except subprocess.CalledProcessError as e:
        print(f"❌ 服务启动失败: {e}")

def main():
    """主函数"""
    print("🔍 正在检查运行环境...")
    
    # 环境检查
    checks = [
        ("Python版本", check_python_version),
        ("依赖包", check_dependencies),
        ("配置文件", check_config),
        ("知识库", check_knowledge_base)
    ]
    
    for check_name, check_func in checks:
        print(f"\n📋 检查{check_name}...")
        if not check_func():
            print(f"\n❌ {check_name}检查失败，请修复后重试")
            return
    
    print("\n✅ 所有检查通过！")
    
    # 启动服务
    start_service()

if __name__ == "__main__":
    main() 