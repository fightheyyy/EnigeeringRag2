import os
import re
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

class EngineeringDocumentProcessor:
    """工程文档处理器"""
    
    def __init__(self):
        # 工程规范标识模式
        self.regulation_patterns = {
            'GB': r'GB\s*[/\-]?\s*(\d+(?:\.\d+)?[\-\s]*\d*)',          # 国家标准
            'JGJ': r'JGJ\s*[/\-]?\s*(\d+(?:\.\d+)?[\-\s]*\d*)',       # 行业标准（建工）
            'CJJ': r'CJJ\s*[/\-]?\s*(\d+(?:\.\d+)?[\-\s]*\d*)',       # 行业标准（城建）
            'JGT': r'JGT\s*[/\-]?\s*(\d+(?:\.\d+)?[\-\s]*\d*)',       # 行业标准（建材）
            'DBJ': r'DBJ\s*[/\-]?\s*(\d+(?:\.\d+)?[\-\s]*\d*)',       # 地方标准
        }
        
        # 条款编号模式
        self.clause_patterns = [
            r'(\d+)\.(\d+)\.(\d+)',      # 如：8.2.1
            r'第(\d+)章',                 # 如：第8章
            r'第(\d+)节',                 # 如：第2节
            r'(\d+)\.(\d+)',             # 如：8.2
        ]
        
        # 工程专业术语
        self.engineering_terms = {
            "混凝土": ["强度等级", "配合比", "保护层", "钢筋", "浇筑", "养护", "抗压强度"],
            "钢结构": ["焊接", "螺栓连接", "防腐涂装", "变形", "承载力", "稳定性"],
            "脚手架": ["立杆", "横杆", "连墙件", "剪刀撑", "安全网", "荷载"],
            "地基基础": ["承载力", "沉降", "桩基", "地基处理", "基坑支护"],
            "防水工程": ["防水材料", "防水层", "渗漏", "防水卷材", "防水涂料"],
            "保温工程": ["保温材料", "导热系数", "保温层", "热桥", "节能"],
        }

    def process_document(self, content: str, file_path: str) -> Dict:
        """处理工程文档，提取关键信息"""
        try:
            # 基本信息提取
            doc_info = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'content_length': len(content),
                'processed_time': datetime.now().isoformat()
            }
            
            # 识别文档类型
            doc_info['document_type'] = self._identify_document_type(content, file_path)
            
            # 提取规范信息
            doc_info['regulation_info'] = self._extract_regulation_info(content)
            
            # 提取章节结构
            doc_info['sections'] = self._extract_sections(content)
            
            # 提取关键术语
            doc_info['key_terms'] = self._extract_key_terms(content)
            
            # 提取技术要求
            doc_info['technical_requirements'] = self._extract_technical_requirements(content)
            
            # 清理和标准化内容
            doc_info['cleaned_content'] = self._clean_content(content)
            
            return doc_info
            
        except Exception as e:
            logger.error(f"文档处理失败: {e}")
            return {'error': str(e), 'file_path': file_path}
    
    def _identify_document_type(self, content: str, file_path: str) -> str:
        """识别文档类型"""
        content_lower = content.lower()
        file_name_lower = os.path.basename(file_path).lower()
        
        # 根据内容特征判断
        if any(pattern in content for pattern in ['GB', 'JGJ', 'CJJ', 'JGT']):
            if '设计' in content:
                return 'design_standard'
            elif '施工' in content or '验收' in content:
                return 'construction_standard'
            elif '安全' in content:
                return 'safety_standard'
            else:
                return 'regulation'
        
        # 根据文件名判断
        if any(keyword in file_name_lower for keyword in ['图纸', 'drawing', '设计图']):
            return 'drawing'
        elif any(keyword in file_name_lower for keyword in ['规范', 'standard', '标准']):
            return 'regulation'
        elif any(keyword in file_name_lower for keyword in ['说明', 'specification']):
            return 'specification'
        
        return 'general'
    
    def _extract_regulation_info(self, content: str) -> Dict:
        """提取规范信息"""
        regulation_info = {}
        
        # 提取规范编号
        for reg_type, pattern in self.regulation_patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                regulation_info['code'] = f"{reg_type} {matches[0]}"
                regulation_info['type'] = reg_type
                break
        
        # 提取规范名称（通常在标题附近）
        lines = content.split('\n')[:10]  # 检查前10行
        for line in lines:
            if any(keyword in line for keyword in ['规范', '标准', '规程', '技术要求']):
                regulation_info['title'] = line.strip()
                break
        
        # 提取发布年份
        year_pattern = r'(19|20)\d{2}'
        years = re.findall(year_pattern, content[:500])  # 在文档开头查找
        if years:
            regulation_info['year'] = years[0]
        
        return regulation_info
    
    def _extract_sections(self, content: str) -> List[Dict]:
        """提取章节结构"""
        sections = []
        lines = content.split('\n')
        
        current_chapter = None
        current_section = None
        
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
            
            # 识别章
            chapter_match = re.match(r'第?(\d+)章\s*(.*)', line)
            if chapter_match:
                current_chapter = {
                    'type': 'chapter',
                    'number': chapter_match.group(1),
                    'title': chapter_match.group(2).strip(),
                    'line_number': i + 1,
                    'content': []
                }
                sections.append(current_chapter)
                continue
            
            # 识别节
            section_match = re.match(r'(\d+)\.(\d+)\s*(.*)', line)
            if section_match:
                current_section = {
                    'type': 'section',
                    'number': f"{section_match.group(1)}.{section_match.group(2)}",
                    'title': section_match.group(3).strip(),
                    'line_number': i + 1,
                    'parent_chapter': current_chapter['number'] if current_chapter else None
                }
                sections.append(current_section)
                continue
            
            # 识别条款
            clause_match = re.match(r'(\d+)\.(\d+)\.(\d+)\s*(.*)', line)
            if clause_match:
                clause = {
                    'type': 'clause',
                    'number': f"{clause_match.group(1)}.{clause_match.group(2)}.{clause_match.group(3)}",
                    'title': clause_match.group(4).strip(),
                    'line_number': i + 1,
                    'parent_section': current_section['number'] if current_section else None
                }
                sections.append(clause)
        
        return sections
    
    def _extract_key_terms(self, content: str) -> List[str]:
        """提取关键技术术语"""
        found_terms = []
        content_lower = content.lower()
        
        for category, terms in self.engineering_terms.items():
            for term in terms:
                if term in content_lower:
                    found_terms.append(term)
        
        # 去重并排序
        return sorted(list(set(found_terms)))
    
    def _extract_technical_requirements(self, content: str) -> List[Dict]:
        """提取技术要求"""
        requirements = []
        lines = content.split('\n')
        
        requirement_keywords = [
            '应符合', '不应小于', '不应大于', '应满足', '必须', 
            '不得', '应采用', '宜采用', '可采用', '严禁'
        ]
        
        for i, line in enumerate(lines):
            line = line.strip()
            if any(keyword in line for keyword in requirement_keywords):
                # 尝试提取数值要求
                numbers = re.findall(r'\d+(?:\.\d+)?', line)
                units = re.findall(r'(mm|cm|m|MPa|kN|℃|%)', line)
                
                requirement = {
                    'line_number': i + 1,
                    'text': line,
                    'numbers': numbers,
                    'units': units,
                    'type': self._classify_requirement(line)
                }
                requirements.append(requirement)
        
        return requirements[:20]  # 限制数量，避免过多
    
    def _classify_requirement(self, text: str) -> str:
        """分类技术要求"""
        text_lower = text.lower()
        
        if any(keyword in text_lower for keyword in ['厚度', '直径', '间距', '长度']):
            return 'dimensional'
        elif any(keyword in text_lower for keyword in ['强度', '荷载', '承载力']):
            return 'structural'
        elif any(keyword in text_lower for keyword in ['材料', '钢筋', '混凝土']):
            return 'material'
        elif any(keyword in text_lower for keyword in ['施工', '浇筑', '安装']):
            return 'construction'
        elif any(keyword in text_lower for keyword in ['检测', '验收', '试验']):
            return 'inspection'
        else:
            return 'general'
    
    def _clean_content(self, content: str) -> str:
        """清理和标准化内容"""
        # 移除多余的空白字符
        content = re.sub(r'\s+', ' ', content)
        
        # 移除特殊字符（保留中文、英文、数字、常用标点）
        content = re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9\s\.\,\;\:\!\?\-\(\)\[\]\/]', '', content)
        
        # 标准化数字格式
        content = re.sub(r'(\d+)\s*\.\s*(\d+)', r'\1.\2', content)
        
        return content.strip()

    def extract_document_metadata(self, content: str, file_path: str) -> Dict:
        """提取文档元数据用于向量数据库存储"""
        processed_info = self.process_document(content, file_path)
        
        metadata = {
            'file_name': processed_info.get('file_name', ''),
            'document_type': processed_info.get('document_type', 'general'),
            'regulation_code': processed_info.get('regulation_info', {}).get('code', ''),
            'regulation_title': processed_info.get('regulation_info', {}).get('title', ''),
            'key_terms': ','.join(processed_info.get('key_terms', [])),
            'sections_count': len(processed_info.get('sections', [])),
            'requirements_count': len(processed_info.get('technical_requirements', [])),
            'content_length': processed_info.get('content_length', 0),
            'processed_time': processed_info.get('processed_time', ''),
        }
        
        return metadata

