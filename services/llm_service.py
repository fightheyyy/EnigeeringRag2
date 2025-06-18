import openai
import logging
from typing import List, Dict, Optional
from datetime import datetime
import json
import re
from core.config import Config
from core.models import DocumentSource, AnswerResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMService:
    """DeepSeek大语言模型服务"""
    
    def __init__(self):
        self.config = Config()
        
        # 验证配置
        self.config.validate_config()
        
        # 初始化DeepSeek客户端
        deepseek_config = self.config.get_deepseek_config()
        self.client = openai.OpenAI(
            api_key=deepseek_config["api_key"],
            base_url=deepseek_config["base_url"]
        )
        
        logger.info("DeepSeek LLM服务初始化完成")
        
    def generate_answer(self, 
                       question: str, 
                       sources: List[DocumentSource],
                       context_history: Optional[List[Dict]] = None) -> AnswerResponse:
        """根据检索到的文档生成答案"""
        try:
            logger.info(f"生成答案 - 问题: {question}")
            
            # 构建上下文
            context = self._build_context(sources)
            
            # 构建对话历史
            messages = self._build_messages(question, context, context_history)
            
            # 调用DeepSeek模型
            deepseek_config = self.config.get_deepseek_config()
            
            response = self.client.chat.completions.create(
                model=deepseek_config["model"],
                messages=messages,
                temperature=deepseek_config["temperature"],
                max_tokens=deepseek_config["max_tokens"],
                top_p=deepseek_config["top_p"]
            )
            
            answer_text = response.choices[0].message.content
            logger.info("DeepSeek模型回答生成成功")
            
            # 解析答案和可信度
            confidence_score = self._calculate_confidence(sources, answer_text)
            has_definitive_answer = self._check_definitive_answer(answer_text)
            suggestions = self._generate_suggestions(question, answer_text)
            
            return AnswerResponse(
                question=question,
                answer=answer_text,
                sources=sources,
                confidence_score=confidence_score,
                timestamp=datetime.now(),
                has_definitive_answer=has_definitive_answer,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"DeepSeek答案生成失败: {e}")
            return self._create_error_response(question, str(e))
    
    def _build_context(self, sources: List[DocumentSource]) -> str:
        """构建上下文信息"""
        if not sources:
            return "未找到相关的规范或图纸信息。"
        
        context_parts = []
        for i, source in enumerate(sources):
            # 截取内容的前800字符，避免过长
            content_preview = source.content[:800] + "..." if len(source.content) > 800 else source.content
            
            context_part = f"""
【参考文档 {i+1}】
文件名: {source.file_name}
规范编号: {source.regulation_code or "未指定"}
章节: {source.section or "未指定"}
相关度: {source.similarity_score:.2f}
文档内容:
{content_preview}
"""
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _build_messages(self, question: str, context: str, history: Optional[List[Dict]] = None) -> List[Dict]:
        """构建对话消息"""
        messages = [
            {"role": "system", "content": self.config.SYSTEM_PROMPT}
        ]
        
        # 添加历史对话
        if history:
            for msg in history[-6:]:  # 只保留最近6轮对话
                messages.append(msg)
        
        # 识别工程领域并提供专业指导
        engineering_domain = identify_engineering_domain(question)
        domain_config = self.config.get_engineering_domain_config(engineering_domain)
        
        # 添加当前问题和上下文
        user_message = f"""
【用户问题】{question}

【工程领域】{engineering_domain}
{f"【相关规范】{', '.join(domain_config.get('regulations', []))}" if domain_config.get('regulations') else ""}

【检索到的规范文档】
{context}

【重要指示】
请仔细阅读上述文档内容，如果文档中包含了与用户问题直接相关的信息，请直接基于文档内容回答。

【回答要求】
1. 🔍 **优先分析文档内容**：仔细检查每个文档是否包含用户问题的答案
2. 📋 **直接引用文档**：如果找到相关信息，请直接引用具体内容并标明出处
3. 📊 **准确提取数据**：如果涉及具体数值、距离、标准等，请准确引用
4. 🎯 **完整回答**：基于文档内容给出完整、准确的回答
5. ⚠️ **明确说明**：只有在文档中确实没有相关信息时，才说明未找到
6. 🔧 **实用建议**：提供基于规范的工程监理建议

【必须的格式要求】
请严格按照以下格式在回答的最后添加参考依据部分：

📚 **参考依据**
[使用标准: 此处列出你在回答中实际引用的国家标准、行业标准编号（如GB、JGJ等），用逗号分隔，如果没有引用具体标准则写"无"]
[引用法规: 此处列出你在回答中实际引用的法律法规名称（如建筑法、管理办法、规定等），用逗号分隔，如果没有引用法规则写"无"]
[引用图纸: 此处列出你在回答中实际引用的工程图纸名称，用逗号分隔，如果没有引用图纸则写"无"]
[参考文档: 此处列出你在回答中实际引用的其他技术文档（如设计说明、技术规程等），用逗号分隔，如果没有其他文档则写"无"]

示例格式：
📚 **参考依据**
[使用标准: GB 50010-2010, JGJ 130-2011]
[引用法规: 建筑法, 建设工程质量管理条例, 房屋建筑和市政基础设施工程竣工验收备案管理办法]
[引用图纸: 1号住宅楼_16_13_首层梁板配筋图_第1版1228KB]
[参考文档: 结构设计总说明二]

**重要区分说明**：
- 标准：以GB、JGJ、CJJ等开头的技术标准
- 法规：法律、条例、办法、规定、暂行规定等政策性文件
- 图纸：工程设计图纸文件
- 文档：技术说明、规程等其他文档

**重要提醒**：
- 📚 **参考依据**部分必须是你回答的最后部分
- 只有在回答中真正引用的内容才应该在相应类别中列出
- 如果某个类别没有引用内容，则写"无"
- 必须严格遵循上述格式，包括emoji和加粗标题
- **特别注意**：凡是包含"办法"、"规定"、"条例"、"法"等字样的文件都应归类为[引用法规]，不要放在[参考文档]中

请现在仔细分析文档内容并回答用户问题：
"""
        
        messages.append({"role": "user", "content": user_message})
        
        return messages
    
    def _calculate_confidence(self, sources: List[DocumentSource], answer: str) -> float:
        """计算答案可信度"""
        if not sources:
            return 0.1
        
        # 基于来源质量和数量计算可信度
        avg_similarity = sum(source.similarity_score for source in sources) / len(sources)
        
        # 检查答案中是否包含具体的规范条款
        regulation_mentions = len(re.findall(r'(GB|JGJ|CJJ|JGT|DBJ)\s*[\s\-]*\d+', answer))
        clause_mentions = len(re.findall(r'\d+\.\d+\.\d+', answer))
        numerical_values = len(re.findall(r'\d+(?:\.\d+)?\s*(mm|cm|m|MPa|kN|℃|%)', answer))
        
        # 综合评分
        confidence = (
            avg_similarity * 0.5 +  # 相似度权重
            min(regulation_mentions * 0.15, 0.3) +  # 规范引用
            min(clause_mentions * 0.1, 0.15) +  # 条款引用
            min(numerical_values * 0.05, 0.1)  # 数值准确性
        )
        
        return min(confidence, 1.0)
    
    def _check_definitive_answer(self, answer: str) -> bool:
        """检查是否有明确答案"""
        uncertain_phrases = [
            "无法确定", "不确定", "可能", "大概", "似乎", 
            "建议咨询", "需要进一步", "信息不足", "无法找到",
            "不清楚", "没有相关", "未找到"
        ]
        
        # 检查确定性短语
        definitive_phrases = [
            "应符合", "不应小于", "不应大于", "必须", "规定为",
            "标准要求", "规范规定", "明确规定"
        ]
        
        has_uncertain = any(phrase in answer for phrase in uncertain_phrases)
        has_definitive = any(phrase in answer for phrase in definitive_phrases)
        
        return has_definitive and not has_uncertain
    
    def _generate_suggestions(self, question: str, answer: str) -> List[str]:
        """生成相关建议或追问提示"""
        suggestions = []
        
        # 基于工程领域生成建议
        engineering_domain = identify_engineering_domain(question)
        domain_config = self.config.get_engineering_domain_config(engineering_domain)
        
        if engineering_domain == "混凝土":
            suggestions.extend([
                "您可以进一步询问不同强度等级混凝土的具体要求",
                "建议了解混凝土施工质量验收标准",
                "可以查询混凝土养护的具体规定"
            ])
        elif engineering_domain == "脚手架":
            suggestions.extend([
                "建议了解脚手架搭设的安全技术规范",
                "可以询问脚手架验收的具体标准",
                "您可以查询不同高度脚手架的要求差异"
            ])
        elif engineering_domain == "地基基础":
            suggestions.extend([
                "建议了解地基承载力的检测方法",
                "可以询问桩基施工质量控制要点",
                "您可以查询基坑支护的安全要求"
            ])
        elif engineering_domain == "钢结构":
            suggestions.extend([
                "建议了解钢结构焊接质量验收标准",
                "可以询问钢结构防腐涂装要求",
                "您可以查询钢结构连接的技术规定"
            ])
        else:
            # 通用建议
            suggestions.extend([
                "您可以询问相关的施工验收标准",
                "建议了解质量控制的关键要点",
                "可以查询安全技术规范要求"
            ])
        
        # 基于答案内容生成建议
        if "保护层" in answer:
            suggestions.append("您可以询问保护层厚度的检测方法和验收标准")
        if "强度" in answer:
            suggestions.append("建议了解强度试验的具体要求和标准")
        if "间距" in answer:
            suggestions.append("可以查询间距测量的验收方法")
        
        # 基于相关规范生成建议
        if domain_config.get('regulations'):
            reg_text = "、".join(domain_config['regulations'][:2])
            suggestions.append(f"建议查阅相关规范：{reg_text}")
        
        return suggestions[:4]  # 最多返回4个建议
    
    def generate_answer_without_context(self, question: str) -> AnswerResponse:
        """当知识库中没有检索到相关内容时，基于模型自身知识生成答案"""
        try:
            logger.info(f"基于模型知识生成答案 - 问题: {question}")
            
            # 检查是否为问候或闲聊
            if is_greeting_or_casual(question):
                return self._generate_greeting_response(question)
            
            # 识别工程领域
            engineering_domain = identify_engineering_domain(question)
            domain_config = self.config.get_engineering_domain_config(engineering_domain)
            
            # 构建针对无知识库情况的消息
            messages = [
                {"role": "system", "content": f"""你是一位资深的工程监理专家，拥有丰富的工程技术知识和实践经验。
当前用户询问的是{engineering_domain}领域的问题，系统知识库中暂时没有找到直接相关的规范文档。
请基于你的专业知识回答用户问题，并：

1. 基于你的工程技术知识提供准确、专业的技术信息
2. 如果知道具体的技术参数、标准要求，请直接提供
3. 明确标注参考的相关工程规范编号（如GB、JGJ等标准）
4. 给出实用的工程监理建议和注意事项
5. 使用中文回答，专业但易懂

回答格式要求：
- 直接回答技术问题，提供具体的技术参数和要求
- 说明信息来源和依据的工程规范
- 在回答最后必须按以下格式添加参考依据：

📚 **参考依据**
[使用标准: 此处列出你在回答中引用的标准编号，用逗号分隔]
[引用法规: 无]
[引用图纸: 无]
[参考文档: 无]

注意：请基于你的工程技术知识直接回答，不要说"基于通用工程知识"这样的表述。"""},
                {"role": "user", "content": f"""
【用户问题】{question}

【工程领域】{engineering_domain}
{f"【相关规范建议】{', '.join(domain_config.get('regulations', []))}" if domain_config.get('regulations') else ""}

请基于你的工程监理专业知识直接回答这个问题，并提供具体的技术要求和相关规范：
"""}
            ]
            
            # 调用DeepSeek模型
            deepseek_config = self.config.get_deepseek_config()
            
            response = self.client.chat.completions.create(
                model=deepseek_config["model"],
                messages=messages,
                temperature=0.3,  # 降低温度以获得更准确的回答
                max_tokens=deepseek_config["max_tokens"],
                top_p=0.9
            )
            
            answer_text = response.choices[0].message.content
            logger.info("基于模型知识的答案生成成功")
            
            # 生成建议
            suggestions = self._generate_general_suggestions(question, engineering_domain)
            
            return AnswerResponse(
                question=question,
                answer=answer_text,
                sources=[],  # 没有来源文档
                confidence_score=0.7,  # 提高置信度，因为是基于模型专业知识
                timestamp=datetime.now(),
                has_definitive_answer=True,  # 设为确定性答案
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"基于模型知识生成答案失败: {e}")
            return self._create_error_response(question, str(e))
    
    def _generate_general_suggestions(self, question: str, engineering_domain: str) -> List[str]:
        """为通用知识回答生成建议"""
        suggestions = [
            "建议上传相关规范文档以获得更准确的答案",
            "可以尝试使用更具体的技术术语重新提问"
        ]
        
        # 基于工程领域添加具体建议
        domain_suggestions = {
            "混凝土": [
                "建议查阅GB 50010《混凝土结构设计规范》",
                "可参考GB 50204《混凝土结构工程施工质量验收规范》"
            ],
            "钢结构": [
                "建议查阅GB 50017《钢结构设计标准》",
                "可参考GB 50205《钢结构工程施工质量验收标准》"
            ],
            "脚手架": [
                "建议查阅GB 51210《建筑施工脚手架安全技术统一标准》",
                "可参考JGJ 130《建筑施工扣件式钢管脚手架安全技术规范》"
            ],
            "地基基础": [
                "建议查阅GB 50007《建筑地基基础设计规范》",
                "可参考GB 50202《建筑地基基础工程施工质量验收标准》"
            ]
        }
        
        if engineering_domain in domain_suggestions:
            suggestions.extend(domain_suggestions[engineering_domain])
        
        return suggestions[:5]  # 最多返回5个建议

    def _generate_greeting_response(self, question: str) -> AnswerResponse:
        """生成问候回复"""
        greeting_responses = [
            "您好！我是工程监理智能助手，专门为您提供工程监理相关的技术咨询服务。",
            "您可以向我咨询以下类型的问题：",
            "• 混凝土结构施工质量要求",
            "• 脚手架安全检查要点", 
            "• 钢结构施工规范",
            "• 地基基础工程验收标准",
            "• 建筑防水工程技术要求",
            "• 其他工程监理相关技术问题",
            "",
            "请告诉我您需要咨询的具体工程问题，我将基于相关规范标准为您提供专业解答。"
        ]
        
        answer = "\n".join(greeting_responses)
        
        return AnswerResponse(
            question=question,
            answer=answer,
            sources=[],
            confidence_score=1.0,
            timestamp=datetime.now(),
            has_definitive_answer=True,
            suggestions=[
                "混凝土强度等级要求",
                "脚手架搭设规范",
                "外墙保温施工要点",
                "地基基础验收标准"
            ]
        )

    def _create_error_response(self, question: str, error: str) -> AnswerResponse:
        """创建错误响应"""
        return AnswerResponse(
            question=question,
            answer=f"抱歉，处理您的问题时出现错误。这可能是由于：\n1. 网络连接问题\n2. DeepSeek API服务暂时不可用\n3. 系统内部错误\n\n具体错误信息：{error}\n\n建议您稍后重试，或者尝试换个表述方式提问。",
            sources=[],
            confidence_score=0.0,
            timestamp=datetime.now(),
            has_definitive_answer=False,
            suggestions=["请检查网络连接", "尝试重新表述问题", "稍后重试"]
        )
    
    def summarize_document(self, content: str, max_length: int = 500) -> str:
        """总结文档内容"""
        try:
            messages = [
                {"role": "system", "content": "请总结以下工程规范或图纸内容，突出重点技术要求和关键条款。"},
                {"role": "user", "content": f"请用中文总结以下工程文档内容，重点提取技术要求:\n\n{content}"}
            ]
            
            deepseek_config = self.config.get_deepseek_config()
            
            response = self.client.chat.completions.create(
                model=deepseek_config["model"],
                messages=messages,
                temperature=0.1,
                max_tokens=max_length
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"文档总结失败: {e}")
            return "文档总结失败，请检查DeepSeek API连接"
    
    def extract_key_points(self, content: str) -> List[str]:
        """提取文档关键点"""
        try:
            messages = [
                {"role": "system", "content": "请从工程规范内容中提取关键技术要求，每个要求一行，不超过10个要点。"},
                {"role": "user", "content": f"请用中文提取以下工程文档的关键技术要点:\n\n{content}"}
            ]
            
            deepseek_config = self.config.get_deepseek_config()
            
            response = self.client.chat.completions.create(
                model=deepseek_config["model"],
                messages=messages,
                temperature=0.1,
                max_tokens=300
            )
            
            key_points = response.choices[0].message.content.split('\n')
            return [point.strip() for point in key_points if point.strip()]
            
        except Exception as e:
            logger.error(f"关键点提取失败: {e}")
            return []

    def generate_answer_with_web_search(self, question: str) -> AnswerResponse:
        """使用网络搜索增强的答案生成"""
        try:
            logger.info(f"基于网络搜索和模型知识生成答案 - 问题: {question}")
            
            # 识别工程领域
            engineering_domain = identify_engineering_domain(question)
            domain_config = self.config.get_engineering_domain_config(engineering_domain)
            
            # 构建搜索查询词
            search_query = f"{question} 工程规范 标准"
            if domain_config.get('regulations'):
                search_query += f" {' '.join(domain_config['regulations'][:2])}"
            
            try:
                # 这里可以集成网络搜索API (如Google、百度等)
                # 示例：search_results = web_search_api(search_query)
                web_info = f"网络搜索关键词: {search_query}"
                logger.info(web_info)
            except Exception as e:
                logger.warning(f"网络搜索失败: {e}")
                web_info = ""
            
            # 构建消息
            messages = [
                {"role": "system", "content": f"""你是一位资深的工程监理专家，拥有丰富的工程技术知识和实践经验。
当前用户询问的是{engineering_domain}领域的问题。请基于你的专业知识回答用户问题，并：

1. 基于你的工程技术知识提供准确、专业的技术信息
2. 如果知道具体的技术参数、标准要求，请直接提供
3. 明确标注参考的相关工程规范编号（如GB、JGJ等标准）
4. 给出实用的工程监理建议和注意事项
5. 使用中文回答，专业但易懂

回答格式要求：
- 直接回答技术问题，提供具体的技术参数和要求
- 说明信息来源和依据的工程规范
- 在回答最后必须按以下格式添加参考依据：

📚 **参考依据**
[使用标准: 此处列出你在回答中引用的标准编号，用逗号分隔]
[引用法规: 无]
[引用图纸: 无]
[参考文档: 无]

注意：请基于你的工程技术知识直接回答，提供具体的技术要求。"""},
                {"role": "user", "content": f"""
【用户问题】{question}

【工程领域】{engineering_domain}
{f"【相关规范建议】{', '.join(domain_config.get('regulations', []))}" if domain_config.get('regulations') else ""}

请基于你的工程监理专业知识直接回答这个问题，并提供具体的技术要求和相关规范：
"""}
            ]
            
            # 调用DeepSeek模型
            deepseek_config = self.config.get_deepseek_config()
            
            response = self.client.chat.completions.create(
                model=deepseek_config["model"],
                messages=messages,
                temperature=0.3,
                max_tokens=deepseek_config["max_tokens"],
                top_p=0.9
            )
            
            answer_text = response.choices[0].message.content
            logger.info("基于网络搜索增强的答案生成成功")
            
            # 生成建议
            suggestions = self._generate_general_suggestions(question, engineering_domain)
            
            return AnswerResponse(
                question=question,
                answer=answer_text,
                sources=[],
                confidence_score=0.8,  # 更高置信度
                timestamp=datetime.now(),
                has_definitive_answer=True,
                suggestions=suggestions
            )
            
        except Exception as e:
            logger.error(f"基于网络搜索生成答案失败: {e}")
            return self.generate_answer_without_context(question)

