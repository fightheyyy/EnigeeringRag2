// 图纸上传功能
let selectedDrawingFile = null;

// 触发图纸上传
function triggerDrawingUpload() {
    const fileInput = document.getElementById('drawingFileInput');
    fileInput.click();
}

// 处理文件选择
document.addEventListener('DOMContentLoaded', function() {
    const fileInput = document.getElementById('drawingFileInput');
    if (fileInput) {
        fileInput.addEventListener('change', handleDrawingFileSelect);
    }
});

function handleDrawingFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // 验证文件类型
    if (file.type !== 'application/pdf') {
        showNotification('请选择PDF格式的图纸文件', 'error');
        return;
    }

    // 验证文件大小 (100MB)
    const maxSize = 100 * 1024 * 1024;
    if (file.size > maxSize) {
        showNotification('文件大小不能超过100MB', 'error');
        return;
    }

    selectedDrawingFile = file;
    showDrawingUploadPanel(file);
}

// 显示图纸上传面板
function showDrawingUploadPanel(file) {
    const panel = document.getElementById('drawingUploadPanel');
    const fileName = document.getElementById('uploadFileName');
    const fileSize = document.getElementById('uploadFileSize');

    fileName.textContent = file.name;
    fileSize.textContent = formatFileSize(file.size);

    panel.style.display = 'block';
    
    // 滚动到面板位置
    setTimeout(() => {
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }, 100);
}

// 取消图纸上传
function cancelDrawingUpload() {
    const panel = document.getElementById('drawingUploadPanel');
    const fileInput = document.getElementById('drawingFileInput');
    
    panel.style.display = 'none';
    fileInput.value = '';
    selectedDrawingFile = null;
    
    // 清空表单
    document.getElementById('uploadProjectName').value = '';
    document.getElementById('uploadDrawingType').value = '';
    document.getElementById('uploadDrawingPhase').value = '';
    
    // 清理重复文件信息
    const duplicateInfo = panel.querySelector('.duplicate-info');
    if (duplicateInfo) {
        duplicateInfo.remove();
    }
    
    // 恢复按钮状态
    const confirmBtn = document.querySelector('.confirm-btn');
    const cancelBtn = document.querySelector('.cancel-btn');
    if (confirmBtn) {
        confirmBtn.textContent = '上传处理';
        confirmBtn.onclick = () => confirmDrawingUpload();
        confirmBtn.disabled = false;
    }
    if (cancelBtn) {
        cancelBtn.textContent = '取消';
    }
}

// 确认图纸上传
async function confirmDrawingUpload() {
    if (!selectedDrawingFile) {
        showNotification('请先选择图纸文件', 'error');
        return;
    }

    const confirmBtn = document.querySelector('.confirm-btn');
    const originalText = confirmBtn.textContent;
    
    try {
        // 禁用按钮并显示加载状态
        confirmBtn.disabled = true;
        confirmBtn.textContent = '上传中...';

        // 准备表单数据
        const formData = new FormData();
        formData.append('file', selectedDrawingFile);
        formData.append('project_name', document.getElementById('uploadProjectName').value);
        formData.append('drawing_type', document.getElementById('uploadDrawingType').value);
        formData.append('drawing_phase', document.getElementById('uploadDrawingPhase').value);
        formData.append('created_by', '用户'); // 可以从用户信息获取

        // 在聊天窗口显示上传进度
        addUploadProgressMessage();

        // 发送上传请求
        const response = await fetch('/upload-drawing', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok) {
            if (result.is_duplicate) {
                // 检测到重复文件
                addDuplicateFileMessage(result);
                showDuplicateConfirmDialog(result);
            } else {
                // 上传成功
                addUploadSuccessMessage(result);
                cancelDrawingUpload(); // 关闭上传面板
                showNotification('图纸上传成功！已添加到知识库', 'success');
            }
        } else {
            // 上传失败
            addUploadErrorMessage(result.detail || '上传失败');
            showNotification(result.detail || '图纸上传失败', 'error');
        }

    } catch (error) {
        console.error('上传错误:', error);
        addUploadErrorMessage('网络错误：' + error.message);
        showNotification('网络错误，请稍后重试', 'error');
    } finally {
        // 恢复按钮状态
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalText;
    }
}

