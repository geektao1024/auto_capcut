#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CapCut 草稿自动生成器 - 增强版
功能：
1. 交互式文件夹选择
2. 音频智能分段（移除静音）
3. 详细日志记录
4. 在 CapCut 中每个音频片段独立可调整
"""

import os
import json
import uuid
import glob
import shutil
import platform
import logging
from datetime import datetime
from mutagen import File as MutagenFile

# 尝试导入 pydub（音频处理）
try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("⚠️  pydub 未安装，音频分段功能将不可用")
    print("   安装命令: pip3 install pydub")

# ============================================================================
# 配置区域
# ============================================================================

# 素材根目录
MATERIAL_BASE_FOLDER = "/Users/mac/YouTube/00批量出图"

# CapCut 草稿目录
CAPCUT_DRAFTS_FOLDER = os.path.expanduser(
    "~/Movies/CapCut/User Data/Projects/com.lveditor.draft"
)

# 日志配置
LOG_FOLDER = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOG_FOLDER, exist_ok=True)

# ============================================================================
# 日志系统
# ============================================================================

def setup_logger(folder_name):
    """设置日志系统"""
    log_filename = f"{folder_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    log_path = os.path.join(LOG_FOLDER, log_filename)
    
    # 创建 logger
    logger = logging.getLogger('CapCutDraft')
    logger.setLevel(logging.DEBUG)
    
    # 清除现有的 handlers
    logger.handlers = []
    
    # 文件 handler（详细日志）
    file_handler = logging.FileHandler(log_path, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    
    # 控制台 handler（简洁输出）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(message)s')
    console_handler.setFormatter(console_formatter)
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logger.info(f"📝 日志文件: {log_path}")
    logger.debug(f"开始处理文件夹: {folder_name}")
    
    return logger


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
        
        status = "✅" if (audio_count > 0 and image_count > 0) else "⚠️"
        print(f"{status} {i:2d}. {folder:30s}  [🎵 {audio_count} 音频, 🖼️  {image_count} 图片]")
    
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
    
    for ext in ['*.mp3', '*.wav', '*.m4a', '*.aac', '*.MP3', '*.WAV']:
        audio_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    for ext in ['*.png', '*.jpg', '*.jpeg', '*.PNG', '*.JPG', '*.JPEG']:
        image_files.extend(glob.glob(os.path.join(folder_path, ext)))
    
    audio_files.sort()
    image_files.sort()
    
    return audio_files, image_files


def get_template_draft(logger):
    """获取模板草稿"""
    logger.debug("查找模板草稿...")
    
    if not os.path.exists(CAPCUT_DRAFTS_FOLDER):
        logger.error(f"CapCut 草稿文件夹不存在: {CAPCUT_DRAFTS_FOLDER}")
        return None
    
    drafts = [d for d in os.listdir(CAPCUT_DRAFTS_FOLDER) 
              if os.path.isdir(os.path.join(CAPCUT_DRAFTS_FOLDER, d))
              and not d.startswith('.')]
    
    if not drafts:
        logger.error("未找到可用的模板草稿")
        return None
    
    template = sorted(drafts, 
                     key=lambda x: os.path.getmtime(os.path.join(CAPCUT_DRAFTS_FOLDER, x)))[-1]
    
    template_path = os.path.join(CAPCUT_DRAFTS_FOLDER, template)
    logger.debug(f"使用模板: {template}")
    
    return template_path


# ============================================================================
# 音频智能分段（核心功能）
# ============================================================================

def split_audio_by_silence(audio_file, output_folder, logger, 
                          min_silence_len=500, silence_thresh=-40):
    """
    智能分段：检测音频中的静音，切分成多个独立片段
    
    Args:
        audio_file: 原始音频文件
        output_folder: 输出文件夹
        logger: 日志对象
        min_silence_len: 最小静音长度（毫秒）
        silence_thresh: 静音阈值（dB）
        
    Returns:
        分段音频文件列表，每个元素包含 (文件路径, 起始时间ms, 时长ms)
    """
    if not PYDUB_AVAILABLE:
        logger.warning("pydub 不可用，跳过音频分段")
        return [(audio_file, 0, None)]  # 返回原文件
    
    logger.info(f"\n🔧 开始音频智能分段...")
    logger.debug(f"参数: min_silence={min_silence_len}ms, thresh={silence_thresh}dB")
    
    try:
        # 加载音频
        logger.debug("加载音频文件...")
        audio = AudioSegment.from_file(audio_file)
        original_duration = len(audio) / 1000
        logger.debug(f"原始时长: {original_duration:.2f}秒")
        
        # 检测非静音片段
        logger.debug("检测非静音片段...")
        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh,
            seek_step=10
        )
        
        logger.info(f"✅ 检测到 {len(nonsilent_ranges)} 个音频片段")
        
        if len(nonsilent_ranges) == 0:
            logger.warning("未检测到非静音片段，使用原音频")
            return [(audio_file, 0, None)]
        
        # 导出每个片段
        os.makedirs(output_folder, exist_ok=True)
        segments = []
        total_duration = 0
        
        for i, (start_ms, end_ms) in enumerate(nonsilent_ranges, 1):
            segment = audio[start_ms:end_ms]
            duration_ms = end_ms - start_ms
            duration_sec = duration_ms / 1000
            
            # 保存片段
            segment_filename = f"audio_segment_{i:02d}.mp3"
            segment_path = os.path.join(output_folder, segment_filename)
            segment.export(segment_path, format="mp3")
            
            segments.append((segment_path, start_ms, duration_ms))
            total_duration += duration_sec
            
            logger.debug(f"片段 {i}: {start_ms/1000:.2f}s - {end_ms/1000:.2f}s (时长 {duration_sec:.2f}s)")
        
        removed_duration = original_duration - total_duration
        removed_percent = (removed_duration / original_duration) * 100
        
        logger.info(f"\n📊 分段统计:")
        logger.info(f"  原时长: {original_duration:.2f}秒")
        logger.info(f"  新时长: {total_duration:.2f}秒")
        logger.info(f"  移除: {removed_duration:.2f}秒 ({removed_percent:.1f}%)")
        logger.info(f"  片段数: {len(segments)} 个")
        
        return segments
        
    except Exception as e:
        logger.error(f"音频分段失败: {e}", exc_info=True)
        logger.warning("回退到使用原音频")
        return [(audio_file, 0, None)]


# ============================================================================
# CapCut 草稿创建
# ============================================================================

def create_capcut_draft(folder_name, audio_file, image_files, logger):
    """创建 CapCut 草稿（支持多音频片段）"""
    
    logger.info(f"\n{'='*70}")
    logger.info(f"🎬 开始创建 CapCut 草稿: {folder_name}")
    logger.info(f"{'='*70}")
    
    # 获取模板
    logger.debug("步骤 1/8: 获取模板草稿")
    template_path = get_template_draft(logger)
    if not template_path:
        return None
    
    logger.info(f"✅ 使用模板: {os.path.basename(template_path)}")
    
    # 创建草稿文件夹
    logger.debug("步骤 2/8: 创建草稿文件夹")
    draft_name = f"{folder_name}_{datetime.now().strftime('%H%M%S')}"
    draft_folder = os.path.join(CAPCUT_DRAFTS_FOLDER, draft_name)
    
    if os.path.exists(draft_folder):
        logger.debug(f"删除已存在的草稿: {draft_folder}")
        shutil.rmtree(draft_folder)
    
    logger.debug(f"复制模板到: {draft_folder}")
    shutil.copytree(template_path, draft_folder)
    logger.info(f"✅ 草稿文件夹创建完成")
    
    # 创建 media 文件夹
    logger.debug("步骤 3/8: 创建 media 文件夹")
    media_folder = os.path.join(draft_folder, "Resources", "media")
    audio_segments_folder = os.path.join(media_folder, "audio_segments")
    os.makedirs(audio_segments_folder, exist_ok=True)
    logger.debug(f"Media 文件夹: {media_folder}")
    
    # 音频智能分段
    logger.debug("步骤 4/8: 音频智能分段")
    logger.info(f"\n🎵 处理音频: {os.path.basename(audio_file)}")
    
    # 询问是否分段
    if PYDUB_AVAILABLE:
        print("\n" + "-"*70)
        print("🔇 是否启用音频智能分段？")
        print("   - 自动检测并移除静音片段")
        print("   - 在 CapCut 中每个片段独立，可手动调整")
        print("-"*70)
        use_split = input("启用分段？(y/n，默认y): ").strip().lower()
        
        if use_split != 'n':
            # 选择模式
            print("\n分段模式:")
            print("  1. 保守 (>500ms, <-45dB) - 保留更多停顿")
            print("  2. 标准 (>500ms, <-40dB) - 平衡效果 ⭐")
            print("  3. 激进 (>300ms, <-35dB) - 删除更多间隙")
            
            mode = input("选择模式 (1-3，默认2): ").strip() or "2"
            
            params = {
                "1": (500, -45),
                "2": (500, -40),
                "3": (300, -35)
            }
            
            min_silence, thresh = params.get(mode, (500, -40))
            logger.info(f"使用模式: {mode} (min_silence={min_silence}ms, thresh={thresh}dB)")
            
            audio_segments = split_audio_by_silence(
                audio_file, audio_segments_folder, logger,
                min_silence_len=min_silence,
                silence_thresh=thresh
            )
        else:
            logger.info("跳过音频分段，使用原音频")
            audio_segments = [(audio_file, 0, None)]
    else:
        logger.warning("pydub 不可用，使用原音频")
        audio_segments = [(audio_file, 0, None)]
    
    # 复制音频片段到 media 文件夹
    logger.debug("步骤 5/8: 复制音频片段")
    copied_audio_segments = []
    for i, (segment_path, start_ms, duration_ms) in enumerate(audio_segments, 1):
        dest_filename = f"audio_{i:02d}.mp3"
        dest_path = os.path.join(media_folder, dest_filename)
        shutil.copy2(segment_path, dest_path)
        copied_audio_segments.append((dest_path, start_ms, duration_ms))
        logger.debug(f"复制音频片段 {i}: {dest_filename}")
    
    logger.info(f"✅ 复制 {len(copied_audio_segments)} 个音频片段")
    
    # 复制图片
    logger.debug("步骤 6/8: 复制图片文件")
    copied_images = []
    for i, img_file in enumerate(image_files, 1):
        img_dest = os.path.join(media_folder, os.path.basename(img_file))
        shutil.copy2(img_file, img_dest)
        copied_images.append(img_dest)
        logger.debug(f"复制图片 {i}: {os.path.basename(img_file)}")
    
    logger.info(f"✅ 复制 {len(copied_images)} 张图片")
    
    # 计算总时长
    logger.debug("步骤 7/8: 计算总时长")
    total_duration_micro = 0
    for audio_path, _, duration_ms in copied_audio_segments:
        if duration_ms:
            total_duration_micro += duration_ms * 1000  # ms -> microseconds
        else:
            # 如果没有 duration_ms，读取文件实际时长
            try:
                audio_meta = MutagenFile(audio_path)
                segment_duration_sec = audio_meta.info.length
                total_duration_micro += int(segment_duration_sec * 1000000)
            except:
                total_duration_micro += 3000000  # 默认3秒
    
    total_duration_sec = total_duration_micro / 1000000
    logger.debug(f"总时长: {total_duration_sec:.2f}秒")
    
    # 修改草稿文件
    logger.debug("步骤 8/8: 生成草稿 JSON")
    draft_info_path = os.path.join(draft_folder, "draft_info.json")
    
    with open(draft_info_path, 'r', encoding='utf-8') as f:
        draft = json.load(f)
    
    # 更新基本信息
    draft['draft_name'] = draft_name
    draft['draft_root_path'] = draft_folder
    draft['id'] = str(uuid.uuid4()).upper()
    draft['duration'] = total_duration_micro
    
    now_micro = int(datetime.now().timestamp() * 1000000)
    draft['create_time'] = now_micro
    draft['update_time'] = now_micro
    
    # 16:9 画布
    if 'canvas_config' in draft:
        draft['canvas_config']['width'] = 1920
        draft['canvas_config']['height'] = 1080
        draft['canvas_config']['ratio'] = '16:9'
    
    # 清空材料
    draft['materials']['audios'] = []
    draft['materials']['videos'] = []
    
    # 添加多个音频材料（每个片段独立）
    logger.debug("添加音频材料...")
    audio_material_ids = []
    for i, (audio_path, _, duration_ms) in enumerate(copied_audio_segments, 1):
        # 获取精确时长
        try:
            audio_meta = MutagenFile(audio_path)
            duration_micro = int(audio_meta.info.length * 1000000)
        except:
            if duration_ms:
                duration_micro = duration_ms * 1000
            else:
                duration_micro = 3000000
        
        audio_id = str(uuid.uuid4()).upper()
        audio_material = {
            "app_id": 0,
            "category_id": "",
            "check_flag": 1,
            "duration": duration_micro,
            "id": audio_id,
            "name": os.path.basename(audio_path),
            "path": audio_path,
            "type": "extract_music",
            "wave_points": []
        }
        draft['materials']['audios'].append(audio_material)
        audio_material_ids.append((audio_id, duration_micro))
        logger.debug(f"音频片段 {i}: {duration_micro/1000000:.2f}秒")
    
    # 添加图片材料
    logger.debug("添加图片材料...")
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
    
    # 创建视频轨道（图片平均分配）
    logger.debug("创建视频轨道...")
    time_per_image = total_duration_micro // len(image_ids)
    video_segments = []
    
    for i, img_id in enumerate(image_ids):
        start_time = i * time_per_image
        duration = time_per_image
        
        if i == len(image_ids) - 1:
            duration = total_duration_micro - start_time
        
        segment = {
            "id": str(uuid.uuid4()).upper(),
            "material_id": img_id,
            "target_timerange": {"start": start_time, "duration": duration},
            "source_timerange": {"start": 0, "duration": duration},
            "visible": True,
            "clip": {
                "alpha": 1.0,
                "scale": {"x": 1.0, "y": 1.0}
            }
        }
        video_segments.append(segment)
    
    video_track = {
        "attribute": 0,
        "flag": 0,
        "id": str(uuid.uuid4()).upper(),
        "type": "video",
        "segments": video_segments
    }
    draft['tracks'].append(video_track)
    logger.debug(f"视频轨道: {len(video_segments)} 个片段")
    
    # 创建音频轨道（多个独立片段）
    logger.debug("创建音频轨道...")
    audio_segments_json = []
    current_time = 0
    
    for i, (audio_id, duration_micro) in enumerate(audio_material_ids):
        segment = {
            "id": str(uuid.uuid4()).upper(),
            "material_id": audio_id,
            "target_timerange": {"start": current_time, "duration": duration_micro},
            "source_timerange": {"start": 0, "duration": duration_micro},
            "volume": 1.0,
            "visible": True
        }
        audio_segments_json.append(segment)
        current_time += duration_micro
        logger.debug(f"音频轨道片段 {i+1}: {current_time/1000000:.2f}秒")
    
    audio_track = {
        "attribute": 0,
        "flag": 0,
        "id": str(uuid.uuid4()).upper(),
        "type": "audio",
        "segments": audio_segments_json
    }
    draft['tracks'].append(audio_track)
    logger.debug(f"音频轨道: {len(audio_segments_json)} 个片段")
    
    # 保存草稿
    logger.debug("保存草稿文件...")
    with open(draft_info_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(draft_folder, "draft_info.json.bak"), 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ 草稿创建完成！")
    logger.info(f"{'='*70}")
    logger.info(f"📝 草稿名称: {draft_name}")
    logger.info(f"📁 草稿路径: {draft_folder}")
    logger.info(f"⏱️  总时长: {total_duration_sec:.2f} 秒")
    logger.info(f"🎵 音频片段: {len(audio_material_ids)} 个（独立可调）")
    logger.info(f"🖼️  图片片段: {len(image_ids)} 个")
    logger.info(f"📝 日志文件: {logger.handlers[0].baseFilename}")
    
    return draft_folder


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    
    print("\n" + "="*70)
    print("🎬 CapCut 草稿自动生成器 - 增强版 v2.0")
    print("   ✨ 支持音频智能分段")
    print("   ✨ 详细日志记录")
    print("="*70)
    print(f"素材目录: {MATERIAL_BASE_FOLDER}")
    print(f"草稿目录: {CAPCUT_DRAFTS_FOLDER}")
    print(f"日志目录: {LOG_FOLDER}")
    
    if not PYDUB_AVAILABLE:
        print("\n⚠️  提示: pydub 未安装，音频分段功能将不可用")
        print("   安装命令: pip3 install pydub")
    
    # 获取可用文件夹
    folders = get_available_folders()
    
    if not folders:
        print("\n❌ 未找到可用的素材文件夹")
        return
    
    # 选择文件夹
    selected_folder = select_folder(folders)
    
    if not selected_folder:
        return
    
    # 设置日志
    logger = setup_logger(selected_folder)
    
    # 获取素材路径
    folder_path = os.path.join(MATERIAL_BASE_FOLDER, selected_folder)
    
    logger.info(f"\n✅ 已选择: {selected_folder}")
    logger.info(f"📁 路径: {folder_path}")
    logger.debug(f"完整路径: {folder_path}")
    
    # 查找媒体文件
    logger.debug("查找媒体文件...")
    audio_files, image_files = find_media_files(folder_path)
    
    if not audio_files:
        logger.error("该文件夹没有音频文件")
        print("\n❌ 该文件夹没有音频文件")
        print("支持的格式: mp3, wav, m4a, aac")
        return
    
    if not image_files:
        logger.error("该文件夹没有图片文件")
        print("\n❌ 该文件夹没有图片文件")
        print("支持的格式: png, jpg, jpeg")
        return
    
    logger.info(f"\n📦 找到素材:")
    logger.info(f"  🎵 音频: {len(audio_files)} 个")
    for i, audio in enumerate(audio_files[:3], 1):
        logger.info(f"     {i}. {os.path.basename(audio)}")
    if len(audio_files) > 3:
        logger.info(f"     ... 还有 {len(audio_files)-3} 个")
    
    logger.info(f"  🖼️  图片: {len(image_files)} 个")
    for i, img in enumerate(image_files[:3], 1):
        logger.info(f"     {i}. {os.path.basename(img)}")
    if len(image_files) > 3:
        logger.info(f"     ... 还有 {len(image_files)-3} 个")
    
    # 使用第一个音频
    audio_file = audio_files[0]
    logger.debug(f"使用音频文件: {audio_file}")
    
    # 确认创建
    print("\n" + "-"*70)
    confirm = input("确认创建草稿？(y/n): ").strip().lower()
    
    if confirm != 'y':
        logger.info("用户取消操作")
        print("❌ 已取消")
        return
    
    logger.info("用户确认，开始创建草稿")
    
    # 创建草稿
    try:
        draft_folder = create_capcut_draft(selected_folder, audio_file, image_files, logger)
        
        if draft_folder:
            print("\n" + "="*70)
            print("🎉 完成！")
            print("="*70)
            print("\n💡 下一步:")
            print("  1. 打开 CapCut 应用")
            print("  2. 找到新创建的草稿")
            print("  3. 在音频轨道上可以看到多个独立片段")
            print("  4. 每个片段可以单独调整、删除、移动")
            print("  5. 手动删除多余的片段或调整时长")
            print("  6. 完成后导出视频")
            
            logger.info("草稿创建流程完成")
            
            # 询问是否打开 CapCut
            print("\n" + "-"*70)
            open_app = input("是否现在打开 CapCut？(y/n): ").strip().lower()
            
            if open_app == 'y':
                logger.info("打开 CapCut 应用")
                print(f"\n🚀 正在打开 CapCut...")
                if platform.system() == "Darwin":
                    os.system("open -a CapCut")
                elif platform.system() == "Windows":
                    os.system("start CapCut")
                print("✅ CapCut 已打开")
            
            print("\n👋 感谢使用！")
            logger.info("程序正常结束")
            
    except Exception as e:
        logger.error(f"创建草稿失败: {e}", exc_info=True)
        print(f"\n❌ 创建草稿时发生错误: {e}")
        print(f"详细信息请查看日志文件")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 已退出")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

