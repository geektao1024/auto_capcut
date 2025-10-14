# 方案 B：半自动化剪映草稿生成方案

## 📋 方案定位

**核心理念：自动化 + 人工精修 = 最佳效果**

```
方案 A（全自动）      方案 B（半自动）         手动剪辑
    ↓                     ↓                      ↓
快速但固定     ←→  灵活可调整  ←→        费时但完美
```

### 为什么选择方案 B？

✅ **保留方案 A 的优点：**
- 自动移除静音
- 自动语音识别
- 智能图片分配逻辑
- 批量处理能力

✅ **增加人工干预能力：**
- 可在剪映中调整图片时长
- 可手动微调字幕
- 可添加转场和特效
- 可调整配音音量
- 可二次调色和美化

---

## 🎯 工作流程

### 完整流程图

```
输入音频（含间隙）
    ↓
[自动] 步骤1: 移除静音 → clean_audio.mp3
    ↓
[人工检查点 ①] 试听处理后音频，确认效果
    ↓
[自动] 步骤2: 语音识别 → subtitles.srt
    ↓
[人工检查点 ②] 检查字幕准确性，手动修正
    ↓
[自动] 步骤3: 生成剪映草稿 → JianyingPro Drafts/
    ↓
[人工检查点 ③] 在剪映中打开草稿
    ↓
[人工] 步骤4: 剪映中精修
    ├─ 调整图片时长和位置
    ├─ 修改字幕样式
    ├─ 添加转场效果
    ├─ 调整音量和滤镜
    └─ 添加背景音乐
    ↓
[人工] 步骤5: 导出最终视频 → final.mp4
```

---

## 💡 方案 B 的核心优势

### 对比三种方案

| 特性 | 方案A（全自动） | 方案B（半自动）⭐ | 手动剪辑 |
|------|----------------|------------------|---------|
| **速度** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐ |
| **灵活性** | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ |
| **质量** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **可调整性** | ❌ | ✅ 强 | ✅ 完全 |
| **批量处理** | ✅ | ✅ | ❌ |
| **学习成本** | 低 | 中 | 低 |
| **适合场景** | 快速测试 | **生产环境** | 单个精品 |

---

## 🛠️ 技术实现

### 架构设计

```
技术栈：
├── Python 自动化层
│   ├── pydub (音频处理)
│   ├── whisper (语音识别)
│   └── 智能分配算法
├── 剪映草稿生成层
│   ├── JSON 格式草稿
│   ├── 时间轴精确对齐
│   └── 材料自动导入
└── 剪映手动精修层
    ├── 可视化编辑
    ├── 特效和转场
    └── 最终导出
```

---

## 📦 完整代码实现

