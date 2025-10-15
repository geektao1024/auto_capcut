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
# 尝试导入 PIL（读取图片尺寸）
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

# 尝试导入 pydub（音频处理）
try:
    from pydub import AudioSegment
    from pydub.silence import detect_nonsilent
    PYDUB_AVAILABLE = True
except ImportError:
    PYDUB_AVAILABLE = False
    print("⚠️  pydub 未安装，音频分段功能将不可用")
    print("   安装命令: pip3 install pydub")

# Whisper字幕功能已移除，建议使用CapCut内置识别

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

# 音频调整参数
AUDIO_VOLUME_DB = 13.6  # 音量增益（dB），+13.6dB
AUDIO_SPEED = 1.08      # 播放速度，1.08倍速

# 画布配置
CANVAS_WIDTH = 1080     # 9:16 竖屏宽度
CANVAS_HEIGHT = 1920    # 9:16 竖屏高度
CANVAS_RATIO = "9:16"   # 画布比例

# 音效配置
INTRO_SOUND_FILE = "惊叹音效.WAV"  # 开头音效文件名
INTRO_SOUND_VOLUME = 1.0          # 音效音量（1.0 = 100%）

# 画面特效配置
ENABLE_SHAKE_EFFECT = True  # 是否启用震动特效
SHAKE_SPEED = 2.0           # 震动速度（0-10）
SHAKE_INTENSITY = 5.0       # 震动强度（0-10）

# 背景填充配置
ENABLE_CANVAS_BLUR = True   # 是否启用背景模糊填充
CANVAS_BLUR_AMOUNT = 0.375  # 模糊强度（0-1，0.375 = 37.5%）

# 字幕功能已移除 - 请使用CapCut内置"智能字幕"功能

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

