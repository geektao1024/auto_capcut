#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut 草稿自动生成器
自动从 "00批量出图" 文件夹读取素材，生成 CapCut 草稿
"""

import os
import json
import uuid
import glob
import shutil
import platform
from datetime import datetime
from mutagen import File as MutagenFile

# ============================================================================
# 配置区域
# ============================================================================

# 素材根目录
MATERIAL_BASE_FOLDER = "/Users/mac/YouTube/00批量出图"

# CapCut 草稿目录
CAPCUT_DRAFTS_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)

# 模板草稿（使用最新的草稿作为模板）
TEMPLATE_DRAFT = None  # 自动检测


# ============================================================================
# 工具函数
# ============================================================================

def get_available_folders():
    """获取所有可用的素材文件夹"""
    if not os.path.exists(MATERIAL_BASE_FOLDER):
        print(f"❌ 素材文件夹不存在: {MATERIAL_BASE_FOLDER}")
        return []
    
    folders = []
    for item in os.listdir(MATERIAL_BASE_FOLDER):
        item_path = os.path.join(MATERIAL_BASE_FOLDER, item)
        if os.path.isdir(item_path):
            folders.append(item)
    
    # 按名称排序（日期命名会自动按时间排序）
    folders.sort(reverse=True)
    return folders


def select_folder(folders):
    """让用户选择要处理的文件夹"""
    print("\n" + "="*70)
    print("📁 可用的素材文件夹:")
    print("="*70)
    
    for i, folder in enumerate(folders, 1):
        folder_path = os.path.join(MATERIAL_BASE_FOLDER, folder)
        
        # 统计文件数量
        audio_count = len(glob.glob(os.path.join(folder_path, "*.mp3"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.wav"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.m4a")))
        
        image_count = len(glob.glob(os.path.join(folder_path, "*.png"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.jpg"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.jpeg")))
        
        print(f"{i:2d}. {folder:30s}  [🎵 {audio_count} 音频, 🖼️  {image_count} 图片]")
    
    print("\n0. 退出")
    print("="*70)
    
    while True:
        try:
            choice = input("\n请选择文件夹编号: ").strip()
            
            if choice == '0':
                print("👋 已退出")
                return None
            
            choice_num = int(choice)
            if 1 <= choice_num <= len(folders):
                return folders[choice_num - 1]
            else:
                print(f"❌ 请输入 0-{len(folders)} 之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n👋 已退出")
            return None


def find_media_files(folder_path):
    """查找文件夹中的音频和图片文件"""
    audio_files = []
    image_files = []
    
    # 查找音频
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.MP3', '*.WAV']:
        audio_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    # 查找图片
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        image_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    # 自然排序
    audio_files.sort()
    image_files.sort()
    
    return audio_files, image_files


def get_template_draft():
    """获取模板草稿"""
    if not os.path.exists(CAPCUT_DRAFTS_FOLDER):
        print(f"❌ CapCut 草稿文件夹不存在: {CAPCUT_DRAFTS_FOLDER}")
        return None
    
    # 找到最新的草稿作为模板
    drafts = [d for d in os.listdir(CAPCUT_DRAFTS_FOLDER) 
              if os.path.isdir(os.path.join(CAPCUT_DRAFTS_FOLDER, d))
              and not d.startswith('.')]
    
    if not drafts:
        print("❌ 未找到可用的模板草稿")
        return None
    
    # 按修改时间排序，获取最新的
    template = sorted(drafts, 
                     key=lambda x: os.path.getmtime(os.path.join(CAPCUT_DRAFTS_FOLDER, x)))[-1]
    
    return os.path.join(CAPCUT_DRAFTS_FOLDER, template)


def create_capcut_draft(folder_name, audio_files, image_files):
    """创建 CapCut 草稿"""
    
    print(f"\n{'='*70}")
    print(f"🎬 开始创建 CapCut 草稿: {folder_name}")
    print(f"{'='*70}")
    
    # 检查素材
    if not audio_files:
        print("❌ 未找到音频文件")
        return None
    
    if not image_files:
        print("❌ 未找到图片文件")
        return None
    
    # 使用第一个音频文件
    audio_file = audio_files[0]
    
    print(f"\n📊 素材统计:")
    print(f"  🎵 音频: {os.path.basename(audio_file)}")
    print(f"  🖼️  图片: {len(image_files)} 张")
    
    # 获取音频时长
    try:
        audio = MutagenFile(audio_file)
        audio_duration_sec = audio.info.length
        audio_duration_micro = int(audio_duration_sec * 1000000)
        print(f"  ⏱️  时长: {audio_duration_sec:.2f} 秒")
    except Exception as e:
        print(f"⚠️  无法读取音频时长: {e}")
        audio_duration_micro = 10000000  # 默认10秒
        audio_duration_sec = 10.0
    
    # 获取模板
    template_path = get_template_draft()
    if not template_path:
        return None
    
    print(f"\n📋 使用模板: {os.path.basename(template_path)}")
    
    # 创建草稿文件夹
    draft_name = f"{folder_name}_{datetime.now().strftime('%H%M%S')}"
    draft_folder = os.path.join(CAPCUT_DRAFTS_FOLDER, draft_name)
    
    # 复制模板
    if os.path.exists(draft_folder):
        shutil.rmtree(draft_folder)
    
    shutil.copytree(template_path, draft_folder)
    print(f"✅ 复制模板结构")
    
    # 创建 media 文件夹
    media_folder = os.path.join(draft_folder, "Resources", "media")
    os.makedirs(media_folder, exist_ok=True)
    
    # 复制音频文件
    audio_dest = os.path.join(media_folder, "audio.mp3")
    shutil.copy2(audio_file, audio_dest)
    print(f"✅ 复制音频文件")
    
    # 复制图片文件
    copied_images = []
    for i, img_file in enumerate(image_files):
        img_dest = os.path.join(media_folder, os.path.basename(img_file))
        shutil.copy2(img_file, img_dest)
        copied_images.append(img_dest)
    print(f"✅ 复制 {len(copied_images)} 张图片")
    
    # 修改草稿文件
    draft_info_path = os.path.join(draft_folder, "draft_info.json")
    
    with open(draft_info_path, 'r', encoding='utf-8') as f:
        draft = json.load(f)
    
    # 更新基本信息
    draft['draft_name'] = draft_name
    draft['draft_root_path'] = draft_folder
    draft['id'] = str(uuid.uuid4()).upper()
    draft['duration'] = audio_duration_micro
    
    # 更新时间
    now_micro = int(datetime.now().timestamp() * 1000000)
    draft['create_time'] = now_micro
    draft['update_time'] = now_micro
    
    # 更新画布为 16:9
    if 'canvas_config' in draft:
        draft['canvas_config']['width'] = 1920
        draft['canvas_config']['height'] = 1080
        draft['canvas_config']['ratio'] = '16:9'
    
    # 清空材料
    draft['materials']['audios'] = []
    draft['materials']['videos'] = []
    
    # 添加音频材料
    audio_id = str(uuid.uuid4()).upper()
    audio_material = {
        "app_id": 0,
        "category_id": "",
        "category_name": "",
        "check_flag": 1,
        "duration": audio_duration_micro,
        "id": audio_id,
        "name": "audio.mp3",
        "path": audio_dest,
        "type": "extract_music",
        "wave_points": []
    }
    draft['materials']['audios'].append(audio_material)
    
    # 添加图片材料
    image_ids = []
    for img_path in copied_images:
        img_id = str(uuid.uuid4()).upper()
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
            "id": img_id,
            "material_name": os.path.basename(img_path),
            "path": img_path,
            "type": "photo"
        }
        draft['materials']['videos'].append(image_material)
        image_ids.append(img_id)
    
    # 清空轨道
    draft['tracks'] = []
    
    # 创建视频轨道
    time_per_image = audio_duration_micro // len(image_ids)
    video_segments = []
    
    for i, img_id in enumerate(image_ids):
        start_time = i * time_per_image
        duration = time_per_image
        
        # 最后一张图片延长到结束
        if i == len(image_ids) - 1:
            duration = audio_duration_micro - start_time
        
        segment = {
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
            "enable_color_curves": True,
            "enable_color_match_adjust": False,
            "enable_color_wheels": True,
            "enable_lut": True,
            "enable_smart_color_adjust": False,
            "extra_material_refs": [],
            "group_id": "",
            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
            "id": str(uuid.uuid4()).upper(),
            "material_id": img_id,
            "render_index": i + 1,
            "source_timerange": {"duration": duration, "start": 0},
            "speed": 1.0,
            "target_timerange": {"duration": duration, "start": start_time},
            "visible": True,
            "volume": 1.0
        }
        video_segments.append(segment)
    
    video_track = {
        "attribute": 0,
        "flag": 0,
        "id": str(uuid.uuid4()).upper(),
        "is_default_name": True,
        "name": "",
        "segments": video_segments,
        "type": "video"
    }
    draft['tracks'].append(video_track)
    
    # 创建音频轨道
    audio_segment = {
        "caption_info": None,
        "cartoon": False,
        "clip": None,
        "common_keyframes": [],
        "enable_adjust": False,
        "extra_material_refs": [],
        "group_id": "",
        "id": str(uuid.uuid4()).upper(),
        "material_id": audio_id,
        "render_index": 0,
        "source_timerange": {"duration": audio_duration_micro, "start": 0},
        "speed": 1.0,
        "target_timerange": {"duration": audio_duration_micro, "start": 0},
        "visible": True,
        "volume": 1.0
    }
    
    audio_track = {
        "attribute": 0,
        "flag": 0,
        "id": str(uuid.uuid4()).upper(),
        "is_default_name": True,
        "name": "",
        "segments": [audio_segment],
        "type": "audio"
    }
    draft['tracks'].append(audio_track)
    
    # 保存草稿
    with open(draft_info_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    # 保存备份
    with open(os.path.join(draft_folder, "draft_info.json.bak"), 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*70}")
    print(f"✅ 草稿创建完成！")
    print(f"{'='*70}")
    print(f"📝 草稿名称: {draft_name}")
    print(f"📁 草稿路径: {draft_folder}")
    print(f"⏱️  总时长: {audio_duration_sec:.2f} 秒")
    print(f"🎵 音频: 1 个")
    print(f"🖼️  图片: {len(image_ids)} 个")
    print(f"🎬 视频片段: {len(video_segments)} 个")
    
    return draft_folder


def open_capcut():
    """打开 CapCut 应用"""
    print(f"\n🚀 正在打开 CapCut...")
    
    if platform.system() == "Darwin":  # macOS
        os.system("open -a CapCut")
    elif platform.system() == "Windows":
        os.system("start CapCut")
    
    print("✅ CapCut 已打开")


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    
    print("\n" + "="*70)
    print("🎬 CapCut 草稿自动生成器")
    print("="*70)
    print(f"素材目录: {MATERIAL_BASE_FOLDER}")
    print(f"草稿目录: {CAPCUT_DRAFTS_FOLDER}")
    
    # 获取可用文件夹
    folders = get_available_folders()
    
    if not folders:
        print("\n❌ 未找到可用的素材文件夹")
        return
    
    # 选择文件夹
    selected_folder = select_folder(folders)
    
    if not selected_folder:
        return
    
    # 获取素材路径
    folder_path = os.path.join(MATERIAL_BASE_FOLDER, selected_folder)
    
    print(f"\n✅ 已选择: {selected_folder}")
    print(f"📁 路径: {folder_path}")
    
    # 查找媒体文件
    audio_files, image_files = find_media_files(folder_path)
    
    if not audio_files:
        print("\n❌ 该文件夹没有音频文件")
        print("支持的格式: mp3, wav, m4a, aac")
        return
    
    if not image_files:
        print("\n❌ 该文件夹没有图片文件")
        print("支持的格式: png, jpg, jpeg")
        return
    
    print(f"\n📦 找到素材:")
    print(f"  🎵 音频: {len(audio_files)} 个")
    for i, audio in enumerate(audio_files[:3], 1):
        print(f"     {i}. {os.path.basename(audio)}")
    if len(audio_files) > 3:
        print(f"     ... 还有 {len(audio_files)-3} 个")
    
    print(f"  🖼️  图片: {len(image_files)} 个")
    for i, img in enumerate(image_files[:3], 1):
        print(f"     {i}. {os.path.basename(img)}")
    if len(image_files) > 3:
        print(f"     ... 还有 {len(image_files)-3} 个")
    
    # 确认创建
    print("\n" + "-"*70)
    confirm = input("确认创建草稿？(y/n): ").strip().lower()
    
    if confirm != 'y':
        print("❌ 已取消")
        return
    
    # 创建草稿
    draft_folder = create_capcut_draft(selected_folder, audio_files, image_files)
    
    if draft_folder:
        print("\n" + "="*70)
        print("🎉 完成！")
        print("="*70)
        print("\n💡 下一步:")
        print("  1. 打开 CapCut 应用")
        print("  2. 在项目列表中找到新创建的草稿")
        print("  3. 双击打开进行编辑")
        print("  4. 完成后导出视频")
        
        # 询问是否打开 CapCut
        print("\n" + "-"*70)
        open_app = input("是否现在打开 CapCut？(y/n): ").strip().lower()
        
        if open_app == 'y':
            open_capcut()
        
        print("\n👋 感谢使用！")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已退出")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

