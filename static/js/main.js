// 应用主控制器
class App {
    constructor() {
        this.initialized = false;
        this.components = {};
        this.config = {
            version: '1.0.0',
            apiEndpoint: '',
            maxRetries: 3,
            retryDelay: 1000
        };
    }

    async init() {
        if (this.initialized) return;

        try {
            console.log('🚀 启动工程监理智能问答系统...');
            
            // 检查浏览器兼容性
            this.checkBrowserCompatibility();
            
            // 初始化组件
            await this.initializeComponents();
            
            // 设置全局事件监听
            this.setupGlobalEvents();
            
            // 加载用户偏好设置
            this.loadUserPreferences();
            
            // 初始化示例问题
            this.initializeExamples();
            
            this.initialized = true;
            console.log('✅ 系统初始化完成');
            
        } catch (error) {
            console.error('❌ 系统初始化失败:', error);
            this.showInitializationError(error);
        }
    }

    checkBrowserCompatibility() {
        const requiredFeatures = [
            'fetch',
            'Promise',
            'localStorage',
            'addEventListener'
        ];

        const missingFeatures = requiredFeatures.filter(feature => 
            !(feature in window) && !(feature in window.constructor.prototype)
        );

        if (missingFeatures.length > 0) {
            throw new Error(`浏览器不支持以下特性: ${missingFeatures.join(', ')}`);
        }
    }

    async initializeComponents() {
        // 初始化聊天管理器
        this.components.chat = new ChatManager();
        chatManager = this.components.chat; // 设置全局引用
        
        // 初始化UI组件
        this.components.ui = new UIManager();
        
        console.log('📦 组件初始化完成');
    }

    setupGlobalEvents() {
        // 全局错误处理
        window.addEventListener('error', (event) => {
            console.error('全局错误:', event.error);
            this.handleGlobalError(event.error);
        });

        // 未处理的Promise rejection
        window.addEventListener('unhandledrejection', (event) => {
            console.error('未处理的Promise rejection:', event.reason);
            this.handleGlobalError(event.reason);
        });

        // 页面可见性变化
        document.addEventListener('visibilitychange', () => {
            if (document.visibilityState === 'visible') {
                this.onPageVisible();
            } else {
                this.onPageHidden();
            }
        });

        // 网络状态变化
        window.addEventListener('online', () => this.onNetworkOnline());
        window.addEventListener('offline', () => this.onNetworkOffline());
    }

    loadUserPreferences() {
        const preferences = Utils.storage.get('user_preferences', {
            theme: 'light',
            fontSize: 'normal',
            animations: true,
            notifications: true
        });

        this.applyUserPreferences(preferences);
    }

    applyUserPreferences(preferences) {
        // 应用主题
        if (preferences.theme === 'dark') {
            document.body.classList.add('dark-theme');
        }

        // 应用字体大小
        if (preferences.fontSize !== 'normal') {
            document.body.classList.add(`font-size-${preferences.fontSize}`);
        }

        // 应用动画设置
        if (!preferences.animations) {
            document.body.classList.add('reduced-motion');
        }
    }

    initializeExamples() {
        const examples = [
            '混凝土结构保护层最小厚度是多少？',
            '脚手架连墙件最大间距要求？',
            '钢筋锚固长度如何计算？',
            '外墙保温材料有什么要求？',
            '应急厕所设置距离要求？',
            '建筑防火间距的规定？'
        ];

        const exampleContainer = Utils.dom.get('#exampleQuestions');
        if (exampleContainer) {
            exampleContainer.innerHTML = '';
            
            examples.forEach(question => {
                const exampleDiv = Utils.dom.create('div', {
                    className: 'example-question',
                    innerHTML: Utils.text.escapeHtml(question)
                });
                
                Utils.events.on(exampleDiv, 'click', () => {
                    if (this.components.chat) {
                        this.components.chat.askExample(question);
                    }
                });
                
                exampleContainer.appendChild(exampleDiv);
            });
        }
    }

    handleGlobalError(error) {
        // 记录错误到控制台
        console.error('应用错误:', error);
        
        // 显示用户友好的错误信息
        const errorMessage = this.getErrorMessage(error);
        this.showNotification(errorMessage, 'error');
    }

    getErrorMessage(error) {
        if (error.name === 'NetworkError' || error.message.includes('fetch')) {
            return '网络连接出现问题，请检查网络后重试';
        } else if (error.name === 'TypeError') {
            return '系统出现技术问题，请刷新页面重试';
        } else {
            return '系统出现未知错误，请稍后重试';
        }
    }