def db_to_linear(db):
    """
    将 dB 值转换为线性增益
    
    Args:
        db: 分贝值（例如：13.6）
        
    Returns:
        线性增益值（例如：4.786）
    """
    import math
    return math.pow(10, db / 20)


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
    
    # 找到第一个有效的文件夹（有音频和图片）
    default_index = None
    for i, folder in enumerate(folders, 1):
        folder_path = os.path.join(MATERIAL_BASE_FOLDER, folder)
        
        # 统计文件数量
        audio_count = len(glob.glob(os.path.join(folder_path, "*.mp3"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.wav"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.m4a")))
        
        image_count = len(glob.glob(os.path.join(folder_path, "*.png"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.jpg"))) + \
                     len(glob.glob(os.path.join(folder_path, "*.jpeg")))
        
        is_valid = (audio_count > 0 and image_count > 0)
        status = "✅" if is_valid else "⚠️"
        
        # 记录第一个有效文件夹
        if is_valid and default_index is None:
            default_index = i
        
        # 标记默认选项
        default_marker = " ⭐" if i == default_index else ""
        print(f"{status} {i:2d}. {folder:30s}  [🎵 {audio_count} 音频, 🖼️  {image_count} 图片]{default_marker}")
    
    print("\n0. 退出")
    print("="*70)
    
    # 显示默认提示
    if default_index:
        default_text = f" (默认: {default_index})"
    else:
        default_text = ""
    
    while True:
        try:
            choice = input(f"\n请选择文件夹编号{default_text}: ").strip()
            
            # 直接回车使用默认值
            if choice == '' and default_index:
                print(f"✅ 使用默认选项: {default_index}. {folders[default_index - 1]}")
                return folders[default_index - 1]
            
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
# 字幕功能已移除 - 请使用CapCut内置"智能字幕"功能
# ============================================================================
# 
# 在CapCut中使用字幕：
# 1. 打开生成的草稿
# 2. 点击"文字" → "智能字幕"  
# 3. 选择语言并识别
# 4. CapCut会自动生成准确的字幕


# ============================================================================
# 音频智能分段（核心功能）
# ============================================================================

def split_audio_by_silence(audio_file, output_folder, logger, 
                          min_silence_len=300, silence_thresh=-35):
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
        
        # 🚀 优化：先加速音频，再检测静音（可以移除更多细微间隙）
        logger.debug(f"步骤1: 将音频加速到 {AUDIO_SPEED}x...")
        # 通过改变帧率实现变速（不改变音调）
        audio_sped_up = audio._spawn(audio.raw_data, overrides={
            "frame_rate": int(audio.frame_rate * AUDIO_SPEED)
        })
        # 重新设置为原始采样率（保持音调，实现变速）
        audio_sped_up = audio_sped_up.set_frame_rate(audio.frame_rate)
        sped_up_duration = len(audio_sped_up) / 1000
        logger.debug(f"加速后时长: {sped_up_duration:.2f}秒 (缩短了 {original_duration - sped_up_duration:.2f}秒)")
        
        # 检测非静音片段（在加速后的音频上检测，停顿更短，更容易移除）
        logger.debug("步骤2: 检测非静音片段（在加速后的音频上）...")
        nonsilent_ranges = detect_nonsilent(
            audio_sped_up,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh,
            seek_step=5  # 更精细的检测步长
        )
        
        logger.info(f"✅ 检测到 {len(nonsilent_ranges)} 个音频片段")
        
        if len(nonsilent_ranges) == 0:
            logger.warning("未检测到非静音片段，使用原音频")
            return [(audio_file, 0, None)]
        
        # 导出每个片段（使用加速后的音频）
        os.makedirs(output_folder, exist_ok=True)
        segments = []
        total_duration = 0
        
        for i, (start_ms, end_ms) in enumerate(nonsilent_ranges, 1):
            # 从加速后的音频中提取片段
            segment = audio_sped_up[start_ms:end_ms]
            duration_ms = end_ms - start_ms
            duration_sec = duration_ms / 1000
            
            # 保存片段
            segment_filename = f"audio_segment_{i:02d}.mp3"
            segment_path = os.path.join(output_folder, segment_filename)
            segment.export(segment_path, format="mp3", bitrate="192k")
            
            segments.append((segment_path, start_ms, duration_ms))
            total_duration += duration_sec
            
            logger.debug(f"片段 {i}: {start_ms/1000:.2f}s - {end_ms/1000:.2f}s (时长 {duration_sec:.2f}s)")
        
        removed_duration = original_duration - total_duration
        removed_percent = (removed_duration / original_duration) * 100
        
        logger.info(f"\n📊 分段统计:")
        logger.info(f"  原音频时长: {original_duration:.2f}秒")
        logger.info(f"  加速后时长: {sped_up_duration:.2f}秒 ({AUDIO_SPEED}x)")
        logger.info(f"  消除静音后: {total_duration:.2f}秒")
        logger.info(f"  总共移除: {removed_duration:.2f}秒 ({removed_percent:.1f}%)")
        logger.info(f"  音频片段数: {len(segments)} 个")
        logger.info(f"  ⚡ 优化策略: 先加速 → 再消除静音 = 更彻底清理间隙")
        
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
        use_split = input("启用分段？(y/n，默认: y): ").strip().lower()
        
        # 直接回车默认为 y
        if use_split == '':
            use_split = 'y'
            print("✅ 使用默认选项: y")
        
        if use_split != 'n':
            # 选择模式（优化后更激进）
            print("\n分段模式（已优化：先加速 → 再消除静音）:")
            print("  1. 保守 (>400ms, <-40dB) - 保留明显停顿")
            print("  2. 标准 (>300ms, <-35dB) - 移除大部分间隙")
            print("  3. 激进 (>200ms, <-30dB) - 最大化移除静音 ⭐ 推荐")
            print("  4. 极限 (>150ms, <-25dB) - 删除所有细微间隙")
            
            mode = input("选择模式 (1-4，默认3): ").strip() or "3"
            
            params = {
                "1": (400, -40),
                "2": (300, -35),
                "3": (200, -30),  # 默认推荐
                "4": (150, -25)
            }
            
            min_silence, thresh = params.get(mode, (200, -30))
            logger.info(f"使用模式: {mode} (min_silence={min_silence}ms, thresh={thresh}dB)")
            logger.info(f"⚡ 优化策略: 先加速到 {AUDIO_SPEED}x → 再检测静音 → 更彻底清理")
            
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
    
    # 9:16 竖屏画布（手机视频）
    if 'canvas_config' in draft:
        draft['canvas_config']['width'] = CANVAS_WIDTH
        draft['canvas_config']['height'] = CANVAS_HEIGHT
        draft['canvas_config']['ratio'] = CANVAS_RATIO
        logger.debug(f"画布设置: {CANVAS_WIDTH}x{CANVAS_HEIGHT} ({CANVAS_RATIO})")
    
    # 清空材料
    draft['materials']['audios'] = []
    draft['materials']['videos'] = []
    
    # 添加震动画面特效（如果启用）
    shake_effect_id = None
    if ENABLE_SHAKE_EFFECT:
        logger.info(f"\n🎨 添加震动画面特效...")
        shake_effect_id = str(uuid.uuid4()).upper()
        
        # 确保 video_effects 列表存在（真实草稿中特效在这里，不是material_animations）
        if 'video_effects' not in draft['materials']:
            draft['materials']['video_effects'] = []
        
        # 震动特效（UI范围0-100，公式：JSON = UI÷100）
        shake_effect = {
            "adjust_params": [
                {
                    "default_value": 0.5,
                    "name": "effects_adjust_intensity",
                    "value": SHAKE_INTENSITY / 100.0  # UI值5 → 0.05
                },
                {
                    "default_value": 0.33,
                    "name": "effects_adjust_speed",
                    "value": SHAKE_SPEED / 100.0  # UI值2 → 0.02
                }
            ],
            "algorithm_artifact_path": "",
            "apply_target_type": 2,
            "apply_time_range": None,
            "bind_segment_id": "",
            "category_id": "100000",
            "category_name": "画面特效",
            "common_keyframes": [],
            "covering_relation_change": 0,
            "disable_effect_faces": [],
            "effect_id": "7399470393884527877",
            "effect_mask": [],
            "enable_mask": True,
            "formula_id": "",
            "id": shake_effect_id,
            "item_effect_type": 0,
            "name": "震动",
            "path": "/Users/mac/Library/Containers/com.lemon.lvoverseas/Data/Movies/CapCut/User Data/Cache/effect/7399470393884527877/d11532bfbfbd6f9af59026c2c42f2570",
            "platform": "all",
            "render_index": 0,
            "request_id": str(uuid.uuid4()).upper(),
            "resource_id": "7399470393884527877",
            "source_platform": 1,
            "sub_type": 0,
            "time_range": None,
            "track_render_index": 0,
            "transparent_params": "",
            "type": "video_effect",
            "value": 1.0,
            "version": ""
        }
        
        draft['materials']['video_effects'].append(shake_effect)
        logger.info(f"✅ 震动特效已添加到 video_effects（UI强度={SHAKE_INTENSITY:.0f}, 速度={SHAKE_SPEED:.0f} → JSON值={SHAKE_INTENSITY/100:.2f}, {SHAKE_SPEED/100:.2f}）")
        logger.debug(f"特效ID: {shake_effect_id}, 公式: JSON = UI ÷ 100")
    
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
    
    # 添加开头音效（如果存在）
    intro_sound_id = None
    intro_sound_duration = 0
    intro_sound_path = os.path.join(os.path.dirname(__file__), INTRO_SOUND_FILE)
    
    if os.path.exists(intro_sound_path):
        logger.info(f"\n🔔 检测到开头音效: {INTRO_SOUND_FILE}")
        try:
            # 获取音效时长
            sound_meta = MutagenFile(intro_sound_path)
            intro_sound_duration = int(sound_meta.info.length * 1000000)
            
            # 复制音效到 media 文件夹
            sound_dest = os.path.join(media_folder, INTRO_SOUND_FILE)
            shutil.copy2(intro_sound_path, sound_dest)
            
            # 添加音效材料
            intro_sound_id = str(uuid.uuid4()).upper()
            sound_material = {
                "app_id": 0,
                "category_id": "",
                "check_flag": 1,
                "duration": intro_sound_duration,
                "id": intro_sound_id,
                "name": INTRO_SOUND_FILE,
                "path": sound_dest,
                "type": "extract_music",
                "wave_points": []
            }
            draft['materials']['audios'].append(sound_material)
            
            logger.info(f"✅ 添加开头音效: {INTRO_SOUND_FILE} (时长 {intro_sound_duration/1000000:.2f}秒)")
            logger.debug(f"音效路径: {sound_dest}")
        except Exception as e:
            logger.warning(f"⚠️  添加开头音效失败: {e}")
            intro_sound_id = None
    else:
        logger.debug(f"未找到开头音效文件: {intro_sound_path}")
    
    # 添加图片材料
    logger.debug("添加图片材料...")
    image_ids = []
    for img_path in copied_images:
        # 读取图片实际尺寸
        img_width, img_height = 1920, 1080  # 默认值
        if PIL_AVAILABLE:
            try:
                with Image.open(img_path) as img:
                    img_width, img_height = img.size
                    logger.debug(f"图片尺寸: {img_width}x{img_height}")
            except Exception as e:
                logger.warning(f"无法读取图片尺寸: {e}")
        
        img_id = str(uuid.uuid4()).upper()
        local_material_id = str(uuid.uuid4()).upper()
        
        image_material = {
            "aigc_type": "none",
            "category_id": "",
            "category_name": "local",
            "check_flag": 63487,
            "crop": {
                "lower_left_x": 0.0, "lower_left_y": 1.0,
                "lower_right_x": 1.0, "lower_right_y": 1.0,
                "upper_left_x": 0.0, "upper_left_y": 0.0,
                "upper_right_x": 1.0, "upper_right_y": 0.0
            },
            "duration": 10800000000,
            "extra_type_option": 0,
            "file_Path": img_path,
            "has_audio": False,
            "height": img_height,
            "width": img_width,
            "id": img_id,
            "intensifies_path": "",
            "is_ai_generate": False,
            "is_unified_beauty_mode": False,
            "local_material_id": local_material_id,
            "material_id": "",
            "material_name": os.path.basename(img_path),
            "material_url": "",
            "matting": {
                "flag": 0,
                "has_use_quick_brush": False,
                "has_use_quick_eraser": False,
                "interactiveTime": [],
                "path": "",
                "strokes": []
            },
            "media_path": "",
            "object_locked": None,
            "origin_material_id": "",
            "path": img_path,
            "picture_from": "none",
            "picture_set_category_id": "",
            "picture_set_category_name": "",
            "request_id": "",
            "reverse_intensifies_path": "",
            "reverse_path": "",
            "source_platform": 0,
            "stable": False,
            "team_id": "",
            "type": "photo",
            "video_algorithm": {
                "algorithms": [],
                "deflicker": None,
                "motion_blur_config": None,
                "noise_reduction": None,
                "path": "",
                "quality_enhance": None,
                "time_range": None
            }
        }
        draft['materials']['videos'].append(image_material)
        image_ids.append((img_id, local_material_id))
    
    # 添加背景模糊填充材料（如果启用）
    canvas_blur_ids = []
    if ENABLE_CANVAS_BLUR:
        logger.info(f"\n🖼️  添加背景模糊填充...")
        
        # 确保 canvases 列表存在
        if 'canvases' not in draft['materials']:
            draft['materials']['canvases'] = []
        
        # 为每个图片创建一个canvas_blur
        for i, (img_id, _) in enumerate(image_ids):
            canvas_blur_id = str(uuid.uuid4()).upper()
            canvas_blur = {
                "album_image": "",
                "blur": CANVAS_BLUR_AMOUNT,
                "color": "",
                "id": canvas_blur_id,
                "image": "",
                "image_id": "",
                "image_name": "",
                "source_platform": 0,
                "team_id": "",
                "type": "canvas_blur"
            }
            draft['materials']['canvases'].append(canvas_blur)
            canvas_blur_ids.append(canvas_blur_id)
            logger.debug(f"为图片 {i+1} 创建背景模糊: blur={CANVAS_BLUR_AMOUNT}")
        
        logger.info(f"✅ 创建了 {len(canvas_blur_ids)} 个背景模糊填充（模糊度: {CANVAS_BLUR_AMOUNT*100:.1f}%）")
    
    # 添加必要的默认材料（为每个片段创建独立的材料）
    logger.info(f"\n🔧 创建默认材料（speeds, colors等）...")
    default_materials_list = []
    
    # 为每个图片片段创建一套默认材料
    for i in range(len(image_ids)):
        # 1. Speed (速度控制)
        speed_id = str(uuid.uuid4()).upper()
        if 'speeds' not in draft['materials']:
            draft['materials']['speeds'] = []
        draft['materials']['speeds'].append({
            "curve_speed": None,
            "id": speed_id,
            "mode": 0,
            "speed": 1.0,
            "type": "speed"
        })
        
        # 2. Placeholder Info (占位符信息)
        placeholder_id = str(uuid.uuid4()).upper()
        if 'placeholder_infos' not in draft['materials']:
            draft['materials']['placeholder_infos'] = []
        draft['materials']['placeholder_infos'].append({
            "error_path": "",
            "error_text": "",
            "id": placeholder_id,
            "meta_type": "none",
            "res_path": "",
            "res_text": "",
            "type": "placeholder_info"
        })
        
        # 3. Sound Channel Mapping (音频通道映射)
        sound_channel_id = str(uuid.uuid4()).upper()
        if 'sound_channel_mappings' not in draft['materials']:
            draft['materials']['sound_channel_mappings'] = []
        draft['materials']['sound_channel_mappings'].append({
            "audio_channel_mapping": 0,
            "id": sound_channel_id,
            "is_config_open": False,
            "type": ""
        })
        
        # 4. Material Color (材料颜色)
        color_id = str(uuid.uuid4()).upper()
        if 'material_colors' not in draft['materials']:
            draft['materials']['material_colors'] = []
        draft['materials']['material_colors'].append({
            "gradient_angle": 90.0,
            "gradient_colors": [],
            "gradient_percents": [],
            "height": 0.0,
            "id": color_id,
            "is_color_clip": False,
            "is_gradient": False,
            "solid_color": "",
            "width": 0.0
        })
        
        # 5. Loudness (响度)
        loudness_id = str(uuid.uuid4()).upper()
        if 'loudnesses' not in draft['materials']:
            draft['materials']['loudnesses'] = []
        draft['materials']['loudnesses'].append({
            "enable": False,
            "file_id": "",
            "id": loudness_id,
            "loudness_param": None,
            "target_loudness": 0.0,
            "time_range": None
        })
        
        # 6. Vocal Separation (人声分离)
        vocal_id = str(uuid.uuid4()).upper()
        if 'vocal_separations' not in draft['materials']:
            draft['materials']['vocal_separations'] = []
        draft['materials']['vocal_separations'].append({
            "choice": 0,
            "enter_from": "",
            "final_algorithm": "",
            "id": vocal_id,
            "production_path": "",
            "removed_sounds": [],
            "time_range": None,
            "type": "vocal_separation"
        })
        
        # 保存这一套材料的ID（顺序很重要）
        default_materials_list.append({
            "speed_id": speed_id,
            "placeholder_id": placeholder_id,
            "sound_channel_id": sound_channel_id,
            "color_id": color_id,
            "loudness_id": loudness_id,
            "vocal_id": vocal_id
        })
    
    logger.info(f"✅ 创建了 {len(default_materials_list)} 套默认材料")
    
    # 添加本地素材列表（显示在左侧素材库）
    logger.debug("创建本地素材列表...")
    local_materials = []
    
    # 添加所有图片到本地素材
    for img_id, local_material_id in image_ids:
        # 找到对应的素材信息
        img_material = next((m for m in draft['materials']['videos'] if m['id'] == img_id), None)
        if img_material:
            local_material = {
                "create_time": now_micro,
                "duration": img_material['duration'],
                "extra_info": "",
                "file_Path": img_material['path'],
                "file_name": img_material['material_name'],
                "file_size": os.path.getsize(img_material['path']) if os.path.exists(img_material['path']) else 0,
                "height": img_material['height'],
                "width": img_material['width'],
                "id": local_material_id,
                "import_time": now_micro,
                "import_time_ms": now_micro,
                "item_source": 1,
                "md5": "",
                "metetype": "photo",
                "roughcut_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "sub_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "type": 0
            }
            local_materials.append(local_material)
    
    # 添加所有音频到本地素材
    for audio_id, duration_micro in audio_material_ids:
        audio_material = next((m for m in draft['materials']['audios'] if m['id'] == audio_id), None)
        if audio_material:
            local_material_id = str(uuid.uuid4()).upper()
            local_material = {
                "create_time": now_micro,
                "duration": duration_micro,
                "extra_info": "",
                "file_Path": audio_material['path'],
                "file_name": audio_material['name'],
                "file_size": os.path.getsize(audio_material['path']) if os.path.exists(audio_material['path']) else 0,
                "height": 0,
                "width": 0,
                "id": local_material_id,
                "import_time": now_micro,
                "import_time_ms": now_micro,
                "item_source": 1,
                "md5": "",
                "metetype": "music",
                "roughcut_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "sub_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "type": 1
            }
            local_materials.append(local_material)
            # 更新音频材料的 local_material_id
            audio_material['local_material_id'] = local_material_id
    
    # 添加开头音效到本地素材（如果存在）
    if intro_sound_id:
        sound_material = next((m for m in draft['materials']['audios'] if m['id'] == intro_sound_id), None)
        if sound_material:
            local_material_id = str(uuid.uuid4()).upper()
            local_material = {
                "create_time": now_micro,
                "duration": intro_sound_duration,
                "extra_info": "",
                "file_Path": sound_material['path'],
                "file_name": sound_material['name'],
                "file_size": os.path.getsize(sound_material['path']) if os.path.exists(sound_material['path']) else 0,
                "height": 0,
                "width": 0,
                "id": local_material_id,
                "import_time": now_micro,
                "import_time_ms": now_micro,
                "item_source": 1,
                "md5": "",
                "metetype": "music",
                "roughcut_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "sub_time_range": {
                    "duration": -1,
                    "start": -1
                },
                "type": 1
            }
            local_materials.append(local_material)
            sound_material['local_material_id'] = local_material_id
            logger.debug(f"添加音效到本地素材: {INTRO_SOUND_FILE}")
    
    # 将本地素材列表添加到草稿
    if 'materials' not in draft:
        draft['materials'] = {}
    draft['materials']['local_materials'] = local_materials
    logger.debug(f"本地素材列表: {len(local_materials)} 个（{len(image_ids)} 图片 + {len(audio_material_ids)} 音频）")
    
    # 清空轨道
    draft['tracks'] = []
    
    # 创建视频轨道（智能分配图片到音频）
    logger.debug("创建视频轨道（智能图片分配）...")
    logger.info(f"\n🎨 智能图片分配策略:")
    logger.info(f"  • 短音频 (<1.5秒) → 配 1 张图片，跳过下一张")
    logger.info(f"  • 长音频 (≥1.5秒) → 配 2 张图片，平均分配")
    
    video_segments = []
    current_time = 0
    image_index = 0  # 当前使用的图片索引
    
    # 遍历每个音频段，智能分配图片
    canvas_blur_index = 0  # 跟踪当前使用的canvas_blur索引
    default_material_index = 0  # 跟踪当前使用的默认材料索引
    for audio_idx, (audio_id, duration_micro) in enumerate(audio_material_ids):
        audio_duration_sec = duration_micro / 1000000
        
        logger.debug(f"\n音频段 {audio_idx + 1}: 时长 {audio_duration_sec:.2f}秒")
        
        # 判断音频时长
        if audio_duration_sec < 1.5:
            # 短音频：只配一张图片，跳过下一张图片
            if image_index < len(image_ids):
                img_id, local_material_id = image_ids[image_index]
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
                    "intensifies_audio": False,
                    "is_placeholder": False,
                    "is_tone_modify": False,
                    "keyframe_refs": [],
                    "last_nonzero_volume": 1.0,
                    "material_id": img_id,
                    "render_index": len(video_segments) + 1,
                    "responsive_layout": {
                        "enable": False,
                        "horizontal_pos_layout": 0,
                        "size_layout": 0,
                        "target_follow": "",
                        "vertical_pos_layout": 0
                    },
                    "reverse": False,
                    "source_timerange": {"start": 0, "duration": duration_micro},
                    "speed": 1.0,
                    "target_timerange": {"start": current_time, "duration": duration_micro},
                    "template_id": "",
                    "template_scene": "default",
                    "track_attribute": 0,
                    "track_render_index": 1,
                    "uniform_scale": {"on": True, "value": 1.0},
                    "visible": True,
                    "volume": 1.0
                }
                # 按顺序添加所有材料到extra_material_refs（固定8个，顺序很重要）
                if default_material_index < len(default_materials_list):
                    mats = default_materials_list[default_material_index]
                    # 1. Speed
                    segment["extra_material_refs"].append(mats["speed_id"])
                    # 2. Placeholder
                    segment["extra_material_refs"].append(mats["placeholder_id"])
                    # 3. Canvas (如果启用背景模糊)
                    if ENABLE_CANVAS_BLUR and canvas_blur_index < len(canvas_blur_ids):
                        segment["extra_material_refs"].append(canvas_blur_ids[canvas_blur_index])
                        canvas_blur_index += 1
                    # 4. Material Animation (空，保留位置)
                    # 5. Sound Channel
                    segment["extra_material_refs"].append(mats["sound_channel_id"])
                    # 6. Color
                    segment["extra_material_refs"].append(mats["color_id"])
                    # 7. Loudness
                    segment["extra_material_refs"].append(mats["loudness_id"])
                    # 8. Vocal Separation
                    segment["extra_material_refs"].append(mats["vocal_id"])
                    default_material_index += 1
                video_segments.append(segment)
                logger.debug(f"  短音频配1张图片: 图片{image_index + 1} (时长{audio_duration_sec:.2f}秒)")
                
                # 跳过下一张图片（增加视觉节奏感）
                if image_index + 1 < len(image_ids):
                    logger.debug(f"  ⏭️  跳过图片{image_index + 2}（优化视觉节奏）")
                image_index += 2
            else:
                logger.warning(f"  警告: 音频段 {audio_idx + 1} 没有足够的图片")
        
        else:
            # 长音频：配两张图片，平均分配时间
            if image_index + 1 < len(image_ids):
                half_duration = duration_micro // 2
                remaining_duration = duration_micro - half_duration
                
                # 第一张图片（前半段）
                first_img_id, first_local_id = image_ids[image_index]
                first_segment = {
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
                    "intensifies_audio": False,
                    "is_placeholder": False,
                    "is_tone_modify": False,
                    "keyframe_refs": [],
                    "last_nonzero_volume": 1.0,
                    "material_id": first_img_id,
                    "render_index": len(video_segments) + 1,
                    "responsive_layout": {
                        "enable": False,
                        "horizontal_pos_layout": 0,
                        "size_layout": 0,
                        "target_follow": "",
                        "vertical_pos_layout": 0
                    },
                    "reverse": False,
                    "source_timerange": {"start": 0, "duration": half_duration},
                    "speed": 1.0,
                    "target_timerange": {"start": current_time, "duration": half_duration},
                    "template_id": "",
                    "template_scene": "default",
                    "track_attribute": 0,
                    "track_render_index": 1,
                    "uniform_scale": {"on": True, "value": 1.0},
                    "visible": True,
                    "volume": 1.0
                }
                # 按顺序添加所有材料到extra_material_refs（第一张图片，固定8个）
                if default_material_index < len(default_materials_list):
                    mats = default_materials_list[default_material_index]
                    first_segment["extra_material_refs"].append(mats["speed_id"])
                    first_segment["extra_material_refs"].append(mats["placeholder_id"])
                    if ENABLE_CANVAS_BLUR and canvas_blur_index < len(canvas_blur_ids):
                        first_segment["extra_material_refs"].append(canvas_blur_ids[canvas_blur_index])
                        canvas_blur_index += 1
                    # Material Animation (空，保留位置)
                    first_segment["extra_material_refs"].append(mats["sound_channel_id"])
                    first_segment["extra_material_refs"].append(mats["color_id"])
                    first_segment["extra_material_refs"].append(mats["loudness_id"])
                    first_segment["extra_material_refs"].append(mats["vocal_id"])
                    default_material_index += 1
                
                # 第二张图片（后半段）
                second_img_id, second_local_id = image_ids[image_index + 1]
                second_segment = {
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
                    "intensifies_audio": False,
                    "is_placeholder": False,
                    "is_tone_modify": False,
                    "keyframe_refs": [],
                    "last_nonzero_volume": 1.0,
                    "material_id": second_img_id,
                    "render_index": len(video_segments) + 2,
                    "responsive_layout": {
                        "enable": False,
                        "horizontal_pos_layout": 0,
                        "size_layout": 0,
                        "target_follow": "",
                        "vertical_pos_layout": 0
                    },
                    "reverse": False,
                    "source_timerange": {"start": 0, "duration": remaining_duration},
                    "speed": 1.0,
                    "target_timerange": {"start": current_time + half_duration, "duration": remaining_duration},
                    "template_id": "",
                    "template_scene": "default",
                    "track_attribute": 0,
                    "track_render_index": 1,
                    "uniform_scale": {"on": True, "value": 1.0},
                    "visible": True,
                    "volume": 1.0
                }
                # 按顺序添加所有材料到extra_material_refs（第二张图片，固定8个）
                if default_material_index < len(default_materials_list):
                    mats = default_materials_list[default_material_index]
                    second_segment["extra_material_refs"].append(mats["speed_id"])
                    second_segment["extra_material_refs"].append(mats["placeholder_id"])
                    if ENABLE_CANVAS_BLUR and canvas_blur_index < len(canvas_blur_ids):
                        second_segment["extra_material_refs"].append(canvas_blur_ids[canvas_blur_index])
                        canvas_blur_index += 1
                    # Material Animation (空，保留位置)
                    second_segment["extra_material_refs"].append(mats["sound_channel_id"])
                    second_segment["extra_material_refs"].append(mats["color_id"])
                    second_segment["extra_material_refs"].append(mats["loudness_id"])
                    second_segment["extra_material_refs"].append(mats["vocal_id"])
                    default_material_index += 1
                
                video_segments.append(first_segment)
                video_segments.append(second_segment)
                
                logger.debug(f"  长音频配2张图片: 图片{image_index + 1}({half_duration/1000000:.2f}s) + 图片{image_index + 2}({remaining_duration/1000000:.2f}s)")
                image_index += 2
            
            elif image_index < len(image_ids):
                # 只剩一张图片了，用完整时长
                img_id, local_material_id = image_ids[image_index]
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
                    "intensifies_audio": False,
                    "is_placeholder": False,
                    "is_tone_modify": False,
                    "keyframe_refs": [],
                    "last_nonzero_volume": 1.0,
                    "material_id": img_id,
                    "render_index": len(video_segments) + 1,
                    "responsive_layout": {
                        "enable": False,
                        "horizontal_pos_layout": 0,
                        "size_layout": 0,
                        "target_follow": "",
                        "vertical_pos_layout": 0
                    },
                    "reverse": False,
                    "source_timerange": {"start": 0, "duration": duration_micro},
                    "speed": 1.0,
                    "target_timerange": {"start": current_time, "duration": duration_micro},
                    "template_id": "",
                    "template_scene": "default",
                    "track_attribute": 0,
                    "track_render_index": 1,
                    "uniform_scale": {"on": True, "value": 1.0},
                    "visible": True,
                    "volume": 1.0
                }
                # 按顺序添加所有材料到extra_material_refs（剩余一张图片，固定8个）
                if default_material_index < len(default_materials_list):
                    mats = default_materials_list[default_material_index]
                    segment["extra_material_refs"].append(mats["speed_id"])
                    segment["extra_material_refs"].append(mats["placeholder_id"])
                    if ENABLE_CANVAS_BLUR and canvas_blur_index < len(canvas_blur_ids):
                        segment["extra_material_refs"].append(canvas_blur_ids[canvas_blur_index])
                        canvas_blur_index += 1
                    # Material Animation (空，保留位置)
                    segment["extra_material_refs"].append(mats["sound_channel_id"])
                    segment["extra_material_refs"].append(mats["color_id"])
                    segment["extra_material_refs"].append(mats["loudness_id"])
                    segment["extra_material_refs"].append(mats["vocal_id"])
                    default_material_index += 1
                video_segments.append(segment)
                logger.debug(f"  长音频配1张图片: 图片{image_index + 1}（剩余最后一张）")
                image_index += 1
            else:
                logger.warning(f"  警告: 音频段 {audio_idx + 1} 没有足够的图片")
        
        current_time += duration_micro
    
    # 统计图片使用情况
    used_images = len(video_segments)
    total_images = len(image_ids)
    unused_images = total_images - image_index
    
    logger.info(f"\n📊 图片分配统计:")
    logger.info(f"  总图片数: {total_images}")
    logger.info(f"  已使用: {used_images} 个视频片段")
    logger.info(f"  实际用图: {image_index} 张")
    if unused_images > 0:
        logger.info(f"  未使用: {unused_images} 张（可添加更多音频或减少图片）")
    logger.info(f"  跳过图片: {image_index - used_images} 张（短音频优化）")
    
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
    
    # 计算音量（dB 转线性）
    volume_linear = db_to_linear(AUDIO_VOLUME_DB)
    logger.info(f"🔊 音频增益: +{AUDIO_VOLUME_DB}dB (线性值: {volume_linear:.2f})")
    logger.info(f"⚡ 音频已预先加速到 {AUDIO_SPEED}x（无需在 CapCut 中再次调速）")
    
    audio_segments_json = []
    current_time = 0
    
    for i, (audio_id, duration_micro) in enumerate(audio_material_ids):
        # 音频已经在导出时加速，这里直接使用实际时长
        segment = {
            "id": str(uuid.uuid4()).upper(),
            "material_id": audio_id,
            "target_timerange": {"start": current_time, "duration": duration_micro},
            "source_timerange": {"start": 0, "duration": duration_micro},
            "volume": volume_linear,
            "visible": True
        }
        audio_segments_json.append(segment)
        current_time += duration_micro
        logger.debug(f"音频轨道片段 {i+1}: {duration_micro/1000000:.2f}s (已包含 {AUDIO_SPEED}x 加速)")
    
    audio_track = {
        "attribute": 0,
        "flag": 0,
        "id": str(uuid.uuid4()).upper(),
        "type": "audio",
        "segments": audio_segments_json
    }
    draft['tracks'].append(audio_track)
    logger.debug(f"主音频轨道: {len(audio_segments_json)} 个片段")
    
    # ============================================================================
    # 字幕功能已移除 - 请在CapCut中使用"智能字幕"功能
    # ============================================================================
    logger.info(f"\n📝 字幕提示: 在CapCut中点击「文字」→「智能字幕」自动识别")
    
    # 创建音效轨道（如果有开头音效）
    if intro_sound_id:
        logger.debug("创建音效轨道...")
        
        sound_segment = {
            "id": str(uuid.uuid4()).upper(),
            "material_id": intro_sound_id,
            "target_timerange": {"start": 0, "duration": intro_sound_duration},
            "source_timerange": {"start": 0, "duration": intro_sound_duration},
            "volume": INTRO_SOUND_VOLUME,
            "visible": True
        }
        
        sound_track = {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "type": "audio",
            "segments": [sound_segment]
        }
        draft['tracks'].append(sound_track)
        
        logger.info(f"🔔 创建音效轨道: 开头位置 (0-{intro_sound_duration/1000000:.2f}秒)")
        logger.debug(f"音效音量: {INTRO_SOUND_VOLUME * 100:.0f}%")
    
    # 创建特效轨道（如果启用震动特效）
    if shake_effect_id:
        logger.info(f"\n🎬 创建特效轨道: 震动特效（覆盖整个视频）")
        
        effect_segment = {
            "caption_info": None,
            "cartoon": False,
            "clip": None,
            "color_correct_alg_result": "",
            "common_keyframes": [],
            "desc": "",
            "digital_human_template_group_id": "",
            "enable_adjust": False,
            "enable_adjust_mask": False,
            "enable_color_correct_adjust": False,
            "enable_color_curves": True,
            "enable_color_match_adjust": False,
            "enable_color_wheels": True,
            "enable_hsl": False,
            "enable_hsl_curves": True,
            "enable_lut": False,
            "enable_smart_color_adjust": False,
            "enable_video_mask": True,
            "extra_material_refs": [],
            "group_id": "",
            "hdr_settings": None,
            "id": str(uuid.uuid4()).upper(),
            "intensifies_audio": False,
            "is_loop": False,
            "is_placeholder": False,
            "is_tone_modify": False,
            "keyframe_refs": [],
            "last_nonzero_volume": 1.0,
            "lyric_keyframes": None,
            "material_id": shake_effect_id,
            "raw_segment_id": "",
            "render_index": 11000,
            "render_timerange": {"duration": 0, "start": 0},
            "responsive_layout": {
                "enable": False,
                "horizontal_pos_layout": 0,
                "size_layout": 0,
                "target_follow": "",
                "vertical_pos_layout": 0
            },
            "reverse": False,
            "source": "segmentsourcenormal",
            "source_timerange": None,
            "speed": 1.0,
            "state": 0,
            "target_timerange": {"duration": total_duration_micro, "start": 0},
            "template_id": "",
            "template_scene": "default",
            "track_attribute": 0,
            "track_render_index": 2,
            "uniform_scale": None,
            "visible": True,
            "volume": 1.0
        }
        
        effect_track = {
            "attribute": 0,
            "flag": 0,
            "id": str(uuid.uuid4()).upper(),
            "is_default_name": True,
            "name": "",
            "type": "effect",
            "segments": [effect_segment]
        }
        
        draft['tracks'].append(effect_track)
        logger.info(f"✅ 特效轨道已创建（震动覆盖整个视频：{total_duration_sec:.2f}秒）")
    
    # 字幕功能已移除
    
    # 保存草稿
    logger.debug("保存草稿文件...")
    with open(draft_info_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    with open(os.path.join(draft_folder, "draft_info.json.bak"), 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False, indent=2)
    
    # 音频已经在导出时加速，这里的 total_duration_sec 就是最终时长
    logger.info(f"\n{'='*70}")
    logger.info(f"✅ 草稿创建完成！")
    logger.info(f"{'='*70}")
    logger.info(f"📝 草稿名称: {draft_name}")
    logger.info(f"📁 草稿路径: {draft_folder}")
    logger.info(f"📱 画布比例: {CANVAS_WIDTH}x{CANVAS_HEIGHT} ({CANVAS_RATIO} 竖屏)")
    logger.info(f"⏱️  视频总时长: {total_duration_sec:.2f} 秒")
    logger.info(f"⚡ 音频加速: {AUDIO_SPEED}x (已预先处理)")
    logger.info(f"🔊 音量增益: +{AUDIO_VOLUME_DB}dB")
    logger.info(f"🎵 音频片段: {len(audio_material_ids)} 个（独立可调）")
    if intro_sound_id:
        logger.info(f"🔔 开头音效: {INTRO_SOUND_FILE} ({intro_sound_duration/1000000:.2f}秒)")
    logger.info(f"🖼️  图片片段: {len(video_segments)} 个（智能分配）")
    if shake_effect_id:
        logger.info(f"🎨 画面特效: 震动 (整个片段持续)")
    if ENABLE_CANVAS_BLUR:
        logger.info(f"🖼️  背景模糊: 已启用 (模糊度={CANVAS_BLUR_AMOUNT*100:.1f}%)")
    logger.info(f"📝 字幕功能: 请在CapCut中使用「智能字幕」")
    logger.info(f"📦 素材库: {len(local_materials)} 个素材（显示在左侧）")
    logger.info(f"📝 日志文件: {logger.handlers[0].baseFilename}")
    
    return draft_folder


# ============================================================================
# 主程序
# ============================================================================

def main():
    """主程序入口"""
    
    print("\n" + "="*70)
    print("🎬 CapCut 草稿自动生成器 - 增强版 v3.2.0")
    print("   ✨ 音频智能分段（优化算法）")
    print("   ✨ 智能图片分配（对齐音频）")
    print(f"   ✨ 音频增益: +{AUDIO_VOLUME_DB}dB | 速度: {AUDIO_SPEED}x")
    print(f"   📱 画布比例: {CANVAS_RATIO} (竖屏)")
    if ENABLE_SHAKE_EFFECT:
        print(f"   🎨 画面特效: 震动（强度{SHAKE_INTENSITY:.0f}/速度{SHAKE_SPEED:.0f}）")
    if ENABLE_CANVAS_BLUR:
        print(f"   🖼️  背景模糊: {CANVAS_BLUR_AMOUNT*100:.1f}% 填充")
    print(f"   📝 字幕功能: 请在CapCut中使用「智能字幕」")
    print("   ⚡ 一键启动: 所有选项支持默认值（直接回车）")
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
    confirm = input("确认创建草稿？(y/n，默认: y): ").strip().lower()
    
    # 直接回车默认为 y
    if confirm == '':
        confirm = 'y'
        print("✅ 使用默认选项: y")
    
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
            open_app = input("是否现在打开 CapCut？(y/n，默认: y): ").strip().lower()
            
            # 直接回车默认为 y
            if open_app == '':
                open_app = 'y'
                print("✅ 使用默认选项: y")
            
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

