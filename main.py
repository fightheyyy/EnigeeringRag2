from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from datetime import datetime
import uuid
import logging
import os
import re
from typing import List, Optional, Dict

from core.config import Config
from core.models import QuestionRequest, AnswerResponse, KnowledgeDocument, SystemStatus  
from services.bigmodel_knowledge_base import BigModelKnowledgeBase as KnowledgeBaseManager
from services.llm_service import LLMService, enhance_engineering_question
from services.mysql_standards_service import get_mysql_standards_service
from services.drawing_upload_service import get_drawing_service

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 初始化FastAPI应用
app = FastAPI(
    title="工程监理智能问答系统",
    description="为现场监理工程师提供规范和图纸查询服务",
    version="1.0.0"
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/static", StaticFiles(directory="static"), name="static")

# 初始化服务
config = Config()

# 知识库配置 - 支持多个专门的知识库
KNOWLEDGE_BASES = {
    "standards": "国家标准库",
    "engineering_knowledge_base": "原有工程知识库", 
    "regulations": "法律法规库",
    "drawings": "项目图纸库"      # 预留
}

# 默认使用standards集合（国家标准库）
DEFAULT_COLLECTION = "standards"

# 使用BigModel知识库，指定standards集合
kb_manager = KnowledgeBaseManager(
    api_key=config.bigmodel_api_key,
    collection_name=DEFAULT_COLLECTION
)
llm_service = LLMService()

# 初始化MySQL标准服务
try:
    standards_service = get_mysql_standards_service()
    logger.info("✅ MySQL标准数据库服务初始化成功")
except Exception as e:
    logger.error(f"❌ MySQL标准数据库服务初始化失败: {e}")
    standards_service = None

# 初始化图纸上传服务
try:
    drawing_service = get_drawing_service()
    logger.info("✅ 图纸上传服务初始化成功")
except Exception as e:
    logger.error(f"❌ 图纸上传服务初始化失败: {e}")
    drawing_service = None

# 存储会话历史（生产环境中应使用数据库）
session_history = {}

def extract_used_standards_from_answer(answer: str) -> List[str]:
    """从答案中提取DeepSeek标注的使用标准"""
    # 查找[使用标准: XXX]格式的标注
    pattern = r'\[使用标准:\s*([^\]]+)\]'
    match = re.search(pattern, answer)
    
    if match:
        standards_text = match.group(1).strip()
        if standards_text.lower() == "无":
            return []
        
        # 分割多个标准（用逗号分隔）
        standards = [std.strip() for std in standards_text.split(',')]
        return [std for std in standards if std]  # 过滤空字符串
    
    return []

def analyze_answer_sources(answer: str, sources: List) -> Dict[str, List]:
    """
    分析答案中实际使用的来源类型
    
    Args:
        answer: 大模型生成的答案
        sources: 检索到的所有来源
        
    Returns:
        Dict包含不同类型的来源信息
    """
    used_sources = {
        'standards': [],  # 标准来源
        'regulations': [],  # 法规来源  
        'drawings': [],  # 图纸来源
        'source_files': []  # 所有来源文件名
    }
    
    # 从答案的参考来源部分提取实际使用的来源
    import re
    
    # 方法1: 查找📚 参考来源部分
    source_pattern = r'📚 参考来源：\s*(.*?)(?=💭|$)'
    source_match = re.search(source_pattern, answer, re.DOTALL)
    
    if source_match:
        source_text = source_match.group(1)
        
        # 提取来源文件名（格式：1. 文件名 - 块X (相关度: XX.X%)）
        # 修改正则表达式以更好地匹配文件名
        file_pattern = r'\d+\.\s*([^-\n]+?)(?:\s*-\s*块|\s*\()'
        file_matches = re.findall(file_pattern, source_text)
        
        for file_name in file_matches:
            file_name = file_name.strip()
            used_sources['source_files'].append(file_name)
            _classify_source_type(file_name, used_sources)
    
    # 方法2: 查找答案中的（来源：块X）格式
    block_pattern = r'（来源：块(\d+)）'
    block_matches = re.findall(block_pattern, answer)
    
    if block_matches and sources:
        logger.info(f"🔍 在答案中发现块引用: {block_matches}")
        for block_num in block_matches:
            try:
                block_index = int(block_num)
                # 从sources列表中找到对应的来源
                if 0 <= block_index < len(sources):
                    source = sources[block_index]
                    file_name = source.file_name if hasattr(source, 'file_name') else str(source)
                    used_sources['source_files'].append(file_name)
                    _classify_source_type(file_name, used_sources)
                    logger.info(f"✅ 识别到来源: 块{block_index} -> {file_name}")
            except (ValueError, IndexError):
                continue
    
    # 方法3: 查找答案中的文本引用（如"以上信息来源于结构设计总说明二"）
    text_source_patterns = [
        r'以上信息来源于([^中。，]+)',
        r'信息来源于([^中。，]+)',
        r'来源于([^中。，]+)',
        r'根据([^中。，]*设计说明[^中。，]*)',
        r'参考([^中。，]*设计说明[^中。，]*)'
    ]
    
    for pattern in text_source_patterns:
        text_matches = re.findall(pattern, answer)
        for match in text_matches:
            source_name = match.strip()
            if len(source_name) > 2:  # 过滤太短的匹配
                used_sources['source_files'].append(source_name)
                _classify_source_type(source_name, used_sources)
                logger.info(f"✅ 识别到文本来源: {source_name}")
    
    # 也从[使用标准: XXX]中提取
    used_standards = extract_used_standards_from_answer(answer)
    if used_standards and "无" not in used_standards:
        for standard in used_standards:
            if any(indicator in standard for indicator in ['住宅楼', '设计说明', '图纸', '大样']):
                used_sources['drawings'].append(standard)
            else:
                used_sources['standards'].append(standard)
    
    return used_sources

def _classify_source_type(file_name: str, used_sources: Dict[str, List]):
    """根据文件名分类来源类型"""
    # 图纸识别：包含住宅楼、设计说明等关键词
    drawing_keywords = ['住宅楼', '设计说明', '图纸', '大样', '详图', '施工图', '结构', '建筑', '给排水', '电气', '暖通', '桩基', '基础', '平面图', '立面图', '剖面图']
    if any(keyword in file_name for keyword in drawing_keywords):
        used_sources['drawings'].append(file_name)
    # 标准识别：GB、JGJ等开头或包含.txt
    elif (any(file_name.startswith(prefix) for prefix in ['GB', 'JGJ', 'CJJ', 'JTG', 'JTS', 'CJ']) or 
          file_name.endswith('.txt')):
        used_sources['standards'].append(file_name)
    # 法规识别：包含管理办法、条例等
    elif any(keyword in file_name for keyword in ['管理办法', '条例', '暂行办法', '规定', '通知', '意见']):
        used_sources['regulations'].append(file_name)

def optimize_reference_display(answer: str) -> str:
    """优化参考依据显示，隐藏值为"无"的类别，并使用Markdown格式"""
    import re
    
    # 查找参考依据部分
    reference_pattern = r'📚\s*\*\*参考依据\*\*\s*(.*?)(?=\n\n|$)'
    reference_match = re.search(reference_pattern, answer, re.DOTALL)
    
    if not reference_match:
        return answer
    
    reference_content = reference_match.group(1).strip()
    
    # 提取各个类别
    categories = {
        '使用标准': r'\[使用标准:\s*([^\]]+)\]',
        '引用法规': r'\[引用法规:\s*([^\]]+)\]', 
        '引用图纸': r'\[引用图纸:\s*([^\]]+)\]',
        '参考文档': r'\[参考文档:\s*([^\]]+)\]'
    }
    
    # 构建新的参考依据部分
    new_reference_lines = ["## 📚 参考依据"]
    
    for category_name, pattern in categories.items():
        match = re.search(pattern, reference_content)
        if match:
            value = match.group(1).strip()
            if value and value != "无":
                new_reference_lines.append(f"**{category_name}**: {value}")
    
    # 如果没有任何有效的参考依据，保持原样
    if len(new_reference_lines) == 1:
        return answer
    
    # 替换原来的参考依据部分
    new_reference_section = "\n".join(new_reference_lines)
    
    # 替换答案中的参考依据部分
    new_answer = re.sub(
        r'📚\s*\*\*参考依据\*\*.*?(?=\n\n|$)', 
        new_reference_section, 
        answer, 
        flags=re.DOTALL
    )
    
    return new_answer

def smart_filter_standards(answer: str, standards: List) -> List:
    """智能过滤标准：基于答案内容过滤出真正相关的标准"""
    if not standards:
        return []
    
    # 不相关的标准关键词
    irrelevant_keywords = [
        "水效限定值", "水效等级", "坐便器", "蹲便器", "小便器", 
        "便器冲洗阀", "节水", "用水量", "冲洗功能"
    ]
    
    # 相关的标准关键词
    relevant_keywords = [
        "应急避难场所", "地震应急", "应急厕所", "避难场所", 
        "场址及配套设施", "21734"
    ]
    
    filtered = []
    for standard in standards:
        standard_name = standard.standard_name.lower()
        
        # 检查是否包含不相关关键词
        is_irrelevant = any(keyword in standard_name for keyword in irrelevant_keywords)
        
        # 检查是否包含相关关键词
        is_relevant = any(keyword in standard_name.lower() for keyword in relevant_keywords)
        
        # 检查答案中是否直接提及该标准
        answer_lower = answer.lower()
        standard_mentioned = (
            standard.standard_number.lower() in answer_lower or
            standard.standard_number.replace("-", "").replace(" ", "").lower() in answer_lower.replace("-", "").replace(" ", "")
        )
        
        # 决策逻辑：
        # 1. 如果在答案中被明确提及，则包含
        # 2. 如果包含相关关键词且不包含不相关关键词，则包含
        # 3. 如果包含不相关关键词，则排除
        if standard_mentioned or (is_relevant and not is_irrelevant):
            filtered.append(standard)
        elif is_irrelevant:
            # 明确排除不相关的标准
            logger.info(f"过滤掉不相关标准: {standard.standard_number} - {standard.standard_name}")
            continue
    
    # 如果过滤后没有标准，保留第一个（通常是最相关的）
    if not filtered and standards:
        filtered = [standards[0]]
    
    # 最多返回2个标准以避免信息过载
    return filtered[:2]

@app.on_event("startup")
async def startup_event():
    """应用启动时的初始化"""
    logger.info("工程监理智能问答系统启动中...")
    
    # 显示当前知识库信息
    try:
        info = kb_manager.get_collection_info()
        logger.info(f"📚 当前知识库: {KNOWLEDGE_BASES[DEFAULT_COLLECTION]} ({DEFAULT_COLLECTION})")
        logger.info(f"📊 文档数量: {info.get('count', 0)} 个")
        logger.info(f"🤖 向量模型: {info.get('embedding_model', 'unknown')}")
        logger.info(f"📐 向量维度: {info.get('embedding_dimension', 0)}")
    except Exception as e:
        logger.error(f"获取知识库信息失败: {e}")
    
    # 显示MySQL标准库状态
    if standards_service:
        logger.info("✅ MySQL标准数据库集成已启用")
    else:
        logger.warning("⚠️ MySQL标准数据库集成未启用")
    
    logger.info("系统启动完成")

@app.get("/", response_class=FileResponse)
async def get_homepage():
    """返回主页"""
    return FileResponse("static/index.html")

@app.get("/admin", response_class=FileResponse)
async def get_admin_page():
    """返回管理页面"""
    return FileResponse("static/admin.html")

@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """处理用户问题"""
    try:
        logger.info(f"收到问题: {request.question}")
        
        # 初始化所有知识库管理器
        standards_kb_manager = KnowledgeBaseManager(
            api_key=config.bigmodel_api_key,
            collection_name="standards"
        )
        regulations_kb_manager = KnowledgeBaseManager(
            api_key=config.bigmodel_api_key,
            collection_name="regulations"
        )
        
        # 步骤1: 直接使用用户问题检索知识库（不添加额外内容）
        user_question = request.question
        
        # 步骤2: 检索所有知识库
        all_results = []
        seen_content = set()  # 避免重复内容
        
        logger.info("🔍 开始检索所有知识库...")
        
        # 搜索国家标准库
        logger.info(f"📊 搜索standards库: {user_question}")
        standards_result = standards_kb_manager.search(user_question, n_results=config.MAX_RETRIEVAL_RESULTS)
        
        if standards_result and "results" in standards_result:
            for result in standards_result["results"]:
                content_hash = hash(result['content'][:100])
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    result['source_type'] = 'standards'
                    all_results.append(result)
        
        # 搜索法规库
        logger.info(f"🏛️ 搜索regulations库: {user_question}")
        regulations_result = regulations_kb_manager.search(user_question, n_results=config.MAX_RETRIEVAL_RESULTS)
        
        if regulations_result and "results" in regulations_result:
            for result in regulations_result["results"]:
                content_hash = hash(result['content'][:100])
                if content_hash not in seen_content:
                    seen_content.add(content_hash)
                    result['source_type'] = 'regulations'
                    all_results.append(result)
        
        # 搜索图纸知识库
        if drawing_service and drawing_service.drawings_kb:
            try:
                logger.info(f"📋 搜索drawings库: {user_question}")
                drawings_result = drawing_service.drawings_kb.search(user_question, n_results=config.MAX_RETRIEVAL_RESULTS)
                
                if drawings_result and "results" in drawings_result:
                    for result in drawings_result["results"]:
                        content_hash = hash(result['content'][:100])
                        if content_hash not in seen_content:
                            seen_content.add(content_hash)
                            result['source_type'] = 'drawings'
                            all_results.append(result)
            except Exception as e:
                logger.warning(f"图纸知识库搜索失败: {e}")
        
        # 按相似度排序并取前N个结果
        all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        final_results = all_results[:config.MAX_RETRIEVAL_RESULTS * 2]
        
        # 包装为标准格式
        sources_result = {"results": final_results}
        
        # 处理搜索结果并应用相似度阈值过滤
        sources = []
        if sources_result and "results" in sources_result:
            for result in sources_result["results"]:
                similarity = result.get('similarity', 0)
                if similarity >= config.SIMILARITY_THRESHOLD:
                    # 创建兼容DocumentSource模型的对象
                    from core.models import DocumentSource
                    
                    metadata = result.get('metadata', {})
                    source_obj = DocumentSource(
                        title=metadata.get('standard_number', '未知标准'),
                        content=result['content'],
                        source=metadata.get('source_file', '未知文件'),
                        similarity=similarity,
                        metadata=metadata,
                        file_name=metadata.get('source_file', '未知文件'),
                        regulation_code=metadata.get('standard_number', ''),
                        section=f"块{metadata.get('chunk_index', 0)}",
                        similarity_score=similarity
                    )
                    sources.append(source_obj)
        
        if not sources:
            logger.warning(f"知识库中未找到相关文档（阈值: {config.SIMILARITY_THRESHOLD}），使用模型通用知识回答")
            # 当知识库中没有检索到相关内容时，让大模型基于自身知识生成答案
            return llm_service.generate_answer_without_context(request.question)
        
        # 获取会话历史
        session_id = request.session_id or "default"
        history = session_history.get(session_id, [])
        
        # 步骤3: 大模型生成答案
        response = llm_service.generate_answer(
            question=request.question,
            sources=sources,
            context_history=history
        )
        
                # 步骤4: 根据答案中的结构化参考依据检索URL
        related_standards = []
        related_regulations = []
        related_drawings = []
        
        if standards_service:
            try:
                logger.info("🔍 根据结构化参考依据检索相关URL...")
                answer_text = response.answer
                
                # 提取结构化参考依据
                import re
                reference_section_pattern = r'📚\s*\*\*参考依据\*\*\s*(.*?)(?:\n\n|$)'
                reference_match = re.search(reference_section_pattern, answer_text, re.DOTALL)
                
                if reference_match:
                    reference_content = reference_match.group(1).strip()
                    logger.info(f"📚 找到参考依据部分: {reference_content}")
                    
                    # 4.1 提取并检索标准URL
                    standard_pattern = r'\[使用标准:\s*([^\]]+)\]'
                    standard_match = re.search(standard_pattern, reference_content)
                    if standard_match:
                        standards_text = standard_match.group(1).strip()
                        if standards_text and standards_text != "无":
                            standard_refs = [s.strip() for s in standards_text.split(',') if s.strip()]
                            logger.info(f"📊 提取到标准引用: {standard_refs}")
                            for ref in standard_refs:
                                standards = standards_service.search_standards_by_name(ref, 2)
                                related_standards.extend(standards)
                    
                    # 4.2 提取并检索法规URL
                    regulation_pattern = r'\[引用法规:\s*([^\]]+)\]'
                    regulation_match = re.search(regulation_pattern, reference_content)
                    if regulation_match:
                        regulations_text = regulation_match.group(1).strip()
                        if regulations_text and regulations_text != "无":
                            regulation_refs = [r.strip() for r in regulations_text.split(',') if r.strip()]
                            logger.info(f"🏛️ 提取到法规引用: {regulation_refs}")
                            # 基于法规名称检索
                            regulations = standards_service.find_regulation_by_content_keywords(' '.join(regulation_refs))
                            related_regulations.extend(regulations)
                    
                    # 4.3 提取并检索图纸URL
                    drawing_pattern = r'\[引用图纸:\s*([^\]]+)\]'
                    drawing_match = re.search(drawing_pattern, reference_content)
                    if drawing_match:
                        drawings_text = drawing_match.group(1).strip()
                        if drawings_text and drawings_text != "无":
                            drawing_refs = [d.strip() for d in drawings_text.split(',') if d.strip()]
                            logger.info(f"📐 提取到图纸引用: {drawing_refs}")
                            
                            if drawing_service:
                                drawings = drawing_service.get_drawings_list(limit=50)
                                for drawing_ref in drawing_refs:
                                    for drawing_info in drawings:
                                        drawing_db_name = drawing_info.get('drawing_name', '')
                                        original_filename = drawing_info.get('original_filename', '')
                                        
                                        # 精确匹配或包含匹配
                                        if (drawing_ref in drawing_db_name or 
                                            drawing_db_name in drawing_ref or
                                            drawing_ref in original_filename):
                                            related_drawings.append(drawing_info)
                                            logger.info(f"✅ 匹配到图纸: {drawing_db_name}")
                                            break
                    
                    # 4.4 提取并检索参考文档URL（也作为图纸检索）
                    document_pattern = r'\[参考文档:\s*([^\]]+)\]'
                    document_match = re.search(document_pattern, reference_content)
                    if document_match:
                        documents_text = document_match.group(1).strip()
                        if documents_text and documents_text != "无":
                            document_refs = [d.strip() for d in documents_text.split(',') if d.strip()]
                            logger.info(f"📄 提取到文档引用: {document_refs}")
                            
                            # 检查参考文档中是否包含法规（兼容处理）
                            regulation_keywords = ['办法', '规定', '条例', '法律', '法规', '暂行规定', '管理规定']
                            potential_regulations = []
                            technical_documents = []
                            
                            for doc_ref in document_refs:
                                if any(keyword in doc_ref for keyword in regulation_keywords):
                                    potential_regulations.append(doc_ref)
                                    logger.info(f"🏛️ 在参考文档中发现法规: {doc_ref}")
                                else:
                                    technical_documents.append(doc_ref)
                            
                            # 检索法规URL
                            if potential_regulations:
                                regulations = standards_service.find_regulation_by_content_keywords(' '.join(potential_regulations))
                                related_regulations.extend(regulations)
                            
                            # 检索技术文档URL（作为图纸检索）
                            if technical_documents and drawing_service:
                                drawings = drawing_service.get_drawings_list(limit=50)
                                for doc_ref in technical_documents:
                                    for drawing_info in drawings:
                                        drawing_db_name = drawing_info.get('drawing_name', '')
                                        original_filename = drawing_info.get('original_filename', '')
                                        
                                        # 精确匹配或包含匹配
                                        if (doc_ref in drawing_db_name or 
                                            drawing_db_name in doc_ref or
                                            doc_ref in original_filename):
                                            related_drawings.append(drawing_info)
                                            logger.info(f"✅ 匹配到参考文档: {drawing_db_name}")
                                            break
                
                else:
                    # 兼容旧格式
                    logger.info("📚 未找到新格式参考依据，使用兼容模式...")
                    standard_refs = standards_service.extract_standard_references(answer_text)
                    if standard_refs:
                        logger.info(f"📊 在答案中发现标准引用: {standard_refs}")
                        for ref in standard_refs:
                            standards = standards_service.search_standards_by_name(ref, 2)
                            related_standards.extend(standards)
                
                # 去重
                related_drawings = list({d.get('drawing_name', ''): d for d in related_drawings}.values())
                
                # 记录找到的资源
                if related_standards:
                    logger.info(f"✅ 找到 {len(related_standards)} 个相关标准")
                if related_regulations:
                    logger.info(f"✅ 找到 {len(related_regulations)} 个相关法规")
                if related_drawings:
                    logger.info(f"✅ 找到 {len(related_drawings)} 个相关图纸")
                    
            except Exception as e:
                logger.error(f"查询数据库失败: {e}")
        
        # 步骤5: 将URL添加到答案中
        url_info = ""
        
        # 添加标准URL
        if related_standards:
            url_info += "\n\n## 📋 相关国家标准\n"
            for standard in related_standards[:3]:  # 最多3个
                url_info += f"• **{standard.standard_number}**: {standard.standard_name}\n"
                if standard.file_url:
                    url_info += f"  📄 [查看标准文档]({standard.file_url})\n"
                url_info += "\n"
        
        # 添加法规URL
        if related_regulations:
            url_info += "\n## 🏛️ 相关法规\n"
            for regulation in related_regulations[:2]:  # 最多2个
                url_info += f"• **{regulation.legal_name}**\n"
                if regulation.legal_url:
                    url_info += f"  📄 [查看法规文档]({regulation.legal_url})\n"
                url_info += "\n"
        
        # 添加图纸URL
        if related_drawings:
            url_info += "\n## 📐 相关图纸\n"
            for drawing in related_drawings[:3]:  # 最多3个
                drawing_name = drawing.get('drawing_name', '未知图纸')
                url_info += f"• **{drawing_name}**\n"
                if drawing.get('minio_url'):
                    url_info += f"  📄 [查看图纸]({drawing.get('minio_url')})\n"
                url_info += "\n"
        
        # 优化参考依据显示（隐藏"无"的类别）
        response.answer = optimize_reference_display(response.answer)
        
        # 将URL信息添加到答案中
        if url_info:
            response.answer += url_info
        
        # 更新会话历史
        history.append({"role": "user", "content": request.question})
        history.append({"role": "assistant", "content": response.answer})
        session_history[session_id] = history[-10:]  # 只保留最近10轮对话
        
        response.session_id = session_id
        
        logger.info(f"生成答案完成，可信度: {response.confidence_score:.2f}")
        return response
        
    except Exception as e:
        logger.error(f"处理问题失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    title: str = Form(...),
    document_type: str = Form("regulation")
):
    """上传文档到知识库"""
    try:
        # 检查文件类型
        if not any(file.filename.endswith(ext) for ext in config.SUPPORTED_FILE_TYPES):
            raise HTTPException(
                status_code=400, 
                detail=f"不支持的文件类型。支持的类型: {config.SUPPORTED_FILE_TYPES}"
            )
        
        # 读取文件内容
        content = await file.read()
        content_str = content.decode('utf-8', errors='ignore')
        
        # 创建文档对象
        document = KnowledgeDocument(
            id=str(uuid.uuid4()),
            title=title,
            content=content_str,
            file_path=file.filename,
            file_type=file.filename.split('.')[-1],
            document_type=document_type,
            upload_time=datetime.now(),
            last_updated=datetime.now()
        )
        
        # 添加到知识库
        success = kb_manager.add_document(document)
        
        if success:
            return {"message": "文档上传成功", "document_id": document.id}
        else:
            raise HTTPException(status_code=500, detail="文档上传失败")
            
    except Exception as e:
        logger.error(f"文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/upload-batch")
async def upload_documents_batch(
    files: List[UploadFile] = File(...),
    chunk_size: int = Form(800),
    chunk_overlap: int = Form(100)
):
    """批量上传文档到知识库（增量添加）"""
    try:
        if len(files) > 20:  # 限制单次上传文件数量
            raise HTTPException(status_code=400, detail="单次最多上传20个文件")
        
        results = []
        total_chunks = 0
        
        for file in files:
            # 检查文件类型
            if not any(file.filename.endswith(ext) for ext in config.SUPPORTED_FILE_TYPES):
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": f"不支持的文件类型"
                })
                continue
            
            try:
                # 读取文件内容
                content = await file.read()
                content_str = content.decode('utf-8', errors='ignore')
                
                # 分割文档
                chunks = kb_manager.split_document(content_str, chunk_size, chunk_overlap)
                
                # 准备元数据
                metadatas = []
                for i, chunk in enumerate(chunks):
                    metadata = {
                        "source_file": file.filename,
                        "chunk_index": i,
                        "chunk_count": len(chunks),
                        "document_type": "uploaded",
                        "upload_time": datetime.now().isoformat()
                    }
                    metadatas.append(metadata)
                
                # 批量添加到知识库
                doc_ids = kb_manager.add_documents_batch(chunks, metadatas)
                
                results.append({
                    "filename": file.filename,
                    "status": "success",
                    "chunks_added": len(doc_ids),
                    "document_ids": doc_ids[:5]  # 只返回前5个ID
                })
                
                total_chunks += len(chunks)
                
            except Exception as e:
                results.append({
                    "filename": file.filename,
                    "status": "failed",
                    "error": str(e)
                })
        
        # 获取更新后的知识库统计
        kb_stats = kb_manager.get_knowledge_base_stats()
        
        return {
            "message": f"批量上传完成，共添加 {total_chunks} 个文档块",
            "total_chunks_added": total_chunks,
            "files_processed": len(files),
            "results": results,
            "knowledge_base_stats": kb_stats
        }
        
    except Exception as e:
        logger.error(f"批量文档上传失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/add-text")