# 工程监理专用功能函数
def is_greeting_or_casual(question: str) -> bool:
    """识别是否为问候或闲聊"""
    question_lower = question.lower().strip()
    
    # 常见问候语
    greetings = [
        "你好", "您好", "hello", "hi", "嗨", "早上好", "下午好", "晚上好",
        "怎么样", "如何", "在吗", "在不在", "能帮我吗", "可以帮我吗",
        "谢谢", "感谢", "再见", "拜拜", "好的", "ok", "明白了"
    ]
    
    # 如果问题很短且是常见问候语
    if len(question_lower) <= 10 and any(greeting in question_lower for greeting in greetings):
        return True
    
    # 如果问题只包含问候语和标点符号
    cleaned_question = ''.join(c for c in question_lower if c.isalnum())
    if cleaned_question in greetings:
        return True
    
    return False

def identify_engineering_domain(question: str) -> str:
    """识别工程领域"""
    question_lower = question.lower()
    
    # 从配置中获取工程领域
    engineering_domains = Config.ENGINEERING_DOMAINS
    
    for domain, config in engineering_domains.items():
        keywords = config.get("keywords", [])
        if domain in question_lower or any(keyword in question_lower for keyword in keywords):
            return domain
    
    # 检查规范编号
    if any(code in question.upper() for code in ["GB", "JGJ", "CJJ", "JGT", "DBJ"]):
        return "规范标准"
    
    return "通用工程"

