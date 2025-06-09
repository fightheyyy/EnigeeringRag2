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

# 初始化服务
config = Config()

# 知识库配置 - 支持多个专门的知识库
KNOWLEDGE_BASES = {
    "standards": "国家标准库",
    "engineering_knowledge_base": "原有工程知识库", 
    "regulations": "法律法规库",  # 预留
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

@app.get("/", response_class=HTMLResponse)
async def get_homepage():
    """返回主页"""
    return """
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>工程监理智能问答系统</title>
        <style>
            * { margin: 0; padding: 0; box-sizing: border-box; }
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f7fa; }
            .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
            .header { text-align: center; margin-bottom: 40px; }
            .header h1 { color: #2c3e50; font-size: 2.5em; margin-bottom: 10px; }
            .header p { color: #7f8c8d; font-size: 1.2em; }
            
            .chat-container { 
                background: white; 
                border-radius: 12px; 
                box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
                overflow: hidden;
                height: 600px;
                display: flex;
                flex-direction: column;
            }
            
            .chat-header { 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                color: white; 
                padding: 20px; 
                text-align: center;
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            
            .kb-selector {
                background: rgba(255,255,255,0.2);
                border: 1px solid rgba(255,255,255,0.3);
                border-radius: 6px;
                color: white;
                padding: 8px 12px;
                font-size: 14px;
                cursor: pointer;
            }
            
            .kb-selector option {
                background: #333;
                color: white;
            }
            
            .chat-messages { 
                flex: 1; 
                padding: 20px; 
                overflow-y: auto; 
                display: flex;
                flex-direction: column;
                gap: 15px;
            }
            
            .message { 
                max-width: 80%; 
                padding: 15px; 
                border-radius: 18px; 
                word-wrap: break-word;
                line-height: 1.4;
            }
            
            .message.user { 
                background: #007bff; 
                color: white; 
                align-self: flex-end; 
                margin-left: auto;
            }
            
            .message.assistant { 
                background: #f8f9fa; 
                color: #333; 
                align-self: flex-start; 
                border: 1px solid #e9ecef;
            }
            
            .sources {
                margin-top: 10px;
                padding: 10px;
                background: #e7f3ff;
                border-radius: 8px;
                font-size: 0.9em;
            }
            
            .source-item {
                margin: 5px 0;
                color: #0066cc;
            }
            
            .standards-section {
                margin-top: 15px;
                padding: 15px;
                background: #f0f8ff;
                border-radius: 8px;
                border-left: 4px solid #007bff;
            }
            
            .standard-item {
                margin: 10px 0;
                padding: 10px;
                background: white;
                border-radius: 6px;
                border: 1px solid #e3f2fd;
            }
            
            .standard-link {
                color: #007bff;
                text-decoration: none;
                font-weight: 500;
            }
            
            .standard-link:hover {
                text-decoration: underline;
            }
            
            .suggestions {
                margin-top: 10px;
                padding: 10px;
                background: #fff3cd;
                border-radius: 8px;
                font-size: 0.9em;
            }
            
            .chat-input { 
                display: flex; 
                padding: 20px; 
                border-top: 1px solid #e9ecef;
                gap: 10px;
            }
            
            .chat-input input { 
                flex: 1; 
                padding: 12px 16px; 
                border: 2px solid #e9ecef; 
                border-radius: 25px; 
                outline: none;
                font-size: 16px;
            }
            
            .chat-input input:focus { 
                border-color: #007bff; 
            }
            
            .chat-input button { 
                padding: 12px 24px; 
                background: #007bff; 
                color: white; 
                border: none; 
                border-radius: 25px; 
                cursor: pointer;
                font-size: 16px;
                transition: background 0.3s;
            }
            
            .chat-input button:hover { 
                background: #0056b3; 
            }
            
            .chat-input button:disabled { 
                background: #6c757d; 
                cursor: not-allowed;
            }
            
            .loading { 
                display: none; 
                color: #6c757d; 
                font-style: italic;
                align-self: flex-start;
            }
            
            .examples {
                margin-top: 30px;
                background: white;
                border-radius: 12px;
                padding: 30px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
            
            .examples h3 {
                color: #2c3e50;
                margin-bottom: 20px;
                text-align: center;
            }
            
            .example-questions {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 15px;
            }
            
            .example-question {
                padding: 15px;
                background: #f8f9fa;
                border-radius: 8px;
                cursor: pointer;
                transition: all 0.3s;
                border: 1px solid #e9ecef;
            }
            
            .example-question:hover {
                background: #e9ecef;
                transform: translateY(-2px);
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🏗️ 工程监理智能问答系统</h1>
                <p>专业的规范查询与图纸解读助手</p>
            </div>
            
            <div class="chat-container">
                <div class="chat-header">
                    <div>
                        <h3>智能助手在线</h3>
                        <p id="headerDescription">我可以帮您查询工程规范、标准和设计图纸信息</p>
                    </div>
                    <div>
                        <select class="kb-selector" id="knowledgeBaseSelector" onchange="switchKnowledgeBase()">
                            <option value="standards">📋 国家标准库</option>
                            <option value="engineering_knowledge_base">📚 工程知识库</option>
                            <option value="regulations">⚖️ 法律法规库</option>
                            <option value="drawings">📐 项目图纸库</option>
                        </select>
                    </div>
                </div>
                
                <div class="chat-messages" id="chatMessages">
                    <div class="message assistant">
                        您好！我是您的工程监理智能助手。我可以帮助您查询：<br>
                        • 国家和地方工程建设规范标准<br>
                        • 项目设计图纸技术要求<br>
                        • 施工质量验收标准<br>
                        • 安全技术规范<br><br>
                        请直接提出您的问题，比如"混凝土保护层厚度要求"或"脚手架连墙件间距规定"。
                    </div>
                </div>
                
                <div class="loading" id="loading">正在查询相关规范和图纸...</div>
                
                <div class="chat-input">
                    <input type="text" id="messageInput" placeholder="请输入您的问题..." />
                    <button onclick="sendMessage()" id="sendButton">发送</button>
                </div>
            </div>
            
            <div class="examples">
                <h3>💡 常见问题示例</h3>
                <div class="example-questions">
                    <div class="example-question" onclick="askExample('混凝土结构保护层最小厚度是多少？')">
                        混凝土结构保护层最小厚度是多少？
                    </div>
                    <div class="example-question" onclick="askExample('脚手架连墙件最大间距要求？')">
                        脚手架连墙件最大间距要求？
                    </div>
                    <div class="example-question" onclick="askExample('钢筋锚固长度如何计算？')">
                        钢筋锚固长度如何计算？
                    </div>
                    <div class="example-question" onclick="askExample('外墙保温材料有什么要求？')">
                        外墙保温材料有什么要求？
                    </div>
                </div>
            </div>
        </div>

        <script>
            let sessionId = 'session_' + Date.now();
            
            function addMessage(content, isUser, sources = null, suggestions = null) {
                const messagesContainer = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${isUser ? 'user' : 'assistant'}`;
                
                let html = content;
                
                if (sources && sources.length > 0) {
                    html += '<div class="sources"><strong>📚 参考来源：</strong>';
                    sources.forEach((source, index) => {
                        html += `<div class="source-item">
                            ${index + 1}. ${source.file_name}
                            ${source.regulation_code ? ' (' + source.regulation_code + ')' : ''}
                            ${source.section ? ' - ' + source.section : ''}
                            (相关度: ${(source.similarity_score * 100).toFixed(1)}%)
                        </div>`;
                    });
                    html += '</div>';
                }
                
                if (suggestions && suggestions.length > 0) {
                    html += '<div class="suggestions"><strong>💭 相关建议：</strong><br>';
                    suggestions.forEach(suggestion => {
                        html += `• ${suggestion}<br>`;
                    });
                    html += '</div>';
                }
                
                messageDiv.innerHTML = html;
                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            async function sendMessage() {
                const input = document.getElementById('messageInput');
                const sendButton = document.getElementById('sendButton');
                const loading = document.getElementById('loading');
                
                const question = input.value.trim();
                if (!question) return;
                
                // 显示用户消息
                addMessage(question, true);
                input.value = '';
                
                // 禁用输入
                sendButton.disabled = true;
                loading.style.display = 'block';
                
                try {
                    const response = await fetch('/ask', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({
                            question: question,
                            session_id: sessionId
                        })
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        addMessage(result.answer, false, result.sources, result.suggestions);
                    } else {
                        addMessage('抱歉，处理您的问题时出现错误：' + result.detail, false);
                    }
                } catch (error) {
                    addMessage('网络错误，请稍后重试', false);
                    console.error('Error:', error);
                } finally {
                    sendButton.disabled = false;
                    loading.style.display = 'none';
                }
            }
            
            function askExample(question) {
                document.getElementById('messageInput').value = question;
                sendMessage();
            }
            
            // 切换知识库
            async function switchKnowledgeBase() {
                const selector = document.getElementById('knowledgeBaseSelector');
                const selectedKB = selector.value;
                const headerDescription = document.getElementById('headerDescription');
                
                try {
                    const response = await fetch('/switch-knowledge-base', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                        },
                        body: JSON.stringify({"collection_name": selectedKB})
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        // 更新界面描述
                        const kbDescriptions = {
                            'standards': '专业的国家标准查询服务 📋',
                            'engineering_knowledge_base': '工程技术知识查询服务 📚',
                            'regulations': '法律法规查询服务 ⚖️',
                            'drawings': '项目图纸查询服务 📐'
                        };
                        
                        headerDescription.textContent = kbDescriptions[selectedKB] || '智能问答服务';
                        
                        // 显示切换成功消息
                        addMessage(`✅ 已切换到 ${result.message}\\n📊 包含 ${result.document_count} 个文档`, false);
                        
                        // 重置session
                        sessionId = 'session_' + Date.now();
                    } else {
                        addMessage(`❌ 切换失败：${result.detail}`, false);
                    }
                } catch (error) {
                    addMessage('切换知识库时发生网络错误', false);
                    console.error('Switch KB Error:', error);
                }
            }
            
            // 页面加载时获取当前知识库状态
            async function loadKnowledgeBases() {
                try {
                    const response = await fetch('/knowledge-bases');
                    const result = await response.json();
                    
                    if (response.ok) {
                        const selector = document.getElementById('knowledgeBaseSelector');
                        selector.value = result.current_collection;
                        
                        // 更新选择器选项状态
                        Array.from(selector.options).forEach(option => {
                            const kbInfo = result.knowledge_bases[option.value];
                            if (kbInfo && kbInfo.status === 'not_available') {
                                option.disabled = true;
                                option.textContent += ' (不可用)';
                            } else if (kbInfo) {
                                option.textContent += ` (${kbInfo.document_count} 文档)`;
                            }
                        });
                    }
                } catch (error) {
                    console.error('Load KB Error:', error);
                }
            }
            
            // 回车发送
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    sendMessage();
                }
            });
            
            // 页面加载完成后初始化
            document.addEventListener('DOMContentLoaded', function() {
                loadKnowledgeBases();
            });
        </script>
    </body>
    </html>
    """

@app.post("/ask", response_model=AnswerResponse)
async def ask_question(request: QuestionRequest):
    """处理用户问题"""
    try:
        logger.info(f"收到问题: {request.question}")
        
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
        
        # 执行多重检索并合并结果
        all_results = []
        seen_content = set()  # 避免重复内容
        
        for query in search_queries:
            sources_result = kb_manager.search(query, n_results=config.MAX_RETRIEVAL_RESULTS)
            
            if sources_result and "results" in sources_result:
                for result in sources_result["results"]:
                    content_hash = hash(result['content'][:100])  # 使用内容前100字符的哈希避免重复
                    if content_hash not in seen_content:
                        seen_content.add(content_hash)
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
        
        # 查询相关标准信息
        related_standards = []
        if standards_service:
            try:
                logger.info(f"开始查询相关标准，检索到 {len(sources)} 个文档片段")
                
                for i, source in enumerate(sources):
                    logger.info(f"处理文档片段 {i+1}/{len(sources)}: {source.metadata.get('standard_number', '未知')}")
                    
                    # 从文档内容和元数据中查找相关标准
                    standards = standards_service.find_standards_for_content(
                        source.content, 
                        source.metadata
                    )
                    logger.info(f"  匹配到 {len(standards)} 个标准")
                    
                    for std in standards:
                        logger.info(f"    - {std.standard_number}: {std.standard_name}")
                        logger.info(f"      URL: {std.file_url}")
                    
                    related_standards.extend(standards)
                
                # 去重
                seen_ids = set()
                unique_standards = []
                for standard in related_standards:
                    if standard.id not in seen_ids:
                        seen_ids.add(standard.id)
                        unique_standards.append(standard)
                related_standards = unique_standards[:3]  # 最多返回3个相关标准
                
                if related_standards:
                    logger.info(f"✅ 最终匹配到 {len(related_standards)} 个相关标准")
                    for std in related_standards:
                        logger.info(f"  - {std.standard_number}: {std.standard_name}")
                        logger.info(f"    URL: {std.file_url}")
                else:
                    logger.warning("❌ 未找到相关标准")
                    
            except Exception as e:
                logger.error(f"查询标准信息失败: {e}")
                import traceback
                traceback.print_exc()
        
        # 生成答案
        response = llm_service.generate_answer(
            question=request.question,
            sources=sources,
            context_history=history
        )
        
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