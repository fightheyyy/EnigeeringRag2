"""
MySQL标准数据库服务
用于查询国家标准信息和文件存放地址
"""

import pymysql
import logging
from typing import List, Dict, Optional, Any
import re
from dataclasses import dataclass

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class StandardInfo:
    """标准信息数据类"""
    id: int
    standard_number: str
    standard_name: str
    file_url: str
    status: str
    publish_date: Optional[str] = None
    implement_date: Optional[str] = None
    document_id: Optional[str] = None

@dataclass
class RegulationInfo:
    """法规信息数据类"""
    id: int
    legal_name: str
    legal_url: str

class MySQLStandardsService:
    """MySQL标准数据库服务"""
    
    def __init__(self, host: str, port: str, user: str, password: str, database: str):
        """
        初始化MySQL连接服务
        
        Args:
            host: 数据库主机地址
            port: 端口号
            user: 用户名
            password: 密码
            database: 数据库名
        """
        self.host = host
        self.port = int(port)
        self.user = user
        self.password = password
        self.database = database
        self.connection = None
        
        # 测试连接
        self._test_connection()
        
    def _test_connection(self):
        """测试数据库连接"""
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor
            )
            connection.close()
            logger.info(f"✅ MySQL数据库连接测试成功: {self.host}:{self.port}/{self.database}")
        except Exception as e:
            logger.error(f"❌ MySQL数据库连接失败: {e}")
            raise
    
    def _get_connection(self):
        """获取数据库连接"""
        try:
            connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                charset='utf8mb4',
                cursorclass=pymysql.cursors.DictCursor,
                autocommit=True
            )
            return connection
        except Exception as e:
            logger.error(f"❌ 获取数据库连接失败: {e}")
            raise
    
    def search_standards_by_name(self, query: str, limit: int = 10) -> List[StandardInfo]:
        """
        根据标准名称搜索标准信息
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            标准信息列表
        """
        connection = None
        try:
            connection = self._get_connection()
            with connection.cursor() as cursor:
                # 使用LIKE进行模糊搜索（搜索标准名称和标准编号）
                sql = """
                SELECT id, standard_number, standard_name, status, 
                       publish_date, implement_date, file_url, document_id
                FROM standards 
                WHERE standard_name LIKE %s OR standard_number LIKE %s
                ORDER BY 
                    CASE WHEN standard_name = %s THEN 1 
                         WHEN standard_number = %s THEN 2 
                         ELSE 3 END,
                    CHAR_LENGTH(standard_name)
                LIMIT %s
                """
                
                like_query = f"%{query}%"
                cursor.execute(sql, (like_query, like_query, query, query, limit))
                results = cursor.fetchall()
                
                standards = []
                for row in results:
                    standard = StandardInfo(
                        id=row['id'],
                        standard_number=row['standard_number'],
                        standard_name=row['standard_name'],
                        file_url=row['file_url'],
                        status=row['status'],
                        publish_date=str(row['publish_date']) if row['publish_date'] else None,
                        implement_date=str(row['implement_date']) if row['implement_date'] else None,
                        document_id=row.get('document_id')
                    )
                    standards.append(standard)
                
                logger.info(f"🔍 搜索标准 '{query}': 找到 {len(standards)} 个结果")
                return standards
                
        except Exception as e:
            logger.error(f"❌ 搜索标准失败: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def search_standards_by_keywords(self, keywords: List[str], limit: int = 5) -> List[StandardInfo]:
        """
        根据关键词列表搜索标准
        
        Args:
            keywords: 关键词列表
            limit: 返回结果数量限制
            
        Returns:
            标准信息列表
        """
        if not keywords:
            return []
        
        all_standards = []
        for keyword in keywords:
            standards = self.search_standards_by_name(keyword, limit)
            all_standards.extend(standards)
        
        # 去重（根据ID）
        seen_ids = set()
        unique_standards = []
        for standard in all_standards:
            if standard.id not in seen_ids:
                seen_ids.add(standard.id)
                unique_standards.append(standard)
        
        return unique_standards[:limit]
    
    def extract_standard_references(self, text: str) -> List[str]:
        """
        从文本中提取标准引用
        
        Args:
            text: 输入文本
            
        Returns:
            标准引用列表
        """
        # 常见的标准格式模式
        patterns = [
            r'GB[\s\+]*\d+(?:\.\d+)?(?:[-\+]\d+)?',  # GB 50010-2010, GB+8076-2008
            r'JGJ[\s\+]*\d+(?:\.\d+)?(?:[-\+]\d+)?',  # JGJ 55-2011, JGJ+130-2011
            r'GB/T[\s\+]*\d+(?:\.\d+)?(?:[-\+]\d+)?',  # GB/T 50152-2012
            r'JGJ/T[\s\+]*\d+(?:\.\d+)?(?:[-\+]\d+)?',  # JGJ/T 385-2015
            r'CJJ[\s\+]*\d+(?:\.\d+)?(?:[-\+]\d+)?',  # CJJ 1-2008
            r'DBJ[\s\+]*\d+(?:\.\d+)?(?:[-\+]\d+)?',  # DBJ 15-31-2016
        ]
        
        references = []
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            references.extend(matches)
        
        # 去重并清理
        unique_refs = []
        for ref in references:
            # 清理格式：将+号替换为空格，统一格式
            clean_ref = re.sub(r'\+', ' ', ref.strip())
            clean_ref = re.sub(r'\s+', ' ', clean_ref)
            if clean_ref and clean_ref not in unique_refs:
                unique_refs.append(clean_ref)
        
        return unique_refs
    
    def find_standards_for_content(self, content: str, metadata: Dict[str, Any] = None) -> List[StandardInfo]:
        """
        为给定内容查找相关标准
        
        Args:
            content: 文档内容
            metadata: 文档元数据
            
        Returns:
            相关标准信息列表
        """
        # 1. 从内容中提取标准引用
        references = self.extract_standard_references(content)
        
        # 2. 从元数据中获取来源文件信息
        source_keywords = []
        if metadata:
            source_file = metadata.get('source_file', '')
            if source_file:
                # 从文件名中提取关键词
                filename_refs = self.extract_standard_references(source_file)
                references.extend(filename_refs)
                
                # 提取其他关键词
                if '外加剂' in source_file:
                    source_keywords.append('外加剂')
                if '混凝土' in source_file:
                    source_keywords.append('混凝土')
        
        # 3. 搜索相关标准
        all_standards = []
        
        # 搜索直接引用的标准
        for ref in references:
            standards = self.search_standards_by_name(ref, 3)
            all_standards.extend(standards)
        
        # 搜索关键词相关的标准
        if source_keywords:
            keyword_standards = self.search_standards_by_keywords(source_keywords, 2)
            all_standards.extend(keyword_standards)
        
        # 去重
        seen_ids = set()
        unique_standards = []
        for standard in all_standards:
            if standard.id not in seen_ids:
                seen_ids.add(standard.id)
                unique_standards.append(standard)
        
        return unique_standards[:5]  # 限制返回5个最相关的标准
    
    def get_standard_by_id(self, standard_id: int) -> Optional[StandardInfo]:
        """
        根据ID获取标准信息
        
        Args:
            standard_id: 标准ID
            
        Returns:
            标准信息或None
        """
        connection = None
        try:
            connection = self._get_connection()
            with connection.cursor() as cursor:
                sql = """SELECT id, standard_number, standard_name, status, 
                        publish_date, implement_date, file_url, document_id 
                        FROM standards WHERE id = %s"""
                cursor.execute(sql, (standard_id,))
                row = cursor.fetchone()
                
                if row:
                    return StandardInfo(
                        id=row['id'],
                        standard_number=row['standard_number'],
                        standard_name=row['standard_name'],
                        file_url=row['file_url'],
                        status=row['status'],
                        publish_date=str(row['publish_date']) if row['publish_date'] else None,
                        implement_date=str(row['implement_date']) if row['implement_date'] else None,
                        document_id=row.get('document_id')
                    )
                return None
                
        except Exception as e:
            logger.error(f"❌ 获取标准信息失败: {e}")
            return None
        finally:
            if connection:
                connection.close()
    
    def get_all_standards_count(self) -> int:
        """获取标准总数"""
        connection = None
        try:
            connection = self._get_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) as count FROM standards")
                result = cursor.fetchone()
                return result['count'] if result else 0
        except Exception as e:
            logger.error(f"❌ 获取标准总数失败: {e}")
            return 0
        finally:
            if connection:
                connection.close()
    
    def get_standards_summary(self) -> Dict[str, Any]:
        """获取标准数据库摘要信息"""
        try:
            total_count = self.get_all_standards_count()
            
            # 获取一些示例标准
            sample_standards = self.search_standards_by_name("GB", 5)
            
            return {
                "total_count": total_count,
                "database_name": self.database,
                "host": self.host,
                "sample_standards": [
                    {"id": s.id, "standard_number": s.standard_number, 
                     "standard_name": s.standard_name, "file_url": s.file_url} 
                    for s in sample_standards
                ]
            }
        except Exception as e:
            logger.error(f"❌ 获取数据库摘要失败: {e}")
            return {"error": str(e)}
    
    def search_regulations_by_name(self, query: str, limit: int = 10) -> List[RegulationInfo]:
        """
        根据法规名称搜索法规信息
        
        Args:
            query: 搜索关键词
            limit: 返回结果数量限制
            
        Returns:
            法规信息列表
        """
        connection = None
        try:
            connection = self._get_connection()
            with connection.cursor() as cursor:
                # 使用LIKE进行模糊搜索
                sql = """
                SELECT id, legal_name, legal_url
                FROM regulations 
                WHERE legal_name LIKE %s
                ORDER BY 
                    CASE WHEN legal_name = %s THEN 1 
                         ELSE 2 END,
                    CHAR_LENGTH(legal_name)
                LIMIT %s
                """
                
                like_query = f"%{query}%"
                cursor.execute(sql, (like_query, query, limit))
                results = cursor.fetchall()
                
                regulations = []
                for row in results:
                    regulation = RegulationInfo(
                        id=row['id'],
                        legal_name=row['legal_name'],
                        legal_url=row['legal_url']
                    )
                    regulations.append(regulation)
                
                logger.info(f"🔍 搜索法规 '{query}': 找到 {len(regulations)} 个结果")
                return regulations
                
        except Exception as e:
            logger.error(f"❌ 搜索法规失败: {e}")
            return []
        finally:
            if connection:
                connection.close()
    
    def find_regulation_by_content_keywords(self, content: str) -> List[RegulationInfo]:
        """
        根据内容关键词查找相关法规
        
        Args:
            content: 内容文本
            
        Returns:
            相关法规信息列表
        """
        logger.info(f"🔍 查找法规，内容: '{content}'")
        
        # 直接搜索完整的法规名称
        all_regulations = []
        
        # 如果内容就是法规名称，直接搜索
        regulations = self.search_regulations_by_name(content, 3)
        if regulations:
            logger.info(f"✅ 直接匹配到法规: {[r.legal_name for r in regulations]}")
            all_regulations.extend(regulations)
        
        # 提取法规关键词进行搜索
        keywords = []
        
        # 常见法规关键词
        regulation_keywords = [
            '住宅专项维修资金', '建筑工程施工', '建筑工程质量', '房地产经纪', 
            '商品房销售', '安全生产管理', '城市房屋便器', '城市公厕', 
            '便器水箱', '公厕管理', '房屋便器', '水箱应用'
        ]
        
        # 检查内容中是否包含这些关键词
        for keyword in regulation_keywords:
            if keyword in content:
                keywords.append(keyword)
        
        # 如果内容包含"办法"、"规定"等法规标识词，提取相关词汇
        if any(term in content for term in ['办法', '规定', '条例', '法律', '法规']):
            # 提取可能的法规名称片段
            import re
            # 提取包含法规标识词的短语
            pattern = r'[\u4e00-\u9fff]+(?:办法|规定|条例|法律|法规)'
            matches = re.findall(pattern, content)
            for match in matches:
                if len(match) > 4:  # 过滤太短的匹配
                    keywords.append(match)
        
        # 去重
        keywords = list(set(keywords))
        logger.info(f"🔍 提取到法规关键词: {keywords}")
        
        # 搜索法规
        for keyword in keywords[:5]:  # 最多搜索5个关键词
            regulations = self.search_regulations_by_name(keyword, 2)
            if regulations:
                logger.info(f"✅ 关键词 '{keyword}' 匹配到法规: {[r.legal_name for r in regulations]}")
            all_regulations.extend(regulations)
        
        # 去重
        seen_ids = set()
        unique_regulations = []
        for regulation in all_regulations:
            if regulation.id not in seen_ids:
                seen_ids.add(regulation.id)
                unique_regulations.append(regulation)
        
        logger.info(f"🎯 最终找到 {len(unique_regulations)} 个法规")
        return unique_regulations[:3]  # 最多返回3个相关法规

