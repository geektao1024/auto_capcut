# Whisper + CapCut 字幕特效实现方案

## 🎯 需求分析

1. **单词逐个弹出效果** 
   - 每个单词单独显示
   - 带入场动画（弹出/淡入）

2. **字幕样式自定义**
   - 颜色（RGB）
   - 描边（宽度、颜色）
   - 字号
   - 字体

## ✅ 技术可行性

### 1. Whisper Word-Level Timestamps

```python
import whisper

model = whisper.load_model("base")
result = model.transcribe(
    "audio.mp3",
    language="en",
    word_timestamps=True  # ⭐ 启用单词级时间戳
)

# 输出示例
{
  "segments": [
    {
      "text": "The little girl walked into the house",
      "words": [
        {"word": "The", "start": 0.0, "end": 0.18},
        {"word": "little", "start": 0.18, "end": 0.42},
        {"word": "girl", "start": 0.42, "end": 0.68},
        {"word": "walked", "start": 0.68, "end": 1.02},
        ...
      ]
    }
  ]
}
```

✅ **优点**：
- 精确的单词时间戳（精度约0.02秒）
- 自动分词，支持多语言
- 开源免费，本地运行

### 2. CapCut字幕样式控制

#### texts材料结构
```json
{
  "id": "UUID",
  "content": "单词内容",
  "fonts": [
    {
      "id": "",
      "name": "SourceHanSansCN-Bold",  // 字体名称
      "path": ""
    }
  ],
  "styles": [
    {
      "fill": {
        "alpha": 1.0,
        "content": {
          "solid": {
            "color": [1.0, 1.0, 0.0]  // ⭐ RGB颜色（黄色）
          }
        }
      },
      "range": [0, 4],  // 应用到整个单词
      "size": 20.0,  // ⭐ 字号
      "stroke": {
        "alpha": 1.0,
        "width": 0.3,  // ⭐ 描边宽度
        "content": {
          "solid": {
            "color": [0.0, 0.0, 0.0]  // ⭐ 描边颜色（黑色）
          }
        }
      }
    }
  ],
  "type": "caption",
  "alignment": 1,  // 0=左对齐, 1=居中, 2=右对齐
  "line_spacing": 0.0,
  "bold": true,  // 粗体
  "italic": false  // 斜体
}
```

✅ **完全可控制**：
- ✅ 颜色：`fill.content.solid.color` (RGB 0-1范围)
- ✅ 描边：`stroke.width` 和 `stroke.content.solid.color`
- ✅ 字号：`size`
- ✅ 字体：`fonts[0].name`
- ✅ 对齐：`alignment`

### 3. 字幕动画效果

#### 方案A: 使用material_animations（入场动画）⭐ 推荐

```json
{
  "materials": {
    "material_animations": [
      {
        "animations": [{
          "anim_adjust_params": null,
          "category_id": "in",
          "category_name": "入场",
          "duration": 200000,  // 0.2秒动画时长
          "id": "431664",  // 动画ID
          "material_type": "text",  // ⭐ 字幕动画
          "name": "向上弹入",  // 或"淡入"、"放大"等
          "panel": "text",
          "path": "特效资源路径",
          "type": "in",
          "start": 0
        }],
        "id": "UUID",
        "type": "sticker_animation"
      }
    ]
  }
}
```

然后在text segment中引用：
```json
{
  "material_id": "字幕material_id",
  "extra_material_refs": [
    "动画material_id"  // ⭐ 引用动画
  ]
}
```

#### 方案B: 使用caption_info（字幕特有动画）

```json
{
  "caption_info": {
    "animations": {
      "in": {
        "type": "bounce",  // 弹跳
        "duration": 200000
      }
    }
  }
}
```

## 🔧 完整实现方案

### 步骤1: 安装Whisper

```bash
pip install openai-whisper
```

### 步骤2: 识别音频获取单词时间戳

