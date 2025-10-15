# 如何删除Whisper模型和依赖

## 方法1：使用提供的脚本（推荐）

```bash
cd /Users/mac/YouTube/01工具类/playwright
chmod +x 删除Whisper模型.sh
./删除Whisper模型.sh
```

## 方法2：手动删除

### 步骤1：卸载Python包

```bash
pip3 uninstall -y openai-whisper
```

### 步骤2：删除模型缓存

```bash
# 删除Whisper模型缓存（主要空间占用）
rm -rf ~/.cache/whisper

# 查看删除前的大小
du -sh ~/.cache/whisper
```

### 步骤3：检查其他依赖（可选）

Whisper还会安装一些依赖，如果不需要可以删除：

```bash
# 查看已安装的包
pip3 list | grep -E "torch|whisper|openai"

# 如果不需要torch，可以删除（注意：其他程序可能需要）
# pip3 uninstall torch torchaudio
```

## 模型大小参考

删除后可释放的空间（取决于下载过的模型）：

| 模型 | 大小 |
|------|------|
| tiny | 39MB |
| base | 74MB |
| small | 244MB |
| medium | 769MB |
| large | 1550MB |

**如果下载过base模型，大约释放74MB空间**

## 验证删除

```bash
# 检查包是否已卸载
pip3 show openai-whisper

# 检查缓存是否已删除
ls -lh ~/.cache/whisper 2>/dev/null || echo "✅ 缓存已删除"
```

## 重新安装（如需）

```bash
pip3 install openai-whisper
```

---

**注意**：删除后，程序将使用v3.2.0版本，不再包含Whisper字幕功能。  
字幕请在CapCut中使用「智能字幕」功能。