### 主程序：`semi_auto_generator.py`

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
方案 B：半自动化剪映草稿生成器
结合方案 A 的智能逻辑 + 剪映的可视化编辑能力
"""

import json
import os
import uuid
import shutil
import glob
import re
from typing import List, Dict, Tuple
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import whisper
from mutagen import File as MutagenFile

# ============================================================================
# 工具函数（继承自 zidongjianji.py 和方案 A）
# ============================================================================

def generate_uuid() -> str:
    """生成UUID"""
    return str(uuid.uuid4()).upper()


def natural_sort_key(filename: str) -> tuple:
    """自然排序键函数"""
    parts = re.findall(r'(\d+)', filename)
    return tuple(int(part) for part in parts)


def get_audio_duration_accurate(audio_file: str) -> int:
    """
    获取音频文件的准确时长（微秒）
    用于剪映草稿的精确时间轴对齐
    """
    try:
        audio = MutagenFile(audio_file)
        if audio is not None and hasattr(audio, 'info') and hasattr(audio.info, 'length'):
            duration_seconds = audio.info.length
            return int(duration_seconds * 1000000)  # 转换为微秒
        else:
            print(f"⚠️  无法读取音频时长: {os.path.basename(audio_file)}")
            return 3000000  # 默认3秒
    except Exception as e:
        print(f"⚠️  读取音频时长出错: {e}")
        return 3000000


# ============================================================================
# 步骤 1: 音频预处理（自动化）
# ============================================================================

def remove_silence_step(
    input_audio: str,
    output_audio: str,
    min_silence_len: int = 500,
    silence_thresh: int = -40
) -> str:
    """
    步骤1：移除音频静音片段
    
    人工检查点：处理完成后，试听 output_audio 确认效果
    
    Args:
        input_audio: 原始音频路径
        output_audio: 输出音频路径
        min_silence_len: 最小静音长度（毫秒）
        silence_thresh: 静音阈值（dB）
        
    Returns:
        处理后的音频路径
    """
    print("\n" + "="*60)
    print("📍 步骤 1/5: 移除音频静音片段")
    print("="*60)
    
    audio = AudioSegment.from_file(input_audio)
    original_duration = len(audio) / 1000
    
    print(f"原始音频时长: {original_duration:.2f}秒")
    print(f"检测参数: 静音>{min_silence_len}ms, 音量<{silence_thresh}dB")
    
    nonsilent_ranges = detect_nonsilent(
        audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh,
        seek_step=10
    )
    
    output = AudioSegment.empty()
    for start, end in nonsilent_ranges:
        output += audio[start:end]
    
    output.export(output_audio, format="mp3")
    
    new_duration = len(output) / 1000
    removed_duration = original_duration - new_duration
    
    print(f"✅ 处理完成")
    print(f"   新时长: {new_duration:.2f}秒")
    print(f"   移除: {removed_duration:.2f}秒 ({removed_duration/original_duration*100:.1f}%)")
    print(f"   输出文件: {output_audio}")
    
    print("\n🔍 人工检查点 ①:")
    print("   请试听处理后的音频，确认以下内容：")
    print("   1. 静音移除是否合适（不要删除太多停顿）")
    print("   2. 音频是否连贯自然")
    print("   3. 如需调整，修改参数后重新运行")
    input("   确认无误后按 Enter 继续...\n")
    
    return output_audio


# ============================================================================
# 步骤 2: 语音识别（自动化 + 人工校对）
# ============================================================================

def transcribe_audio_step(
    audio_path: str,
    srt_path: str,
    model_size: str = "base"
) -> List[dict]:
    """
    步骤2：使用 Whisper 识别英文并生成字幕
    
    人工检查点：识别完成后，检查字幕准确性
    
    Args:
        audio_path: 音频文件路径
        srt_path: 输出 SRT 文件路径
        model_size: Whisper 模型大小
        
    Returns:
        字幕片段列表
    """
    print("\n" + "="*60)
    print("📍 步骤 2/5: 语音识别并生成字幕")
    print("="*60)
    
    print(f"加载 Whisper 模型: {model_size}")
    model = whisper.load_model(model_size)
    
    print("正在识别语音...")
    result = model.transcribe(audio_path, language="en", verbose=False)
    
    # 生成 SRT 字幕
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, segment in enumerate(result['segments'], 1):
            start = format_timestamp(segment['start'])
            end = format_timestamp(segment['end'])
            text = segment['text'].strip()
            
            f.write(f"{i}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f"{text}\n\n")
    
    print(f"✅ 识别完成")
    print(f"   识别到 {len(result['segments'])} 个句子")
    print(f"   字幕文件: {srt_path}")
    
    # 显示前几句字幕
    print("\n前3句字幕预览:")
    for i, segment in enumerate(result['segments'][:3], 1):
        print(f"   {i}. [{segment['start']:.2f}s - {segment['end']:.2f}s]")
        print(f"      {segment['text']}")
    
    print("\n🔍 人工检查点 ②:")
    print("   请检查字幕文件，确认以下内容：")
    print("   1. 文字识别是否准确")
    print("   2. 时间轴是否对齐")
    print("   3. 如有错误，手动编辑 SRT 文件修正")
    print(f"   字幕文件路径: {srt_path}")
    input("   确认无误后按 Enter 继续...\n")
    
    return result['segments']


def format_timestamp(seconds: float) -> str:
    """转换为 SRT 时间格式"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


# ============================================================================
# 步骤 3: 生成剪映草稿（自动化）
# ============================================================================