```python
import whisper

def transcribe_with_word_timestamps(audio_file, language="en"):
    """使用Whisper识别音频，返回单词级时间戳"""
    
    model = whisper.load_model("base")
    result = model.transcribe(
        audio_file,
        language=language,
        word_timestamps=True,
        verbose=False
    )
    
    # 展平所有单词
    words = []
    for segment in result["segments"]:
        for word in segment.get("words", []):
            words.append({
                "text": word["word"].strip(),
                "start": word["start"],
                "end": word["end"]
            })
    
    return words

# 使用
words = transcribe_with_word_timestamps("audio.mp3", "en")
# [
#   {"text": "The", "start": 0.0, "end": 0.18},
#   {"text": "little", "start": 0.18, "end": 0.42},
#   ...
# ]
```

### 步骤3: 生成字幕材料和轨道

```python
def create_word_subtitles(words, draft, config):
    """为每个单词创建字幕材料和片段"""
    
    # 字幕配置（可自定义）
    SUBTITLE_CONFIG = {
        "font_size": 20.0,
        "color": [1.0, 1.0, 0.0],  # 黄色
        "stroke_width": 0.3,
        "stroke_color": [0.0, 0.0, 0.0],  # 黑色描边
        "alignment": 1,  # 居中
        "animation": "bounce"  # 弹跳入场
    }
    
    texts = []
    text_segments = []
    
    for word_data in words:
        word = word_data["text"]
        start = int(word_data["start"] * 1000000)  # 转为微秒
        end = int(word_data["end"] * 1000000)
        duration = end - start
        
        # 1. 创建字幕材料
        text_id = str(uuid.uuid4()).upper()
        text_material = {
            "id": text_id,
            "content": word,
            "fonts": [{
                "id": "",
                "name": "SourceHanSansCN-Bold",
                "path": ""
            }],
            "styles": [{
                "fill": {
                    "alpha": 1.0,
                    "content": {
                        "solid": {
                            "color": SUBTITLE_CONFIG["color"]
                        }
                    }
                },
                "range": [0, len(word)],
                "size": SUBTITLE_CONFIG["font_size"],
                "stroke": {
                    "alpha": 1.0,
                    "width": SUBTITLE_CONFIG["stroke_width"],
                    "content": {
                        "solid": {
                            "color": SUBTITLE_CONFIG["stroke_color"]
                        }
                    }
                }
            }],
            "type": "caption",
            "alignment": SUBTITLE_CONFIG["alignment"],
            "line_spacing": 0.0
        }
        texts.append(text_material)
        
        # 2. 创建字幕片段
        text_segment = {
            "id": str(uuid.uuid4()).upper(),
            "material_id": text_id,
            "target_timerange": {
                "start": start,
                "duration": duration
            },
            "source_timerange": {
                "start": 0,
                "duration": duration
            },
            "extra_material_refs": [],  # 可以添加动画引用
            "caption_info": None,
            "visible": True
        }
        text_segments.append(text_segment)
    
    return texts, text_segments
```

### 步骤4: 添加入场动画（可选）

```python
def create_bounce_animation():
    """创建弹跳入场动画"""
    
    animation_id = str(uuid.uuid4()).upper()
    animation = {
        "animations": [{
            "anim_adjust_params": None,
            "category_id": "in",
            "category_name": "入场",
            "duration": 200000,  # 0.2秒
            "id": "text_bounce",
            "material_type": "text",
            "name": "向上弹入",
            "panel": "text",
            "path": "",
            "type": "in",
            "start": 0
        }],
        "id": animation_id,
        "type": "sticker_animation"
    }
    
    return animation_id, animation
```

### 步骤5: 集成到草稿生成

```python
def create_capcut_draft_with_subtitles(audio_file, images, output_dir):
    """生成带字幕的CapCut草稿"""
    
    # 1. Whisper识别
    print("🎤 识别音频...")
    words = transcribe_with_word_timestamps(audio_file, language="en")
    print(f"✅ 识别到 {len(words)} 个单词")
    
    # 2. 创建基础草稿
    draft = create_base_draft(audio_file, images)
    
    # 3. 添加字幕
    print("📝 生成字幕...")
    texts, text_segments = create_word_subtitles(words, draft, config)
    
    draft['materials']['texts'] = texts
    
    # 4. 创建字幕轨道
    text_track = {
        "type": "text",
        "flag": 0,  # 0=手动添加（脚本生成）
        "attribute": 0,
        "id": str(uuid.uuid4()).upper(),
        "segments": text_segments
    }
    
    draft['tracks'].append(text_track)
    
    # 5. 保存草稿
    save_draft(draft, output_dir)
    
    print(f"✅ 草稿创建完成！包含 {len(words)} 个单词字幕")
```