# 创建全局实例
mysql_standards_service = None

def get_mysql_standards_service() -> MySQLStandardsService:
    """获取MySQL标准服务实例"""
    global mysql_standards_service
    if mysql_standards_service is None:
        # 使用提供的数据库配置
        mysql_standards_service = MySQLStandardsService(
            host="gz-cdb-e0aa423v.sql.tencentcdb.com",
            port="20236",
            user="root",
            password="Aa@114514",
            database="gauz_ai_messages"
        )
    return mysql_standards_service

if __name__ == "__main__":
    # 测试功能
    print("🧪 测试MySQL标准数据库服务...")
    
    service = get_mysql_standards_service()
    
    # 测试搜索功能
    print("\n🔍 测试搜索功能:")
    results = service.search_standards_by_name("GB", 3)
    for result in results:
        print(f"  - {result.standard_number}: {result.standard_name}")
        print(f"    URL: {result.file_url}")
        print(f"    状态: {result.status}")
    
    # 测试标准引用提取
    print("\n📝 测试标准引用提取:")
    test_text = "根据GB 50010-2010和JGJ 55-2011规范要求..."
    refs = service.extract_standard_references(test_text)
    print(f"  提取的标准: {refs}")
    
    # 获取摘要信息
    print("\n📊 数据库摘要:")
    summary = service.get_standards_summary()
    print(f"  总标准数: {summary.get('total_count', 0)}")
    print(f"  数据库: {summary.get('database_name')}") 