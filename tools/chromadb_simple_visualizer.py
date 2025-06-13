"""
ChromaDB简化可视化工具
用于可视化和分析ChromaDB向量数据库
仅使用基本库：matplotlib, pandas, numpy
"""

import chromadb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import warnings
import os
from datetime import datetime
from typing import Dict, List, Any
import json

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

warnings.filterwarnings('ignore')

class ChromaDBSimpleVisualizer:
    """ChromaDB简化可视化器"""
    
    def __init__(self, persist_directory: str = "./chroma_db"):
        """初始化可视化器"""
        self.persist_directory = persist_directory
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collections = {}
        self.load_collections()
        
    def load_collections(self):
        """加载所有集合"""
        try:
            collections = self.client.list_collections()
            for collection in collections:
                self.collections[collection.name] = collection
            print(f"✅ 加载了 {len(self.collections)} 个集合")
        except Exception as e:
            print(f"❌ 加载集合失败: {e}")
    
    def get_database_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        stats = {
            "总集合数": len(self.collections),
            "数据库路径": self.persist_directory,
            "数据库大小": self._get_directory_size(self.persist_directory),
            "集合详情": {}
        }
        
        total_documents = 0
        for name, collection in self.collections.items():
            count = collection.count()
            total_documents += count
            stats["集合详情"][name] = {
                "文档数量": count,
                "集合ID": collection.id
            }
        
        stats["总文档数"] = total_documents
        return stats
    
    def _get_directory_size(self, directory: str) -> str:
        """获取目录大小"""
        try:
            total_size = 0
            for dirpath, dirnames, filenames in os.walk(directory):
                for filename in filenames:
                    filepath = os.path.join(dirpath, filename)
                    total_size += os.path.getsize(filepath)
            
            if total_size < 1024:
                return f"{total_size} B"
            elif total_size < 1024**2:
                return f"{total_size/1024:.1f} KB"
            elif total_size < 1024**3:
                return f"{total_size/(1024**2):.1f} MB"
            else:
                return f"{total_size/(1024**3):.1f} GB"
        except:
            return "未知"
    
    def show_basic_stats(self):
        """显示基本统计信息"""
        stats = self.get_database_stats()
        print("\n" + "="*60)
        print("📊 ChromaDB 数据库统计信息")
        print("="*60)
        print(f"🗂️  数据库路径: {stats['数据库路径']}")
        print(f"💾 数据库大小: {stats['数据库大小']}")
        print(f"📁 总集合数: {stats['总集合数']}")
        print(f"📄 总文档数: {stats['总文档数']}")
        print("\n📚 集合详情:")
        print("-"*40)
        for name, details in stats['集合详情'].items():
            print(f"  📋 {name}:")
            print(f"     - 文档数量: {details['文档数量']}")
            print(f"     - 集合ID: {str(details['集合ID'])[:8]}...")
        print("="*60)
    
    def show_persistence_info(self):
        """显示持久化信息"""
        print(f"\n" + "="*60)
        print("💾 ChromaDB 持久化信息")
        print("="*60)
        print(f"📁 持久化目录: {self.persist_directory}")
        
        if os.path.exists(self.persist_directory):
            print(f"✅ 持久化目录存在")
            
            for root, dirs, files in os.walk(self.persist_directory):
                level = root.replace(self.persist_directory, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f"{indent}📂 {os.path.basename(root)}/")
                
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    size_str = self._format_file_size(file_size)
                    print(f"{subindent}📄 {file} ({size_str})")
        else:
            print(f"❌ 持久化目录不存在")
        
        print("="*60)
    
    def _format_file_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes/1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes/(1024**2):.1f} MB"
        else:
            return f"{size_bytes/(1024**3):.1f} GB"
    
    def plot_basic_stats(self):
        """生成基本统计图表"""
        stats = self.get_database_stats()
        
        collection_names = list(stats["集合详情"].keys())
        collection_counts = [stats["集合详情"][name]["文档数量"] for name in collection_names]
        
        if not collection_names:
            print("❌ 没有集合数据可显示")
            return
        
        fig, axes = plt.subplots(2, 2, figsize=(15, 10))
        fig.suptitle('ChromaDB 数据库统计报告', fontsize=16)
        
        # 柱状图
        axes[0, 0].bar(range(len(collection_names)), collection_counts, color='lightblue')
        axes[0, 0].set_title('各集合文档数量')
        axes[0, 0].set_ylabel('文档数量')
        axes[0, 0].set_xticks(range(len(collection_names)))
        axes[0, 0].set_xticklabels([name[:15] + '...' if len(name) > 15 else name 
                                   for name in collection_names], rotation=45)
        
        # 饼图
        axes[0, 1].pie(collection_counts, labels=[name[:10] + '...' if len(name) > 10 else name 
                                                 for name in collection_names], autopct='%1.1f%%')
        axes[0, 1].set_title('文档分布比例')
        
        # 累计图
        cumulative = np.cumsum(collection_counts)
        axes[1, 0].plot(range(len(collection_names)), cumulative, marker='o', color='green')
        axes[1, 0].set_title('累计文档数')
        axes[1, 0].set_ylabel('累计文档数')
        axes[1, 0].grid(True)
        
        # 信息表格
        axes[1, 1].axis('off')
        info_text = f"""数据库概览
        
总集合数: {stats['总集合数']}
总文档数: {stats['总文档数']}
数据库大小: {stats['数据库大小']}
数据库路径: {stats['数据库路径']}
        """
        axes[1, 1].text(0.1, 0.5, info_text, fontsize=12, verticalalignment='center')
        
        plt.tight_layout()
        plt.savefig('./chromadb_stats.png', dpi=300, bbox_inches='tight')
        plt.show()
        print("📊 统计图表已保存为 chromadb_stats.png")

if __name__ == "__main__":
    print("🚀 启动ChromaDB可视化分析...")
    visualizer = ChromaDBSimpleVisualizer("./data/chroma_db")
    
    visualizer.show_persistence_info()
    visualizer.show_basic_stats()
    visualizer.plot_basic_stats()
    
    print("\n🎉 可视化分析完成!") 