def create_jianying_draft_step(
    template_path: str,
    clean_audio: str,
    image_folder: str,
    segments: List[dict],
    output_folder: str,
    draft_name: str = "auto_draft",
    duration_threshold: float = 1.5
) -> str:
    """
    步骤3：生成剪映草稿
    
    融合 zidongjianji.py 的草稿生成能力 + 方案A的智能分配逻辑
    
    Args:
        template_path: 模板草稿文件路径
        clean_audio: 处理后的音频路径
        image_folder: 图片文件夹路径
        segments: 语音识别的片段列表
        output_folder: 输出文件夹路径
        draft_name: 草稿名称
        duration_threshold: 短/长音频阈值（秒）
        
    Returns:
        草稿文件夹路径
    """
    print("\n" + "="*60)
    print("📍 步骤 3/5: 生成剪映草稿")
    print("="*60)
    
    # 读取模板
    with open(template_path, 'r', encoding='utf-8') as f:
        draft = json.load(f)
    
    # 创建输出文件夹
    draft_folder = os.path.join(output_folder, draft_name)
    os.makedirs(draft_folder, exist_ok=True)
    
    # 获取图片列表并排序
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        image_files.extend(glob.glob(os.path.join(image_folder, ext)))
    
    if not image_files:
        raise ValueError(f"❌ 在 {image_folder} 中未找到图片文件！")
    
    image_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    
    print(f"找到 {len(image_files)} 张图片")
    print(f"识别到 {len(segments)} 个句子")
    
    # 保留原有的基础材料
    original_audios = [audio for audio in draft['materials']['audios'] 
                      if audio.get('name') == 'messironaldo.MP3']
    original_videos = [video for video in draft['materials']['videos'] 
                      if video.get('material_name') in ['black.png', '173874-850026348_small.mp4']]
    
    # 重置材料列表
    draft['materials']['audios'] = original_audios
    draft['materials']['videos'] = original_videos
    
    # 清空第一个视频轨道
    for track in draft['tracks']:
        if track['type'] == 'video' and track.get('flag', 0) == 0:
            track['segments'] = []
            break
    
    # ========== 添加处理后的音频材料 ==========
    audio_duration = get_audio_duration_accurate(clean_audio)
    audio_id = generate_uuid()
    
    audio_material = {
        "app_id": 0,
        "category_id": "",
        "category_name": "",
        "check_flag": 1,
        "duration": audio_duration,
        "id": audio_id,
        "name": os.path.basename(clean_audio),
        "path": clean_audio,
        "type": "extract_music",
        "wave_points": []
    }
    
    draft['materials']['audios'].append(audio_material)
    print(f"✅ 添加音频: {os.path.basename(clean_audio)} ({audio_duration/1000000:.2f}秒)")
    
    # ========== 添加图片材料 ==========
    image_ids = []
    for image_file in image_files:
        image_id = generate_uuid()
        
        image_material = {
            "aigc_type": "none",
            "category_id": "",
            "check_flag": 63487,
            "crop": {
                "lower_left_x": 0.0, "lower_left_y": 1.0,
                "lower_right_x": 1.0, "lower_right_y": 1.0,
                "upper_left_x": 0.0, "upper_left_y": 0.0,
                "upper_right_x": 1.0, "upper_right_y": 0.0
            },
            "duration": 10800000000,
            "has_audio": False,
            "height": 2048,
            "width": 1152,
            "id": image_id,
            "material_name": os.path.basename(image_file),
            "path": image_file,
            "type": "photo"
        }
        
        draft['materials']['videos'].append(image_material)
        image_ids.append(image_id)
    
    print(f"✅ 添加 {len(image_ids)} 张图片")
    
    # ========== 智能分配图片到时间轴（核心逻辑）==========
    print(f"\n=== 智能图片分配（阈值: {duration_threshold}秒）===")
    
    video_track = None
    for track in draft['tracks']:
        if track['type'] == 'video' and track.get('flag', 0) == 0:
            video_track = track
            break
    
    if not video_track:
        raise ValueError("❌ 未找到视频轨道")
    
    image_index = 0
    
    for i, segment in enumerate(segments):
        start_time_micro = int(segment['start'] * 1000000)
        end_time_micro = int(segment['end'] * 1000000)
        duration_micro = end_time_micro - start_time_micro
        duration_sec = duration_micro / 1000000
        
        if duration_sec < duration_threshold:
            # ========== 短音频：1张图片 ==========
            if image_index < len(image_ids):
                segment_json = create_video_segment(
                    material_id=image_ids[image_index],
                    start_time=start_time_micro,
                    duration=duration_micro,
                    render_index=len(video_track['segments']) + 1
                )
                
                video_track['segments'].append(segment_json)
                print(f"句子 {i+1} (短 {duration_sec:.2f}s): 图片 {image_index+1}")
                image_index += 1
        else:
            # ========== 长音频：2张图片 ==========
            if image_index + 1 < len(image_ids):
                half_duration = duration_micro // 2
                
                # 第一张图片
                seg1 = create_video_segment(
                    material_id=image_ids[image_index],
                    start_time=start_time_micro,
                    duration=half_duration,
                    render_index=len(video_track['segments']) + 1
                )
                video_track['segments'].append(seg1)
                
                # 第二张图片
                seg2 = create_video_segment(
                    material_id=image_ids[image_index + 1],
                    start_time=start_time_micro + half_duration,
                    duration=duration_micro - half_duration,
                    render_index=len(video_track['segments']) + 2
                )
                video_track['segments'].append(seg2)
                
                print(f"句子 {i+1} (长 {duration_sec:.2f}s): 图片 {image_index+1} + {image_index+2}")
                image_index += 2
    
    print(f"\n📊 图片使用统计:")
    print(f"   总图片: {len(image_ids)}")
    print(f"   已使用: {image_index}")
    print(f"   未使用: {len(image_ids) - image_index}")
    
    # ========== 创建音频轨道 ==========
    audio_track_id = generate_uuid()
    audio_segment = {
        "id": generate_uuid(),
        "material_id": audio_id,
        "source_timerange": {"duration": audio_duration, "start": 0},
        "target_timerange": {"duration": audio_duration, "start": 0},
        "volume": 10.0,  # +20dB 对白音量
        "visible": True,
        "speed": 1.0
    }
    
    audio_track = {
        "attribute": 0,
        "flag": 0,
        "id": audio_track_id,
        "is_default_name": True,
        "name": "",
        "segments": [audio_segment],
        "type": "audio"
    }
    
    draft['tracks'].append(audio_track)
    
    # 更新总时长
    draft['duration'] = audio_duration
    
    print(f"✅ 创建音频轨道")
    
    # ========== 调整背景音乐和其他元素 ==========
    adjust_background_elements(draft, audio_duration)
    
    # 保存草稿文件
    draft_content_path = os.path.join(draft_folder, "draft_content.json")
    with open(draft_content_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    # 复制模板文件夹的其他文件
    template_folder = os.path.dirname(template_path)
    for item in os.listdir(template_folder):
        if item != "draft_content.json":
            src_path = os.path.join(template_folder, item)
            dst_path = os.path.join(draft_folder, item)
            
            try:
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                elif os.path.isdir(src_path):
                    if os.path.exists(dst_path):
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
            except Exception as e:
                print(f"⚠️  复制文件时出错 {item}: {e}")
    
    print(f"\n✅ 剪映草稿生成完成")
    print(f"   草稿路径: {draft_folder}")
    print(f"   总时长: {audio_duration/1000000:.2f}秒")
    
    return draft_folder


def create_video_segment(material_id: str, start_time: int, duration: int, render_index: int) -> dict:
    """创建视频片段 JSON"""
    return {
        "caption_info": None,
        "cartoon": False,
        "clip": {
            "alpha": 1.0,
            "flip": {"horizontal": False, "vertical": False},
            "rotation": 0.0,
            "scale": {"x": 1.0, "y": 1.0},
            "transform": {"x": 0.0, "y": 0.0}
        },
        "common_keyframes": [],
        "enable_adjust": True,
        "extra_material_refs": [],
        "id": generate_uuid(),
        "material_id": material_id,
        "render_index": render_index,
        "source_timerange": {"duration": duration, "start": 0},
        "speed": 1.0,
        "target_timerange": {"duration": duration, "start": start_time},
        "visible": True,
        "volume": 1.0
    }


def adjust_background_elements(draft: dict, total_duration: int):
    """调整背景音乐、黑色背景等元素的时长"""
    for track in draft['tracks']:
        if track['type'] == 'audio':
            for segment in track['segments']:
                if 'material_id' in segment:
                    for audio_material in draft['materials']['audios']:
                        if (audio_material['id'] == segment['material_id'] and 
                            audio_material.get('name') == 'messironaldo.MP3'):
                            segment['target_timerange']['duration'] = total_duration
                            if 'source_timerange' in segment:
                                segment['source_timerange']['duration'] = total_duration
                            segment['volume'] = 3.16  # +10dB 背景音乐
                            print(f"✅ 调整背景音乐到 {total_duration/1000000:.2f}秒")
        
        if track['type'] == 'video':
            for segment in track['segments']:
                if 'material_id' in segment:
                    for video_material in draft['materials']['videos']:
                        if video_material['id'] == segment['material_id']:
                            material_name = video_material.get('material_name', '')
                            if 'black.png' in material_name.lower():
                                segment['target_timerange']['duration'] = total_duration
                                if 'source_timerange' in segment:
                                    segment['source_timerange']['duration'] = total_duration


# ============================================================================
# 步骤 4: 人工精修指引
# ============================================================================

def manual_editing_guide(draft_folder: str):
    """
    步骤4：人工精修指引
    
    提供详细的剪映操作指南
    """
    print("\n" + "="*60)
    print("📍 步骤 4/5: 在剪映中精修")
    print("="*60)
    
    print("\n🔍 人工检查点 ③:")
    print(f"   草稿已生成，请在剪映中打开进行精修")
    print(f"   草稿路径: {draft_folder}")
    
    print("\n📝 精修清单（建议按顺序进行）:")
    print("\n1️⃣  检查时间轴对齐")
    print("   ☐ 图片切换时间是否合理")
    print("   ☐ 音频是否与画面同步")
    print("   ☐ 调整图片显示时长（如需要）")
    
    print("\n2️⃣  字幕优化")
    print("   ☐ 导入 SRT 字幕文件")
    print("   ☐ 调整字幕样式（字体、大小、颜色）")
    print("   ☐ 添加字幕描边或阴影")
    print("   ☐ 调整字幕位置")
    
    print("\n3️⃣  视觉效果")
    print("   ☐ 添加图片转场（推荐：叠化、擦除）")
    print("   ☐ 添加图片动画（缩放、平移）")
    print("   ☐ 调整画面比例（确保16:9）")
    print("   ☐ 添加滤镜或调色")
    
    print("\n4️⃣  音频优化")
    print("   ☐ 调整对白音量")
    print("   ☐ 添加/调整背景音乐")
    print("   ☐ 添加音效（如需要）")
    print("   ☐ 使用音频降噪")
    
    print("\n5️⃣  最终检查")
    print("   ☐ 预览完整视频")
    print("   ☐ 检查是否有卡顿或跳帧")
    print("   ☐ 确认字幕无遮挡")
    print("   ☐ 确认音画同步")
    
    print("\n💡 快捷键提示:")
    print("   空格键: 播放/暂停")
    print("   J/K/L: 倒退/暂停/快进")
    print("   Cmd+Z: 撤销")
    print("   Cmd+S: 保存")
    
    input("\n完成精修后按 Enter 继续...\n")


# ============================================================================
# 步骤 5: 导出指引
# ============================================================================

def export_guide():
    """
    步骤5：导出视频指引
    """
    print("\n" + "="*60)
    print("📍 步骤 5/5: 导出视频")
    print("="*60)
    
    print("\n📤 导出设置建议:")
    print("   分辨率: 1920x1080 (16:9)")
    print("   帧率: 30fps")
    print("   码率: 自动或 5000kbps")
    print("   格式: MP4 (H.264)")
    
    print("\n⚙️  导出步骤:")
    print("   1. 点击右上角「导出」按钮")
    print("   2. 选择导出分辨率为 1080P")
    print("   3. 选择导出格式为 MP4")
    print("   4. 设置导出路径")
    print("   5. 点击「导出」开始渲染")
    
    print("\n⏱️  预计导出时间:")
    print("   1分钟视频 ≈ 1-3分钟渲染时间（取决于特效数量）")
    
    print("\n✅ 完成！")


# ============================================================================
# 主程序流程
# ============================================================================

def semi_auto_workflow(
    input_audio: str,
    image_folder: str,
    template_path: str,
    output_base_folder: str,
    draft_name: str = "video_draft",
    jianying_drafts_folder: str = None,
    duration_threshold: float = 1.5,
    min_silence_len: int = 500,
    silence_thresh: int = -40,
    whisper_model: str = "base"
):
    """
    方案 B：半自动化工作流程
    
    Args:
        input_audio: 原始音频路径
        image_folder: 图片文件夹路径
        template_path: 剪映模板草稿路径
        output_base_folder: 临时输出文件夹
        draft_name: 草稿名称
        jianying_drafts_folder: 剪映草稿最终目标文件夹
        duration_threshold: 短/长音频阈值（秒）
        min_silence_len: 最小静音长度（毫秒）
        silence_thresh: 静音阈值（dB）
        whisper_model: Whisper 模型大小
    """
    print("\n" + "="*70)
    print("🎬 方案 B：半自动化剪映草稿生成器")
    print("   结合自动化效率 + 人工精修质量")
    print("="*70)
    
    # 创建临时工作文件夹
    os.makedirs(output_base_folder, exist_ok=True)
    
    # 定义中间文件路径
    clean_audio = os.path.join(output_base_folder, "clean_audio.mp3")
    srt_path = os.path.join(output_base_folder, "subtitles.srt")
    
    # ========== 步骤 1: 移除静音 ==========
    clean_audio = remove_silence_step(
        input_audio=input_audio,
        output_audio=clean_audio,
        min_silence_len=min_silence_len,
        silence_thresh=silence_thresh
    )
    
    # ========== 步骤 2: 语音识别 ==========
    segments = transcribe_audio_step(
        audio_path=clean_audio,
        srt_path=srt_path,
        model_size=whisper_model
    )
    
    # ========== 步骤 3: 生成剪映草稿 ==========
    draft_folder = create_jianying_draft_step(
        template_path=template_path,
        clean_audio=clean_audio,
        image_folder=image_folder,
        segments=segments,
        output_folder=output_base_folder,
        draft_name=draft_name,
        duration_threshold=duration_threshold
    )
    
    # 移动草稿到剪映文件夹（如果指定）
    if jianying_drafts_folder:
        final_draft_path = os.path.join(jianying_drafts_folder, draft_name)
        
        # 如果目标已存在，先删除
        if os.path.exists(final_draft_path):
            shutil.rmtree(final_draft_path)
        
        # 移动草稿
        shutil.move(draft_folder, final_draft_path)
        draft_folder = final_draft_path
        
        print(f"\n✅ 草稿已移动到剪映文件夹")
        print(f"   {final_draft_path}")
    
    # ========== 步骤 4: 人工精修指引 ==========
    manual_editing_guide(draft_folder)
    
    # ========== 步骤 5: 导出指引 ==========
    export_guide()
    
    print("\n" + "="*70)
    print("🎉 方案 B 流程完成！")
    print("="*70)
    print(f"\n📁 输出文件:")
    print(f"   草稿: {draft_folder}")
    print(f"   字幕: {srt_path}")
    print(f"   音频: {clean_audio}")
    
    print("\n💡 后续步骤:")
    print("   1. 在剪映中打开草稿进行精修")
    print("   2. 完成后导出最终视频")
    print("   3. 如需批量处理，重复运行脚本")


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    # ========== 配置路径 ==========
    
    # 输入文件
    INPUT_AUDIO = "/Users/mac/YouTube/01工具类/playwright/input.mp3"
    IMAGE_FOLDER = "/Users/mac/YouTube/01工具类/playwright/reference_images/01"
    
    # 剪映模板（需要提前创建一个基础模板）
    TEMPLATE_PATH = "/Users/mac/Desktop/template_draft/draft_content.json"
    
    # 输出路径
    OUTPUT_BASE_FOLDER = "/Users/mac/YouTube/01工具类/playwright/temp_output"
    JIANYING_DRAFTS_FOLDER = "/Users/mac/Movies/JianyingPro/User Data/Projects/com.lveditor.draft"
    
    # 草稿名称（建议用项目名）
    DRAFT_NAME = "story_01"
    
    # ========== 可调参数 ==========
    
    # 短/长音频阈值（秒）
    DURATION_THRESHOLD = 1.5
    
    # 静音检测参数
    MIN_SILENCE_LEN = 500   # 毫秒
    SILENCE_THRESH = -40    # dB
    
    # Whisper 模型（tiny/base/small/medium）
    WHISPER_MODEL = "base"
    
    # ========== 执行流程 ==========
    
    semi_auto_workflow(
        input_audio=INPUT_AUDIO,
        image_folder=IMAGE_FOLDER,
        template_path=TEMPLATE_PATH,
        output_base_folder=OUTPUT_BASE_FOLDER,
        draft_name=DRAFT_NAME,
        jianying_drafts_folder=JIANYING_DRAFTS_FOLDER,
        duration_threshold=DURATION_THRESHOLD,
        min_silence_len=MIN_SILENCE_LEN,
        silence_thresh=SILENCE_THRESH,
        whisper_model=WHISPER_MODEL
    )
```

---

## 🎯 核心优势详解

### 1. 保留方案 A 的智能逻辑

```python
# 智能图片分配算法（完全继承）
if duration < 1.5:
    配1张图片
else:
    配2张图片（平均分配）
```

### 2. 增加3个人工检查点

```
检查点 ①: 音频处理后
    └─ 试听效果，调整参数

检查点 ②: 字幕生成后
    └─ 校对文字，修正错误

检查点 ③: 草稿生成后
    └─ 剪映中精修，添加特效
```

### 3. 灵活的参数调整

| 参数 | 默认值 | 调整方向 |
|------|-------|---------|
| `duration_threshold` | 1.5秒 | 控制图片切换频率 |
| `min_silence_len` | 500ms | 控制删除的静音长度 |
| `silence_thresh` | -40dB | 控制静音检测灵敏度 |
| `whisper_model` | base | 控制识别速度/质量 |

---

## 📖 使用流程

### 第一次使用（创建模板）

```bash
# 1. 在剪映中创建一个基础项目
#    - 添加黑色背景
#    - 设置16:9分辨率
#    - 添加默认背景音乐（可选）
#    - 保存项目

# 2. 找到剪映草稿文件
#    macOS: ~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/

# 3. 复制草稿作为模板
cp -r "你的草稿文件夹" /path/to/template_draft/
```

### 日常使用

```bash
# 1. 修改配置路径
INPUT_AUDIO = "你的音频.mp3"
IMAGE_FOLDER = "你的图片文件夹"

# 2. 运行脚本
python semi_auto_generator.py

# 3. 按提示操作
#    - 确认音频效果
#    - 确认字幕准确性
#    - 在剪映中精修
#    - 导出视频
```

---

## 🛠️ 环境配置

### 安装依赖

```bash
# 与方案 A 相同
pip install pydub whisper moviepy mutagen
brew install ffmpeg  # macOS
```

### 剪映安装

```bash
# macOS
下载: https://lv.ulikecam.com/

# Windows
下载: https://www.capcut.cn/
```

---

## ⚙️ 参数调优指南

### 场景 1: 音频间隙太多

```python
# 增大静音长度阈值
MIN_SILENCE_LEN = 800  # 从 500 增加到 800

# 或降低静音音量阈值
SILENCE_THRESH = -35  # 从 -40 提高到 -35
```

### 场景 2: 图片切换太快

```python
# 提高短/长音频阈值
DURATION_THRESHOLD = 2.0  # 从 1.5 提高到 2.0
# 效果：更多音频段会被分配2张图片
```

### 场景 3: 字幕识别不准

```python
# 使用更大的模型
WHISPER_MODEL = "small"  # 从 base 升级到 small
# 或手动编辑 SRT 文件
```

---

## 🚀 进阶技巧

### 批量处理多个故事

```python
def batch_process_stories(story_configs: List[dict]):
    """批量处理多个故事"""
    for i, config in enumerate(story_configs, 1):
        print(f"\n{'='*70}")
        print(f"处理故事 {i}/{len(story_configs)}: {config['draft_name']}")
        print(f"{'='*70}")
        
        semi_auto_workflow(**config)
        
        # 暂停，等待用户确认
        if i < len(story_configs):
            input(f"\n故事 {i} 完成，按 Enter 处理下一个...\n")

# 使用
stories = [
    {
        "input_audio": "story1/audio.mp3",
        "image_folder": "story1/images",
        "draft_name": "story_01",
        # ... 其他参数
    },
    {
        "input_audio": "story2/audio.mp3",
        "image_folder": "story2/images",
        "draft_name": "story_02",
        # ... 其他参数
    }
]

batch_process_stories(stories)
```

### 自定义图片分配策略

```python
# 在 create_jianying_draft_step() 中修改

# 策略1: 更激进的切换（更多双图）
DURATION_THRESHOLD = 1.0

# 策略2: 固定每个句子2张图
for segment in segments:
    # 无论时长，都分配2张图片
    配2张图片

# 策略3: 按关键词切换
if "important" in segment['text']:
    配3张图片  # 重点内容多配图
else:
    配1张图片
```

### 添加自动转场

```python
# 在生成草稿时添加转场效果（需要研究剪映草稿格式）
# 或在剪映中手动批量添加
```

---

## 📊 方案 A vs 方案 B 对比

### 实际工作流程对比

| 步骤 | 方案 A | 方案 B |
|------|--------|--------|
| 1. 音频处理 | 自动 | 自动 + 人工确认 |
| 2. 语音识别 | 自动 | 自动 + 人工校对 |
| 3. 图片分配 | 自动（固定） | 自动 + 剪映调整 |
| 4. 字幕样式 | 代码固定 | 剪映可视化调整 |
| 5. 特效转场 | 无 | 剪映中添加 |
| 6. 背景音乐 | 无 | 剪映中添加 |
| 7. 最终导出 | Python导出 | 剪映导出 |

### 时间成本对比

```
方案 A（1分钟视频）:
├── 自动处理: 3-5分钟
└── 总时间: 3-5分钟

方案 B（1分钟视频）:
├── 自动处理: 2分钟
├── 人工确认: 2分钟
├── 剪映精修: 5-10分钟
└── 总时间: 9-14分钟

手动剪辑（1分钟视频）:
├── 导入素材: 2分钟
├── 剪辑对齐: 10-15分钟
├── 添加字幕: 5-10分钟
├── 特效调整: 5-10分钟
└── 总时间: 22-37分钟
```

### 质量对比

```
方案 A: ⭐⭐⭐
    ├── 优点: 快速一致
    └── 缺点: 缺少个性化

方案 B: ⭐⭐⭐⭐⭐
    ├── 优点: 自动化 + 可定制
    └── 缺点: 需要一定时间

手动剪辑: ⭐⭐⭐⭐
    ├── 优点: 完全控制
    └── 缺点: 耗时且重复性高
```

---

## 💡 最佳实践建议

### 1. 首次使用流程

```
Day 1: 环境搭建
    ├── 安装 Python 依赖
    ├── 创建剪映模板
    └── 测试小样本（10秒音频）

Day 2: 参数调优
    ├── 调整静音检测参数
    ├── 调整图片切换阈值
    └── 熟悉剪映操作

Day 3: 正式生产
    └── 批量处理视频
```

### 2. 文件组织建议

```
项目文件夹/
├── scripts/
│   └── semi_auto_generator.py
├── templates/
│   └── base_draft/
│       └── draft_content.json
├── projects/
│   ├── story_01/
│   │   ├── audio.mp3
│   │   ├── images/
│   │   └── output/
│   └── story_02/
│       ├── audio.mp3
│       ├── images/
│       └── output/
└── final_videos/
    ├── story_01.mp4
    └── story_02.mp4
```

### 3. 质量检查清单

```
音频质量 ✓
    ☐ 无明显杂音
    ☐ 音量适中
    ☐ 静音删除合理

字幕质量 ✓
    ☐ 文字准确
    ☐ 时间对齐
    ☐ 无错别字

画面质量 ✓
    ☐ 图片清晰
    ☐ 切换自然
    ☐ 比例正确 (16:9)

整体效果 ✓
    ☐ 音画同步
    ☐ 节奏流畅
    ☐ 无卡顿
```

---

## 🐛 常见问题

### Q1: 找不到剪映草稿文件夹？

```bash
# macOS 路径
~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/

# Windows 路径
C:\Users\你的用户名\AppData\Local\JianyingPro\User Data\Projects\com.lveditor.draft\
```

### Q2: 草稿在剪映中无法打开？

```
可能原因:
1. draft_content.json 格式错误
2. 路径中包含特殊字符
3. 剪映版本不兼容

解决方案:
1. 使用最新版剪映
2. 检查 JSON 格式
3. 重新创建模板
```

### Q3: 图片在剪映中显示不正确？

```
检查:
1. 图片路径是否正确（绝对路径）
2. 图片文件是否存在
3. 图片格式是否支持（PNG/JPG）

解决:
在剪映中重新导入图片
```

---

## 📝 总结

### 方案 B 的核心价值

```
自动化部分（省时）:
✅ 音频静音移除 (省80%时间)
✅ 语音识别生成字幕 (省90%时间)
✅ 智能图片分配 (省70%时间)

人工部分（提质）:
✅ 参数微调
✅ 字幕校对
✅ 视觉效果
✅ 特效转场

最终效果:
= 方案A的速度 × 0.5
+ 手动剪辑的质量 × 0.9
```

### 适用场景

**✅ 最适合：**
- 需要批量生产视频
- 对质量有一定要求
- 愿意花时间精修
- 熟悉剪映操作

**❌ 不适合：**
- 只做一个视频（直接手动更快）
- 完全不懂剪映
- 需要极致自动化

### 后续优化方向

- [ ] 自动添加字幕样式模板
- [ ] 支持更多转场效果
- [ ] AI 智能配音
- [ ] 自动生成封面
- [ ] Web 界面化操作

---

*文档版本: 1.0*  
*最后更新: 2025-10-14*  
*作者: Claude + 用户协作*