async def add_text_to_knowledge_base(
    request: dict
):
    """直接添加文本到知识库（增量添加）"""
    try:
        text_content = request.get("content", "").strip()
        title = request.get("title", "手动添加的文本")
        document_type = request.get("document_type", "manual")
        chunk_size = request.get("chunk_size", 800)
        chunk_overlap = request.get("chunk_overlap", 100)
        
        if not text_content:
            raise HTTPException(status_code=400, detail="文本内容不能为空")
        
        if len(text_content) > 50000:  # 限制单次添加的文本长度
            raise HTTPException(status_code=400, detail="单次添加的文本长度不能超过50000字符")
        
        # 分割文档
        chunks = kb_manager.split_document(text_content, chunk_size, chunk_overlap)
        
        # 准备元数据
        metadatas = []
        for i, chunk in enumerate(chunks):
            metadata = {
                "source_file": title,
                "chunk_index": i,
                "chunk_count": len(chunks),
                "document_type": document_type,
                "add_time": datetime.now().isoformat(),
                "content_length": len(chunk)
            }
            metadatas.append(metadata)
        
        # 批量添加到知识库
        doc_ids = kb_manager.add_documents_batch(chunks, metadatas)
        
        # 获取更新后的知识库统计
        kb_stats = kb_manager.get_knowledge_base_stats()
        
        return {
            "message": f"成功添加文本，共分割为 {len(chunks)} 个文档块",
            "title": title,
            "chunks_added": len(chunks),
            "document_ids": doc_ids,
            "knowledge_base_stats": kb_stats
        }
        
    except Exception as e:
        logger.error(f"添加文本到知识库失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/remove-documents")
