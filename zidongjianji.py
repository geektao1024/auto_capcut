#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import uuid
import shutil
import glob
import re
import subprocess
import random
from typing import List, Dict
from collections import defaultdict
from mutagen import File as MutagenFile

def generate_uuid() -> str:
    """生成UUID"""
    return str(uuid.uuid4()).upper()

def natural_sort_key(filename: str) -> tuple:
    """
    自然排序键函数，确保1-1, 1-2, 1-3...而不是1-1, 1-10, 1-11...
    """
    # 提取文件名中的数字部分
    parts = re.findall(r'(\d+)', filename)
    return tuple(int(part) for part in parts)

def get_audio_duration_accurate(audio_file: str) -> int:
    """
    获取音频文件的准确时长（微秒）
    使用mutagen库读取音频元数据
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
        print(f"⚠️  读取音频时长出错 {os.path.basename(audio_file)}: {e}")
        return 3000000  # 默认3秒

def get_story_groups(image_folder: str, audio_folder: str) -> Dict[str, Dict[str, List[str]]]:
    """
    根据文件名前缀分组获取故事文件
    
    Args:
        image_folder: 图片文件夹路径
        audio_folder: 音频文件夹路径
        
    Returns:
        字典，键为故事编号，值为包含图片和音频文件列表的字典
    """
    story_groups = defaultdict(lambda: {'images': [], 'audios': []})
    
    # 处理图片文件 - 支持两种格式：
    # 格式1：数字 (数字).扩展名，如 "1 (1).png"
    # 格式2：数字-数字.扩展名，如 "2-03.jpg"
    if os.path.exists(image_folder):
        for ext in ['*.jpg', '*.jpeg', '*.png', '*.bmp']:
            image_files = glob.glob(os.path.join(image_folder, ext))
            for image_file in image_files:
                filename = os.path.basename(image_file)
                story_id = None
                
                # 尝试匹配格式1：数字 (数字).扩展名
                match1 = re.match(r'^(\d+)\s*\(.*\)\.(jpg|jpeg|png|bmp)$', filename, re.IGNORECASE)
                if match1:
                    story_id = match1.group(1)
                else:
                    # 尝试匹配格式2：数字-数字.扩展名
                    match2 = re.match(r'^(\d+)-.*\.(jpg|jpeg|png|bmp)$', filename, re.IGNORECASE)
                    if match2:
                        story_id = match2.group(1)
                
                if story_id:
                    story_groups[story_id]['images'].append(image_file)
    
    # 处理音频文件 - 匹配格式：数字-数字.扩展名，如 "1-1.mp3"
    if os.path.exists(audio_folder):
        for ext in ['*.mp3', '*.wav', '*.m4a', '*.aac']:
            audio_files = glob.glob(os.path.join(audio_folder, ext))
            for audio_file in audio_files:
                filename = os.path.basename(audio_file)
                # 匹配格式：数字-任意内容.扩展名
                match = re.match(r'^(\d+)-.*\.(mp3|wav|m4a|aac)$', filename, re.IGNORECASE)
                if match:
                    story_id = match.group(1)
                    story_groups[story_id]['audios'].append(audio_file)
    
    # 对每个故事的文件进行自然排序
    for story_id in story_groups:
        story_groups[story_id]['images'].sort(key=lambda x: natural_sort_key(os.path.basename(x)))
        story_groups[story_id]['audios'].sort(key=lambda x: natural_sort_key(os.path.basename(x)))
    
    return dict(story_groups)

def create_single_story_draft(template_path: str, story_id: str, image_files: List[str], audio_files: List[str], output_folder: str):
    """
    为单个故事创建剪映草稿
    
    Args:
        template_path: 模板草稿文件路径
        story_id: 故事编号
        image_files: 图片文件列表
        audio_files: 音频文件列表
        output_folder: 输出文件夹路径
    """
    
    print(f"\n=== 创建故事 {story_id} 的草稿 ===")
    print(f"图片文件数量: {len(image_files)}")
    print(f"音频文件数量: {len(audio_files)}")
    
    # 显示音频文件排序
    if audio_files:
        print("音频文件排序:")
        for i, audio_file in enumerate(audio_files[:5]):  # 显示前5个
            print(f"  {i+1}. {os.path.basename(audio_file)}")
        if len(audio_files) > 5:
            print(f"  ... 还有 {len(audio_files)-5} 个文件")
    
    # 读取模板
    with open(template_path, 'r', encoding='utf-8') as f:
        draft = json.load(f)
    
    # 创建故事专用输出文件夹
    story_output_folder = os.path.join(output_folder, story_id)
    os.makedirs(story_output_folder, exist_ok=True)
    
    # 保留原有的基础材料
    original_audios = [audio for audio in draft['materials']['audios'] if audio['name'] == 'messironaldo.MP3']
    original_videos = [video for video in draft['materials']['videos'] if video['material_name'] in ['black.png', '173874-850026348_small.mp4']]
    
    # 重置材料列表
    draft['materials']['audios'] = original_audios
    draft['materials']['videos'] = original_videos
    
    # 清空第一个视频轨道的片段
    for track in draft['tracks']:
        if track['type'] == 'video' and track.get('flag', 0) == 0:
            track['segments'] = []
            break
    
    # 添加音频材料
    audio_ids = []
    
    for audio_file in audio_files:
        file_name = os.path.basename(audio_file)
        audio_id = generate_uuid()
        
        # 获取音频文件的估算时长
        duration = get_audio_duration_accurate(audio_file)
        
        audio_material = {
            "app_id": 0,
            "category_id": "",
            "category_name": "",
            "check_flag": 1,
            "copyright_limit_type": "none",
            "duration": duration,
            "effect_id": "",
            "formula_id": "",
            "id": audio_id,
            "intensifies_path": "",
            "is_ai_clone_tone": False,
            "is_text_edit_overdub": False,
            "is_ugc": False,
            "local_material_id": "",
            "music_id": "",
            "name": file_name,
            "path": audio_file,
            "query": "",
            "request_id": "",
            "resource_id": "",
            "search_id": "",
            "source_from": "",
            "source_platform": 0,
            "team_id": "",
            "text_id": "",
            "tone_category_id": "",
            "tone_category_name": "",
            "tone_effect_id": "",
            "tone_effect_name": "",
            "tone_platform": "",
            "tone_second_category_id": "",
            "tone_second_category_name": "",
            "tone_speaker": "",
            "tone_type": "",
            "type": "extract_music",
            "video_id": "",
            "wave_points": []
        }
        
        draft['materials']['audios'].append(audio_material)
        audio_ids.append((audio_id, duration))
        
        print(f"✅ 添加音频: {file_name} (真实时长: {duration/1000000:.1f}秒)")
    
    # 添加图片材料
    image_ids = []
    
    for image_file in image_files:
        file_name = os.path.basename(image_file)
        image_id = generate_uuid()
        
        image_material = {
            "aigc_type": "none",
            "audio_fade": None,
            "cartoon_path": "",
            "category_id": "",
            "category_name": "",
            "check_flag": 63487,
            "crop": {
                "lower_left_x": 0.0,
                "lower_left_y": 1.0,
                "lower_right_x": 1.0,
                "lower_right_y": 1.0,
                "upper_left_x": 0.0,
                "upper_left_y": 0.0,
                "upper_right_x": 1.0,
                "upper_right_y": 0.0
            },
            "crop_ratio": "free",
            "crop_scale": 1.0,
            "duration": 10800000000,
            "extra_type_option": 0,
            "formula_id": "",
            "freeze": None,
            "has_audio": False,
            "height": 2048,
            "id": image_id,
            "intensifies_audio_path": "",
            "intensifies_path": "",
            "is_ai_generate_content": False,
            "is_copyright": False,
            "is_text_edit_overdub": False,
            "is_unified_beauty_mode": False,
            "local_id": "",
            "local_material_id": "",
            "material_id": "",
            "material_name": file_name,
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
            "path": image_file,
            "picture_from": "none",
            "picture_set_category_id": "",
            "picture_set_category_name": "",
            "request_id": "",
            "reverse_intensifies_path": "",
            "reverse_path": "",
            "smart_motion": None,
            "source": 0,
            "source_platform": 0,
            "stable": {
                "matrix_path": "",
                "stable_level": 0,
                "time_range": {
                    "duration": 0,
                    "start": 0
                }
            },
            "team_id": "",
            "type": "photo",
            "video_algorithm": {
                "algorithms": [],
                "complement_frame_config": None,
                "deflicker": None,
                "gameplay_configs": [],
                "motion_blur_config": None,
                "noise_reduction": None,
                "path": "",
                "quality_enhance": None,
                "time_range": None
            },
            "width": 1152
        }
        
        draft['materials']['videos'].append(image_material)
        image_ids.append(image_id)
        
        print(f"✅ 添加图片: {file_name}")
    
    # 创建图片轨道片段
    if image_ids and audio_ids:
        # 找到第一个视频轨道
        video_track = None
        for track in draft['tracks']:
            if track['type'] == 'video' and track.get('flag', 0) == 0:
                video_track = track
                break
        
        if video_track:
            current_time = 0
            image_index = 0  # 当前使用的图片索引
            
            print(f"\n=== 开始分配图片到音频 ===")
            
            # 遍历每个音频段
            for audio_idx, (audio_id, duration) in enumerate(audio_ids):
                audio_duration_seconds = duration / 1000000  # 转换为秒
                
                print(f"\n音频段 {audio_idx + 1}: 时长 {audio_duration_seconds:.2f}秒")
                
                # 判断音频时长是否不足1.5秒
                if audio_duration_seconds < 1.5:
                    # 短音频：只配一张图片，跳过下一张图片
                    if image_index < len(image_ids):
                        image_id = image_ids[image_index]
                        segment_id = generate_uuid()
                        
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
                            "extra_material_refs": [generate_uuid() for _ in range(5)],
                            "group_id": "",
                            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
                            "id": segment_id,
                            "intensifies_audio": False,
                            "is_placeholder": False,
                            "is_tone_modify": False,
                            "keyframe_refs": [],
                            "last_nonzero_volume": 1.0,
                            "material_id": image_id,
                            "render_index": len(video_track['segments']) + 1,
                            "responsive_layout": {
                                "enable": False,
                                "horizontal_pos_layout": 0,
                                "size_layout": 0,
                                "target_follow": "",
                                "vertical_pos_layout": 0
                            },
                            "reverse": False,
                            "source_timerange": {"duration": duration, "start": 0},
                            "speed": 1.0,
                            "target_timerange": {"duration": duration, "start": current_time},
                            "template_id": "",
                            "template_scene": "default",
                            "track_attribute": 0,
                            "track_render_index": 1,
                            "uniform_scale": {"on": True, "value": 1.0},
                            "visible": True,
                            "volume": 1.0
                        }
                        
                        video_track['segments'].append(segment)
                        print(f"  短音频配1张图片: 图片{image_index + 1} (时长{audio_duration_seconds:.2f}秒)")
                        print(f"  跳过图片{image_index + 2}，不再使用")
                        image_index += 2  # 跳过下一张图片，永远不再使用
                    else:
                        print(f"  警告: 音频段 {audio_idx + 1} 没有足够的图片")
                else:
                    # 长音频：配两张图片，平均分配时间
                    if image_index + 1 < len(image_ids):
                        # 第一张图片
                        first_image_id = image_ids[image_index]
                        first_segment_id = generate_uuid()
                        half_duration = duration // 2
                        
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
                            "extra_material_refs": [generate_uuid() for _ in range(5)],
                            "group_id": "",
                            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
                            "id": first_segment_id,
                            "intensifies_audio": False,
                            "is_placeholder": False,
                            "is_tone_modify": False,
                            "keyframe_refs": [],
                            "last_nonzero_volume": 1.0,
                            "material_id": first_image_id,
                            "render_index": len(video_track['segments']) + 1,
                            "responsive_layout": {
                                "enable": False,
                                "horizontal_pos_layout": 0,
                                "size_layout": 0,
                                "target_follow": "",
                                "vertical_pos_layout": 0
                            },
                            "reverse": False,
                            "source_timerange": {"duration": half_duration, "start": 0},
                            "speed": 1.0,
                            "target_timerange": {"duration": half_duration, "start": current_time},
                            "template_id": "",
                            "template_scene": "default",
                            "track_attribute": 0,
                            "track_render_index": 1,
                            "uniform_scale": {"on": True, "value": 1.0},
                            "visible": True,
                            "volume": 1.0
                        }
                        
                        # 第二张图片
                        second_image_id = image_ids[image_index + 1]
                        second_segment_id = generate_uuid()
                        remaining_duration = duration - half_duration
                        
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
                            "extra_material_refs": [generate_uuid() for _ in range(5)],
                            "group_id": "",
                            "hdr_settings": {"intensity": 1.0, "mode": 1, "nits": 1000},
                            "id": second_segment_id,
                            "intensifies_audio": False,
                            "is_placeholder": False,
                            "is_tone_modify": False,
                            "keyframe_refs": [],
                            "last_nonzero_volume": 1.0,
                            "material_id": second_image_id,
                            "render_index": len(video_track['segments']) + 2,
                            "responsive_layout": {
                                "enable": False,
                                "horizontal_pos_layout": 0,
                                "size_layout": 0,
                                "target_follow": "",
                                "vertical_pos_layout": 0
                            },
                            "reverse": False,
                            "source_timerange": {"duration": remaining_duration, "start": 0},
                            "speed": 1.0,
                            "target_timerange": {"duration": remaining_duration, "start": current_time + half_duration},
                            "template_id": "",
                            "template_scene": "default",
                            "track_attribute": 0,
                            "track_render_index": 1,
                            "uniform_scale": {"on": True, "value": 1.0},
                            "visible": True,
                            "volume": 1.0
                        }
                        
                        video_track['segments'].append(first_segment)
                        video_track['segments'].append(second_segment)
                        print(f"  长音频配2张图片: 图片{image_index + 1}({half_duration/1000000:.2f}秒) + 图片{image_index + 2}({remaining_duration/1000000:.2f}秒)")
                        image_index += 2
                    else:
                        print(f"  警告: 音频段 {audio_idx + 1} 没有足够的图片配对")
                
                current_time += duration
            
            # 计算实际使用的图片数量（不包括跳过的）
            used_images = len(video_track['segments'])
            skipped_images = image_index - used_images
            
            print(f"✅ 创建图片轨道，使用了 {used_images} 张图片，共 {len(video_track['segments'])} 个片段")
            if skipped_images > 0:
                print(f"⚠️  跳过了 {skipped_images} 张图片（因短音频而永久跳过）")
            
            # 如果还有剩余的图片没有使用，给出提示
            if image_index < len(image_ids):
                unused_count = len(image_ids) - image_index
                print(f"ℹ️  还有 {unused_count} 张图片未使用")
            
            # 添加入场动画效果到除第一张图片外的所有图片
            print(f"\n=== 开始添加入场动画效果 ===")
            
            # 确保 material_animations 存在
            if 'material_animations' not in draft['materials']:
                draft['materials']['material_animations'] = []
            
            # 创建四种入场动画效果
            animations = []
            
            # 创建动感放大动画
            zoom_in_animation = {
                'animations': [{
                'anim_adjust_params': None,
                'category_id': 'in',
                'category_name': '入场',
                'duration': 200000,  # 0.2秒
                'id': '431662',
                'material_type': 'video',
                'name': '动感放大',
                'panel': 'video',
                'path': '/Users/a47/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Cache/effect/431662/8fb560c01e4ccffbc4dc084f9c418838',
                'platform': 'all',
                'request_id': str(uuid.uuid4()),
                'resource_id': '6740867832570974733',
                'start': 0,
                'type': 'in'
                }],
                'id': str(uuid.uuid4()).upper(),
                'multi_language_current': 'none',
                'type': 'sticker_animation'
            }
            draft['materials']['material_animations'].append(zoom_in_animation)
            animations.append(zoom_in_animation)
            print(f"✅ 创建动感放大动画: {zoom_in_animation['id']}")
            
            # 创建轻微抖动动画
            gentle_shake_animation = {
                'animations': [{
                'anim_adjust_params': None,
                'category_id': 'in',
                'category_name': '入场',
                'duration': 200000,  # 0.2秒
                'id': '431664',
                'material_type': 'video',
                'name': '轻微抖动',
                'panel': 'video',
                'path': '/Users/a47/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Cache/effect/431664/944c5561f3d23baa068cee2bba4f15f5',
                'platform': 'all',
                'request_id': str(uuid.uuid4()),
                'resource_id': '6739418227031413256',
                'start': 0,
                'type': 'in'
                }],
                'id': str(uuid.uuid4()).upper(),
                'multi_language_current': 'none',
                'type': 'sticker_animation'
            }
            draft['materials']['material_animations'].append(gentle_shake_animation)
            animations.append(gentle_shake_animation)
            print(f"✅ 创建轻微抖动动画: {gentle_shake_animation['id']}")
            
            # 创建向右甩入动画
            swipe_right_animation = {
                'animations': [{
                'anim_adjust_params': None,
                'category_id': 'in',
                'category_name': '入场',
                'duration': 200000,  # 0.2秒
                'id': '431636',
                'material_type': 'video',
                'name': '向右甩入',
                'panel': 'video',
                'path': '/Users/a47/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Cache/effect/431636/c83f7d144853d115a9e8572e667c6bfe',
                'platform': 'all',
                'request_id': str(uuid.uuid4()),
                'resource_id': '6739338727866241539',
                'start': 0,
                'type': 'in'
                }],
                'id': str(uuid.uuid4()).upper(),
                'multi_language_current': 'none',
                'type': 'sticker_animation'
            }
            draft['materials']['material_animations'].append(swipe_right_animation)
            animations.append(swipe_right_animation)
            print(f"✅ 创建向右甩入动画: {swipe_right_animation['id']}")
            
            # 创建左右抖动动画
            shake_animation = {
                'animations': [{
                'anim_adjust_params': None,
                'category_id': 'in',
                'category_name': '入场',
                'duration': 200000,  # 0.2秒
                'id': '431654',
                'material_type': 'video',
                'name': '左右抖动',
                'panel': 'video',
                'path': '/Users/a47/Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Cache/effect/431654/267653b22765bd8348dda092f8de3cfe',
                'platform': 'all',
                'request_id': str(uuid.uuid4()),
                'resource_id': '6739418540421419524',
                'start': 0,
                'type': 'in'
                }],
                'id': str(uuid.uuid4()).upper(),
                'multi_language_current': 'none',
                'type': 'sticker_animation'
            }
            draft['materials']['material_animations'].append(shake_animation)
            animations.append(shake_animation)
            print(f"✅ 创建左右抖动动画: {shake_animation['id']}")
            
            # 定义一个函数，随机选择一个动画，但不会连续选择相同的动画
            last_animation = None
            def get_random_animation():
                nonlocal last_animation
                available_animations = [anim for anim in animations if anim != last_animation]
                if not available_animations:  # 如果没有可用的动画，使用所有动画
                    available_animations = animations
                selected_animation = random.choice(available_animations)
                last_animation = selected_animation
                return selected_animation
            
            # 应用入场动画效果到除第一张图片外的所有图片上
            animation_count = 0
            for i, segment in enumerate(video_track['segments']):
                # 跳过第一个图片片段
                if i == 0:
                    print(f"跳过第一张图片，不应用动画效果")
                    continue
                
                # 随机选择一个动画效果，但不会连续选择相同的动画
                animation_to_apply = get_random_animation()
                
                # 确保 extra_material_refs 存在
                if 'extra_material_refs' not in segment:
                    segment['extra_material_refs'] = []
                
                # 应用动画效果
                segment['extra_material_refs'].append(animation_to_apply['id'])
                animation_name = animation_to_apply['animations'][0]['name']
                print(f"✅ 已将 {animation_name} 动画效果应用到图片片段 {i+1}")
                animation_count += 1
            
            print(f"✅ 入场动画效果应用完成，共为 {animation_count} 张图片添加了动画")
    
    # 创建音频轨道
    if audio_ids:
        audio_track_id = generate_uuid()
        segments = []
        current_time = 0
        
        for i, (audio_id, duration) in enumerate(audio_ids):
            segment_id = generate_uuid()
            
            segment = {
                "caption_info": None,
                "cartoon": False,
                "clip": None,
                "common_keyframes": [],
                "enable_adjust": False,
                "enable_color_curves": True,
                "enable_color_match_adjust": False,
                "enable_color_wheels": True,
                "enable_lut": False,
                "enable_smart_color_adjust": False,
                "extra_material_refs": [generate_uuid() for _ in range(4)],
                "group_id": "",
                "hdr_settings": None,
                "id": segment_id,
                "intensifies_audio": False,
                "is_placeholder": False,
                "is_tone_modify": False,
                "keyframe_refs": [],
                "last_nonzero_volume": 1.0,
                "material_id": audio_id,
                "render_index": i,
                "responsive_layout": {
                    "enable": False,
                    "horizontal_pos_layout": 0,
                    "size_layout": 0,
                    "target_follow": "",
                    "vertical_pos_layout": 0
                },
                "reverse": False,
                "source_timerange": {"duration": duration, "start": 0},  # 使用完整时长
                "speed": 1.0,
                "target_timerange": {"duration": duration, "start": current_time},
                "template_id": "",
                "template_scene": "default",
                "track_attribute": 0,
                "track_render_index": 0,
                "uniform_scale": None,
                "visible": True,
                "volume": 10.0  # +20dB 对白音量
            }
            
            segments.append(segment)
            current_time += duration
        
        # 创建音频轨道
        audio_track = {
            "attribute": 0,
            "flag": 0,
            "id": audio_track_id,
            "is_default_name": True,
            "name": "",
            "segments": segments,
            "type": "audio"
        }
        
        draft['tracks'].append(audio_track)
        
        # 更新总时长
        total_audio_duration = sum(duration for _, duration in audio_ids)
        draft['duration'] = total_audio_duration
        
        print(f"✅ 创建音频轨道，包含 {len(audio_ids)} 个片段，总音频时长 {total_audio_duration/1000000:.1f}秒")
    
    # 修改背景音乐messironaldo.MP3的时长和音量
    total_video_duration = draft['duration']  # 使用视频总时长
    
    for track in draft['tracks']:
        if track['type'] == 'audio':
            for segment in track['segments']:
                if 'material_id' in segment:
                    # 查找对应的音频材料
                    for audio_material in draft['materials']['audios']:
                        if (audio_material['id'] == segment['material_id'] and 
                            audio_material['name'] == 'messironaldo.MP3'):
                            # 延长背景音乐到整个视频时长
                            segment['target_timerange']['duration'] = total_video_duration
                            if 'source_timerange' in segment and segment['source_timerange'] is not None:
                                segment['source_timerange']['duration'] = total_video_duration
                            # 设置背景音乐音量为+10dB
                            segment['volume'] = 3.16  # +10dB 背景音乐音量
                            print(f"✅ 延长背景音乐 messironaldo.MP3 到 {total_video_duration/1000000:.2f}秒，音量设为 +10dB")
                            break
    
    # 调整black.png和MP4片段的时长
    for track in draft['tracks']:
        if track['type'] == 'video':
            for segment in track['segments']:
                if 'material_id' in segment:
                    # 查找对应的视频材料
                    for video_material in draft['materials']['videos']:
                        if video_material['id'] == segment['material_id']:
                            material_name = video_material.get('material_name', '') or video_material.get('name', '')
                            
                            # 调整black.png时长到整个视频
                            if 'black.png' in material_name.lower():
                                segment['target_timerange']['duration'] = total_video_duration
                                if 'source_timerange' in segment and segment['source_timerange'] is not None:
                                    segment['source_timerange']['duration'] = total_video_duration
                                print(f"✅ 延长 black.png 到 {total_video_duration/1000000:.2f}秒")
                            
                            # 调整MP4片段到视频末尾（最后5秒）
                            elif '.mp4' in material_name.lower():
                                mp4_duration = 5000000  # 5秒
                                mp4_start = total_video_duration - mp4_duration
                                segment['target_timerange']['start'] = mp4_start
                                segment['target_timerange']['duration'] = mp4_duration
                                if 'source_timerange' in segment and segment['source_timerange'] is not None:
                                    segment['source_timerange']['duration'] = mp4_duration
                                print(f"✅ 调整 MP4 片段到视频末尾，时长5秒，开始时间 {mp4_start/1000000:.2f}秒")
                            break
    
    # 调整轨道2（效果轨道）的时长
    for track in draft['tracks']:
        if track['type'] == 'effect':
            for segment in track['segments']:
                segment['target_timerange']['duration'] = total_video_duration
                if 'source_timerange' in segment and segment['source_timerange'] is not None:
                    segment['source_timerange']['duration'] = total_video_duration
                print(f"✅ 延长效果轨道到 {total_video_duration/1000000:.2f}秒")
                break
    
    # 保存草稿文件
    output_draft_path = os.path.join(story_output_folder, "draft_content.json")
    with open(output_draft_path, 'w', encoding='utf-8') as f:
        json.dump(draft, f, ensure_ascii=False)
    
    # 复制模板文件夹的其他文件
    template_folder = os.path.dirname(template_path)
    for item in os.listdir(template_folder):
        if item != "draft_content.json":
            src_path = os.path.join(template_folder, item)
            dst_path = os.path.join(story_output_folder, item)
            
            try:
                if os.path.isfile(src_path):
                    shutil.copy2(src_path, dst_path)
                elif os.path.isdir(src_path):
                    if os.path.exists(dst_path):
                        shutil.rmtree(dst_path)
                    shutil.copytree(src_path, dst_path)
            except Exception as e:
                print(f"复制文件时出错 {item}: {e}")
    
    print(f"✅ 故事 {story_id} 草稿生成完成！")
    print(f"📁 输出文件夹: {story_output_folder}")
    print(f"🎵 音频片段: {len(audio_ids)}")
    print(f"🖼️  图片片段: {len(image_ids)}")
    print(f"⏱️  总时长: {draft['duration']/1000000:.2f}秒")

def batch_create_drafts(template_path: str, image_folder: str, audio_folder: str, output_base_folder: str):
    """
    批量创建多个故事的剪映草稿
    
    Args:
        template_path: 模板草稿文件路径
        image_folder: 图片文件夹路径
        audio_folder: 音频文件夹路径
        output_base_folder: 输出基础文件夹路径
    """
    
    print("=== 剪映草稿批量生成器（最终版）===")
    print(f"模板文件: {template_path}")
    print(f"图片文件夹: {image_folder}")
    print(f"音频文件夹: {audio_folder}")
    print(f"输出基础文件夹: {output_base_folder}")
    
    # 检查模板文件
    if not os.path.exists(template_path):
        print(f"❌ 模板文件不存在: {template_path}")
        return
    
    # 获取故事分组
    story_groups = get_story_groups(image_folder, audio_folder)
    
    if not story_groups:
        print("❌ 没有找到任何符合命名规律的文件")
        return
    
    print(f"\n找到 {len(story_groups)} 个故事:")
    for story_id in sorted(story_groups.keys(), key=int):
        images_count = len(story_groups[story_id]['images'])
        audios_count = len(story_groups[story_id]['audios'])
        print(f"  故事 {story_id}: {images_count} 张图片, {audios_count} 个音频")
        
        # 显示前几个文件名作为示例
        if story_groups[story_id]['images']:
            print(f"    图片示例: {os.path.basename(story_groups[story_id]['images'][0])}")
        if story_groups[story_id]['audios']:
            print(f"    音频示例: {os.path.basename(story_groups[story_id]['audios'][0])}")
    
    # 确保输出文件夹存在
    os.makedirs(output_base_folder, exist_ok=True)
    
    # 为每个故事创建草稿
    for story_id in sorted(story_groups.keys(), key=int):
        story_data = story_groups[story_id]
        
        # 只有当故事有图片或音频文件时才创建草稿
        if story_data['images'] or story_data['audios']:
            create_single_story_draft(
                template_path=template_path,
                story_id=story_id,
                image_files=story_data['images'],
                audio_files=story_data['audios'],
                output_folder=output_base_folder
            )
        else:
            print(f"⚠️  故事 {story_id} 没有找到任何文件，跳过")
    
    print(f"\n🎉 批量生成完成！")
    print(f"📁 所有草稿保存在: {output_base_folder}")
    print(f"📊 总共生成了 {len([s for s in story_groups.values() if s['images'] or s['audios']])} 个草稿")

def main():
    """主函数"""
    
    # 配置路径
    template_path = "/Users/47rc/Desktop/纯净99/draft_content.json"  # 模板草稿文件
    image_folder = "/Users/47rc/Downloads"  # 图片文件夹
    audio_folder = "/Users/47rc/Downloads"  # 音频文件夹
    output_base_folder = "/Users/47rc/Desktop/58jianying"  # 临时输出文件夹
    final_destination = "/Users/47rc/Desktop/Youtube/剪映draft/JianyingPro Drafts"  # 最终目标文件夹
    adjust_script_path = "/Users/47rc/Desktop/AutoAI/adjust_draft_images两张图一段语音.py"  # 调整脚本路径
    
    print("=== 第一步：批量生成草稿 ===")
    # 批量生成草稿
    batch_create_drafts(template_path, image_folder, audio_folder, output_base_folder)
    
    print("\n=== 跳过调整脚本，使用新的短音频逻辑 ===")
    print("短音频（< 1.5秒）只配1张图片，长音频（≥ 1.5秒）配2张图片")
    
    # print("\n=== 第二步：运行调整脚本 ===")
    # # 运行调整脚本
    # try:
    #     result = subprocess.run([
    #         "python", adjust_script_path
    #     ], capture_output=True, text=True, cwd="/Users/47rc/Desktop/AutoAI")
    #     
    #     if result.returncode == 0:
    #         print("✅ 调整脚本运行成功")
    #         print("调整脚本输出:")
    #         print(result.stdout)
    #     else:
    #         print("❌ 调整脚本运行失败")
    #         print("错误输出:")
    #         print(result.stderr)
    #         return
    # except Exception as e:
    #     print(f"❌ 运行调整脚本时出错: {e}")
    #     return
    
    print("\n=== 第二步：移动草稿到最终目录 ===")
    # 确保最终目标目录存在
    os.makedirs(final_destination, exist_ok=True)
    
    # 获取所有生成的草稿文件夹
    if os.path.exists(output_base_folder):
        draft_folders = [f for f in os.listdir(output_base_folder) 
                        if os.path.isdir(os.path.join(output_base_folder, f))]
        
        moved_count = 0
        for folder_name in draft_folders:
            src_path = os.path.join(output_base_folder, folder_name)
            dst_path = os.path.join(final_destination, folder_name)
            
            try:
                # 如果目标文件夹已存在，先删除
                if os.path.exists(dst_path):
                    shutil.rmtree(dst_path)
                
                # 移动文件夹
                shutil.move(src_path, dst_path)
                print(f"✅ 已移动草稿: {folder_name}")
                moved_count += 1
                
            except Exception as e:
                print(f"❌ 移动草稿 {folder_name} 时出错: {e}")
        
        print(f"\n🎉 处理完成！")
        print(f"📊 总共处理了 {moved_count} 个草稿")
        print(f"📁 所有草稿已保存到: {final_destination}")
        
        # 清理临时文件夹
        try:
            if os.path.exists(output_base_folder) and not os.listdir(output_base_folder):
                os.rmdir(output_base_folder)
                print(f"🧹 已清理临时文件夹: {output_base_folder}")
        except Exception as e:
            print(f"⚠️  清理临时文件夹时出错: {e}")
    else:
        print("❌ 未找到生成的草稿文件夹")

if __name__ == "__main__":
    main() 