## 🎨 样式自定义配置

### 预设样式模板

```python
# 配置文件顶部
SUBTITLE_STYLES = {
    "默认": {
        "font_size": 20.0,
        "color": [1.0, 1.0, 1.0],  # 白色
        "stroke_width": 0.3,
        "stroke_color": [0.0, 0.0, 0.0]  # 黑色描边
    },
    "黄色突出": {
        "font_size": 22.0,
        "color": [1.0, 1.0, 0.0],  # 黄色
        "stroke_width": 0.4,
        "stroke_color": [0.0, 0.0, 0.0]
    },
    "红色强调": {
        "font_size": 24.0,
        "color": [1.0, 0.2, 0.2],  # 红色
        "stroke_width": 0.5,
        "stroke_color": [1.0, 1.0, 1.0]  # 白色描边
    }
}

# 使用
SUBTITLE_CONFIG = SUBTITLE_STYLES["黄色突出"]
```

## 📊 效果对比

| 功能 | CapCut手动识别 | Whisper脚本生成 |
|------|--------------|----------------|
| 单词时间戳 | ✅ 自动 | ✅ 自动（word_timestamps） |
| 单词逐个弹出 | ✅ 支持 | ✅ 完全可实现 |
| 颜色自定义 | ✅ UI调整 | ✅ 代码配置 |
| 描边控制 | ✅ UI调整 | ✅ 代码配置 |
| 入场动画 | ✅ 丰富 | ⚠️ 需研究动画ID |
| 准确度 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ (接近) |
| 自动化程度 | ⭐⭐ (需手动点击) | ⭐⭐⭐⭐⭐ (全自动) |

## ⚠️ 注意事项

### 1. 动画效果限制

**简单入场动画** ✅ 可实现：
- 淡入（opacity变化）
- 位置移动（从下向上）

**复杂动画** ⚠️ 需研究：
- 弹跳效果（需要CapCut特定的动画资源）
- 旋转、缩放（需要找到对应的动画ID）

**解决方案**：
1. 先实现基础样式（颜色、描边）✅
2. 使用简单的淡入效果 ✅
3. 如需复杂动画，用户可在CapCut中手动添加

### 2. 性能考虑

```python
# Whisper模型大小选择
models = {
    "tiny": "最快，准确度较低",
    "base": "推荐，速度和准确度平衡",  # ⭐
    "small": "较准确，稍慢",
    "medium": "很准确，较慢",
    "large": "最准确，最慢"
}

# 对于英文短视频（<1分钟），base模型即可
model = whisper.load_model("base")
```

### 3. 中文支持

```python
# 中文识别
result = model.transcribe(
    audio_file,
    language="zh",  # 中文
    word_timestamps=True
)

# 注意：中文的word_timestamps可能按字分，不是按词
```

## 🚀 快速开始

### 最小可行方案（MVP）

```python
# 1. 安装
pip install openai-whisper

# 2. 基础实现（20行代码）
import whisper

model = whisper.load_model("base")
result = model.transcribe("audio.mp3", word_timestamps=True)

# 提取所有单词
words = []
for seg in result["segments"]:
    words.extend(seg.get("words", []))

# 生成字幕（简化版）
for word in words:
    print(f'{word["word"]}: {word["start"]:.2f}s - {word["end"]:.2f}s')
```

## ✅ 结论

**完全可行！** ✅

1. **单词时间戳**: Whisper的word_timestamps功能完美支持
2. **样式控制**: CapCut的texts材料结构完全可编程控制
   - ✅ 颜色
   - ✅ 描边
   - ✅ 字号
   - ✅ 字体
3. **逐词弹出**: 为每个单词创建独立的字幕片段即可实现
4. **入场动画**: 基础动画可实现，复杂动画需进一步研究

**建议实施步骤**：
1. ✅ 先实现基础版（单词字幕 + 样式自定义）
2. ✅ 测试效果
3. ⚠️ 如需特定动画，分析CapCut现有动画结构
4. ✅ 逐步完善

---

**要不要现在就开始集成Whisper？** 🚀