async def remove_documents_by_source(
    source_file: str
):
    """根据来源文件删除文档（用于更新文档）"""
    try:
        # 这个功能需要在BigModelKnowledgeBase中实现
        # 目前ChromaDB支持根据metadata过滤删除
        removed_count = kb_manager.remove_documents_by_source(source_file)
        
        kb_stats = kb_manager.get_knowledge_base_stats()
        
        return {
            "message": f"成功删除来源为 '{source_file}' 的文档",
            "removed_count": removed_count,
            "knowledge_base_stats": kb_stats
        }
        
    except Exception as e:
        logger.error(f"删除文档失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/status", response_model=SystemStatus)
async def get_system_status():
    """获取系统状态"""
    try:
        stats = kb_manager.get_knowledge_base_stats()
        
        return SystemStatus(
            status="正常运行",
            knowledge_base_stats=stats,
            llm_service_status="正常",
            uptime="运行中"
        )
        
    except Exception as e:
        logger.error(f"获取系统状态失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/search")
async def search_knowledge_base(query: str, top_k: int = 5):
    """搜索当前知识库"""
    try:
        sources_result = kb_manager.search(query, n_results=top_k)
        
        results = []
        if sources_result and "results" in sources_result:
            for result in sources_result["results"]:
                results.append({
                    "content": result['content'][:200] + "..." if len(result['content']) > 200 else result['content'],
                    "file_name": result.get('metadata', {}).get('source_file', '未知文件'),
                    "standard_number": result.get('metadata', {}).get('standard_number', ''),
                    "document_type": result.get('metadata', {}).get('document_type', ''),
                    "similarity_score": result.get('similarity', 0)
                })
        
        return {
            "query": query,
            "collection": DEFAULT_COLLECTION,
            "collection_name": KNOWLEDGE_BASES[DEFAULT_COLLECTION],
            "results": results
        }
        
    except Exception as e:
        logger.error(f"知识库搜索失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/knowledge-bases")
