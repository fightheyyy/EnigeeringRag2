from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
from datetime import datetime
import uuid
import logging
import os
import re
from typing import List, Optional

from core.config import Config
from core.models import QuestionRequest, AnswerResponse, KnowledgeDocument, SystemStatus  
from services.bigmodel_knowledge_base import BigModelKnowledgeBase as KnowledgeBaseManager
from services.llm_service import LLMService, enhance_engineering_question
from services.mysql_standards_service import get_mysql_standards_service

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
        
        # 增强问题表述
        enhanced_question = enhance_engineering_question(request.question)
        
        # 多重检索策略：使用多个查询词提高检索准确性
        search_queries = [enhanced_question]
        
        # 针对特定问题添加替代查询词
        original_q = request.question.lower()
        if "应急厕所" in original_q and "距离" in original_q:
            search_queries.extend([
                "应急厕所设置要求",
                "6.1.6 应急厕所",
                "应急避难场所厕所设置",
                "GB 21734 应急厕所",
                "篷宿区厕所距离"
            ])
        elif "厕所" in original_q and ("间距" in original_q or "距离" in original_q):
            search_queries.extend([
                "应急厕所设置要求",
                "厕所布局要求"
            ])
        
        # 执行多重检索并合并结果（同时搜索所有知识库）
        all_results = []
        seen_content = set()  # 避免重复内容
        
        logger.info("🔍 开始检索所有知识库...")
        
        for query in search_queries:
            # 搜索国家标准库
            logger.info(f"📊 搜索standards库: {query}")
            standards_result = standards_kb_manager.search(query, n_results=config.MAX_RETRIEVAL_RESULTS)
            
            if standards_result and "results" in standards_result:
                for result in standards_result["results"]:
                    content_hash = hash(result['content'][:100])
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        # 标记来源为standards
                        result['source_type'] = 'standards'
                        all_results.append(result)
            
            # 搜索法规库
            logger.info(f"🏛️ 搜索regulations库: {query}")
            regulations_result = regulations_kb_manager.search(query, n_results=config.MAX_RETRIEVAL_RESULTS)
            
            if regulations_result and "results" in regulations_result:
                for result in regulations_result["results"]:
                    content_hash = hash(result['content'][:100])
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
                        # 标记来源为regulations
                        result['source_type'] = 'regulations'
                        all_results.append(result)
        
        # 按相似度排序并取前N个结果
        all_results.sort(key=lambda x: x.get('similarity', 0), reverse=True)
        final_results = all_results[:config.MAX_RETRIEVAL_RESULTS * 2]  # 允许更多结果用于过滤
        
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
        
        # 生成答案
        response = llm_service.generate_answer(
            question=request.question,
            sources=sources,
            context_history=history
        )
        
        # 根据大模型答案中的引用查询MySQL数据库获取URL
        related_standards = []
        related_regulations = []
        
        if standards_service:
            try:
                logger.info("🔍 分析大模型答案中的引用...")
                
                # 从答案中提取标准引用
                answer_text = response.answer
                standard_refs = standards_service.extract_standard_references(answer_text)
                
                if standard_refs:
                    logger.info(f"📊 在答案中发现标准引用: {standard_refs}")
                    for ref in standard_refs:
                        standards = standards_service.search_standards_by_name(ref, 2)
                        related_standards.extend(standards)
                
                # 检查答案中是否包含法规相关内容
                regulation_keywords = [
                    '管理办法', '规定', '条例', '暂行办法', '住宅专项维修资金',
                    '售房单位', '售房款', '多层住宅', '高层住宅', '第八条'
                ]
                
                has_regulation_content = any(keyword in answer_text for keyword in regulation_keywords)
                
                if has_regulation_content:
                    logger.info("🏛️ 答案涉及法规内容，查询regulations表...")
                    question_content = request.question
                    combined_content = question_content + " " + answer_text[:500]  # 结合问题和答案前500字符
                    regulations = standards_service.find_regulation_by_content_keywords(combined_content)
                    related_regulations = regulations
                
                # 去重标准
                if related_standards:
                    seen_ids = set()
                    unique_standards = []
                    for standard in related_standards:
                        if standard.id not in seen_ids:
                            seen_ids.add(standard.id)
                            unique_standards.append(standard)
                    related_standards = unique_standards[:3]
                
                # 记录找到的资源
                if related_standards:
                    logger.info(f"✅ 找到 {len(related_standards)} 个相关标准:")
                    for std in related_standards:
                        logger.info(f"  - {std.standard_number}: {std.standard_name}")
                        logger.info(f"    URL: {std.file_url}")
                
                if related_regulations:
                    logger.info(f"✅ 找到 {len(related_regulations)} 个相关法规:")
                    for reg in related_regulations:
                        logger.info(f"  - {reg.legal_name}")
                        logger.info(f"    URL: {reg.legal_url}")
                    
            except Exception as e:
                logger.error(f"查询MySQL数据库失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 检查答案是否真正回答了问题（内容相关性检查）
        # 只有在确实没有检索到任何相关内容时才回退
        critical_irrelevant_patterns = [
            "根据提供的规范文档内容，未检索到",
            "提供的文档中没有找到",
            "文档中未包含相关信息",
            "[使用标准: 无]"
        ]
        
        # 检查是否是完全无关的回答（更严格的条件）
        is_completely_irrelevant = any(pattern in response.answer for pattern in critical_irrelevant_patterns)
        
        # 如果找到了相关的标准或法规，即使答案中有"未找到"等词汇，也不应该回退
        has_relevant_resources = (len(related_standards) > 0 or len(related_regulations) > 0)
        
        if is_completely_irrelevant and not has_relevant_resources:
            logger.warning("检索到的文档内容与问题不够相关，回退到模型知识回答")
            response = llm_service.generate_answer_without_context(request.question)
            
            # 为回退答案添加会话历史
            history.append({"role": "user", "content": request.question})
            history.append({"role": "assistant", "content": response.answer})
            session_history[session_id] = history[-10:]
            response.session_id = session_id
            
            return response
        
        # 提取答案中实际使用的标准并过滤相关标准列表
        filtered_standards = []
        if related_standards:
            # 从答案中提取DeepSeek标注的使用标准
            used_standards = extract_used_standards_from_answer(response.answer)
            
            if used_standards and "无" not in used_standards:
                # 根据答案中标注的标准过滤相关标准列表
                for standard in related_standards:
                    standard_num = standard.standard_number.replace(" ", "").replace("-", "")
                    for used_std in used_standards:
                        used_std_clean = used_std.replace(" ", "").replace("-", "")
                        if used_std_clean in standard_num or standard_num in used_std_clean:
                            filtered_standards.append(standard)
                            break
            else:
                # 如果没有标注使用标准，使用智能过滤
                filtered_standards = smart_filter_standards(response.answer, related_standards)
            
            # 添加过滤后的标准信息
            if filtered_standards:
                standard_info = "\n\n📋 **相关国家标准：**\n"
                for standard in filtered_standards:
                    standard_info += f"• **{standard.standard_number}**: {standard.standard_name}\n"
                    standard_info += f"  状态: {standard.status}\n"
                    if standard.file_url:
                        standard_info += f"  📄 [查看标准文档]({standard.file_url})\n"
                    standard_info += "\n"
                
                response.answer += standard_info
        
        # 添加相关法规信息
        if related_regulations:
            regulation_info = "\n\n📋 **相关法律法规：**\n"
            for regulation in related_regulations:
                regulation_info += f"• **{regulation.legal_name}**\n"
                if regulation.legal_url:
                    regulation_info += f"  📄 [查看法规文档]({regulation.legal_url})\n"
                regulation_info += "\n"
            
            response.answer += regulation_info
        
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=config.HOST,
        port=config.PORT,
        reload=config.DEBUG,
        log_level="info"
    ) 