    showNotification(message, type = 'info') {
        const notification = Utils.dom.create('div', {
            className: `notification notification-${type}`,
            innerHTML: `
                <span class="notification-icon">
                    ${type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️'}
                </span>
                <span class="notification-message">${Utils.text.escapeHtml(message)}</span>
                <button class="notification-close" onclick="this.parentNode.remove()">×</button>
            `
        });

        // 添加到页面
        document.body.appendChild(notification);

        // 显示动画
        Utils.animation.fadeIn(notification);

        // 自动隐藏
        setTimeout(() => {
            if (notification.parentNode) {
                Utils.animation.fadeOut(notification).then(() => {
                    notification.remove();
                });
            }
        }, 5000);
    }

    showInitializationError(error) {
        const errorContainer = Utils.dom.create('div', {
            className: 'initialization-error',
            innerHTML: `
                <div class="error-content">
                    <h2>❌ 系统初始化失败</h2>
                    <p>很抱歉，系统无法正常启动。请尝试以下解决方案：</p>
                    <ul>
                        <li>刷新页面重试</li>
                        <li>检查网络连接</li>
                        <li>清除浏览器缓存</li>
                        <li>使用其他浏览器访问</li>
                    </ul>
                    <button onclick="location.reload()" class="retry-button">重新加载</button>
                </div>
            `
        });

        document.body.innerHTML = '';
        document.body.appendChild(errorContainer);
    }

    onPageVisible() {
        // 页面重新可见时的处理
        if (this.components.chat) {
            // 可以在这里检查是否有新消息等
        }
    }

    onPageHidden() {
        // 页面隐藏时的处理
        if (this.components.chat) {
            this.components.chat.saveChatHistory();
        }
    }

    onNetworkOnline() {
        this.showNotification('网络连接已恢复', 'success');
    }

    onNetworkOffline() {
        this.showNotification('网络连接已断开，请检查网络', 'error');
    }
}

// UI管理器
class UIManager {
    constructor() {
        this.backToTopButton = Utils.dom.get('#backToTop');
        this.init();
    }

    init() {
        this.setupBackToTop();
        this.setupResponsiveHandling();
        this.setupKeyboardShortcuts();
    }

    setupBackToTop() {
        if (!this.backToTopButton) return;

        // 监听滚动事件
        const scrollHandler = Utils.throttle(() => {
            const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
            
            if (scrollTop > 300) {
                Utils.dom.addClass(this.backToTopButton, 'show');
            } else {
                Utils.dom.removeClass(this.backToTopButton, 'show');
            }
        }, 100);

        Utils.events.on(window, 'scroll', scrollHandler);
    }

    setupResponsiveHandling() {
        const mediaQuery = window.matchMedia('(max-width: 768px)');
        
        const handleResponsive = (e) => {
            if (e.matches) {
                document.body.classList.add('mobile-view');
            } else {
                document.body.classList.remove('mobile-view');
            }
        };

        mediaQuery.addEventListener('change', handleResponsive);
        handleResponsive(mediaQuery);
    }

    setupKeyboardShortcuts() {
        Utils.events.on(document, 'keydown', (e) => {
            // Ctrl+/ 或 Cmd+/ 显示快捷键帮助
            if ((e.ctrlKey || e.metaKey) && e.key === '/') {
                e.preventDefault();
                this.showKeyboardShortcuts();
            }
            
            // ESC 清空输入
            if (e.key === 'Escape') {
                const messageInput = Utils.dom.get('#messageInput');
                if (messageInput && document.activeElement === messageInput) {
                    messageInput.value = '';
                    messageInput.blur();
                }
            }
        });
    }

    showKeyboardShortcuts() {
        const shortcuts = [
            { key: 'Enter', description: '发送消息' },
            { key: 'Escape', description: '清空输入并失去焦点' },
            { key: 'Ctrl + /', description: '显示快捷键帮助' }
        ];

        const shortcutsHtml = shortcuts.map(shortcut => 
            `<div class="shortcut-item">
                <kbd>${shortcut.key}</kbd>
                <span>${shortcut.description}</span>
            </div>`
        ).join('');

        const modal = Utils.dom.create('div', {
            className: 'shortcuts-modal',
            innerHTML: `
                <div class="modal-content">
                    <h3>⌨️ 键盘快捷键</h3>
                    <div class="shortcuts-list">${shortcutsHtml}</div>
                    <button class="modal-close" onclick="this.closest('.shortcuts-modal').remove()">关闭</button>
                </div>
            `
        });

        document.body.appendChild(modal);
        Utils.animation.fadeIn(modal);

        // 点击背景关闭
        Utils.events.on(modal, 'click', (e) => {
            if (e.target === modal) {
                modal.remove();
            }
        });
    }
}

// 全局函数
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

// 创建全局应用实例
const app = new App();

// DOM加载完成后初始化应用
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => app.init());
} else {
    app.init();
} 