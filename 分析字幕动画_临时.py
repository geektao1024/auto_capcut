import json

# 读取1012草稿
with open('/Users/mac/Movies/CapCut/User Data/Projects/com.lveditor.draft/1012/draft_info.json', 'r') as f:
    data = json.load(f)

print("="*70)
print("【字幕动画和样式分析】")
print("="*70)

# 找到text轨道
tracks = data.get('tracks', [])
text_track = None
for track in tracks:
    if track.get('type') == 'text':
        text_track = track
        break

if text_track:
    segments = text_track.get('segments', [])
    print(f"\n✅ 找到字幕轨道，共 {len(segments)} 个片段")
    
    # 分析第一个字幕片段
    if segments:
        seg = segments[0]
        print(f"\n第1个字幕片段完整结构:")
        print(json.dumps(seg, indent=2, ensure_ascii=False)[:2000])
        print("...")
        
        # 检查关键字段
        print(f"\n关键字段:")
        print(f"  caption_info: {seg.get('caption_info')}")
        print(f"  material_id: {seg.get('material_id')}")
        
        # 找到对应的text material
        material_id = seg.get('material_id')
        texts = data.get('materials', {}).get('texts', [])
        
        for txt in texts:
            if txt.get('id') == material_id:
                print(f"\n对应的字幕material:")
                print(f"  content: {txt.get('content', '')[:80]}")
                print(f"  styles数量: {len(txt.get('styles', []))}")
                
                # 显示第一个style
                if txt.get('styles'):
                    style = txt['styles'][0]
                    print(f"\n  第1个样式:")
                    print(json.dumps(style, indent=4, ensure_ascii=False))
                
                # 检查是否有动画相关字段
                for key in txt.keys():
                    if 'anim' in key.lower() or 'effect' in key.lower():
                        print(f"\n  ⭐ 发现动画字段: {key}")
                        print(f"     值: {txt[key]}")
                break

# 检查materials中是否有caption相关的动画
materials = data.get('materials', {})
for mat_type, mat_list in materials.items():
    if 'caption' in mat_type.lower() or 'animation' in mat_type.lower():
        print(f"\n发现相关材料类型: {mat_type}")
        if isinstance(mat_list, list) and mat_list:
            print(f"  数量: {len(mat_list)}")
            print(f"  示例: {json.dumps(mat_list[0], indent=2, ensure_ascii=False)[:500]}")

print("\n" + "="*70)

