// 前端性能监控模块
class PerformanceMonitor {
    constructor() {
        this.metrics = {
            pageLoadTime: 0,
            firstPaint: 0,
            firstContentfulPaint: 0,
            largestContentfulPaint: 0,
            timeToInteractive: 0,
            cumulativeLayoutShift: 0,
            firstInputDelay: 0
        };
        
        this.resourceTimings = [];
        this.userInteractions = [];
        this.init();
    }

    init() {
        // 等待页面加载完成
        if (document.readyState === 'complete') {
            this.collectMetrics();
        } else {
            window.addEventListener('load', () => this.collectMetrics());
        }

        // 监听性能观察器
        this.setupPerformanceObserver();
        
        // 监听用户交互
        this.trackUserInteractions();
    }

    collectMetrics() {
        // 收集基本的页面性能指标
        const navigation = performance.getEntriesByType('navigation')[0];
        
        if (navigation) {
            this.metrics.pageLoadTime = navigation.loadEventEnd - navigation.loadEventStart;
            
            // 收集关键渲染路径指标
            const paintEntries = performance.getEntriesByType('paint');
            
            paintEntries.forEach(entry => {
                if (entry.name === 'first-paint') {
                    this.metrics.firstPaint = entry.startTime;
                } else if (entry.name === 'first-contentful-paint') {
                    this.metrics.firstContentfulPaint = entry.startTime;
                }
            });
        }

        // 收集资源加载时间
        this.collectResourceTimings();
        
        console.log('📊 Performance Metrics:', this.metrics);
    }

    setupPerformanceObserver() {
        // 观察LCP (Largest Contentful Paint)
        if ('PerformanceObserver' in window) {
            try {
                const lcpObserver = new PerformanceObserver((entryList) => {
                    const entries = entryList.getEntries();
                    const lastEntry = entries[entries.length - 1];
                    this.metrics.largestContentfulPaint = lastEntry.startTime;
                });
                lcpObserver.observe({ entryTypes: ['largest-contentful-paint'] });

                // 观察FID (First Input Delay)
                const fidObserver = new PerformanceObserver((entryList) => {
                    const entries = entryList.getEntries();
                    entries.forEach(entry => {
                        this.metrics.firstInputDelay = entry.processingStart - entry.startTime;
                    });
                });
                fidObserver.observe({ entryTypes: ['first-input'] });

                // 观察CLS (Cumulative Layout Shift)
                const clsObserver = new PerformanceObserver((entryList) => {
                    const entries = entryList.getEntries();
                    entries.forEach(entry => {
                        if (!entry.hadRecentInput) {
                            this.metrics.cumulativeLayoutShift += entry.value;
                        }
                    });
                });
                clsObserver.observe({ entryTypes: ['layout-shift'] });

            } catch (error) {
                console.warn('Performance Observer setup failed:', error);
            }
        }
    }

    collectResourceTimings() {
        const resources = performance.getEntriesByType('resource');
        
        this.resourceTimings = resources.map(resource => ({
            name: resource.name,
            type: this.getResourceType(resource.name),
            size: resource.transferSize || resource.encodedBodySize,
            loadTime: resource.responseEnd - resource.startTime,
            cached: resource.transferSize === 0 && resource.encodedBodySize > 0
        }));

        // 分析慢加载资源
        const slowResources = this.resourceTimings.filter(resource => resource.loadTime > 1000);
        if (slowResources.length > 0) {
            console.warn('🐌 Slow loading resources:', slowResources);
        }
    }

    getResourceType(url) {
        if (url.includes('.css')) return 'css';
        if (url.includes('.js')) return 'js';
        if (url.match(/\.(jpg|jpeg|png|gif|webp|svg)$/i)) return 'image';
        if (url.includes('.woff') || url.includes('.ttf')) return 'font';
        return 'other';
    }

    trackUserInteractions() {
        ['click', 'scroll', 'keypress'].forEach(eventType => {
            document.addEventListener(eventType, (event) => {
                this.userInteractions.push({
                    type: eventType,
                    timestamp: performance.now(),
                    target: event.target.tagName
                });
            });
        });
    }