def create_engineering_samples():
    """创建更丰富的工程监理示例文档"""
    samples = [
        {
            "title": "混凝土结构工程施工质量验收规范 GB 50204-2015",
            "content": """
第4章 模板工程
4.1 一般规定
4.1.1 模板及其支架应根据工程结构形式、荷载大小、地基土类别、施工设备和材料供应等条件进行设计。
4.1.2 模板及其支架应具有足够的承载能力、刚度和稳定性，能可靠地承受浇筑混凝土的重量、侧压力以及施工荷载。

第5章 钢筋工程
5.1 原材料
5.1.1 钢筋进场时，应按现行国家标准《钢筋混凝土用钢 第1部分：热轧光圆钢筋》GB 1499.1的规定抽取试件作力学性能检验。
5.1.2 钢筋的品种、规格、性能等应符合现行国家标准和设计要求。

5.2 钢筋加工
5.2.1 钢筋加工的形状、尺寸应符合设计要求，钢筋的表面应洁净、无损伤、油渍、漆污和铁锈等。
5.2.2 钢筋调直应采用机械方法，也可采用冷拉方法。

5.3 钢筋连接
5.3.1 钢筋的连接可采用绑扎连接、焊接连接或机械连接。
5.3.2 纵向受力钢筋的连接宜优先采用焊接连接或机械连接。

第6章 混凝土工程
6.1 原材料
6.1.1 水泥进场时应进行质量检验，检验项目包括品种、强度等级、包装或散装仓号、出厂日期等。
6.1.2 混凝土用砂应符合现行行业标准《建设用砂》GB/T 14684的规定。

6.2 混凝土配合比
6.2.1 混凝土配合比应通过计算确定，并应满足混凝土强度、耐久性和工作性要求。
6.2.2 配制C30及以上强度等级的混凝土，宜掺用矿物掺合料。

6.3 混凝土施工
6.3.1 混凝土浇筑应连续进行，如因故中断，其间歇时间应符合相关规定。
6.3.2 混凝土浇筑时的自由倾落高度不宜超过2m，当超过2m时，应采取措施。
            """,
            "document_type": "construction_standard",
            "regulation_info": {
                "code": "GB 50204-2015",
                "title": "混凝土结构工程施工质量验收规范",
                "type": "GB"
            }
        },
        {
            "title": "建筑地基基础工程施工质量验收规范 GB 50202-2018",
            "content": """
第3章 地基
3.1 一般规定
3.1.1 地基处理应根据地基土的性质、建筑物的要求和环境条件等确定处理方案。
3.1.2 地基承载力特征值应通过载荷试验确定，也可根据土的物理力学性质指标确定。

第4章 桩基
4.1 一般规定  
4.1.1 桩基工程施工前应编制专项施工方案，并应经审查批准。
4.1.2 桩身质量应符合设计要求，桩身完整性应满足相关标准规定。

4.2 灌注桩
4.2.1 灌注桩成孔质量应符合下列规定：
1. 桩孔的孔径、孔深应符合设计要求；
2. 桩孔应垂直，孔壁应稳定；
3. 孔底沉渣厚度应满足设计要求，对于端承型桩，沉渣厚度不应大于50mm。

4.2.2 灌注桩混凝土灌注应符合下列规定：
1. 混凝土坍落度应为180～220mm；
2. 混凝土应连续灌注，严禁中途停顿；
3. 灌注过程中导管底端应始终埋入混凝土中，埋入深度不应小于2m。

第5章 地下防水
5.1 防水混凝土
5.1.1 防水混凝土的抗渗等级应符合设计要求，不应小于P6。
5.1.2 防水混凝土应采用普通硅酸盐水泥、硅酸盐水泥或快硬硅酸盐水泥。
5.1.3 防水混凝土的水胶比不应大于0.50，胶凝材料用量不应少于320kg/m³。
            """,
            "document_type": "construction_standard", 
            "regulation_info": {
                "code": "GB 50202-2018",
                "title": "建筑地基基础工程施工质量验收规范",
                "type": "GB"
            }
        }
    ]
    
    return samples 