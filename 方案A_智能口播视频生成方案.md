# 方案 A：智能口播视频自动生成方案

## 📋 需求概述

**核心需求：**
1. 处理 ElevenLabs 生成的英文音频（含间隙）
2. 自动移除音频中的静音片段
3. 英文语音识别 + 自动生成字幕
4. 图片按口播智能分布到时间线
5. 生成 16:9 (1920x1080) 视频

**输入材料：**
- 🎵 英文音频文件（MP3/WAV）
- 🖼️ 多张图片（PNG/JPG）

**输出结果：**
- 📹 16:9 视频（MP4）
- 📝 SRT 字幕文件

---

## 🏗️ 技术架构

### 技术栈

```
核心库：
├── pydub (音频处理)
├── whisper (语音识别)
├── moviepy (视频合成)
├── mutagen (音频元数据)
└── ffmpeg (底层引擎)

辅助库：
├── glob (文件匹配)
├── re (正则排序)
└── uuid (唯一ID生成)
```

### 处理流程

```
输入音频 → 移除静音 → 语音识别 → 生成字幕
    ↓           ↓          ↓           ↓
  图片排序 → 智能分配 → 合成视频 → 输出MP4
```

---

## 💡 核心创新点

### 从 `zidongjianji.py` 借鉴的智能逻辑

#### 1. 精准音频时长检测
```python
# 使用 mutagen 库获取微秒级精度
def get_audio_duration_accurate(audio_file: str) -> float:
    audio = MutagenFile(audio_file)
    return audio.info.length  # 秒
```

#### 2. 短音频 vs 长音频的智能分配
```
判断逻辑（阈值：1.5秒）：

短音频（< 1.5s）：
├── 配1张图片
├── 图片显示完整音频时长
└── 适用场景：停顿、过渡句

长音频（≥ 1.5s）：
├── 配2张图片
├── 平均分配时间（各占一半）
└── 适用场景：完整句子、段落
```

#### 3. 自然排序
```python
# 确保文件按 1-1, 1-2, 1-3 而不是 1-1, 1-10, 1-11
def natural_sort_key(filename: str) -> tuple:
    parts = re.findall(r'(\d+)', filename)
    return tuple(int(part) for part in parts)
```

---

## 📦 完整代码实现

