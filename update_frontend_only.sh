#!/bin/bash

echo "🎨 开始更新前端文件，保护向量数据库..."

# 检查是否在正确的目录
if [ ! -f "main.py" ]; then
    echo "❌ 错误：请在项目根目录运行此脚本"
    exit 1
fi

# 备份重要的数据库文件
DB_BACKUP_DIR="./db_backup_temp"
mkdir -p "$DB_BACKUP_DIR"

echo "📦 备份向量数据库文件..."
if [ -d "data/chroma_db" ]; then
    cp -r data/chroma_db "$DB_BACKUP_DIR/"
    echo "✅ 数据库备份完成"
fi

# 获取远程更新
echo "🔄 获取远程更新..."
git fetch origin main

# 只更新前端文件
echo "🎨 更新前端文件..."
git checkout origin/main -- static/css/style.css 2>/dev/null || {
    echo "📥 直接下载CSS文件..."
    curl -s -o static/css/style.css https://raw.githubusercontent.com/fightheyyy/EnigeeringRag2/main/static/css/style.css
}

# 恢复数据库文件
echo "🔄 恢复向量数据库..."
if [ -d "$DB_BACKUP_DIR/chroma_db" ]; then
    rm -rf data/chroma_db
    cp -r "$DB_BACKUP_DIR/chroma_db" data/
    echo "✅ 数据库恢复完成"
fi

# 清理临时备份
rm -rf "$DB_BACKUP_DIR"

# 检查CSS文件是否更新成功
if grep -q "移动端输入框问题" static/css/style.css; then
    echo "✅ 前端优化更新成功！"
    echo "📱 移动端界面优化已应用"
else
    echo "⚠️  CSS文件可能未正确更新，请检查"
fi

echo ""
echo "🎉 更新完成！向量数据库保持不变，前端已更新"
echo "💡 提示：现在可以重启应用查看移动端优化效果" 