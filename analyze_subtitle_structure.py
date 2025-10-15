#!/usr/bin/env python3
"""分析CapCut草稿中的字幕结构"""

import json
import os

draft_path = "/Users/mac/Movies/CapCut/User Data/Projects/com.lveditor.draft/1012/draft_info.json"

print("="*70)
print("【1012 草稿 - 字幕完整分析】")
print("="*70)

with open(draft_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# 1. 轨道分析
tracks = data.get('tracks', [])
print(f'\n1️⃣  轨道总数: {len(tracks)}')
print('-'*70)
for i, track in enumerate(tracks, 1):
    t_type = track.get('type')
    segs = len(track.get('segments', []))
    flag = track.get('flag', 0)
    print(f'{i}. {t_type:15s} - {segs:3d} 个片段 (flag={flag})')
    
# 2. 字幕轨道详情
text_track = None
for track in tracks:
    if track.get('type') == 'text':
        text_track = track
        break

if text_track:
    print(f'\n2️⃣  字幕轨道详情:')
    print('-'*70)
    print(f'   片段数: {len(text_track.get("segments", []))}')
    print(f'   flag: {text_track.get("flag")} (1=识别字幕)')
    print(f'   轨道ID: {text_track.get("id")}')
    
    # 取前3个字幕片段
    segs = text_track.get('segments', [])
    for i in range(min(3, len(segs))):
        seg = segs[i]
        print(f'\n   字幕片段 {i+1}:')
        print(f'     material_id: {seg.get("material_id")}')
        print(f'     时间: {seg.get("target_timerange")}')
        if 'caption_info' in seg and seg['caption_info']:
            print(f'     caption_info: 存在')

# 3. texts材料
materials = data.get('materials', {})
texts = materials.get('texts', [])
print(f'\n3️⃣  texts材料: {len(texts)} 个')
print('-'*70)

if texts:
    # 显示前3个
    for i in range(min(3, len(texts))):
        txt = texts[i]
        print(f'\n   字幕 {i+1}:')
        print(f'     ID: {txt.get("id")}')
        content = txt.get("content", "")
        print(f'     内容: {content[:80]}{"..." if len(content) > 80 else ""}')
        if txt.get("fonts"):
            font_name = txt["fonts"][0].get("name", "未知")
            print(f'     字体: {font_name}')
        print(f'     样式数: {len(txt.get("styles", []))}')

# 4. text_templates
text_templates = materials.get('text_templates', [])
print(f'\n4️⃣  text_templates模板: {len(text_templates)} 个')
print('-'*70)

if text_templates:
    tpl = text_templates[0]
    print(f'\n   模板详情:')
    print(f'     ID: {tpl.get("id")}')
    print(f'     名称: {tpl.get("name", "无")}')
    print(f'     平台: {tpl.get("platform", "无")}')
    print(f'\n   完整JSON (前1500字符):')
    print(json.dumps(tpl, indent=2, ensure_ascii=False)[:1500])
    print('...')

# 5. 配置信息
config = data.get('config', {})
print(f'\n5️⃣  字幕识别配置:')
print('-'*70)
print(f'   subtitle_sync: {config.get("subtitle_sync")}')
print(f'   subtitle_recognition_id: {config.get("subtitle_recognition_id", "无")}')

subtitle_taskinfo = config.get('subtitle_taskinfo', [])
print(f'   subtitle_taskinfo: {len(subtitle_taskinfo)} 个任务')

if subtitle_taskinfo:
    task = subtitle_taskinfo[0]
    print(f'\n   任务1详情:')
    for key in ['ai_accurate_recognize', 'ai_only', 'is_empty', 'language', 'task_id', 'task_state']:
        if key in task:
            print(f'     {key}: {task[key]}')
    
# 6. 保存完整的第一个text和template到文件
if texts:
    with open('sample_text.json', 'w', encoding='utf-8') as f:
        json.dump(texts[0], f, indent=2, ensure_ascii=False)
    print(f'\n✅ 第1个字幕完整JSON已保存到: sample_text.json')

if text_templates:
    with open('sample_template.json', 'w', encoding='utf-8') as f:
        json.dump(text_templates[0], f, indent=2, ensure_ascii=False)
    print(f'✅ 第1个模板完整JSON已保存到: sample_template.json')

print(f'\n{"="*70}')
print(f'分析完成！')
print(f'{"="*70}')

