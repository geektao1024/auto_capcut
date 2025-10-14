#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut 草稿自动生成器
支持 CapCut 国际版和剪映国内版
基于方案 B，自动检测安装版本
"""

import json
import os
import uuid
import platform
import glob
import re
from datetime import datetime
from typing import List, Dict, Optional

# ============================================================================
# 自动检测 CapCut/剪映安装路径
# ============================================================================

def detect_capcut_path() -> Dict[str, str]:
    """
    自动检测 CapCut 或剪映的安装路径
    
    Returns:
        包含草稿路径和版本信息的字典
    """
    system = platform.system()
    result = {
        "drafts_folder": None,
        "app_name": None,
        "app_path": None
    }
    
    if system == "Darwin":  # macOS
        # 检查 CapCut 国际版
        capcut_drafts = os.path.expanduser("~/Movies/CapCut/User Data/Projects/com.lveditor.draft")
        capcut_app = "/Applications/CapCut.app"
        
        if os.path.exists(capcut_drafts):
            result["drafts_folder"] = capcut_drafts
            result["app_name"] = "CapCut"
            result["app_path"] = capcut_app
            print(f"✅ 检测到 CapCut 国际版")
            print(f"   草稿路径: {capcut_drafts}")
            return result
        
        # 检查剪映国内版
        jianying_drafts = os.path.expanduser("~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft")
        jianying_app = "/Applications/JianyingPro.app"
        
        if os.path.exists(jianying_drafts):
            result["drafts_folder"] = jianying_drafts
            result["app_name"] = "剪映"
            result["app_path"] = jianying_app
            print(f"✅ 检测到剪映国内版")
            print(f"   草稿路径: {jianying_drafts}")
            return result
    
    elif system == "Windows":
        username = os.getenv("USERNAME")
        
        # 检查 CapCut 国际版
        capcut_drafts = f"C:/Users/{username}/AppData/Local/CapCut/User Data/Projects/com.lveditor.draft"
        
        if os.path.exists(capcut_drafts):
            result["drafts_folder"] = capcut_drafts
            result["app_name"] = "CapCut"
            print(f"✅ 检测到 CapCut 国际版")
            print(f"   草稿路径: {capcut_drafts}")
            return result
        
        # 检查剪映国内版
        jianying_drafts = f"C:/Users/{username}/AppData/Local/JianyingPro/User Data/Projects/com.lveditor.draft"
        
        if os.path.exists(jianying_drafts):
            result["drafts_folder"] = jianying_drafts
            result["app_name"] = "剪映"
            print(f"✅ 检测到剪映国内版")
            print(f"   草稿路径: {jianying_drafts}")
            return result
    
    print("❌ 未检测到 CapCut 或剪映")
    print("请确保已安装以下软件之一：")
    print("  - CapCut (https://www.capcut.com/)")
    print("  - 剪映 (https://lv.ulikecam.com/)")
    return result


# ============================================================================
# CapCut 草稿生成核心
# ============================================================================

def create_capcut_draft(
    audio_path: str,
    image_folder: str,
    output_folder: str,
    draft_name: str,
    segments: Optional[List[dict]] = None,
    duration_threshold: float = 1.5
) -> str:
    """
    创建 CapCut/剪映草稿
    
    Args:
        audio_path: 音频文件路径
        image_folder: 图片文件夹路径
        output_folder: 输出文件夹（草稿目录）
        draft_name: 草稿名称
        segments: 字幕片段（可选）
        duration_threshold: 短/长音频阈值
        
    Returns:
        草稿文件夹路径
    """
    
    print(f"\n{'='*60}")
    print(f"📝 创建 CapCut 草稿: {draft_name}")
    print(f"{'='*60}")
    
    # 创建草稿文件夹
    draft_folder = os.path.join(output_folder, draft_name)
    os.makedirs(draft_folder, exist_ok=True)
    
    # 生成ID
    draft_id = str(uuid.uuid4()).upper()
    audio_id = str(uuid.uuid4()).upper()
    
    # 获取音频时长
    from mutagen import File as MutagenFile
    try:
        audio_file = MutagenFile(audio_path)
        audio_duration_sec = audio_file.info.length
        audio_duration_micro = int(audio_duration_sec * 1000000)
    except:
        audio_duration_micro = 5000000  # 默认5秒
    
    # 获取图片列表
    image_files = []
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        image_files.extend(glob.glob(os.path.join(image_folder, ext)))
    
    if not image_files:
        raise ValueError(f"❌ 未找到图片文件")
    
    # 自然排序
    def natural_sort_key(s):
        return [int(c) if c.isdigit() else c for c in re.split(r'(\d+)', s)]
    
    image_files.sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    
    print(f"📊 素材统计:")
    print(f"   音频: {os.path.basename(audio_path)} ({audio_duration_sec:.2f}秒)")
    print(f"   图片: {len(image_files)} 张")
    
    # 创建草稿结构
    draft = {
        "canvas_config": {
            "height": 1080,
            "width": 1920,
            "ratio": "16:9"
        },
        "create_time": int(datetime.now().timestamp() * 1000000),
        "draft_name": draft_name,
        "draft_root_path": draft_folder,
        "duration": audio_duration_micro,
        "id": draft_id,
        "materials": {
            "audios": [],
            "videos": [],
            "texts": []
        },
        "platform": "darwin" if platform.system() == "Darwin" else "win32",
        "tracks": [],
        "version": "5.9.0"
    }
    
    # 添加音频材料
    audio_material = {
        "id": audio_id,
        "name": os.path.basename(audio_path),
        "path": audio_path,
        "duration": audio_duration_micro,
        "type": "extract_music"
    }
    draft['materials']['audios'].append(audio_material)
    
    # 添加图片材料
    image_ids = []
    for img_path in image_files:
        img_id = str(uuid.uuid4()).upper()
        image_material = {
            "id": img_id,
            "material_name": os.path.basename(img_path),
            "path": img_path,
            "type": "photo",
            "duration": 10800000000,  # 3小时（足够长）
            "height": 2048,
            "width": 1152
        }
        draft['materials']['videos'].append(image_material)
        image_ids.append(img_id)
    
    # 创建视频轨道
    video_track = {
        "id": str(uuid.uuid4()).upper(),
        "type": "video",
        "segments": []
    }
    
    # 智能分配图片
    if segments:
        # 使用字幕片段信息
        image_index = 0
        
        print(f"\n{'='*60}")
        print(f"🎨 智能图片分配（阈值: {duration_threshold}秒）")
        print(f"{'='*60}")
        
        for i, segment in enumerate(segments):
            start_time = int(segment['start'] * 1000000)
            end_time = int(segment['end'] * 1000000)
            duration = end_time - start_time
            duration_sec = duration / 1000000
            
            if duration_sec < duration_threshold:
                # 短音频：1张图片
                if image_index < len(image_ids):
                    seg = {
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": image_ids[image_index],
                        "target_timerange": {"start": start_time, "duration": duration},
                        "source_timerange": {"start": 0, "duration": duration},
                        "visible": True
                    }
                    video_track['segments'].append(seg)
                    print(f"句子 {i+1} (短 {duration_sec:.2f}s): 图片 {image_index+1}")
                    image_index += 1
            else:
                # 长音频：2张图片
                if image_index + 1 < len(image_ids):
                    half = duration // 2
                    
                    seg1 = {
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": image_ids[image_index],
                        "target_timerange": {"start": start_time, "duration": half},
                        "source_timerange": {"start": 0, "duration": half},
                        "visible": True
                    }
                    video_track['segments'].append(seg1)
                    
                    seg2 = {
                        "id": str(uuid.uuid4()).upper(),
                        "material_id": image_ids[image_index + 1],
                        "target_timerange": {"start": start_time + half, "duration": duration - half},
                        "source_timerange": {"start": 0, "duration": duration - half},
                        "visible": True
                    }
                    video_track['segments'].append(seg2)
                    
                    print(f"句子 {i+1} (长 {duration_sec:.2f}s): 图片 {image_index+1} + {image_index+2}")
                    image_index += 2
    else:
        # 平均分配
        time_per_image = audio_duration_micro // len(image_ids)
        for i, img_id in enumerate(image_ids):
            seg = {
                "id": str(uuid.uuid4()).upper(),
                "material_id": img_id,
                "target_timerange": {"start": i * time_per_image, "duration": time_per_image},
                "source_timerange": {"start": 0, "duration": time_per_image},
                "visible": True
            }
            video_track['segments'].append(seg)
    
    draft['tracks'].append(video_track)
    
    # 创建音频轨道
    audio_track = {
        "id": str(uuid.uuid4()).upper(),
        "type": "audio",
        "segments": [
            {
                "id": str(uuid.uuid4()).upper(),
                "material_id": audio_id,
                "target_timerange": {"start": 0, "duration": audio_duration_micro},
                "source_timerange": {"start": 0, "duration": audio_duration_micro},
                "volume": 10.0
            }
        ]
    }
    draft['tracks'].append(audio_track)
    
    # 保存草稿文件
    draft_content_path = os.path.join(draft_folder, "draft_content.json")
    with open(draft_content_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    # 创建 draft_info.json
    draft_info = {
        "draft_id": draft_id,
        "draft_name": draft_name,
        "draft_root_path": draft_folder,
        "tm_draft_create": int(datetime.now().timestamp() * 1000000),
        "tm_draft_modified": int(datetime.now().timestamp() * 1000000),
        "tm_duration": audio_duration_micro
    }
    
    draft_info_path = os.path.join(draft_folder, "draft_info.json")
    with open(draft_info_path, 'w', encoding='utf-8') as f:
        json.dump(draft_info, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ CapCut 草稿创建完成")
    print(f"   路径: {draft_folder}")
    print(f"   时长: {audio_duration_sec:.2f}秒")
    
    return draft_folder


# ============================================================================
# 使用示例
# ============================================================================

if __name__ == "__main__":
    print("="*70)
    print("🎬 CapCut 草稿自动生成器")
    print("="*70)
    
    # 自动检测 CapCut/剪映
    capcut_info = detect_capcut_path()
    
    if not capcut_info["drafts_folder"]:
        print("\n❌ 未找到 CapCut 或剪映，请先安装")
        exit(1)
    
    # 配置路径
    AUDIO_PATH = "/Users/mac/YouTube/01工具类/playwright/input.mp3"
    IMAGE_FOLDER = "/Users/mac/YouTube/01工具类/playwright/reference_images/01"
    DRAFT_NAME = f"auto_draft_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # 检查文件是否存在
    if not os.path.exists(AUDIO_PATH):
        print(f"\n❌ 音频文件不存在: {AUDIO_PATH}")
        exit(1)
    
    if not os.path.exists(IMAGE_FOLDER):
        print(f"\n❌ 图片文件夹不存在: {IMAGE_FOLDER}")
        exit(1)
    
    # 创建草稿
    try:
        draft_folder = create_capcut_draft(
            audio_path=AUDIO_PATH,
            image_folder=IMAGE_FOLDER,
            output_folder=capcut_info["drafts_folder"],
            draft_name=DRAFT_NAME,
            segments=None,  # 如果有字幕片段，传入这里
            duration_threshold=1.5
        )
        
        print(f"\n{'='*70}")
        print(f"🎉 完成！现在可以在 {capcut_info['app_name']} 中打开草稿了")
        print(f"{'='*70}")
        
    except Exception as e:
        print(f"\n❌ 创建草稿失败: {e}")
        import traceback
        traceback.print_exc()

