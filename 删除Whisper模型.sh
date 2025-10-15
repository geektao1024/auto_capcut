#!/bin/bash

echo "========================================"
echo "删除Whisper模型和依赖"
echo "========================================"

# 1. 卸载whisper包
echo ""
echo "步骤1: 卸载openai-whisper包..."
pip3 uninstall -y openai-whisper

# 2. 删除Whisper模型缓存
echo ""
echo "步骤2: 删除Whisper模型缓存文件..."
echo "Whisper模型通常存储在: ~/.cache/whisper/"

if [ -d "$HOME/.cache/whisper" ]; then
    echo "找到Whisper缓存目录"
    du -sh "$HOME/.cache/whisper" 2>/dev/null || echo "无法获取目录大小"
    
    read -p "确认删除？(y/n): " confirm
    if [ "$confirm" = "y" ]; then
        rm -rf "$HOME/.cache/whisper"
        echo "✅ Whisper缓存已删除"
    else
        echo "❌ 已取消删除"
    fi
else
    echo "未找到Whisper缓存目录（可能已删除或从未下载）"
fi

# 3. 删除可能的其他缓存位置
echo ""
echo "步骤3: 检查其他可能的缓存位置..."

# 检查torch的hub缓存
if [ -d "$HOME/.cache/torch/hub/checkpoints" ]; then
    echo "找到torch checkpoints: $HOME/.cache/torch/hub/checkpoints"
    du -sh "$HOME/.cache/torch/hub/checkpoints" 2>/dev/null || echo "无法获取目录大小"
fi

# 检查huggingface缓存
if [ -d "$HOME/.cache/huggingface" ]; then
    echo "找到huggingface缓存: $HOME/.cache/huggingface"
    echo "（这个缓存可能被其他程序使用，建议保留）"
fi

echo ""
echo "========================================"
echo "✅ Whisper清理完成"
echo "========================================"
echo ""
echo "已释放的空间："
echo "  - tiny模型:   ~39MB"
echo "  - base模型:   ~74MB"  
echo "  - small模型:  ~244MB"
echo "  - medium模型: ~769MB"
echo "  - large模型:  ~1550MB"
echo ""
echo "如需重新安装: pip3 install openai-whisper"

