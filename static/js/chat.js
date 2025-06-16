// 聊天功能管理类
class ChatManager {
    constructor() {
        this.sessionId = Utils.generateId('session');
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
            headerDescription: Utils.dom.get('#headerDescription')
        };

        this.init();
    }

    init() {
        this.bindEvents();
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
        // 简单直接的方法：如果包含 ## 标题，就使用 Markdown 渲染
        if (content.includes('##') && typeof marked !== 'undefined') {
            // 配置marked选项
            marked.setOptions({
                breaks: true,        // 支持换行符转换为<br>
                gfm: true,          // 支持GitHub风格的Markdown
                sanitize: false,    // 允许HTML（我们信任后端内容）
                smartLists: true,   // 智能列表
                smartypants: false  // 不转换引号
            });
            
            // 使用marked解析Markdown
            try {
                let html = marked.parse(content);
                
                // 为表格添加样式类
                html = html.replace(/<table>/g, '<table class="markdown-table">');
                
                // 为代码块添加样式类
                html = html.replace(/<pre><code>/g, '<pre class="markdown-code"><code>');
                
                // 确保链接在新窗口打开
                html = html.replace(/<a href="([^"]*)">/g, '<a href="$1" target="_blank" rel="noopener noreferrer">');
                
                return html;
            } catch (error) {
                console.warn('Markdown解析失败，使用基础格式化:', error);
                return this.formatBasicContent(content);
            }
        } else {
            return this.formatBasicContent(content);
        }
    }

    formatBasicContent(content) {
        // 基础格式化（原有逻辑）
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
        const showCount = 3; // 默认显示前3条
        const sourceId = Utils.generateId('source'); // 生成唯一ID
        
        let html = `<div class="sources" id="${sourceId}">
            <div class="sources-header">
                <strong>📚 参考来源：</strong>
                ${sources.length > showCount ? `<span class="source-count">(共${sources.length}条)</span>` : ''}
            </div>`;
        
        sources.forEach((source, index) => {
            const isHidden = index >= showCount;
            html += `<div class="source-item ${isHidden ? 'source-hidden' : ''}" data-index="${index}">
                ${index + 1}. ${Utils.text.escapeHtml(source.file_name)}
                ${source.regulation_code ? ' (' + Utils.text.escapeHtml(source.regulation_code) + ')' : ''}
                ${source.section ? ' - ' + Utils.text.escapeHtml(source.section) : ''}
                (相关度: ${(source.similarity_score * 100).toFixed(1)}%)
            </div>`;
        });
        
        // 如果有超过3条来源，添加展开/折叠按钮
        if (sources.length > showCount) {
            html += `<div class="source-toggle-btn" onclick="toggleSources('${sourceId}')">
                <span class="toggle-text">展开更多 (${sources.length - showCount})</span>
                <span class="toggle-icon">▼</span>
            </div>`;
        }
        
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

    saveChatHistory() {
        if (this.messageHistory.length > 0) {
            Utils.storage.set(`chat_history_${this.sessionId}`, {
                history: this.messageHistory,
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
                您好！我是您的工程监理智能助手。我会自动搜索所有数据库为您提供答案：<br>
                • 📋 国家和行业标准（GB、JGJ、CJJ等）<br>
                • ⚖️ 法律法规和管理办法<br>
                • 📚 工程技术规范要求<br>
                • 🏗️ 项目图纸内容解读<br>
                • 🔗 相关文档的官方链接<br><br>
                请直接提出您的问题，比如"住宅专项维修资金提取标准"或"钢筋连接质量要求"。
            </div>
        `;
        this.messageHistory = [];
        this.sessionId = Utils.generateId('session');
    }

    // 导出聊天记录
    exportChat() {
        const exportData = {
            sessionId: this.sessionId,
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

// 参考来源展开/折叠功能
function toggleSources(sourceId) {
    const sourceContainer = document.getElementById(sourceId);
    if (!sourceContainer) return;
    
    const hiddenItems = sourceContainer.querySelectorAll('.source-item.source-hidden');
    const shownItems = sourceContainer.querySelectorAll('.source-item.source-shown');
    const toggleBtn = sourceContainer.querySelector('.source-toggle-btn');
    const toggleText = toggleBtn.querySelector('.toggle-text');
    const toggleIcon = toggleBtn.querySelector('.toggle-icon');
    
    const isExpanded = shownItems.length > 0;
    
    if (!isExpanded) {
        // 展开
        hiddenItems.forEach(item => {
            item.classList.remove('source-hidden');
            item.classList.add('source-shown');
        });
        toggleText.textContent = '收起';
        toggleIcon.textContent = '▲';
        toggleBtn.classList.add('expanded');
    } else {
        // 折叠
        shownItems.forEach(item => {
            item.classList.remove('source-shown');
            item.classList.add('source-hidden');
        });
        const hiddenCount = sourceContainer.querySelectorAll('.source-item').length - 3;
        toggleText.textContent = `展开更多 (${hiddenCount})`;
        toggleIcon.textContent = '▼';
        toggleBtn.classList.remove('expanded');
    }
} 