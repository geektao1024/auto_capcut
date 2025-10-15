# CapCut 字幕识别结构分析

## 📋 概述

基于对1012草稿的分析，CapCut的字幕识别功能涉及以下几个部分：

## 1️⃣  轨道结构

### 字幕轨道 (text track)
```json
{
  "type": "text",
  "flag": 1,  // ⭐ 1 = 识别字幕轨道，0 = 手动添加的字幕
  "attribute": 0,
  "segments": [
    {
      "material_id": "指向texts材料的ID",
      "target_timerange": {
        "start": 0,
        "duration": 1000000  // 微秒
      },
      "caption_info": {
        // 字幕样式信息
      }
    }
  ]
}
```

**关键点**:
- `flag: 1` 表示这是AI识别的字幕轨道
- 每个segment对应一句字幕

## 2️⃣  字幕材料 (texts)

```json
{
  "materials": {
    "texts": [
      {
        "id": "UUID",
        "content": "The little girl walked into the house",  // 字幕文字
        "fonts": [
          {
            "id": "字体ID",
            "name": "SourceHanSansCN-Bold",  // 字体名称
            "path": "字体路径"
          }
        ],
        "styles": [
          {
            "fill": {
              "alpha": 1.0,
              "content": {
                "solid": {
                  "color": [1.0, 1.0, 1.0]  // RGB白色
                }
              }
            },
            "range": [0, 37],  // 样式应用范围
            "size": 15.0,  // 字号
            "stroke": {
              "width": 0.2,  // 描边宽度
              "color": [0.0, 0.0, 0.0]  // 描边颜色
            }
          }
        ],
        "type": "caption",
        "duration": 1000000,
        "start_time": 0
      }
    ]
  }
}
```

## 3️⃣  字幕模板 (text_templates)

```json
{
  "materials": {
    "text_templates": [
      {
        "id": "UUID",
        "name": "模板名称",
        "platform": "all",
        "category_id": "字幕分类",
        "category_name": "字幕",
        "resource_id": "资源ID",
        // 包含字幕样式的完整配置
      }
    ]
  }
}
```

## 4️⃣  字幕识别配置 (config)

### 关键配置项

```json
{
  "config": {
    "subtitle_sync": true,  // 是否启用字幕同步
    "subtitle_recognition_id": "",  // 识别ID，空表示未识别或已完成
    "subtitle_taskinfo": [
      {
        "ai_accurate_recognize": true,  // AI精准识别
        "ai_only": false,
        "is_empty": false,
        "language": "en",  // 语言代码：en=英文，zh=中文
        "task_id": "任务ID",
        "task_state": 2,  // 任务状态：0=未开始，1=进行中，2=完成
        "words": [
          {
            "end_time": 1500000,  // 结束时间（微秒）
            "start_time": 0,      // 开始时间（微秒）
            "text": "The little girl",  // 识别文字
            "confidence": 0.95    // 置信度
          }
        ]
      }
    ],
    "subtitle_keywords_config": {
      "font_size_ratio": 1.0,
      "is_change_font_size": false,
      "styles": "{...}",  // JSON字符串
      "subtitle_template_font_size": 0.0,
      "subtitle_template_keywords_original_font_size": 19.5,
      "subtitle_template_original_font_size": 15.0
    }
  }
}
```

## 🔍  识别流程分析

### CapCut智能识别的工作流程

1. **用户操作**:
   - 在CapCut中点击"文本" → "智能字幕" → "识别字幕"
   - 选择语言（英文/中文等）
   - 开始识别

2. **生成的数据**:
   - `subtitle_taskinfo` 包含识别任务和结果
   - `texts` 材料：每句字幕的内容和样式
   - `text` 轨道：字幕片段的时间线排列
   - `text_templates`: 应用的字幕样式模板

3. **数据结构关系**:
```
subtitle_taskinfo.words[] (识别结果)
    ↓
texts[] (字幕材料)
    ↓
text track.segments[] (时间线上的字幕片段)
```

## 🤖 能否用脚本实现？

### 方案A: 纯JSON生成（困难）❌

**问题**:
1. 需要语音识别API（OpenAI Whisper等）
2. 需要完全模拟CapCut的内部数据结构
3. 字幕样式和模板结构复杂

### 方案B: 触发CapCut识别（推荐）✅

**思路**:
1. 脚本生成基础草稿（音频+图片，无字幕）
2. 在config中设置标记，提示用户使用CapCut识别
3. 或者通过CapCut API触发识别（如果有）

### 方案C: 使用Whisper预生成字幕（半自动）⚙️

**步骤**:
1. 用Whisper识别音频 → 得到时间轴字幕
2. 脚本生成texts材料和text轨道
3. 应用默认字幕样式

**优点**: 
- 完全自动化
- 可自定义样式

**缺点**:
- 需要安装Whisper
- 可能不如CapCut识别准确

## 📝 实现建议

### 推荐方案: Whisper + 字幕生成

```python
# 1. 使用Whisper识别
import whisper

model = whisper.load_model("base")
result = model.transcribe(audio_file, language="en")

# result["segments"] 包含:
# - text: 文字
# - start: 开始时间（秒）
# - end: 结束时间（秒）

# 2. 生成texts材料
for segment in result["segments"]:
    text_material = {
        "id": str(uuid.uuid4()).upper(),
        "content": segment["text"],
        "fonts": [...],  # 使用默认字体
        "styles": [...],  # 应用默认样式
        "type": "caption",
        "duration": int((segment["end"] - segment["start"]) * 1000000),
        "start_time": int(segment["start"] * 1000000)
    }
    draft['materials']['texts'].append(text_material)

# 3. 创建text轨道
text_track = {
    "type": "text",
    "flag": 0,  # 0 = 手动添加（不是AI识别）
    "segments": [...]
}
```

## 🎯 下一步行动

1. **查看用户需求**:
   - 是否需要完全自动化字幕？
   - 能否接受在CapCut中手动点击"识别字幕"？
   - 对字幕样式有什么要求？

2. **选择实现方案**:
   - 方案B: 提示用户使用CapCut识别（最简单）
   - 方案C: Whisper预生成（最灵活）

3. **准备实现**:
   - 如果使用Whisper，需要安装：`pip install openai-whisper`
   - 准备默认字幕样式模板
   - 测试生成的字幕在CapCut中的显示效果

---

**建议**: 先实现方案B（提示用户手动识别），如果用户需要完全自动化，再实现方案C（Whisper集成）。

