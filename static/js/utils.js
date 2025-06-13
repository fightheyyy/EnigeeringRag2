// 工具函数库
class Utils {
    // 防抖函数
    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    // 节流函数
    static throttle(func, limit) {
        let inThrottle;
        return function(...args) {
            if (!inThrottle) {
                func.apply(this, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    // 格式化日期
    static formatDate(date = new Date()) {
        const options = {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        };
        return date.toLocaleDateString('zh-CN', options);
    }

    // 生成唯一ID
    static generateId(prefix = 'id') {
        return `${prefix}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // 本地存储封装
    static storage = {
        set(key, value) {
            try {
                localStorage.setItem(key, JSON.stringify(value));
                return true;
            } catch (e) {
                console.warn('Local storage set failed:', e);
                return false;
            }
        },

        get(key, defaultValue = null) {
            try {
                const item = localStorage.getItem(key);
                return item ? JSON.parse(item) : defaultValue;
            } catch (e) {
                console.warn('Local storage get failed:', e);
                return defaultValue;
            }
        },

        remove(key) {
            try {
                localStorage.removeItem(key);
                return true;
            } catch (e) {
                console.warn('Local storage remove failed:', e);
                return false;
            }
        }
    };

    // DOM 操作封装
    static dom = {
        // 获取元素
        get(selector) {
            return document.querySelector(selector);
        },

        // 获取所有匹配元素
        getAll(selector) {
            return document.querySelectorAll(selector);
        },

        // 创建元素
        create(tag, attributes = {}, textContent = '') {
            const element = document.createElement(tag);
            
            Object.entries(attributes).forEach(([key, value]) => {
                if (key === 'className') {
                    element.className = value;
                } else if (key === 'innerHTML') {
                    element.innerHTML = value;
                } else {
                    element.setAttribute(key, value);
                }
            });

            if (textContent) {
                element.textContent = textContent;
            }

            return element;
        },

        // 添加类名
        addClass(element, className) {
            if (element) element.classList.add(className);
        },

        // 移除类名
        removeClass(element, className) {
            if (element) element.classList.remove(className);
        },

        // 切换类名
        toggleClass(element, className) {
            if (element) element.classList.toggle(className);
        },

        // 显示元素
        show(element, display = 'block') {
            if (element) element.style.display = display;
        },

        // 隐藏元素
        hide(element) {
            if (element) element.style.display = 'none';
        },

        // 滚动到元素
        scrollTo(element, behavior = 'smooth') {
            if (element) {
                element.scrollIntoView({ behavior, block: 'center' });
            }
        }
    };

    // 事件管理
    static events = {
        // 添加事件监听
        on(element, event, handler, options = {}) {
            if (element && typeof handler === 'function') {
                element.addEventListener(event, handler, options);
            }
        },

        // 移除事件监听
        off(element, event, handler) {
            if (element && typeof handler === 'function') {
                element.removeEventListener(event, handler);
            }
        },

        // 一次性事件监听
        once(element, event, handler) {
            if (element && typeof handler === 'function') {
                element.addEventListener(event, handler, { once: true });
            }
        },

        // 自定义事件触发
        emit(element, eventName, detail = {}) {
            if (element) {
                const event = new CustomEvent(eventName, { detail });
                element.dispatchEvent(event);
            }
        }
    };

    // HTTP 请求封装
    static http = {
        // GET 请求
        async get(url, options = {}) {
            return await this.request(url, { ...options, method: 'GET' });
        },

        // POST 请求
        async post(url, data, options = {}) {
            return await this.request(url, {
                ...options,
                method: 'POST',
                body: JSON.stringify(data),
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });
        },

        // 通用请求方法
        async request(url, options = {}) {
            try {
                const response = await fetch(url, {
                    ...options,
                    headers: {
                        'Accept': 'application/json',
                        ...options.headers
                    }
                });

                const data = await response.json();

                if (!response.ok) {
                    throw new Error(data.detail || `HTTP ${response.status}`);
                }

                return { success: true, data };
            } catch (error) {
                console.error('Request failed:', error);
                return { success: false, error: error.message };
            }
        }
    };

    // 文本处理工具
    static text = {
        // 截断文本
        truncate(text, length = 100, suffix = '...') {
            return text.length > length ? text.substring(0, length) + suffix : text;
        },

        // 转义HTML
        escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        },

        // 移除HTML标签
        stripHtml(html) {
            const div = document.createElement('div');
            div.innerHTML = html;
            return div.textContent || div.innerText || '';
        },

        // 高亮关键词
        highlight(text, keyword, className = 'highlight') {
            if (!keyword) return text;
            const regex = new RegExp(`(${keyword})`, 'gi');
            return text.replace(regex, `<span class="${className}">$1</span>`);
        }
    };

    // 验证工具
    static validate = {
        // 验证邮箱
        email(email) {
            const regex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            return regex.test(email);
        },

        // 验证手机号
        phone(phone) {
            const regex = /^1[3-9]\d{9}$/;
            return regex.test(phone);
        },

        // 验证非空
        required(value) {
            return value !== null && value !== undefined && value.toString().trim() !== '';
        },

        // 验证长度
        length(value, min = 0, max = Infinity) {
            const len = value ? value.toString().length : 0;
            return len >= min && len <= max;
        }
    };

    // 动画工具
    static animation = {
        // 淡入效果
        fadeIn(element, duration = 300) {
            if (!element) return;
            
            element.style.opacity = '0';
            element.style.display = 'block';
            
            let start = performance.now();
            
            const animate = (timestamp) => {
                const elapsed = timestamp - start;
                const progress = Math.min(elapsed / duration, 1);
                
                element.style.opacity = progress;
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            };
            
            requestAnimationFrame(animate);
        },

        // 淡出效果
        fadeOut(element, duration = 300) {
            if (!element) return;
            
            let start = performance.now();
            const initialOpacity = parseFloat(getComputedStyle(element).opacity) || 1;
            
            const animate = (timestamp) => {
                const elapsed = timestamp - start;
                const progress = Math.min(elapsed / duration, 1);
                
                element.style.opacity = initialOpacity * (1 - progress);
                
                if (progress < 1) {
                    requestAnimationFrame(animate);
                } else {
                    element.style.display = 'none';
                }
            };
            
            requestAnimationFrame(animate);
        }
    };

    // 性能监控
    static performance = {
        // 标记开始时间
        mark(name) {
            if ('performance' in window && 'mark' in performance) {
                performance.mark(`${name}-start`);
            }
        },

        // 测量执行时间
        measure(name) {
            if ('performance' in window && 'mark' in performance && 'measure' in performance) {
                performance.mark(`${name}-end`);
                performance.measure(name, `${name}-start`, `${name}-end`);
                
                const measures = performance.getEntriesByName(name);
                if (measures.length > 0) {
                    return measures[measures.length - 1].duration;
                }
            }
            return 0;
        }
    };
}

// 导出工具类（如果需要）
if (typeof module !== 'undefined' && module.exports) {
    module.exports = Utils;
} 