### 主程序：`auto_video_generator.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
智能口播视频自动生成器
融合 zidongjianji.py 的智能分配逻辑 + 完整自动化流程
"""

import os
import glob
import re
from typing import List, Tuple
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import whisper
from moviepy.editor import *
from mutagen import File as MutagenFile

# ============================================================================
# 工具函数（借鉴 zidongjianji.py）
# ============================================================================

def natural_sort_key(filename: str) -> tuple:
    """
    自然排序键函数，确保 1-1, 1-2, 1-3 而不是 1-1, 1-10, 1-11
    借鉴自 zidongjianji.py 第20-26行
    """
    parts = re.findall(r'(\d+)', filename)
    return tuple(int(part) for part in parts)


def get_audio_duration_accurate(audio_file: str) -> float:
    """
    获取音频文件的精确时长（秒）
    借鉴自 zidongjianji.py 第28-43行
    """
    try:
        audio = MutagenFile(audio_file)
        if audio is not None and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
            return audio.info.length
        else:
            print(f"⚠️  无法读取音频时长: {os.path.basename(audio_file)}")
            return 3.0  # 默认3秒
    except Exception as e:
        print(f"⚠️  读取音频时长出错 {os.path.basename(audio_file)}: {e}")
        return 3.0


# ============================================================================
# 音频处理模块
# ============================================================================

def remove_silence(input_audio: str, output_audio: str) -> str:
    """
    移除音频中的静音片段
    
    Args:
        input_audio: 输入音频路径
        output_audio: 输出音频路径
        
    Returns:
        处理后的音频路径
    """
    print(f"\n🎵 正在处理音频: {os.path.basename(input_audio)}")
    
    audio = AudioSegment.from_file(input_audio)
    original_duration = len(audio) / 1000  # 毫秒转秒
    
    # 检测非静音片段
    # min_silence_len: 最小静音长度（毫秒），低于此值的静音会被保留
    # silence_thresh: 静音阈值（dB），低于此值视为静音
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=500,    # 500ms 以上的静音才会被移除
        silence_thresh=-40,     # -40dB 以下视为静音
        seek_step=10            # 检测步长（毫秒）
    )
    
    # 拼接所有非静音片段
    output = AudioSegment.empty()
    for start, end in nonsilent_ranges:
        output += audio[start:end]
    
    # 导出处理后的音频
    output.export(output_audio, format="mp3")
    
    new_duration = len(output) / 1000
    removed_duration = original_duration - new_duration
    
    print(f"✅ 静音移除完成")
    print(f"   原时长: {original_duration:.2f}秒")
    print(f"   新时长: {new_duration:.2f}秒")
    print(f"   移除: {removed_duration:.2f}秒 ({removed_duration/original_duration*100:.1f}%)")
    
    return output_audio


# ============================================================================
# 语音识别 + 字幕生成模块
# ============================================================================

def generate_subtitles(audio_path: str, srt_path: str) -> List[dict]:
    """
    使用 Whisper 识别英文并生成 SRT 字幕
    
    Args:
        audio_path: 音频文件路径
        srt_path: 输出 SRT 文件路径
        
    Returns:
        字幕片段列表（包含时间戳和文本）
    """
    print(f"\n🎤 正在识别英文语音...")
    
    # 加载 Whisper 模型
    # 可选: tiny, base, small, medium, large
    # base 模型约 140MB，识别速度快，准确度适中
    model = whisper.load_model("base")
    
    # 转录音频
    result = model.transcribe(audio_path, language="en", verbose=True)
    
    # 生成 SRT 字幕文件
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(result['segments'], 1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")
    
    print(f"✅ 字幕生成完成")
    print(f"   识别到 {len(result['segments'])} 个句子")
    print(f"   字幕文件: {srt_path}")
    
    return result['segments']


def format_timestamp(seconds: float) -> str:
    """
    转换为 SRT 时间格式 (HH:MM:SS,mmm)
    
    Args:
        seconds: 时间（秒）
        
    Returns:
        SRT 格式时间字符串
    """
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ============================================================================
# 视频合成模块（核心：智能图片分配）
# ============================================================================

def create_video_with_smart_distribution(
    audio_path: str,
    image_folder: str,
    srt_path: str,
    output_path: str,
    segments: List[dict] = None,
    duration_threshold: float = 1.5
) -> None:
    """
    创建视频，使用智能图片分配逻辑
    
    借鉴 zidongjianji.py 第316-492行的核心逻辑：
    - 短音频段（< 1.5秒）：配1张图片
    - 长音频段（≥ 1.5秒）：配2张图片，平均分配时间
    
    Args:
        audio_path: 处理后的音频路径
        image_folder: 图片文件夹路径
        srt_path: 字幕文件路径
        output_path: 输出视频路径
        segments: 语音识别的片段列表（可选）
        duration_threshold: 短/长音频的时长阈值（秒）
    """
    print(f"\n🎬 正在合成视频...")
    
    # 1. 加载音频
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    
    # 2. 如果没有提供 segments，重新识别
    if segments is None:
        temp_srt = "temp_subtitles.srt"
        segments = generate_subtitles(audio_path, temp_srt)
    
    # 3. 获取所有图片并自然排序
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        image_files.extend(glob.glob(os.path.join(image_folder, ext)))
    
    if not image_files:
        raise ValueError(f"❌ 在 {image_folder} 中未找到图片文件！")
    
    # 使用自然排序
    image_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    
    print(f"   找到 {len(image_files)} 张图片")
    print(f"   识别到 {len(segments)} 个句子")
    
    # 4. 智能分配图片（核心逻辑）
    clips = []
    image_index = 0
    
    print(f"\n=== 智能图片分配（阈值: {duration_threshold}秒）===")
    
    for i, segment in enumerate(segments):
        start_time = segment['start']
        end_time = segment['end']
        duration = end_time - start_time
        text = segment['text'].strip()
        
        # 判断是短音频还是长音频
        if duration < duration_threshold:
            # ========== 短音频：配1张图片 ==========
            if image_index < len(image_files):
                img_path = image_files[image_index]
                
                img_clip = (ImageClip(img_path)
                           .set_start(start_time)
                           .set_duration(duration)
                           .resize(height=1080)  # 保持宽高比，高度1080
                           .set_position("center"))
                
                clips.append(img_clip)
                
                print(f"句子 {i+1} (短音频 {duration:.2f}s): 图片 {image_index+1}")
                print(f"  └─ \"{text[:50]}...\"" if len(text) > 50 else f"  └─ \"{text}\"")
                
                image_index += 1
            else:
                print(f"⚠️  句子 {i+1} 无可用图片")
        
        else:
            # ========== 长音频：配2张图片 ==========
            if image_index + 1 < len(image_files):
                half_duration = duration / 2
                
                # 第一张图片（前半段）
                img1_path = image_files[image_index]
                img1_clip = (ImageClip(img1_path)
                            .set_start(start_time)
                            .set_duration(half_duration)
                            .resize(height=1080)
                            .set_position("center"))
                clips.append(img1_clip)
                
                # 第二张图片（后半段）
                img2_path = image_files[image_index + 1]
                img2_clip = (ImageClip(img2_path)
                            .set_start(start_time + half_duration)
                            .set_duration(duration - half_duration)
                            .resize(height=1080)
                            .set_position("center"))
                clips.append(img2_clip)
                
                print(f"句子 {i+1} (长音频 {duration:.2f}s): 图片 {image_index+1} ({half_duration:.2f}s) + 图片 {image_index+2} ({duration-half_duration:.2f}s)")
                print(f"  └─ \"{text[:50]}...\"" if len(text) > 50 else f"  └─ \"{text}\"")
                
                image_index += 2
            else:
                print(f"⚠️  句子 {i+1} 无足够图片（需要2张）")
    
    # 统计信息
    used_images = image_index
    unused_images = len(image_files) - used_images
    print(f"\n📊 图片使用统计:")
    print(f"   总图片: {len(image_files)}")
    print(f"   已使用: {used_images}")
    print(f"   未使用: {unused_images}")
    if unused_images > 0:
        print(f"   ℹ️  建议减少图片数量或增加音频内容")
    
    # 5. 合成视频（黑色背景）
    background = ColorClip(size=(1920, 1080), color=(0, 0, 0), duration=total_duration)
    video = CompositeVideoClip([background] + clips)
    video = video.set_audio(audio)
    
    # 6. 添加字幕
    def subtitle_generator(txt):
        return TextClip(
            txt,
            font='Arial-Bold',        # 字体
            fontsize=60,              # 字号
            color='white',            # 字体颜色
            stroke_color='black',     # 描边颜色
            stroke_width=2,           # 描边宽度
            method='caption',         # 自动换行
            size=(1800, None)         # 字幕宽度
        )
    
    subtitles = SubtitlesClip(srt_path, subtitle_generator)
    subtitles = subtitles.set_position(('center', 900))  # 底部位置
    
    final_video = CompositeVideoClip([video, subtitles])
    
    # 7. 导出视频
    print(f"\n📹 正在导出视频...")
    final_video.write_videofile(
        output_path,
        fps=30,                # 帧率
        codec='libx264',       # H.264 编码
        audio_codec='aac',     # AAC 音频
        preset='medium',       # 编码速度（ultrafast/fast/medium/slow）
        bitrate='5000k'        # 码率
    )
    
    print(f"\n✅ 视频生成完成！")
    print(f"   输出路径: {output_path}")
    print(f"   分辨率: 1920x1080 (16:9)")
    print(f"   时长: {total_duration:.2f}秒")


# ============================================================================
# 主程序入口
# ============================================================================

def auto_generate_video(
    input_audio: str,
    image_folder: str,
    output_video: str,
    output_srt: str = "subtitles.srt",
    clean_audio: str = "clean_audio.mp3",
    duration_threshold: float = 1.5
) -> None:
    """
    一键生成口播视频
    
    完整流程：
    1. 移除音频静音片段
    2. 英文语音识别
    3. 生成字幕文件
    4. 智能分配图片到时间线
    5. 合成16:9视频
    
    Args:
        input_audio: 原始音频路径
        image_folder: 图片文件夹路径
        output_video: 输出视频路径
        output_srt: 输出字幕路径（默认: subtitles.srt）
        clean_audio: 处理后音频路径（默认: clean_audio.mp3）
        duration_threshold: 短/长音频阈值（默认: 1.5秒）
    """
    print("=" * 60)
    print("🎬 智能口播视频自动生成器")
    print("=" * 60)
    
    # Step 1: 移除静音
    clean_audio_path = remove_silence(input_audio, clean_audio)
    
    # Step 2: 生成字幕
    segments = generate_subtitles(clean_audio_path, output_srt)
    
    # Step 3: 合成视频（智能图片分配）
    create_video_with_smart_distribution(
        audio_path=clean_audio_path,
        image_folder=image_folder,
        srt_path=output_srt,
        output_path=output_video,
        segments=segments,
        duration_threshold=duration_threshold
    )
    
    print("\n" + "=" * 60)
    print("🎉 所有任务完成！")
    print("=" * 60)


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # 配置文件路径
    INPUT_AUDIO = "/Users/mac/YouTube/01工具类/playwright/input.mp3"
    IMAGE_FOLDER = "/Users/mac/YouTube/01工具类/playwright/reference_images/01"
    OUTPUT_VIDEO = "/Users/mac/YouTube/01工具类/playwright/output.mp4"
    
    # 可选参数
    OUTPUT_SRT = "/Users/mac/YouTube/01工具类/playwright/subtitles.srt"
    CLEAN_AUDIO = "/Users/mac/YouTube/01工具类/playwright/clean_audio.mp3"
    DURATION_THRESHOLD = 1.5  # 短/长音频阈值（秒）
    
    # 执行生成
    auto_generate_video(
        input_audio=INPUT_AUDIO,
        image_folder=IMAGE_FOLDER,
        output_video=OUTPUT_VIDEO,
        output_srt=OUTPUT_SRT,
        clean_audio=CLEAN_AUDIO,
        duration_threshold=DURATION_THRESHOLD
    )
```

---

## 🛠️ 环境配置

### 1. 安装 Python 依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate  # Windows

# 安装依赖库
pip install pydub whisper moviepy mutagen

# 安装 Whisper 的依赖
pip install openai-whisper
```

### 2. 安装 FFmpeg

```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt install ffmpeg

# Windows (使用 Chocolatey)
choco install ffmpeg
```

### 3. 验证安装

```bash
# 验证 FFmpeg
ffmpeg -version

# 验证 Python 库
python -c "import whisper; print('Whisper OK')"
python -c "from moviepy.editor import *; print('MoviePy OK')"
python -c "from pydub import AudioSegment; print('Pydub OK')"
```

---

## 📖 使用说明

### 快速开始

```bash
# 1. 修改脚本中的路径配置
INPUT_AUDIO = "你的音频.mp3"
IMAGE_FOLDER = "你的图片文件夹"
OUTPUT_VIDEO = "输出视频.mp4"

# 2. 运行脚本
python auto_video_generator.py
```

### 文件组织建议

```
项目文件夹/
├── auto_video_generator.py   # 主程序
├── input/                     # 输入文件
│   ├── audio.mp3             # 原始音频
│   └── images/               # 图片文件夹
│       ├── 1.png
│       ├── 2.png
│       └── 3.png
├── output/                    # 输出文件
│   ├── final_video.mp4       # 最终视频
│   ├── subtitles.srt         # 字幕文件
│   └── clean_audio.mp3       # 处理后音频
└── README.md
```

### 图片命名建议

```
推荐命名格式（自然排序）：
✅ 1.png, 2.png, 3.png ...
✅ image_01.png, image_02.png ...
✅ scene-1.jpg, scene-2.jpg ...

避免的命名格式：
❌ img1.png, img10.png, img2.png (会乱序)
```

---

## ⚙️ 参数调优

### 1. 静音检测参数

```python
# 在 remove_silence() 函数中调整

nonsilent_ranges = detect_nonsilent(
    audio,
    min_silence_len=500,    # 调整这个值
    silence_thresh=-40,     # 调整这个值
    seek_step=10
)
```

**参数说明：**

| 参数 | 说明 | 建议值 |
|------|------|--------|
| `min_silence_len` | 最小静音长度（ms） | 300-800 |
| `silence_thresh` | 静音阈值（dB） | -50 到 -30 |

**调优建议：**
- 🔇 **间隙太多**：增大 `min_silence_len`（如 800）
- 🔊 **删除过度**：降低 `silence_thresh`（如 -50）

### 2. 短/长音频阈值

```python
# 在主函数中调整
DURATION_THRESHOLD = 1.5  # 秒

# 较激进的切换（更多双图）
DURATION_THRESHOLD = 1.0

# 较保守的切换（更多单图）
DURATION_THRESHOLD = 2.0
```

### 3. Whisper 模型选择

```python
# 在 generate_subtitles() 中调整
model = whisper.load_model("base")  # 改为其他模型
```

**模型对比：**

| 模型 | 大小 | 速度 | 准确度 | 适用场景 |
|------|------|------|--------|---------|
| `tiny` | 39MB | 极快 | ⭐⭐ | 测试用 |
| `base` | 74MB | 快 | ⭐⭐⭐ | **推荐** |
| `small` | 244MB | 中 | ⭐⭐⭐⭐ | 高质量 |
| `medium` | 769MB | 慢 | ⭐⭐⭐⭐⭐ | 专业级 |

### 4. 字幕样式

```python
# 在 subtitle_generator() 中调整

TextClip(
    txt,
    font='Arial-Bold',         # 字体
    fontsize=60,               # 字号（40-80）
    color='white',             # 颜色
    stroke_color='black',      # 描边颜色
    stroke_width=2,            # 描边宽度（1-3）
    method='caption',
    size=(1800, None)          # 字幕宽度
)
```

---

## 🚀 进阶功能

### 批量处理多个视频

```python
def batch_generate_videos(config_list: List[dict]):
    """
    批量生成多个视频
    
    Args:
        config_list: 配置列表，每项包含:
            - input_audio: 音频路径
            - image_folder: 图片文件夹
            - output_video: 输出视频路径
    """
    for i, config in enumerate(config_list, 1):
        print(f"\n{'='*60}")
        print(f"处理第 {i}/{len(config_list)} 个视频")
        print(f"{'='*60}")
        
        auto_generate_video(**config)

# 使用示例
if __name__ == "__main__":
    configs = [
        {
            "input_audio": "story1/audio.mp3",
            "image_folder": "story1/images",
            "output_video": "output/story1.mp4"
        },
        {
            "input_audio": "story2/audio.mp3",
            "image_folder": "story2/images",
            "output_video": "output/story2.mp4"
        }
    ]
    
    batch_generate_videos(configs)
```

### 添加背景音乐

```python
def add_background_music(
    video_path: str,
    music_path: str,
    output_path: str,
    music_volume: float = 0.1  # 背景音乐音量（0.0-1.0）
):
    """添加背景音乐"""
    from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
    
    video = VideoFileClip(video_path)
    original_audio = video.audio
    
    # 加载背景音乐并循环到视频时长
    music = AudioFileClip(music_path).volumex(music_volume)
    music = music.audio_loop(duration=video.duration)
    
    # 混合音频
    final_audio = CompositeAudioClip([original_audio, music])
    video = video.set_audio(final_audio)
    
    video.write_videofile(output_path, codec='libx264', audio_codec='aac')
```

### 添加转场效果

```python
from moviepy.video.fx.fadein import fadein
from moviepy.video.fx.fadeout import fadeout

# 在创建 img_clip 时添加
img_clip = (ImageClip(img_path)
           .set_start(start_time)
           .set_duration(duration)
           .resize(height=1080)
           .set_position("center")
           .fadein(0.3)   # 0.3秒淡入
           .fadeout(0.3)) # 0.3秒淡出
```

---

## 📊 性能优化

### 1. 并行处理音频（多文件）

```python
from multiprocessing import Pool

def process_audio_parallel(audio_files: List[str]):
    """并行处理多个音频"""
    with Pool(processes=4) as pool:
        results = pool.map(remove_silence, audio_files)
    return results
```

### 2. 降低视频渲染时间

```python
# 使用更快的编码预设
final_video.write_videofile(
    output_path,
    fps=30,
    codec='libx264',
    preset='ultrafast',  # 改为 ultrafast（质量稍降）
    threads=8            # 增加线程数
)
```

### 3. 缓存 Whisper 模型

```python
# 全局加载模型，避免重复加载
WHISPER_MODEL = None

def get_whisper_model():
    global WHISPER_MODEL
    if WHISPER_MODEL is None:
        WHISPER_MODEL = whisper.load_model("base")
    return WHISPER_MODEL
```

---

## 🐛 常见问题

### Q1: `ModuleNotFoundError: No module named 'pydub'`
```bash
# 解决：安装缺失的库
pip install pydub
```

### Q2: `RuntimeError: FFmpeg binary not found`
```bash
# 解决：安装 FFmpeg
brew install ffmpeg  # macOS
```

### Q3: 字幕不显示
```bash
# 检查字幕文件是否生成
ls -la subtitles.srt

# 检查字体是否存在
# macOS: /Library/Fonts/
# Windows: C:\Windows\Fonts\
```

### Q4: 图片分辨率不对
```python
# 在代码中调整
.resize(height=1080)  # 改为 .resize(width=1920)
```

### Q5: 内存不足
```python
# 减少并发处理，分批处理
# 或使用更小的 Whisper 模型
model = whisper.load_model("tiny")
```

---

## 📈 后续优化方向

### 短期优化
- [ ] 支持中文语音识别
- [ ] 添加进度条显示
- [ ] 支持更多视频比例（9:16竖屏等）
- [ ] 添加预览功能

### 中期优化
- [ ] 图形化界面（GUI）
- [ ] 云端批量处理
- [ ] AI 自动配图（根据文本内容）
- [ ] 多语言字幕支持

### 长期优化
- [ ] Web 在线服务
- [ ] AI 配音优化
- [ ] 智能剪辑（删除口误、重复）
- [ ] 自动添加转场和特效

---

## 📝 总结

**方案 A 的核心优势：**

✅ **完全自动化** - 从音频到视频一键生成  
✅ **智能分配** - 借鉴 zidongjianji.py 的成熟逻辑  
✅ **高质量输出** - 16:9 标准视频 + 精准字幕  
✅ **可定制化** - 所有参数可调整  
✅ **开源免费** - 无需依赖商业软件

**适用场景：**
- 📹 YouTube/B站 教育视频
- 🎙️ 播客转视频
- 📚 有声书可视化
- 🎬 短视频批量生成

**预期效果：**
```
输入: 1分钟音频 + 10张图片
处理时间: 约3-5分钟（取决于硬件）
输出: 
  ├── 高质量 MP4 视频
  ├── SRT 字幕文件
  └── 处理后的音频
```

---

## 📞 后续支持

如需进一步定制或遇到问题：
1. 提供音频样本进行参数调优
2. 根据实际效果调整代码
3. 添加特定功能需求

**开始实施前建议：**
1. 先用小样本测试（10秒音频 + 3张图）
2. 验证效果后再批量处理
3. 根据实际情况调整阈值参数

---

*文档版本: 1.0*  
*最后更新: 2025-10-13*