async def get_knowledge_bases():
    """获取可用的知识库列表"""
    try:
        # 检查每个知识库的状态
        kb_status = {}
        for kb_id, kb_name in KNOWLEDGE_BASES.items():
            try:
                # 临时创建知识库管理器检查状态
                temp_kb = KnowledgeBaseManager(
                    api_key=config.bigmodel_api_key,
                    collection_name=kb_id
                )
                info = temp_kb.get_collection_info()
                kb_status[kb_id] = {
                    "name": kb_name,
                    "status": "available",
                    "document_count": info.get('count', 0),
                    "is_current": kb_id == DEFAULT_COLLECTION
                }
            except Exception as e:
                kb_status[kb_id] = {
                    "name": kb_name,
                    "status": "not_available",
                    "document_count": 0,
                    "is_current": kb_id == DEFAULT_COLLECTION,
                    "error": str(e)
                }
        
        return {
            "current_collection": DEFAULT_COLLECTION,
            "knowledge_bases": kb_status
        }
        
    except Exception as e:
        logger.error(f"获取知识库列表失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/switch-knowledge-base")
async def switch_knowledge_base(request: dict):
    """切换知识库"""
    global kb_manager, DEFAULT_COLLECTION
    
    # 处理请求参数
    if isinstance(request, str):
        collection_name = request
    else:
        collection_name = request.get("collection_name") or request
    
    if collection_name not in KNOWLEDGE_BASES:
        raise HTTPException(
            status_code=400, 
            detail=f"未知的知识库: {collection_name}. 可用的知识库: {list(KNOWLEDGE_BASES.keys())}"
        )
    
    try:
        # 创建新的知识库管理器
        new_kb_manager = KnowledgeBaseManager(
            api_key=config.bigmodel_api_key,
            collection_name=collection_name
        )
        
        # 测试新知识库是否可用
        info = new_kb_manager.get_collection_info()
        
        # 切换成功
        kb_manager = new_kb_manager
        DEFAULT_COLLECTION = collection_name
        
        logger.info(f"成功切换到知识库: {collection_name} ({KNOWLEDGE_BASES[collection_name]})")
        
        return {
            "message": f"已切换到 {KNOWLEDGE_BASES[collection_name]}",
            "collection": collection_name,
            "document_count": info.get('count', 0),
            "embedding_model": info.get('embedding_model', ''),
            "embedding_dimension": info.get('embedding_dimension', 0)
        }
        
    except Exception as e:
        logger.error(f"切换知识库失败: {e}")
        raise HTTPException(status_code=500, detail=f"切换知识库失败: {str(e)}")