    // 监控关键操作的性能
    measureOperation(operationName, asyncOperation) {
        const startTime = performance.now();
        
        if (asyncOperation instanceof Promise) {
            return asyncOperation.then(result => {
                const endTime = performance.now();
                this.logOperationTime(operationName, endTime - startTime);
                return result;
            });
        } else if (typeof asyncOperation === 'function') {
            try {
                const result = asyncOperation();
                const endTime = performance.now();
                this.logOperationTime(operationName, endTime - startTime);
                return result;
            } catch (error) {
                const endTime = performance.now();
                this.logOperationTime(`${operationName} (error)`, endTime - startTime);
                throw error;
            }
        }
    }

    logOperationTime(operationName, duration) {
        console.log(`⏱️ ${operationName}: ${duration.toFixed(2)}ms`);
        
        // 如果操作时间过长，发出警告
        if (duration > 1000) {
            console.warn(`🚨 Slow operation detected: ${operationName} took ${duration.toFixed(2)}ms`);
        }
    }

    // 获取Core Web Vitals评分
    getCoreWebVitals() {
        return {
            LCP: {
                value: this.metrics.largestContentfulPaint,
                rating: this.getLCPRating(this.metrics.largestContentfulPaint)
            },
            FID: {
                value: this.metrics.firstInputDelay,
                rating: this.getFIDRating(this.metrics.firstInputDelay)
            },
            CLS: {
                value: this.metrics.cumulativeLayoutShift,
                rating: this.getCLSRating(this.metrics.cumulativeLayoutShift)
            }
        };
    }

    getLCPRating(lcp) {
        if (lcp <= 2500) return 'good';
        if (lcp <= 4000) return 'needs-improvement';
        return 'poor';
    }

    getFIDRating(fid) {
        if (fid <= 100) return 'good';
        if (fid <= 300) return 'needs-improvement';
        return 'poor';
    }

    getCLSRating(cls) {
        if (cls <= 0.1) return 'good';
        if (cls <= 0.25) return 'needs-improvement';
        return 'poor';
    }

    // 生成性能报告
    generateReport() {
        const report = {
            timestamp: new Date().toISOString(),
            url: window.location.href,
            userAgent: navigator.userAgent,
            metrics: this.metrics,
            coreWebVitals: this.getCoreWebVitals(),
            resourceTimings: this.resourceTimings,
            recommendations: this.getRecommendations()
        };

        console.log('📋 Performance Report:', report);
        return report;
    }

    getRecommendations() {
        const recommendations = [];
        const vitals = this.getCoreWebVitals();

        if (vitals.LCP.rating !== 'good') {
            recommendations.push('优化最大内容绘制(LCP)：压缩图片、优化服务器响应时间');
        }

        if (vitals.FID.rating !== 'good') {
            recommendations.push('优化首次输入延迟(FID)：减少JavaScript执行时间、使用Web Workers');
        }

        if (vitals.CLS.rating !== 'good') {
            recommendations.push('优化累积布局偏移(CLS)：为图片设置尺寸属性、避免动态插入内容');
        }

        // 检查慢加载资源
        const slowResources = this.resourceTimings.filter(r => r.loadTime > 1000);
        if (slowResources.length > 0) {
            recommendations.push(`优化慢加载资源：${slowResources.length}个资源加载时间超过1秒`);
        }

        return recommendations;
    }

    // 内存使用监控
    monitorMemoryUsage() {
        if ('memory' in performance) {
            const memInfo = performance.memory;
            console.log('🧠 Memory Usage:', {
                used: `${(memInfo.usedJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
                total: `${(memInfo.totalJSHeapSize / 1024 / 1024).toFixed(2)} MB`,
                limit: `${(memInfo.jsHeapSizeLimit / 1024 / 1024).toFixed(2)} MB`
            });

            // 内存使用率超过80%时警告
            const usageRatio = memInfo.usedJSHeapSize / memInfo.jsHeapSizeLimit;
            if (usageRatio > 0.8) {
                console.warn('⚠️ High memory usage detected:', `${(usageRatio * 100).toFixed(1)}%`);
            }
        }
    }

    // 开始持续监控
    startMonitoring(interval = 30000) {
        setInterval(() => {
            this.monitorMemoryUsage();
            this.collectResourceTimings();
        }, interval);
    }
}

// 创建全局性能监控实例
const performanceMonitor = new PerformanceMonitor();

// 暴露给全局
window.performanceMonitor = performanceMonitor;

// 3秒后开始持续监控
setTimeout(() => {
    performanceMonitor.startMonitoring();
}, 3000); 