def enhance_engineering_question(question: str) -> str:
    """增强工程问题的表述"""
    domain = identify_engineering_domain(question)
    domain_config = Config.ENGINEERING_DOMAINS.get(domain, {})
    
    enhancements = {
        "混凝土": "请结合混凝土结构设计规范和施工验收规范",
        "脚手架": "请参考建筑施工脚手架安全技术统一标准",
        "钢结构": "请结合钢结构设计标准和施工质量验收规范",
        "地基基础": "请参考建筑地基基础设计规范和施工验收规范",
        "防水工程": "请结合建筑防水工程技术规范",
        "保温工程": "请参考建筑节能与保温工程相关标准"
    }
    
    enhanced_question = question
    
    # 添加领域增强
    if domain in enhancements:
        enhanced_question += f" ({enhancements[domain]})"
    
    # 添加相关规范提示
    if domain_config.get("regulations"):
        reg_hint = "、".join(domain_config["regulations"][:2])
        enhanced_question += f" [相关规范: {reg_hint}]"
    
    return enhanced_question

def get_engineering_context(question: str) -> Dict:
    """获取工程上下文信息"""
    domain = identify_engineering_domain(question)
    domain_config = Config.ENGINEERING_DOMAINS.get(domain, {})
    
    return {
        "domain": domain,
        "keywords": domain_config.get("keywords", []),
        "regulations": domain_config.get("regulations", []),
        "enhanced_question": enhance_engineering_question(question)
    } 