@app.post("/upload-drawing")
async def upload_project_drawing(
    file: UploadFile = File(...),
    project_name: str = Form(None),
    drawing_type: str = Form(None),
    drawing_phase: str = Form(None),
    created_by: str = Form(None),
    force_upload: bool = Form(False)
):
    """
    上传项目图纸PDF文档
    支持：重复检测、上传到MinIO、记录到MySQL、Gemini文本提取、向量化存储
    """
    if not drawing_service:
        raise HTTPException(status_code=500, detail="图纸上传服务未初始化")
    
    # 验证文件类型
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(status_code=400, detail="只支持PDF格式的图纸文件")
    
    # 验证文件大小（限制为100MB）
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    file_content = await file.read()
    if len(file_content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件太大，最大支持100MB")
    
    try:
        logger.info(f"📋 开始处理图纸上传: {file.filename}")
        
        # 处理图纸上传
        result = drawing_service.process_drawing_upload(
            file_bytes=file_content,
            original_filename=file.filename,
            project_name=project_name,
            drawing_type=drawing_type,
            drawing_phase=drawing_phase,
            created_by=created_by,
            force_upload=force_upload
        )
        
        if result.get("success"):
            return {
                "message": "图纸上传和处理成功",
                "drawing_id": result["drawing_id"],
                "drawing_name": result["drawing_name"],
                "original_filename": result["original_filename"],
                "minio_url": result["minio_url"],
                "vector_chunks_count": result["vector_chunks_count"],
                "process_status": result["process_status"],
                "vector_status": result["vector_status"],
                "file_size_mb": round(len(file_content) / 1024 / 1024, 2),
                "knowledge_base": "drawings"
            }
        elif result.get("is_duplicate"):
            # 返回重复文件信息，让前端处理
            return {
                "message": "检测到重复文件",
                "is_duplicate": True,
                "existing_file": result["existing_file"],
                "duplicate_message": result["message"]
            }
        else:
            raise HTTPException(
                status_code=500, 
                detail=f"图纸处理失败: {result.get('error', '未知错误')}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 图纸上传失败: {e}")
        raise HTTPException(status_code=500, detail=f"图纸上传失败: {str(e)}")

@app.get("/drawings")
async def get_drawings_list(
    project_name: str = None,
    drawing_type: str = None,
    limit: int = 50
):
    """获取图纸列表"""
    if not drawing_service:
        raise HTTPException(status_code=500, detail="图纸上传服务未初始化")
    
    try:
        drawings = drawing_service.get_drawings_list(
            project_name=project_name,
            drawing_type=drawing_type,
            limit=limit
        )
        
        return {
            "message": "获取图纸列表成功",
            "count": len(drawings),
            "drawings": drawings,
            "filters": {
                "project_name": project_name,
                "drawing_type": drawing_type,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 获取图纸列表失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图纸列表失败: {str(e)}")

@app.get("/search-drawings")
async def search_project_drawings(
    query: str,
    top_k: int = 5,
    project_name: str = None,
    drawing_type: str = None
):
    """在图纸向量数据库中搜索相关内容"""
    if not drawing_service:
        raise HTTPException(status_code=500, detail="图纸上传服务未初始化")
    
    try:
        results = drawing_service.search_drawings_in_vector_db(
            query=query,
            top_k=top_k,
            project_name=project_name,
            drawing_type=drawing_type
        )
        
        return {
            "message": "图纸搜索完成",
            "query": query,
            "results_count": len(results),
            "results": results,
            "filters": {
                "project_name": project_name,
                "drawing_type": drawing_type,
                "top_k": top_k
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 图纸搜索失败: {e}")
        raise HTTPException(status_code=500, detail=f"图纸搜索失败: {str(e)}")

@app.get("/drawings-stats")
async def get_drawings_statistics():
    """获取图纸统计信息"""
    if not drawing_service:
        raise HTTPException(status_code=500, detail="图纸上传服务未初始化")
    
    try:
        # 获取向量知识库统计
        kb_stats = drawing_service.drawings_kb.get_knowledge_base_stats()
        
        # 获取MySQL数据库统计
        connection = drawing_service._get_mysql_connection()
        try:
            with connection.cursor() as cursor:
                # 总图纸数量
                cursor.execute("SELECT COUNT(*) as total FROM project_drawings")
                total_count = cursor.fetchone()["total"]
                
                # 按项目分组统计
                cursor.execute("""
                    SELECT project_name, COUNT(*) as count 
                    FROM project_drawings 
                    WHERE project_name IS NOT NULL 
                    GROUP BY project_name 
                    ORDER BY count DESC 
                    LIMIT 10
                """)
                project_stats = cursor.fetchall()
                
                # 按图纸类型分组统计
                cursor.execute("""
                    SELECT drawing_type, COUNT(*) as count 
                    FROM project_drawings 
                    WHERE drawing_type IS NOT NULL 
                    GROUP BY drawing_type 
                    ORDER BY count DESC
                """)
                type_stats = cursor.fetchall()
                
                # 按状态统计
                cursor.execute("""
                    SELECT 
                        process_status,
                        vector_status,
                        COUNT(*) as count 
                    FROM project_drawings 
                    GROUP BY process_status, vector_status
                """)
                status_stats = cursor.fetchall()
                
        finally:
            connection.close()
        
        return {
            "message": "图纸统计信息获取成功",
            "mysql_stats": {
                "total_drawings": total_count,
                "project_distribution": project_stats,
                "type_distribution": type_stats,
                "status_distribution": status_stats
            },
            "vector_kb_stats": kb_stats,
            "knowledge_base_name": "drawings"
        }
        
    except Exception as e:
        logger.error(f"❌ 获取图纸统计失败: {e}")
        raise HTTPException(status_code=500, detail=f"获取图纸统计失败: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info"
    ) 