// 在聊天窗口添加上传进度消息
function addUploadProgressMessage() {
    const chatMessages = document.getElementById('chatMessages');
    const progressMessage = document.createElement('div');
    progressMessage.className = 'message assistant upload-progress-message';
    progressMessage.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <div class="loading-spinner" style="width: 20px; height: 20px;"></div>
            <span>📋 正在上传图纸并处理...</span>
        </div>
        <div style="margin-top: 8px; font-size: 0.9em; color: #666;">
            • 上传到MinIO存储<br>
            • Gemini提取文本内容<br>
            • 向量化并添加到知识库
        </div>
    `;
    
    chatMessages.appendChild(progressMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 在聊天窗口添加上传成功消息
function addUploadSuccessMessage(result) {
    const chatMessages = document.getElementById('chatMessages');
    
    // 移除进度消息
    const progressMsg = chatMessages.querySelector('.upload-progress-message');
    if (progressMsg) {
        progressMsg.remove();
    }
    
    const successMessage = document.createElement('div');
    successMessage.className = 'message assistant upload-success-message';
    successMessage.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <span style="font-size: 1.2em;">✅</span>
            <strong>图纸上传成功！</strong>
        </div>
        <div style="background: white; padding: 12px; border-radius: 8px; border: 1px solid #c3e6cb;">
            <div style="margin-bottom: 8px;"><strong>📋 ${result.drawing_name}</strong></div>
            <div style="font-size: 0.9em; color: #666; line-height: 1.4;">
                • 文件大小: ${result.file_size_mb} MB<br>
                • 向量块数: ${result.vector_chunks_count}<br>
                • 处理状态: ${result.process_status}<br>
                • 知识库: drawings
            </div>
            ${result.minio_url ? `<div style="margin-top: 8px;">
                <a href="${result.minio_url}" target="_blank" style="color: #007bff; text-decoration: none;">
                    🔗 查看原文件
                </a>
            </div>` : ''}
        </div>
        <div style="margin-top: 12px; padding: 8px; background: #e7f3ff; border-radius: 6px; font-size: 0.9em;">
            💡 图纸内容已添加到知识库，您现在可以询问相关问题了！
        </div>
    `;
    
    chatMessages.appendChild(successMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 在聊天窗口添加上传错误消息
function addUploadErrorMessage(errorMsg) {
    const chatMessages = document.getElementById('chatMessages');
    
    // 移除进度消息
    const progressMsg = chatMessages.querySelector('.upload-progress-message');
    if (progressMsg) {
        progressMsg.remove();
    }
    
    const errorMessage = document.createElement('div');
    errorMessage.className = 'message assistant upload-error-message';
    errorMessage.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
            <span style="font-size: 1.2em;">❌</span>
            <strong>图纸上传失败</strong>
        </div>
        <div style="background: white; padding: 12px; border-radius: 8px; border: 1px solid #f5c6cb;">
            ${errorMsg}
        </div>
        <div style="margin-top: 8px; font-size: 0.9em;">
            💡 请检查文件格式和大小，或稍后重试
        </div>
    `;
    
    chatMessages.appendChild(errorMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 在聊天窗口添加重复文件消息
function addDuplicateFileMessage(result) {
    const chatMessages = document.getElementById('chatMessages');
    
    // 移除进度消息
    const progressMsg = chatMessages.querySelector('.upload-progress-message');
    if (progressMsg) {
        progressMsg.remove();
    }
    
    const duplicateMessage = document.createElement('div');
    duplicateMessage.className = 'message assistant upload-duplicate-message';
    duplicateMessage.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
            <span style="font-size: 1.2em;">⚠️</span>
            <strong>检测到重复文件</strong>
        </div>
        <div style="background: white; padding: 12px; border-radius: 8px; border: 1px solid #ffeaa7;">
            <div style="margin-bottom: 8px;"><strong>📋 ${result.existing_file.original_filename}</strong></div>
            <div style="font-size: 0.9em; color: #666; line-height: 1.4;">
                • 已存在的文件ID: ${result.existing_file.id}<br>
                • 上传时间: ${result.existing_file.upload_time}<br>
                • 处理状态: ${result.existing_file.process_status}<br>
                • 向量状态: ${result.existing_file.vector_status}
            </div>
            ${result.existing_file.minio_url ? `<div style="margin-top: 8px;">
                <a href="${result.existing_file.minio_url}" target="_blank" style="color: #007bff; text-decoration: none;">
                    🔗 查看已存在的文件
                </a>
            </div>` : ''}
        </div>
        <div style="margin-top: 12px; padding: 8px; background: #fff3cd; border-radius: 6px; font-size: 0.9em;">
            💡 系统检测到相同的文件已经存在，您可以选择强制重新上传或取消操作
        </div>
    `;
    
    chatMessages.appendChild(duplicateMessage);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// 显示重复文件确认对话框
function showDuplicateConfirmDialog(result) {
    const confirmBtn = document.querySelector('.confirm-btn');
    const originalText = confirmBtn.textContent;
    
    // 更新按钮文本和功能
    confirmBtn.textContent = '强制重新上传';
    confirmBtn.onclick = () => forceUploadDrawing();
    
    // 添加取消按钮的额外说明
    const cancelBtn = document.querySelector('.cancel-btn');
    cancelBtn.textContent = '取消上传';
    
    // 在上传面板中显示重复文件信息
    const panel = document.getElementById('drawingUploadPanel');
    let duplicateInfo = panel.querySelector('.duplicate-info');
    if (!duplicateInfo) {
        duplicateInfo = document.createElement('div');
        duplicateInfo.className = 'duplicate-info';
        duplicateInfo.style.cssText = `
            background: #fff3cd;
            border: 1px solid #ffeaa7;
            border-radius: 6px;
            padding: 10px;
            margin-bottom: 10px;
            font-size: 0.9em;
        `;
        panel.querySelector('.upload-info').insertBefore(duplicateInfo, panel.querySelector('.upload-actions'));
    }
    
    duplicateInfo.innerHTML = `
        <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 6px;">
            <span>⚠️</span>
            <strong>检测到重复文件</strong>
        </div>
        <div>已存在相同文件（${result.existing_file.upload_time}）</div>
        <div style="margin-top: 4px; font-size: 0.85em; color: #856404;">
            点击"强制重新上传"将覆盖处理，或点击"取消上传"
        </div>
    `;
}

// 强制上传图纸
async function forceUploadDrawing() {
    if (!selectedDrawingFile) {
        showNotification('请先选择图纸文件', 'error');
        return;
    }

    const confirmBtn = document.querySelector('.confirm-btn');
    const originalText = confirmBtn.textContent;
    
    try {
        // 禁用按钮并显示加载状态
        confirmBtn.disabled = true;
        confirmBtn.textContent = '强制上传中...';

        // 准备表单数据
        const formData = new FormData();
        formData.append('file', selectedDrawingFile);
        formData.append('project_name', document.getElementById('uploadProjectName').value);
        formData.append('drawing_type', document.getElementById('uploadDrawingType').value);
        formData.append('drawing_phase', document.getElementById('uploadDrawingPhase').value);
        formData.append('created_by', '用户');
        formData.append('force_upload', 'true'); // 强制上传标志

        // 在聊天窗口显示上传进度
        addUploadProgressMessage();

        // 发送上传请求
        const response = await fetch('/upload-drawing', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (response.ok && !result.is_duplicate) {
            // 上传成功
            addUploadSuccessMessage(result);
            cancelDrawingUpload(); // 关闭上传面板
            showNotification('图纸强制上传成功！已添加到知识库', 'success');
        } else {
            // 上传失败
            addUploadErrorMessage(result.detail || result.duplicate_message || '强制上传失败');
            showNotification(result.detail || '图纸强制上传失败', 'error');
        }

    } catch (error) {
        console.error('强制上传错误:', error);
        addUploadErrorMessage('网络错误：' + error.message);
        showNotification('网络错误，请稍后重试', 'error');
    } finally {
        // 恢复按钮状态
        confirmBtn.disabled = false;
        confirmBtn.textContent = originalText;
        confirmBtn.onclick = () => confirmDrawingUpload();
    }
}

// 格式化文件大小
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

// 显示通知
function showNotification(message, type = 'info') {
    // 避免递归调用，直接创建通知
    {
        // 创建简单的通知
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 20px;
            border-radius: 8px;
            color: white;
            font-weight: 500;
            z-index: 1000;
            animation: slideInRight 0.3s ease-out;
        `;
        
        switch(type) {
            case 'success':
                notification.style.background = '#28a745';
                break;
            case 'error':
                notification.style.background = '#dc3545';
                break;
            case 'warning':
                notification.style.background = '#ffc107';
                notification.style.color = '#212529';
                break;
            default:
                notification.style.background = '#007bff';
        }
        
        notification.textContent = message;
        document.body.appendChild(notification);
        
        // 3秒后自动移除
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// 拖拽上传支持
document.addEventListener('DOMContentLoaded', function() {
    const chatContainer = document.querySelector('.chat-container');
    if (!chatContainer) return;

    // 防止默认拖拽行为
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        chatContainer.addEventListener(eventName, preventDefaults, false);
        document.body.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // 拖拽进入和离开的视觉反馈
    ['dragenter', 'dragover'].forEach(eventName => {
        chatContainer.addEventListener(eventName, highlight, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        chatContainer.addEventListener(eventName, unhighlight, false);
    });

    function highlight(e) {
        chatContainer.style.background = 'rgba(0, 123, 255, 0.1)';
        chatContainer.style.border = '2px dashed #007bff';
    }

    function unhighlight(e) {
        chatContainer.style.background = '';
        chatContainer.style.border = '';
    }

    // 处理文件拖拽
    chatContainer.addEventListener('drop', handleDrop, false);

    function handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            const file = files[0];
            if (file.type === 'application/pdf') {
                selectedDrawingFile = file;
                showDrawingUploadPanel(file);
            } else {
                showNotification('请拖拽PDF格式的图纸文件', 'warning');
            }
        }
    }
}); 