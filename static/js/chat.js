// 聊天功能管理类
class ChatManager {
    constructor() {
        this.sessionId = Utils.generateId('session');
        this.currentKnowledgeBase = 'standards';
        this.messageHistory = [];
        this.isLoading = false;
        
        // 缓存DOM元素
        this.elements = {
            chatMessages: Utils.dom.get('#chatMessages'),
            messageInput: Utils.dom.get('#messageInput'),
            sendButton: Utils.dom.get('#sendButton'),
            clearButton: Utils.dom.get('#clearButton'),
            loading: Utils.dom.get('#loading'),
            charCount: Utils.dom.get('#charCount'),
            knowledgeBaseSelector: Utils.dom.get('#knowledgeBaseSelector'),
            headerDescription: Utils.dom.get('#headerDescription')
        };

        this.init();
    }

    init() {
        this.bindEvents();
        this.loadKnowledgeBases();
        this.loadChatHistory();
        this.updateCharCount();
    }

    bindEvents() {
        // 发送消息事件
        Utils.events.on(this.elements.sendButton, 'click', () => this.sendMessage());
        
        // 回车发送
        Utils.events.on(this.elements.messageInput, 'keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });

        // 清空输入
        Utils.events.on(this.elements.clearButton, 'click', () => this.clearInput());

        // 字符计数
        Utils.events.on(this.elements.messageInput, 'input', 
            Utils.debounce(() => this.updateCharCount(), 100)
        );

        // 知识库切换
        Utils.events.on(this.elements.knowledgeBaseSelector, 'change', 
            () => this.switchKnowledgeBase()
        );

        // 监听窗口关闭前保存历史记录
        Utils.events.on(window, 'beforeunload', () => this.saveChatHistory());
    }

    async sendMessage() {
        const question = this.elements.messageInput.value.trim();
        if (!question || this.isLoading) return;

        // 验证输入
        if (!Utils.validate.required(question)) {
            this.showError('请输入问题内容');
            return;
        }

        if (!Utils.validate.length(question, 1, 500)) {
            this.showError('问题长度应在1-500字符之间');
            return;
        }

        // 显示用户消息
        this.addMessage(question, 'user');
        this.elements.messageInput.value = '';
        this.updateCharCount();

        // 设置加载状态
        this.setLoading(true);

        // 性能监控
        Utils.performance.mark('send-message');

        try {
            const response = await Utils.http.post('/ask', {
                question: question,
                session_id: this.sessionId
            });

            if (response.success) {
                this.addMessage(response.data.answer, 'assistant', {
                    sources: response.data.sources,
                    suggestions: response.data.suggestions,
                    standards: response.data.standards
                });
                
                // 记录到历史
                this.messageHistory.push(
                    { type: 'user', content: question, timestamp: new Date() },
                    { type: 'assistant', content: response.data.answer, timestamp: new Date() }
                );
            } else {
                this.addMessage(`抱歉，处理您的问题时出现错误：${response.error}`, 'assistant');
            }
        } catch (error) {
            console.error('Send message error:', error);
            this.addMessage('网络错误，请稍后重试', 'assistant');
        } finally {
            this.setLoading(false);
            Utils.performance.measure('send-message');
        }
    }

    addMessage(content, type, metadata = {}) {
        const messageDiv = Utils.dom.create('div', {
            className: `message ${type}`,
            'data-timestamp': new Date().toISOString()
        });

        let html = this.formatMessageContent(content);

        // 添加来源信息
        if (metadata.sources && metadata.sources.length > 0) {
            html += this.renderSources(metadata.sources);
        }

        // 添加标准信息
        if (metadata.standards && metadata.standards.length > 0) {
            html += this.renderStandards(metadata.standards);
        }

        // 添加建议
        if (metadata.suggestions && metadata.suggestions.length > 0) {
            html += this.renderSuggestions(metadata.suggestions);
        }

        messageDiv.innerHTML = html;
        this.elements.chatMessages.appendChild(messageDiv);
        
        // 滚动到底部
        this.scrollToBottom();

        // 添加动画效果
        requestAnimationFrame(() => {
            messageDiv.classList.add('show');
        });
    }

    formatMessageContent(content) {
        // 处理换行符
        content = content.replace(/\n/g, '<br>');
        
        // 处理链接
        content = content.replace(
            /https?:\/\/[^\s<>"]+/g,
            '<a href="$&" target="_blank" rel="noopener noreferrer">$&</a>'
        );

        // 处理粗体标记
        content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        return content;
    }

    renderSources(sources) {
        let html = '<div class="sources"><strong>📚 参考来源：</strong>';
        sources.forEach((source, index) => {
            html += `<div class="source-item">
                ${index + 1}. ${Utils.text.escapeHtml(source.file_name)}
                ${source.regulation_code ? ' (' + Utils.text.escapeHtml(source.regulation_code) + ')' : ''}
                ${source.section ? ' - ' + Utils.text.escapeHtml(source.section) : ''}
                (相关度: ${(source.similarity_score * 100).toFixed(1)}%)
            </div>`;
        });
        html += '</div>';
        return html;
    }

    renderStandards(standards) {
        let html = '<div class="standards-section"><strong>📋 相关标准：</strong>';
        standards.forEach(standard => {
            html += `<div class="standard-item">
                <strong>${Utils.text.escapeHtml(standard.standard_number)}</strong>: 
                ${Utils.text.escapeHtml(standard.standard_name)}
                <br><span style="color: #666; font-size: 0.9em;">
                    状态: ${Utils.text.escapeHtml(standard.status)} | 
                    实施日期: ${Utils.text.escapeHtml(standard.implementation_date)}
                </span>
                ${standard.pdf_url ? `<br><a href="${standard.pdf_url}" target="_blank" class="standard-link">📄 查看标准文档</a>` : ''}
            </div>`;
        });
        html += '</div>';
        return html;
    }

    renderSuggestions(suggestions) {
        let html = '<div class="suggestions"><strong>💭 相关建议：</strong><br>';
        suggestions.forEach(suggestion => {
            html += `• ${Utils.text.escapeHtml(suggestion)}<br>`;
        });
        html += '</div>';
        return html;
    }

    showError(message) {
        // 创建错误提示
        const errorDiv = Utils.dom.create('div', {
            className: 'error-message',
            innerHTML: `⚠️ ${message}`
        });

        this.elements.chatMessages.appendChild(errorDiv);
        this.scrollToBottom();

        // 3秒后自动移除
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.parentNode.removeChild(errorDiv);
            }
        }, 3000);
    }

    setLoading(loading) {
        this.isLoading = loading;
        this.elements.sendButton.disabled = loading;
        
        if (loading) {
            Utils.dom.show(this.elements.loading, 'flex');
        } else {
            Utils.dom.hide(this.elements.loading);
        }
    }

    clearInput() {
        this.elements.messageInput.value = '';
        this.updateCharCount();
        this.elements.messageInput.focus();
    }

    updateCharCount() {
        const length = this.elements.messageInput.value.length;
        this.elements.charCount.textContent = `${length}/500`;
        
        // 字符数接近限制时改变颜色
        if (length > 450) {
            this.elements.charCount.style.color = '#dc3545';
        } else if (length > 400) {
            this.elements.charCount.style.color = '#ffc107';
        } else {
            this.elements.charCount.style.color = '#7f8c8d';
        }
    }

    scrollToBottom() {
        requestAnimationFrame(() => {
            this.elements.chatMessages.scrollTop = this.elements.chatMessages.scrollHeight;
        });
    }

    async switchKnowledgeBase() {
        const selectedKB = this.elements.knowledgeBaseSelector.value;
        if (selectedKB === this.currentKnowledgeBase) return;

        this.setLoading(true);

        try {
            const response = await Utils.http.post('/switch-knowledge-base', {
                collection_name: selectedKB
            });

            if (response.success) {
                this.currentKnowledgeBase = selectedKB;
                
                // 更新界面描述
                const kbDescriptions = {
                    'standards': '专业的国家标准查询服务 📋',
                    'engineering_knowledge_base': '工程技术知识查询服务 📚',
                    'regulations': '法律法规查询服务 ⚖️',
                    'drawings': '项目图纸查询服务 📐'
                };

                this.elements.headerDescription.textContent = 
                    kbDescriptions[selectedKB] || '智能问答服务';

                // 显示切换成功消息
                this.addMessage(
                    `✅ 已切换到 ${response.data.message}\n📊 包含 ${response.data.document_count} 个文档`,
                    'assistant'
                );

                // 重置session
                this.sessionId = Utils.generateId('session');
            } else {
                this.addMessage(`❌ 切换失败：${response.error}`, 'assistant');
            }
        } catch (error) {
            console.error('Switch KB error:', error);
            this.addMessage('切换知识库时发生网络错误', 'assistant');
        } finally {
            this.setLoading(false);
        }
    }

    async loadKnowledgeBases() {
        try {
            const response = await Utils.http.get('/knowledge-bases');
            
            if (response.success) {
                this.currentKnowledgeBase = response.data.current_collection;
                this.elements.knowledgeBaseSelector.value = this.currentKnowledgeBase;

                // 更新选择器选项状态
                Array.from(this.elements.knowledgeBaseSelector.options).forEach(option => {
                    const kbInfo = response.data.knowledge_bases[option.value];
                    if (kbInfo && kbInfo.status === 'not_available') {
                        option.disabled = true;
                        option.textContent += ' (不可用)';
                    } else if (kbInfo) {
                        option.textContent += ` (${kbInfo.document_count} 文档)`;
                    }
                });
            }
        } catch (error) {
            console.error('Load KB error:', error);
        }
    }

    saveChatHistory() {
        if (this.messageHistory.length > 0) {
            Utils.storage.set(`chat_history_${this.sessionId}`, {
                history: this.messageHistory,
                knowledgeBase: this.currentKnowledgeBase,
                timestamp: new Date()
            });
        }
    }

    loadChatHistory() {
        // 加载最近的聊天记录（可选功能）
        const recentSessions = Utils.storage.get('recent_sessions', []);
        if (recentSessions.length > 0) {
            // 可以在这里实现历史记录恢复逻辑
        }
    }

    askExample(question) {
        this.elements.messageInput.value = question;
        this.sendMessage();
    }

    // 清除聊天记录
    clearChat() {
        this.elements.chatMessages.innerHTML = `
            <div class="message assistant">
                您好！我是您的工程监理智能助手。我可以帮助您查询：<br>
                • 国家和地方工程建设规范标准<br>
                • 项目设计图纸技术要求<br>
                • 施工质量验收标准<br>
                • 安全技术规范<br><br>
                请直接提出您的问题，比如"混凝土保护层厚度要求"或"脚手架连墙件间距规定"。
            </div>
        `;
        this.messageHistory = [];
        this.sessionId = Utils.generateId('session');
    }

    // 导出聊天记录
    exportChat() {
        const exportData = {
            sessionId: this.sessionId,
            knowledgeBase: this.currentKnowledgeBase,
            messages: this.messageHistory,
            exportTime: new Date().toISOString()
        };

        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
            type: 'application/json'
        });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_export_${Utils.formatDate().replace(/[^\d]/g, '')}.json`;
        a.click();
        URL.revokeObjectURL(url);
    }
}

// 全局聊天管理器实例
let chatManager = null;

// 兼容性函数（保持与原始代码的兼容性）
function sendMessage() {
    if (chatManager) {
        chatManager.sendMessage();
    }
}

function askExample(question) {
    if (chatManager) {
        chatManager.askExample(question);
    }
}

function clearInput() {
    if (chatManager) {
        chatManager.clearInput();
    }
}

function switchKnowledgeBase() {
    if (chatManager) {
        chatManager.switchKnowledgeBase();
    }
} 