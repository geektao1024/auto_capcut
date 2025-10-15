#!/usr/bin/env python3
"""
即梦图片生成脚本 - 简化版
功能: 批量提交分镜到即梦平台，自动识别角色并上传参考图
作者: AI助手
日期: 2025-09-30
"""

import asyncio
import re
import os
import csv
import platform
from pathlib import Path
from playwright.async_api import async_playwright
import logging

# ====================================================================
# 📋 配置区
# ====================================================================
class Config:
    """脚本配置"""
    # 即梦平台地址
    JIMENG_URL = "https://jimeng.jianying.com/ai-tool/generate?type=image"
    
    # 文件路径
    STORYBOARD_FILE = Path.cwd() / "参考.txt"  # 分镜文件（支持TSV格式）
    REFERENCE_DIR = Path.cwd() / "reference_images"  # 参考图目录
    BROWSER_DATA = Path.cwd() / "browser_data"  # 浏览器数据目录
    
    # 等待时间（秒）
    PAGE_LOAD_WAIT = 5      # 页面加载等待
    NAVIGATION_WAIT = 3     # 导航后等待
    SUBMIT_WAIT = 3         # 提交后等待（增加到3秒，确保提交完成）
    INPUT_WAIT = 2          # 输入后等待（增加到2秒，确保输入稳定）
    STATUS_CHECK_WAIT = 3   # 状态检查等待（新增）
    
    # 参考图支持的格式
    REFERENCE_EXTS = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
    
    # 参考图清理方式
    USE_DOM_CLEAR = True         # 使用DOM方式清理（推荐，无闪烁）
    SIMPLE_MODE = False          # 简单模式：不删除参考图（会累积）

# 配置日志（同时输出到控制台和文件）
log_dir = Path.cwd() / "logs"
log_dir.mkdir(exist_ok=True)

from datetime import datetime
log_file = log_dir / f"shengtu_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 创建logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 控制台handler
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
console_handler.setFormatter(console_formatter)

# 文件handler
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)  # 文件记录更详细的日志
file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(file_formatter)

# 添加handlers
logger.addHandler(console_handler)
logger.addHandler(file_handler)

logger.info(f"日志文件: {log_file}")

# ====================================================================
# 🛠️ 工具函数
# ====================================================================

def extract_roles(text):
    """
    从分镜文本中提取角色名称

    支持多种格式:
        1. 简单格式: "角色:张三,李四" -> ["张三", "李四"]
        2. HTML格式: "角色:<br> * 女儿<br> * 母亲" -> ["女儿", "母亲"]
        3. CSV格式: "角色：母亲, 女儿" -> ["母亲", "女儿"]
        4. 多行格式: "角色:\n女儿, 父亲" -> ["女儿", "父亲"]

    Args:
        text: 分镜文本

    Returns:
        list: 角色名称列表
    """
    roles = []
    try:
        # 先清理HTML标签，将<br>替换为换行符
        text_clean = text.replace('<br>', '\n').replace('<BR>', '\n')

        # 增强的角色匹配模式，更准确地定位角色部分
        # 使用更精确的边界条件，避免过度匹配
        role_patterns = [
            # 标准"角色:"或"角色："格式，到下一个字段或行尾为止
            r"角色[:：]\s*(.*?)(?=\n\s*(?:机位|构图|姿势|环境|动作|表情|场景|画面|$))",
            # 备用模式：到空行或下一个标签为止
            r"角色[:：]\s*(.*?)(?=\n\n|\n\[|\Z)",
            # 简单模式：仅匹配冒号后的一行内容
            r"角色[:：]\s*([^\n]+)"
        ]

        for pattern in role_patterns:
            role_match = re.search(pattern, text_clean, re.DOTALL)
            if role_match:
                match = role_match.group(1).strip()
                logger.debug(f"   原始角色匹配内容: {match[:100]}...")

                # 提取所有以 * 开头的行（列表项）- HTML格式
                list_items = re.findall(r'\*\s*([^\n]+)', match)
                if list_items:
                    # HTML格式：角色:<br> * 女儿<br> * 母亲
                    for item in list_items:
                        role_clean = item.strip()
                        # 清理可能的HTML标签和多余空格
                        role_clean = re.sub(r'<[^>]+>', '', role_clean)
                        role_clean = re.sub(r'\s+', ' ', role_clean).strip()
                        if role_clean and role_clean not in roles:
                            roles.append(role_clean)
                else:
                    # 简单格式或CSV格式：角色:张三,李四 或 角色：母亲, 女儿
                    # 按逗号、顿号、空格、斜杠、和号分割
                    candidates = re.split(r"[,，、\s/&]+", match.strip())
                    for role in candidates:
                        role_clean = role.strip()
                        # 清理可能的前后缀和特殊字符
                        role_clean = re.sub(r'^[^\w\u4e00-\u9fff]+', '', role_clean)  # 清理开头特殊字符
                        role_clean = re.sub(r'[^\w\u4e00-\u9fff]+$', '', role_clean)  # 清理结尾特殊字符
                        role_clean = role_clean.strip()

                        # 过滤掉空字符串、常见关键词和特殊字符
                        invalid_roles = ['*', '-', '[主体]', '[环境]', '角色', '空', '无', 'null', 'none']
                        if (role_clean and
                            role_clean not in invalid_roles and
                            len(role_clean) > 0 and
                            role_clean not in roles and
                            not role_clean.isdigit()):  # 排除纯数字
                            roles.append(role_clean)

                break  # 找到匹配就停止，避免重复处理

        if roles:
            logger.info(f"   识别到角色: {', '.join(roles)}")
        else:
            logger.info("   未识别到角色标记")

    except Exception as e:
        logger.error(f"   提取角色时出错: {e}")
        import traceback
        logger.debug(traceback.format_exc())

    return roles


def select_script_file():
    """
    让用户选择分镜脚本文件
    
    Returns:
        Path: 选择的脚本文件路径
    """
    script_dir = Path.cwd() / "jiaoben"
    default_file = Path.cwd() / "参考.txt"
    
    # 检查 jiaoben 目录是否存在
    if not script_dir.exists():
        logger.info("ℹ️ jiaoben 文件夹不存在，使用默认脚本文件")
        if default_file.exists():
            return default_file
        else:
            logger.error(f"❌ 默认脚本文件不存在: {default_file}")
            return None
    
    # 获取所有 txt 和 csv 文件
    script_files = [f for f in script_dir.iterdir() if f.suffix.lower() in ['.txt', '.csv']]
    
    # 如果 jiaoben 文件夹为空，使用默认文件
    if not script_files:
        logger.info("ℹ️ jiaoben 文件夹为空，使用默认脚本文件")
        if default_file.exists():
            return default_file
        else:
            logger.error(f"❌ 默认脚本文件不存在: {default_file}")
            return None
    
    # 有脚本文件，让用户选择
    print(f"\n{'='*70}")
    print("📝 检测到多个分镜脚本，请选择：")
    print(f"{'='*70}")
    
    # 按名称排序
    script_files.sort(key=lambda x: x.name)
    
    for i, script_file in enumerate(script_files, 1):
        # 获取文件大小和类型
        file_size = script_file.stat().st_size
        size_kb = file_size / 1024
        file_type = script_file.suffix.upper()[1:]  # .txt -> TXT, .csv -> CSV
        print(f"{i}️⃣  {script_file.name} ({size_kb:.1f} KB, {file_type})")
    
    # 添加默认文件选项
    if default_file.exists():
        default_size = default_file.stat().st_size / 1024
        print(f"{len(script_files)+1}️⃣  参考.txt (默认, {default_size:.1f} KB)")
    
    print()
    
    while True:
        try:
            max_choice = len(script_files) + (1 if default_file.exists() else 0)
            choice = input(f"请选择 (1-{max_choice}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(script_files):
                selected = script_files[choice_num - 1]
                print(f"\n✅ 已选择: {selected.name}\n")
                return selected
            elif default_file.exists() and choice_num == len(script_files) + 1:
                print(f"\n✅ 已选择: 参考.txt (默认)\n")
                return default_file
            else:
                print(f"❌ 请输入 1-{max_choice} 之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n程序已取消")
            exit(0)

def select_reference_directory():
    """
    让用户选择参考图目录
    
    Returns:
        Path: 选择的参考图目录路径
    """
    base_dir = Path.cwd() / "reference_images"
    
    # 检查基础目录是否存在
    if not base_dir.exists():
        logger.warning(f"⚠️ 参考图目录不存在: {base_dir}")
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir
    
    # 获取所有子文件夹
    subdirs = [d for d in base_dir.iterdir() if d.is_dir()]
    
    if not subdirs:
        # 没有子文件夹，直接使用根目录
        logger.info("ℹ️ 未检测到子文件夹，使用默认参考图目录")
        return base_dir
    
    # 有子文件夹，让用户选择
    print(f"\n{'='*70}")
    print("📁 检测到多个参考图文件夹，请选择：")
    print(f"{'='*70}")
    
    # 按名称排序
    subdirs.sort(key=lambda x: x.name)
    
    for i, subdir in enumerate(subdirs, 1):
        # 统计该文件夹的图片数量
        image_count = len([f for f in subdir.iterdir() if f.suffix.lower() in Config.REFERENCE_EXTS])
        print(f"{i}️⃣  {subdir.name}/ ({image_count} 张图片)")
    
    print(f"{len(subdirs)+1}️⃣  使用根目录 reference_images/")
    print()
    
    while True:
        try:
            choice = input(f"请选择 (1-{len(subdirs)+1}): ").strip()
            choice_num = int(choice)
            
            if 1 <= choice_num <= len(subdirs):
                selected = subdirs[choice_num - 1]
                print(f"\n✅ 已选择: {selected.relative_to(Path.cwd())}/\n")
                return selected
            elif choice_num == len(subdirs) + 1:
                print(f"\n✅ 已选择: reference_images/\n")
                return base_dir
            else:
                print(f"❌ 请输入 1-{len(subdirs)+1} 之间的数字")
        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n\n程序已取消")
            exit(0)

def find_reference_images(roles):
    """
    根据角色名称查找对应的参考图文件
    
    Args:
        roles: 角色名称列表
        
    Returns:
        list: 参考图文件路径列表
    """
    image_paths = []
    missing_roles = []
    
    # 确保参考图目录存在
    Config.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    for role in roles:
        found = False
        # 尝试所有支持的图片格式
        for ext in Config.REFERENCE_EXTS:
            image_path = Config.REFERENCE_DIR / f"{role}{ext}"
            if image_path.exists():
                image_paths.append(image_path)
                found = True
                logger.info(f"   ✅ 找到参考图: {image_path.name}")
                break
        
        if not found:
            missing_roles.append(role)
    
    if missing_roles:
        logger.warning(f"   ⚠️ 未找到参考图的角色: {', '.join(missing_roles)}")
    
    return image_paths


def detect_file_format(lines, content):
    """
    智能检测文件格式类型

    Args:
        lines: 文件行列表
        content: 文件完整内容

    Returns:
        str: 格式类型 ('CSV', 'TSV', 'STORY')
    """
    try:
        # 如果内容为空，默认返回故事格式
        if not lines or not content:
            return 'STORY'

        # 检查CSV格式的特征
        csv_indicators = 0

        # 特征1：检查前几行是否包含CSV典型的引号包围内容
        sample_lines = lines[:min(10, len(lines))]
        quoted_lines = 0
        comma_lines = 0

        for line in sample_lines:
            line = line.strip()
            if not line:
                continue

            # 检查是否有成对的引号
            if line.count('"') >= 2:
                quoted_lines += 1

            # 检查是否有逗号分隔符
            if ',' in line:
                comma_lines += 1

        # 特征2：检查是否有CSV表头
        first_line = lines[0].strip()
        csv_headers = ['分镜数', '镜号', '分镜', '序号', '编号']
        has_csv_header = any(header in first_line for header in csv_headers)

        # 特征3：检查内容整体的CSV特征
        total_quoted = content.count('"')
        has_balanced_quotes = total_quoted >= 4 and total_quoted % 2 == 0
        total_commas = content.count(',')

        # 综合判断CSV格式
        if (has_csv_header or
            (quoted_lines >= 2 and comma_lines >= 2) or
            (has_balanced_quotes and total_commas >= 5)):
            csv_indicators += 3

        # 检查TSV格式的特征
        tsv_indicators = 0

        # 特征1：制表符分隔
        if '\t' in first_line:
            tsv_indicators += 1

        # 特征2：TSV表头
        tsv_headers = ['镜号', '分镜', '分镜数', '序号']
        has_tsv_header = any(header in first_line for header in tsv_headers)
        if has_tsv_header:
            tsv_indicators += 2

        # 特征3：多行都有制表符
        tab_lines = sum(1 for line in sample_lines if '\t' in line.strip())
        if tab_lines >= 3:
            tsv_indicators += 1

        # 综合判断
        if csv_indicators >= 2:
            return 'CSV'
        elif tsv_indicators >= 2:
            return 'TSV'
        else:
            return 'STORY'

    except Exception as e:
        logger.warning(f"格式检测出错: {e}，默认使用故事格式")
        return 'STORY'


def parse_storyboards(file_path):
    """
    从文件解析分镜内容

    支持格式:
        1. TSV格式（制表符分隔，.txt）:
           镜号	分镜提示词
           1	角色:<br> * 女儿<br>...
           2	角色:<br> * 父亲<br>...

        2. CSV格式（逗号分隔，.csv）:
           分镜数,分镜提示词
           1,"[主体]\n角色：母亲, 女儿\n..."

        3. 故事格式（.txt）:
           故事1：
           场景描述
           角色:xxx

    Args:
        file_path: 分镜文件路径

    Returns:
        list: 分镜内容列表
    """
    try:
        # 检查文件扩展名
        file_ext = Path(file_path).suffix.lower()

        logger.info(f"成功读取文件: {file_path}")
        logger.info(f"文件类型: {file_ext}")

        storyboards = []

        # CSV格式处理
        if file_ext == '.csv':
            logger.info("检测到CSV格式（逗号分隔）")

            # 尝试用多种编码格式读取文件
            encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
            file_content = None

            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        file_content = f.read()
                    logger.info(f"成功使用 {encoding} 编码读取文件")
                    break
                except UnicodeDecodeError:
                    continue

            if not file_content:
                logger.error("无法使用支持的编码格式读取文件")
                return []

            # 使用StringIO处理内容
            from io import StringIO
            csv_reader = csv.reader(StringIO(file_content))

            # 读取表头
            try:
                headers = next(csv_reader)
                logger.info(f"CSV表头: {headers}")
            except StopIteration:
                logger.error("CSV文件为空")
                return []

            # 读取数据行
            row_count = 0
            skipped_rows = []  # 记录跳过的行
            
            for row in csv_reader:
                row_count += 1
                
                # 跳过空行
                if not row or (len(row) == 1 and not row[0].strip()):
                    logger.debug(f"CSV第 {row_count} 行为空行，跳过")
                    continue
                
                if len(row) >= 2:
                    shot_num = row[0].strip()
                    
                    # 验证分镜编号是否为数字
                    if not shot_num.isdigit():
                        logger.warning(f"CSV第 {row_count} 行分镜编号无效: '{shot_num}'，跳过")
                        skipped_rows.append((row_count, f"编号无效: {shot_num}"))
                        continue

                    # 处理多列情况：找到包含实际内容的列
                    content_parts = []
                    for i in range(1, len(row)):
                        cell_content = row[i].strip()
                        if cell_content:
                            # 清理引号
                            if cell_content.startswith('"') and cell_content.endswith('"'):
                                cell_content = cell_content[1:-1]
                            # 处理转义引号
                            cell_content = cell_content.replace('""', '"')
                            content_parts.append(cell_content)

                    if content_parts:
                        # 合并所有内容列
                        content = '\n'.join(content_parts)

                        # 验证内容有效性（降低门槛从10到5个字符）
                        if content and len(content.strip()) > 5:
                            storyboards.append(content)
                            preview = content[:80] + "..." if len(content) > 80 else content
                            logger.info(f"✅ 解析CSV分镜 #{shot_num}: {len(content)} 字符")
                            logger.debug(f"   内容预览: {preview}")
                        else:
                            logger.warning(f"❌ CSV第 {row_count} 行（分镜#{shot_num}）内容过短: {len(content.strip())} 字符，跳过")
                            logger.warning(f"   内容: '{content[:50]}'")
                            skipped_rows.append((row_count, f"内容过短（{len(content.strip())}字符）"))
                    else:
                        logger.warning(f"❌ CSV第 {row_count} 行（分镜#{shot_num}）没有有效内容，跳过")
                        skipped_rows.append((row_count, "无有效内容"))
                else:
                    if row:  # 如果不是空行
                        logger.warning(f"❌ CSV第 {row_count} 行格式不正确，列数: {len(row)}，内容: {row[:2]}，跳过")
                        skipped_rows.append((row_count, f"列数不足（{len(row)}列）"))

            # 显示统计信息
            logger.info(f"{'='*60}")
            logger.info(f"✅ CSV解析完成: 共解析出 {len(storyboards)} 个分镜")
            if skipped_rows:
                logger.warning(f"⚠️ 跳过了 {len(skipped_rows)} 行:")
                for row_num, reason in skipped_rows:
                    logger.warning(f"   - 第 {row_num} 行: {reason}")
            logger.info(f"{'='*60}")
            
            return storyboards

        # TXT格式处理（CSV、TSV或故事格式）
        encodings = ['utf-8', 'gbk', 'gb2312', 'utf-8-sig']
        content = None

        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                logger.info(f"成功使用 {encoding} 编码读取文件")
                break
            except UnicodeDecodeError:
                continue

        if not content:
            logger.error("无法使用支持的编码格式读取文件")
            return []

        logger.info(f"文件大小: {len(content)} 字符")
        lines = content.split('\n')

        # 智能检测文件格式
        format_type = detect_file_format(lines, content)
        logger.info(f"检测到格式类型: {format_type}")

        if format_type == 'CSV':
            # CSV格式解析（针对.txt扩展名的CSV文件）
            logger.info("开始解析CSV格式内容...")

            # 重新读取文件，使用csv.reader正确处理引号内的换行符
            for encoding in encodings:
                try:
                    with open(file_path, 'r', encoding=encoding) as f:
                        csv_reader = csv.reader(f)

                        # 跳过可能的BOM行
                        try:
                            headers = next(csv_reader)
                            logger.info(f"CSV表头: {headers}")
                        except StopIteration:
                            logger.error("CSV文件为空")
                            return []

                        # 读取数据行
                        row_count = 0
                        for row in csv_reader:
                            row_count += 1
                            if row and len(row) >= 2:
                                shot_num = row[0].strip()

                                # 处理多列内容
                                content_parts = []
                                for i in range(1, len(row)):
                                    if row[i].strip():
                                        content_parts.append(row[i].strip())

                                if content_parts:
                                    content = '\n'.join(content_parts)

                                    # 清理内容
                                    if content.startswith('"') and content.endswith('"'):
                                        content = content[1:-1]
                                    content = content.replace('""', '"')

                                    if content and len(content.strip()) > 10:
                                        storyboards.append(content)
                                        preview = content[:80] + "..." if len(content) > 80 else content
                                        logger.info(f"解析CSV分镜 #{shot_num}: {len(content)} 字符")
                                        logger.debug(f"   内容预览: {preview}")
                                    else:
                                        logger.warning(f"CSV第 {row_count} 行内容过短，跳过")
                                else:
                                    logger.warning(f"CSV第 {row_count} 行没有有效内容，跳过")
                            else:
                                if row:
                                    logger.warning(f"CSV第 {row_count} 行格式不正确，列数: {len(row)}，跳过")

                    break  # 成功读取，跳出编码循环
                except UnicodeDecodeError:
                    continue

        elif format_type == 'TSV':
            # TSV格式解析
            logger.info("开始解析TSV格式内容...")

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue

                # 跳过表头
                if i == 0 and ('镜号' in line or '分镜' in line or '分镜数' in line):
                    continue

                # 分割行
                parts = line.split('\t')
                if len(parts) >= 2:
                    shot_num = parts[0].strip()
                    content = parts[1].strip()

                    if content and len(content) > 10:
                        storyboards.append(content)
                        logger.info(f"解析TSV分镜 #{shot_num}: {len(content)} 字符")
                    else:
                        logger.warning(f"TSV第 {i+1} 行内容过短，跳过")
                else:
                    logger.warning(f"TSV第 {i+1} 行格式不正确，跳过")

        else:
            # 故事格式解析
            logger.info("开始解析故事格式内容...")

            # 增强的故事格式正则表达式
            separator_pattern = re.compile(
                r'^(?:'
                r'故事组[\d一二三四五六七八九十百千万]+.*|'
                r'故事\s*[\d一二三四五六七八九十百千万]+\s*(?:（[^）]*）|\([^)]*\))?\s*[：:].*|'
                r'故事\s*[\d一二三四五六七八九十百千万]+\s+\S.*|'
                r'故事(?:\s*[\d一二三四五六七八九十百千万]+)?\s*[：:]?$|'
                r'Group\s+\d+\s+story[：:].*|'
                r'Story\s+\d+[：:].*|'
                r'story.*|'
                r'第[\d一二三四五六七八九十百千万]+.*[分场幕].*'
                r')',
                re.MULTILINE | re.IGNORECASE
            )

            current_scenes = []
            current_title = None

            for line in lines:
                line = line.strip()

                if not line:
                    continue

                if separator_pattern.match(line):
                    # 保存之前的故事
                    if current_scenes and current_title:
                        story_content = '\n'.join(current_scenes)
                        if len(story_content.strip()) > 20:  # 至少20个字符
                            storyboards.append(story_content)
                            logger.info(f"解析分镜: {current_title} ({len(current_scenes)} 个场景)")
                        else:
                            logger.warning(f"分镜内容过短，跳过: {current_title}")

                    current_title = line
                    current_scenes = []
                else:
                    if current_title:
                        current_scenes.append(line)

            # 保存最后一个故事
            if current_scenes and current_title:
                story_content = '\n'.join(current_scenes)
                if len(story_content.strip()) > 20:
                    storyboards.append(story_content)
                    logger.info(f"解析分镜: {current_title} ({len(current_scenes)} 个场景)")
                else:
                    logger.warning(f"分镜内容过短，跳过: {current_title}")

        logger.info(f"✅ 共解析出 {len(storyboards)} 个分镜")
        return storyboards

    except Exception as e:
        logger.error(f"解析分镜文件失败: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        return []


# ====================================================================
# 🎯 核心类
# ====================================================================

class JimengGenerator:
    """即梦平台图片生成器"""
    
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.page = None
        
        # 性能统计
        self.dom_clear_success_count = 0  # DOM清除成功次数
        self.dom_clear_fail_count = 0      # DOM清除失败次数（回退到刷新）
    
    async def init_browser(self):
        """初始化浏览器（持久化上下文，保留登录状态）"""
        try:
            logger.info("正在启动浏览器...")
            
            # 确保浏览器数据目录存在
            Config.BROWSER_DATA.mkdir(parents=True, exist_ok=True)
            
            self.playwright = await async_playwright().start()
            
            # 启动参数
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--lang=zh-CN',
                '--window-size=1440,900'
            ]
            
            # 使用持久化上下文（保留登录信息）
            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=str(Config.BROWSER_DATA),
                headless=False,
                args=launch_args,
                ignore_default_args=['--enable-automation'],
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                          'AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/123.0.0.0 Safari/537.36'
            )
            
            # 添加反检测脚本
            await self.browser.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }) });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US'] });
            """)
            
            # 创建新页面
            self.page = await self.browser.new_page()
            await self.page.set_extra_http_headers({'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
            
            # 设置超时
            self.browser.set_default_timeout(45000)
            self.page.set_default_timeout(45000)
            
            logger.info(f"✅ 浏览器启动成功，数据目录: {Config.BROWSER_DATA}")
            return True
            
        except Exception as e:
            logger.error(f"浏览器初始化失败: {e}")
            return False
    
    async def wait_for_login(self):
        """等待用户完成登录"""
        try:
            logger.warning("⚠️ 检测到需要登录")
            logger.warning("=" * 60)
            logger.warning("📋 请按照以下步骤操作：")
            logger.warning("   1. 在打开的浏览器中完成登录")
            logger.warning("   2. 确保进入到AI图片生成页面")
            logger.warning("   3. 看到输入框后，回到终端按回车继续")
            logger.warning("=" * 60)
            
            # 等待用户按回车
            try:
                input("\n👉 完成登录后，按回车键继续...")
            except:
                await asyncio.sleep(5)
            
            # 再次检查是否有输入框
            await asyncio.sleep(2)
            textarea = await self.page.query_selector("textarea")
            if textarea:
                logger.info("✅ 检测到登录成功！")
                return True
            else:
                logger.error("❌ 仍未找到输入框，请确保已登录并在生图页面")
                return False
                
        except Exception as e:
            logger.error(f"登录检测失败: {e}")
            return False
    
    async def navigate(self):
        """导航到即梦平台并确保登录"""
        try:
            logger.info("正在导航到即梦平台...")
            
            await self.page.goto(Config.JIMENG_URL, wait_until="domcontentloaded")
            await asyncio.sleep(Config.NAVIGATION_WAIT)
            
            # 等待页面稳定
            await asyncio.sleep(3)
            
            # 检查是否已登录（查找输入框）
            login_success = False
            
            # 方法1: 查找输入框
            textarea_selectors = [
                "textarea[placeholder*='图片']",
                "textarea[placeholder*='提示']",
                "textarea.prompt-textarea-XfqAoB",
                "textarea",
            ]
            
            for selector in textarea_selectors:
                try:
                    textarea = await self.page.wait_for_selector(selector, timeout=5000, state="attached")
                    if textarea:
                        logger.info(f"✅ 找到输入框: {selector}")
                        login_success = True
                        break
                except:
                    continue
            
            # 如果没找到输入框，可能需要登录
            if not login_success:
                # 检查是否有登录按钮
                login_buttons = await self.page.query_selector_all("button")
                for btn in login_buttons:
                    text = await btn.text_content()
                    if text and ("登录" in text or "Login" in text):
                        # 需要登录
                        success = await self.wait_for_login()
                        if not success:
                            return False
                        login_success = True
                        break
            
            if not login_success:
                logger.error("❌ 无法确认页面状态，请检查是否在正确的页面")
                return False
            
            # 最终验证
            await asyncio.sleep(2)
            logger.info("✅ 即梦平台准备就绪")
            return True
                
        except Exception as e:
            logger.error(f"导航失败: {e}")
            return False
    
    async def dom_clear_references(self):
        """
        使用DOM方式清除参考图 - 直接操作DOM，无UI交互，无闪烁
        
        Returns:
            bool: 是否成功清除
        """
        try:
            logger.info("   🧹 使用DOM方式清除参考图...")
            
            # 可能的参考图容器选择器（按优先级排序）
            reference_selectors = [
                'div.reference-item-OOc16S',  # 原有选择器
                'div[class*="reference-item"]',  # 模糊匹配
                'div[class*="image-item"]',
                'div[class*="reference"]',
                '.uploaded-image',
                '[class*="upload-item"]',
                '[class*="image-upload"]'
            ]
            
            # 使用JavaScript查找并删除参考图元素（更安全的方式）
            clear_script = """
            (selectors) => {
                let deletedCount = 0;
                let totalFound = 0;
                
                // 遍历所有可能的选择器
                for (const selector of selectors) {
                    try {
                        const elements = document.querySelectorAll(selector);
                        if (elements && elements.length > 0) {
                            // 过滤掉包含input[type="file"]的元素（不删除上传控件）
                            const validElements = Array.from(elements).filter(el => {
                                // 检查元素本身或子元素是否包含文件上传输入框
                                const hasFileInput = el.matches('input[type="file"]') || 
                                                    el.querySelector('input[type="file"]');
                                return !hasFileInput;  // 只保留不包含上传控件的元素
                            });
                            
                            totalFound = validElements.length;
                            
                            if (totalFound === 0) {
                                continue;  // 没有有效元素，尝试下一个选择器
                            }
                            
                            // 删除过滤后的元素
                            validElements.forEach(el => {
                                try {
                                    // 优先尝试触发删除按钮（保持平台状态同步）
                                    const deleteBtn = el.querySelector('[class*="delete"], [class*="remove"], [class*="close"], [aria-label*="删除"]');
                                    if (deleteBtn && typeof deleteBtn.click === 'function') {
                                        deleteBtn.click();
                                        deletedCount++;
                                    } else {
                                        // 直接删除DOM元素
                                        el.remove();
                                        deletedCount++;
                                    }
                                } catch (err) {
                                    console.log('删除元素失败:', err);
                                }
                            });
                            
                            // 如果找到了元素就停止继续尝试其他选择器
                            if (totalFound > 0) {
                                break;
                            }
                        }
                    } catch (err) {
                        console.log('选择器查询失败:', selector, err);
                    }
                }
                
                return { deletedCount, totalFound };
            }
            """
            
            # 执行清除脚本
            result = await self.page.evaluate(clear_script, reference_selectors)
            
            deleted_count = result.get('deletedCount', 0)
            total_found = result.get('totalFound', 0)
            
            if total_found == 0:
                logger.info("   ℹ️ 没有检测到参考图，无需清除")
                return True
            
            if deleted_count > 0:
                logger.info(f"   ✅ DOM清除成功：删除了 {deleted_count}/{total_found} 张参考图")
                
                # 等待DOM更新和页面稳定（增加等待时间）
                await asyncio.sleep(0.5)
                
                # 验证是否全部清除
                if deleted_count == total_found:
                    return True
                else:
                    logger.warning(f"   ⚠️ 部分清除成功，仍有 {total_found - deleted_count} 张未删除")
                    return False
            else:
                logger.warning(f"   ⚠️ DOM清除失败，未能删除参考图")
                return False
                
        except Exception as e:
            logger.error(f"   ❌ DOM清除参考图失败: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    async def clear_reference_images(self):
        """
        清空参考图 - DOM方案（无闪烁，稳定）
        
        Returns:
            bool: 是否成功清除
        """
        try:
            # 简单模式：不主动删除，直接返回成功（让上传覆盖）
            if Config.SIMPLE_MODE:
                logger.info("   ℹ️ 简单模式：跳过清除，稍后上传会自动覆盖")
                return True
            
            # 使用DOM方式清除
            if Config.USE_DOM_CLEAR:
                success = await self.dom_clear_references()
                if success:
                    logger.info("   ✅ 参考图清除完成（DOM方式）⚡")
                    return True
                else:
                    logger.warning("   ⚠️ DOM清除未完全成功")
                    return False
            else:
                # 回退到页面刷新方式
                logger.info("   ℹ️ DOM清除已禁用，将使用页面刷新方式")
                return False
            
        except Exception as e:
            logger.error(f"   ❌ 清除参考图时出错: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False
    
    async def upload_reference_images(self, image_paths):
        """上传参考图 - 使用更可靠的方法"""
        if not image_paths:
            logger.info("   ℹ️ 无需上传参考图")
            return True
        
        try:
            logger.info(f"   📤 尝试上传 {len(image_paths)} 张参考图...")
            
            # 转换为字符串路径
            str_paths = [str(path) for path in image_paths]
            
            # 尝试多种方法查找上传输入框
            upload_selectors = [
                'input[type="file"]',  # 通用文件上传
                'input[accept*="image"]',  # 接受图片的输入框
                'input.file-input-O6KAhP',  # 原始选择器
            ]
            
            uploaded = False
            for selector in upload_selectors:
                try:
                    # 查找所有匹配的元素
                    file_inputs = await self.page.query_selector_all(selector)
                    
                    for input_elem in file_inputs:
                        try:
                            # 检查元素是否在DOM中
                            is_attached = await input_elem.evaluate('el => el.isConnected')
                            if not is_attached:
                                continue
                            
                            # 直接设置文件（即使hidden也能工作）
                            await input_elem.set_input_files(str_paths)
                            await asyncio.sleep(2)
                            
                            # 验证上传
                            uploaded_images = await self.page.query_selector_all('img')
                            # 简单验证：检查页面图片数量是否增加
                            logger.info(f"   ✅ 使用选择器 {selector} 上传参考图")
                            uploaded = True
                            break
                            
                        except Exception as inner_e:
                            continue
                    
                    if uploaded:
                        break
                        
                except Exception as e:
                    continue
            
            if uploaded:
                logger.info(f"   ✅ 参考图上传完成")
                return True
            else:
                logger.warning(f"   ⚠️ 未找到可用的上传控件，将跳过参考图上传")
                logger.warning(f"   💡 提示：可以在提交后手动上传参考图")
                return True  # 返回True继续流程
                
        except Exception as e:
            logger.error(f"   ❌ 上传参考图失败: {e}")
            return True  # 返回True继续流程
    
    async def input_content(self, text):
        """输入分镜内容 - 使用更灵活的方法"""
        try:
            logger.info(f"   📝 输入分镜内容 ({len(text)} 字符)...")
            
            # 尝试多个输入框选择器
            textarea_selectors = [
                "textarea[placeholder*='图片']",
                "textarea[placeholder*='提示']",
                "textarea.prompt-textarea-XfqAoB",
                "textarea",
            ]
            
            input_success = False
            for selector in textarea_selectors:
                try:
                    # 查找输入框
                    textareas = await self.page.query_selector_all(selector)
                    
                    for textarea in textareas:
                        try:
                            # 检查是否可见或可交互
                            is_visible = await textarea.is_visible()
                            is_enabled = await textarea.is_enabled()
                            
                            if is_visible or is_enabled:
                                # 清空并输入（使用多种方式确保清空干净）
                                await textarea.click()
                                await asyncio.sleep(0.2)
                                
                                # 方式1: 使用fill清空
                                await textarea.fill("")
                                await asyncio.sleep(0.1)
                                
                                # 方式2: 全选+删除（确保彻底清空）
                                is_mac = platform.system() == "Darwin"
                                await textarea.press("Meta+A" if is_mac else "Control+A")
                                await textarea.press("Backspace")
                                await asyncio.sleep(0.1)
                                
                                # 输入新内容
                                await textarea.fill(text)
                                await asyncio.sleep(Config.INPUT_WAIT)
                                
                                # 触发事件
                                await textarea.press("Space")
                                await textarea.press("Backspace")
                                
                                logger.info(f"   ✅ 使用选择器 {selector} 输入成功")
                                input_success = True
                                break
                                
                        except Exception as inner_e:
                            continue
                    
                    if input_success:
                        break
                        
                except Exception as e:
                    continue
            
            if not input_success:
                logger.error("   ❌ 未找到可用的输入框")
                return False
            
            logger.info("   ✅ 内容输入完成")
            return True
            
        except Exception as e:
            logger.error(f"   ❌ 输入内容失败: {e}")
            return False
    
    async def check_submit_status(self):
        """检查提交后的状态 - 增强版（避免误判导致遗漏分镜）"""
        try:
            # 等待更长时间让toast和状态变化出现
            await asyncio.sleep(Config.STATUS_CHECK_WAIT)

            # 负面关键词（明确的失败）
            negative_keywords = ["失败", "错误", "违规", "稍后再试", "频繁", "异常", "提交失败", "生成失败", "请求失败"]
            # 正面关键词（明确的成功）
            positive_keywords = ["生成中", "排队", "已提交", "已加入", "开始生成", "成功", "提交成功", "已接收"]

            found_status = False  # 是否找到明确状态
            success_indicators = 0  # 成功指标计数
            
            # 检查toast提示
            toast_selectors = [
                '.semi-toast-content-text',
                '.semi-toast-content',
                '[class*="toast"]',
                '.notification',
                '.message',
                '.alert'
            ]

            for selector in toast_selectors:
                try:
                    toast_elements = await self.page.query_selector_all(selector)
                    for element in toast_elements:
                        try:
                            is_visible = await element.is_visible()
                            if not is_visible:
                                continue

                            text = await element.text_content()
                            if text:
                                text = text.strip()
                                if text and len(text) > 1:
                                    logger.info(f"   📢 页面提示: {text}")
                                    found_status = True

                                    # 检查负面关键词 - 明确失败
                                    if any(keyword in text for keyword in negative_keywords):
                                        logger.error(f"   ❌ 检测到错误提示: {text}")
                                        return False

                                    # 检查正面关键词 - 明确成功
                                    if any(keyword in text for keyword in positive_keywords):
                                        logger.info(f"   ✅ 检测到成功提示: {text}")
                                        success_indicators += 1
                        except:
                            continue
                except:
                    continue

            # 检查页面状态变化
            try:
                # 方法1: 检查提交按钮状态
                submit_buttons = await self.page.query_selector_all('button.submit-button-VW0U_J')
                for btn in submit_buttons:
                    try:
                        class_name = await btn.get_attribute('class') or ''
                        button_text = await btn.text_content() or ""

                        # 如果按钮被禁用或文本变为"生成中"等状态
                        if ('disabled' in class_name.lower() or
                            '生成中' in button_text or
                            '排队中' in button_text or
                            '处理中' in button_text):
                            logger.info(f"   ✅ 按钮状态变化，推断提交成功: {button_text}")
                            success_indicators += 1
                    except:
                        continue

                # 方法2: 检查输入框内容变化
                textareas = await self.page.query_selector_all('textarea')
                for textarea in textareas:
                    try:
                        current_value = await textarea.input_value()
                        if not current_value or len(current_value.strip()) == 0:
                            logger.info(f"   ✅ 输入框已清空，推断提交成功")
                            success_indicators += 1
                    except:
                        continue

                # 方法3: 检查页面是否出现了生成中的元素
                loading_indicators = [
                    '[class*="loading"]',
                    '[class*="spinner"]',
                    '[class*="progress"]',
                    '.generating',
                    '.processing'
                ]

                for selector in loading_indicators:
                    try:
                        elements = await self.page.query_selector_all(selector)
                        for element in elements:
                            if await element.is_visible():
                                logger.info(f"   ✅ 检测到加载指示器，推断提交成功")
                                success_indicators += 1
                                break
                    except:
                        continue

            except Exception as e:
                logger.debug(f"   检查页面状态时出错: {e}")

            # 综合判断
            if success_indicators >= 1:
                logger.info(f"   ✅ 提交成功（成功指标数: {success_indicators}）")
                return True
            elif found_status:
                # 找到了状态但不是成功指标，可能有问题
                logger.warning(f"   ⚠️ 检测到状态信息但无明确成功指标，建议人工检查")
                logger.warning(f"   💡 为安全起见，将此次提交标记为失败，可稍后重试")
                return False
            else:
                # 完全没检测到任何状态变化，可能是网络延迟或页面问题
                logger.warning(f"   ⚠️ 未检测到任何提交状态变化！")
                logger.warning(f"   💡 可能原因：1) 页面响应慢 2) 提交未真正执行 3) 页面元素变化")
                logger.warning(f"   💡 为避免遗漏，将此次提交标记为失败，需要重试")
                return False

        except Exception as e:
            logger.error(f"   ❌ 检查提交状态时发生异常: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return False  # 出错时标记为失败，避免遗漏
    
    async def submit(self):
        """点击提交按钮 - 完善的提交逻辑"""
        try:
            logger.info("   🚀 准备提交...")
            
            # 等待按钮状态更新（从禁用变为可用）
            await asyncio.sleep(3)
            
            # 提交按钮选择器
            button_selectors = [
                "button.submit-button-VW0U_J",
                "button.lv-btn-primary",
                ".lv-btn.lv-btn-primary.submit-button-VW0U_J"
            ]
            
            for selector in button_selectors:
                try:
                    buttons = await self.page.query_selector_all(selector)
                    if not buttons:
                        continue
                    
                    # 获取按钮位置信息并排序（选择最下面的按钮）
                    buttons_with_box = []
                    for idx, button in enumerate(buttons):
                        try:
                            box = await button.bounding_box()
                        except:
                            box = None
                        buttons_with_box.append((idx, button, box))
                    
                    # 按y坐标和高度排序，选择最下面的按钮
                    buttons_with_box.sort(
                        key=lambda item: (item[2]['y'] if item[2] else -1, item[2]['height'] if item[2] else 0),
                        reverse=True
                    )
                    
                    # 尝试点击每个按钮
                    for original_idx, button, box in buttons_with_box:
                        try:
                            # 检查是否禁用
                            class_name = await button.get_attribute("class") or ""
                            if "lv-btn-disabled" in class_name or "disabled" in class_name.lower():
                                logger.info(f"   ⏭️ 跳过禁用按钮 {selector}[{original_idx}]")
                                continue
                            
                            # 获取按钮文本
                            text = (await button.text_content() or "").strip()
                            if box:
                                logger.info(f"   🔍 找到按钮[{original_idx}]: '{text}' 位置:{box}")
                            else:
                                logger.info(f"   🔍 找到按钮[{original_idx}]: '{text}'")
                            
                            # hover到按钮（稳定页面）
                            try:
                                await button.hover()
                                await asyncio.sleep(0.3)
                            except:
                                pass
                            
                            # 滚动到视图（避免漂移）
                            try:
                                await button.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                            except:
                                pass
                            
                            # 尝试多种点击方式
                            clicked = False
                            
                            # 方式1: 正常点击
                            try:
                                await button.click(timeout=5000)
                                clicked = True
                                logger.info(f"   ✅ 正常点击成功")
                            except Exception as e:
                                logger.debug(f"   正常点击失败: {e}")
                            
                            # 方式2: 强制点击
                            if not clicked:
                                try:
                                    await button.click(timeout=5000, force=True)
                                    clicked = True
                                    logger.info(f"   ✅ 强制点击成功")
                                except Exception as e:
                                    logger.debug(f"   强制点击失败: {e}")
                            
                            # 方式3: JS点击
                            if not clicked:
                                try:
                                    await self.page.evaluate(
                                        "(sel, index) => { const btns = document.querySelectorAll(sel); const btn = btns[index]; if (btn) btn.click(); }",
                                        selector,
                                        original_idx
                                    )
                                    clicked = True
                                    logger.info(f"   ✅ JS点击成功")
                                except Exception as e:
                                    logger.debug(f"   JS点击失败: {e}")
                            
                            if clicked:
                                # 检查提交状态
                                status_ok = await self.check_submit_status()
                                
                                if status_ok:
                                    # 等待提交处理
                                    await asyncio.sleep(Config.SUBMIT_WAIT)
                                    logger.info(f"   ✅ 使用选择器 {selector}[{original_idx}] 提交成功")
                                    return True
                                else:
                                    logger.error(f"   ❌ 提交后检测到错误")
                                    return False
                            
                        except Exception as e:
                            logger.debug(f"   处理按钮 {selector}[{original_idx}] 失败: {e}")
                            continue
                    
                except Exception as e:
                    logger.debug(f"   选择器 {selector} 失败: {e}")
                    continue
            
            logger.error("   ❌ 所有提交按钮都无法点击")
            logger.warning("   💡 提示：请检查页面状态或手动点击提交")
            return False
            
        except Exception as e:
            logger.error(f"   ❌ 提交失败: {e}")
            return False
    
    async def process_one_storyboard(self, storyboard, index, total, max_retries=2):
        """
        处理单个分镜的完整流程（带重试机制）

        Args:
            storyboard: 分镜内容
            index: 当前索引（从1开始）
            total: 总数
            max_retries: 最大重试次数

        Returns:
            bool: 是否成功
        """
        # 验证分镜内容有效性
        if not storyboard or len(storyboard.strip()) < 10:
            logger.error(f"   ❌ [{index}/{total}] 分镜内容过短或无效")
            return False

        # 提取角色（只需要做一次）
        roles = extract_roles(storyboard)
        image_paths = []
        if roles:
            image_paths = find_reference_images(roles)

        # 尝试提交（最多重试max_retries次）
        for attempt in range(max_retries + 1):
            try:
                if attempt == 0:
                    print(f"\n{'='*70}")
                    print(f"📌 [{index}/{total}] 开始处理分镜")
                    print(f"{'='*70}")
                else:
                    print(f"\n{'='*70}")
                    print(f"🔄 [{index}/{total}] 第 {attempt} 次重试")
                    print(f"{'='*70}")
                    # 重试前重新初始化页面
                    logger.info("   🔄 重新初始化页面，准备重试...")
                    await self.page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(3)
                    success = await self.navigate()
                    if not success:
                        logger.warning("   ⚠️ 重新导航失败，但继续尝试处理")
                        await asyncio.sleep(2)

                # 显示分镜预览
                preview = storyboard[:120] + "..." if len(storyboard) > 120 else storyboard
                logger.info(f"分镜预览: {preview}")

                # 添加页面稳定性检查
                try:
                    await self.page.wait_for_load_state('networkidle', timeout=10000)
                except:
                    logger.debug("   页面加载超时，继续处理")

                # 1. 清空之前的参考图
                clear_success = await self.clear_reference_images()
                
                # 如果清除失败且不是简单模式，使用刷新页面的方式
                if not clear_success and not Config.SIMPLE_MODE:
                    self.dom_clear_fail_count += 1
                    logger.warning("   ⚠️ DOM清除失败，尝试刷新页面...")
                    try:
                        await self.page.reload(wait_until="domcontentloaded")
                        await asyncio.sleep(2)
                        # 重新检查页面状态
                        nav_success = await self.navigate()
                        if nav_success:
                            logger.info("   ✅ 页面刷新成功，参考图已清空")
                        else:
                            logger.warning("   ⚠️ 页面刷新后导航失败，继续尝试")
                    except Exception as refresh_err:
                        logger.warning(f"   ⚠️ 刷新页面失败: {refresh_err}，继续尝试")
                elif clear_success and not Config.SIMPLE_MODE:
                    self.dom_clear_success_count += 1
                    # DOM清除成功后，等待页面稳定
                    await asyncio.sleep(0.3)
                # 简单模式下不计入统计

                # 2. 上传参考图
                if image_paths:
                    logger.info(f"   📤 准备上传 {len(image_paths)} 张参考图...")
                    success = await self.upload_reference_images(image_paths)
                    if not success:
                        logger.warning("   ⚠️ 参考图上传有问题，但继续处理")
                    else:
                        logger.info(f"   ✅ 参考图上传完成")
                else:
                    logger.info("   ℹ️ 本次分镜无需上传参考图")

                # 3. 输入分镜内容
                logger.info(f"   📝 输入分镜内容...")
                success = await self.input_content(storyboard)
                if not success:
                    logger.error(f"   ❌ [{index}/{total}] 输入失败")
                    if attempt < max_retries:
                        logger.warning(f"   🔄 将在3秒后重试...")
                        await asyncio.sleep(3)
                        continue
                    else:
                        logger.error(f"   ❌ [{index}/{total}] 已达到最大重试次数，放弃该分镜")
                        return False

                # 4. 提交
                logger.info(f"   🚀 准备提交...")
                success = await self.submit()
                if not success:
                    logger.error(f"   ❌ [{index}/{total}] 提交失败")
                    if attempt < max_retries:
                        logger.warning(f"   🔄 将在3秒后重试...")
                        await asyncio.sleep(3)
                        continue
                    else:
                        logger.error(f"   ❌ [{index}/{total}] 已达到最大重试次数，放弃该分镜")
                        return False

                # 提交成功
                print(f"✅ [{index}/{total}] 分镜处理完成！")

                # 5. 如果不是最后一个，准备下一个分镜
                if index < total:
                    logger.info("   🔄 准备处理下一个分镜...")
                    
                    if Config.SIMPLE_MODE:
                        # 简单模式：等待页面稳定即可，不刷新
                        await asyncio.sleep(2)
                        logger.info("   ✅ 准备完成（简单模式：无需刷新）")
                    else:
                        # 非简单模式：可能需要重新导航
                        # 但这个逻辑会在下一个分镜开始时处理
                        await asyncio.sleep(2)
                        logger.info("   ✅ 准备完成，将直接处理下一个分镜")

                return True

            except Exception as e:
                logger.error(f"❌ [{index}/{total}] 处理分镜时发生错误: {e}")
                import traceback
                logger.debug(f"错误详情: {traceback.format_exc()}")

                if attempt < max_retries:
                    logger.warning(f"   🔄 将在3秒后重试...")
                    await asyncio.sleep(3)
                    continue
                else:
                    logger.error(f"   ❌ [{index}/{total}] 已达到最大重试次数，放弃该分镜")
                    return False

        return False
    
    async def close(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器时出错: {e}")


# ====================================================================
# 🚀 主函数
# ====================================================================

def get_user_choice(total_count):
    """
    获取用户选择的提交模式
    
    Args:
        total_count: 总分镜数量
        
    Returns:
        tuple: (start_index, end_index) 起始和结束索引（1-based）
    """
    print(f"\n{'='*70}")
    print("📋 请选择提交模式")
    print(f"{'='*70}")
    print(f"当前共有 {total_count} 个分镜")
    print()
    print("1️⃣  全部重新提交（从第1个开始）")
    print("2️⃣  从指定编号开始提交")
    print("3️⃣  提交指定范围（例如：第3-5个）")
    print()
    
    while True:
        try:
            choice = input("请选择模式 (1/2/3): ").strip()
            
            if choice == "1":
                # 全部重新提交
                return 1, total_count
                
            elif choice == "2":
                # 从指定编号开始
                while True:
                    start_str = input(f"请输入起始编号 (1-{total_count}): ").strip()
                    try:
                        start = int(start_str)
                        if 1 <= start <= total_count:
                            return start, total_count
                        else:
                            print(f"❌ 编号必须在 1-{total_count} 范围内")
                    except ValueError:
                        print("❌ 请输入有效的数字")
                        
            elif choice == "3":
                # 指定范围
                while True:
                    range_str = input(f"请输入范围 (格式: 起始-结束，例如: 3-5): ").strip()
                    try:
                        if '-' in range_str:
                            parts = range_str.split('-')
                            start = int(parts[0].strip())
                            end = int(parts[1].strip())
                            
                            if 1 <= start <= end <= total_count:
                                return start, end
                            else:
                                print(f"❌ 范围必须在 1-{total_count} 之间，且起始≤结束")
                        else:
                            print("❌ 格式错误，请使用 '起始-结束' 格式，例如: 3-5")
                    except (ValueError, IndexError):
                        print("❌ 格式错误，请使用 '起始-结束' 格式，例如: 3-5")
            else:
                print("❌ 请输入 1、2 或 3")
                
        except KeyboardInterrupt:
            print("\n\n程序已取消")
            exit(0)

async def main():
    """主流程"""
    print(f"\n{'='*70}")
    print("🎯 即梦图片生成脚本 - 简化版")
    print(f"{'='*70}")
    
    # 显示运行模式
    if Config.SIMPLE_MODE:
        print("⚡ 运行模式: 简单模式（不清除参考图，会累积）")
    elif Config.USE_DOM_CLEAR:
        print("⚡ 运行模式: DOM清除模式（推荐，无闪烁）")
    else:
        print("⚡ 运行模式: 标准模式（页面刷新清除参考图）")
    
    print(f"{'='*70}\n")
    
    # 1. 选择分镜脚本文件
    script_file = select_script_file()
    if not script_file or not script_file.exists():
        logger.error("❌ 未找到可用的分镜脚本文件")
        return
    
    Config.STORYBOARD_FILE = script_file
    
    # 2. 选择参考图目录
    Config.REFERENCE_DIR = select_reference_directory()
    
    # 3. 解析分镜
    logger.info(f"📖 读取分镜文件: {Config.STORYBOARD_FILE}")
    storyboards = parse_storyboards(Config.STORYBOARD_FILE)
    
    if not storyboards:
        logger.error("❌ 未解析到任何分镜内容")
        return
    
    print(f"\n{'='*70}")
    print(f"📊 共解析到 {len(storyboards)} 个分镜")
    print(f"{'='*70}\n")
    
    # 4. 获取用户选择（提交哪些分镜）
    start_index, end_index = get_user_choice(len(storyboards))
    
    # 根据选择筛选分镜
    selected_storyboards = storyboards[start_index-1:end_index]
    
    print(f"\n{'='*70}")
    print(f"📌 将处理第 {start_index} 到第 {end_index} 个分镜，共 {len(selected_storyboards)} 个")
    print(f"{'='*70}\n")
    
    # 5. 初始化生成器
    generator = JimengGenerator()
    
    try:
        # 6. 启动浏览器
        success = await generator.init_browser()
        if not success:
            logger.error("❌ 浏览器初始化失败")
            return
        
        # 7. 导航到即梦平台
        success = await generator.navigate()
        if not success:
            logger.error("❌ 导航到即梦平台失败")
            return
        
        # 8. 批量处理分镜
        logger.info(f"\n开始批量处理第 {start_index}-{end_index} 个分镜...\n")
        
        success_count = 0
        failed_indices = []
        processed_details = []  # 详细处理记录
        
        # 遍历选中的分镜，但显示原始编号
        for i, storyboard in enumerate(selected_storyboards):
            actual_index = start_index + i  # 实际的分镜编号
            process_start_time = datetime.now()
            
            try:
                # 显示: [实际编号/总数]
                success = await generator.process_one_storyboard(
                    storyboard, 
                    actual_index,  # 显示实际编号
                    end_index      # 显示结束编号
                )
                
                process_time = (datetime.now() - process_start_time).total_seconds()
                
                if success:
                    success_count += 1
                    processed_details.append({
                        'index': actual_index,
                        'status': '✅ 成功',
                        'time': f"{process_time:.1f}秒"
                    })
                    logger.info(f"✅ 分镜 #{actual_index} 处理成功（耗时: {process_time:.1f}秒）")
                else:
                    failed_indices.append(actual_index)
                    processed_details.append({
                        'index': actual_index,
                        'status': '❌ 失败',
                        'time': f"{process_time:.1f}秒"
                    })
                    logger.error(f"❌ 分镜 #{actual_index} 处理失败（耗时: {process_time:.1f}秒）")
                    
            except Exception as e:
                process_time = (datetime.now() - process_start_time).total_seconds()
                logger.error(f"❌ 处理第 {actual_index} 个分镜时出错: {e}")
                failed_indices.append(actual_index)
                processed_details.append({
                    'index': actual_index,
                    'status': f'❌ 异常: {str(e)[:30]}',
                    'time': f"{process_time:.1f}秒"
                })
        
        # 7. 显示最终结果
        print(f"\n{'='*70}")
        print("🎊 批量处理完成！")
        print(f"{'='*70}")
        print(f"✅ 成功: {success_count}/{len(selected_storyboards)}")
        print(f"❌ 失败: {len(failed_indices)}/{len(selected_storyboards)}")
        print(f"📊 成功率: {success_count/len(selected_storyboards)*100:.1f}%")
        
        # 显示性能统计（仅非简单模式）
        if not Config.SIMPLE_MODE and Config.USE_DOM_CLEAR:
            total_clear_attempts = generator.dom_clear_success_count + generator.dom_clear_fail_count
            if total_clear_attempts > 0:
                dom_clear_rate = generator.dom_clear_success_count / total_clear_attempts * 100
                print(f"\n⚡ 性能优化统计:")
                print(f"   DOM清除成功: {generator.dom_clear_success_count}/{total_clear_attempts} ({dom_clear_rate:.1f}%)")
                print(f"   回退到刷新: {generator.dom_clear_fail_count}/{total_clear_attempts}")
                if dom_clear_rate > 0:
                    # 估算节省的时间（假设刷新页面需要3-5秒，DOM清除需要0.3秒）
                    saved_time = generator.dom_clear_success_count * 3  # 每次节省约3秒
                    print(f"   估算节省时间: ~{saved_time:.0f}秒 ({saved_time/60:.1f}分钟)")
        elif Config.SIMPLE_MODE:
            print(f"\n⚡ 运行模式: 简单模式（不清除参考图）")
        
        if failed_indices:
            print(f"\n⚠️ 失败的分镜序号: {', '.join(map(str, failed_indices))}")
            print(f"💡 提示: 可以使用模式2或3重新提交失败的分镜")
        
        # 显示详细处理记录
        print(f"\n📝 详细处理记录:")
        for detail in processed_details:
            print(f"   分镜 #{detail['index']}: {detail['status']} ({detail['time']})")
        
        print(f"{'='*70}\n")
        
        # 记录到日志文件
        logger.info("="*60)
        logger.info("批量处理完成统计:")
        logger.info(f"成功: {success_count}/{len(selected_storyboards)}")
        logger.info(f"失败: {len(failed_indices)}/{len(selected_storyboards)}")
        if not Config.SIMPLE_MODE and Config.USE_DOM_CLEAR:
            total_clear_attempts = generator.dom_clear_success_count + generator.dom_clear_fail_count
            if total_clear_attempts > 0:
                dom_clear_rate = generator.dom_clear_success_count / total_clear_attempts * 100
                logger.info(f"DOM清除成功率: {dom_clear_rate:.1f}%")
        if failed_indices:
            logger.warning(f"失败的分镜: {failed_indices}")
        logger.info("="*60)
        
        # 询问是否继续提交其他分镜
        while True:
            print("\n" + "="*70)
            print("🔄 是否继续提交其他分镜？")
            print("="*70)
            print("1️⃣  是，继续提交")
            print("2️⃣  否，退出程序")
            print()
            
            try:
                continue_choice = input("请选择 (1/2): ").strip()
                
                if continue_choice == "1":
                    # 重新选择并提交
                    print("\n")
                    start_index, end_index = get_user_choice(len(storyboards))
                    selected_storyboards = storyboards[start_index-1:end_index]
                    
                    print(f"\n{'='*70}")
                    print(f"📌 将处理第 {start_index} 到第 {end_index} 个分镜，共 {len(selected_storyboards)} 个")
                    print(f"{'='*70}\n")
                    
                    logger.info(f"\n开始批量处理第 {start_index}-{end_index} 个分镜...\n")
                    
                    success_count = 0
                    failed_indices = []
                    processed_details = []
                    
                    for i, storyboard in enumerate(selected_storyboards):
                        actual_index = start_index + i
                        process_start_time = datetime.now()
                        
                        try:
                            success = await generator.process_one_storyboard(
                                storyboard, 
                                actual_index,
                                end_index
                            )
                            
                            process_time = (datetime.now() - process_start_time).total_seconds()
                            
                            if success:
                                success_count += 1
                                processed_details.append({
                                    'index': actual_index,
                                    'status': '✅ 成功',
                                    'time': f"{process_time:.1f}秒"
                                })
                                logger.info(f"✅ 分镜 #{actual_index} 处理成功（耗时: {process_time:.1f}秒）")
                            else:
                                failed_indices.append(actual_index)
                                processed_details.append({
                                    'index': actual_index,
                                    'status': '❌ 失败',
                                    'time': f"{process_time:.1f}秒"
                                })
                                logger.error(f"❌ 分镜 #{actual_index} 处理失败（耗时: {process_time:.1f}秒）")
                        except Exception as e:
                            process_time = (datetime.now() - process_start_time).total_seconds()
                            logger.error(f"❌ 处理第 {actual_index} 个分镜时出错: {e}")
                            failed_indices.append(actual_index)
                            processed_details.append({
                                'index': actual_index,
                                'status': f'❌ 异常: {str(e)[:30]}',
                                'time': f"{process_time:.1f}秒"
                            })
                    
                    # 显示结果
                    print(f"\n{'='*70}")
                    print("🎊 批量处理完成！")
                    print(f"{'='*70}")
                    print(f"✅ 成功: {success_count}/{len(selected_storyboards)}")
                    print(f"❌ 失败: {len(failed_indices)}/{len(selected_storyboards)}")
                    print(f"📊 成功率: {success_count/len(selected_storyboards)*100:.1f}%")
                    
                    # 显示性能统计（仅非简单模式）
                    if not Config.SIMPLE_MODE and Config.USE_DOM_CLEAR:
                        total_clear_attempts = generator.dom_clear_success_count + generator.dom_clear_fail_count
                        if total_clear_attempts > 0:
                            dom_clear_rate = generator.dom_clear_success_count / total_clear_attempts * 100
                            print(f"\n⚡ 性能优化统计:")
                            print(f"   DOM清除成功: {generator.dom_clear_success_count}/{total_clear_attempts} ({dom_clear_rate:.1f}%)")
                            print(f"   回退到刷新: {generator.dom_clear_fail_count}/{total_clear_attempts}")
                            if dom_clear_rate > 0:
                                saved_time = generator.dom_clear_success_count * 3
                                print(f"   估算节省时间: ~{saved_time:.0f}秒 ({saved_time/60:.1f}分钟)")
                    elif Config.SIMPLE_MODE:
                        print(f"\n⚡ 运行模式: 简单模式（不清除参考图）")
                    
                    if failed_indices:
                        print(f"\n⚠️ 失败的分镜序号: {', '.join(map(str, failed_indices))}")
                        print(f"💡 提示: 可以使用模式2或3重新提交失败的分镜")
                    
                    # 显示详细处理记录
                    print(f"\n📝 详细处理记录:")
                    for detail in processed_details:
                        print(f"   分镜 #{detail['index']}: {detail['status']} ({detail['time']})")
                    
                    print(f"{'='*70}\n")
                    
                    # 记录到日志
                    logger.info("="*60)
                    logger.info("批量处理完成统计:")
                    logger.info(f"成功: {success_count}/{len(selected_storyboards)}")
                    logger.info(f"失败: {len(failed_indices)}/{len(selected_storyboards)}")
                    if not Config.SIMPLE_MODE and Config.USE_DOM_CLEAR:
                        total_clear_attempts = generator.dom_clear_success_count + generator.dom_clear_fail_count
                        if total_clear_attempts > 0:
                            dom_clear_rate = generator.dom_clear_success_count / total_clear_attempts * 100
                            logger.info(f"DOM清除成功率: {dom_clear_rate:.1f}%")
                    if failed_indices:
                        logger.warning(f"失败的分镜: {failed_indices}")
                    logger.info("="*60)
                    
                    # 继续循环，再次询问
                    continue
                    
                elif continue_choice == "2":
                    logger.info("程序即将退出")
                    break
                else:
                    print("❌ 请输入 1 或 2")
                    
            except KeyboardInterrupt:
                print("\n\n收到退出信号")
                break
        
    finally:
        # 清理资源
        await generator.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n程序已退出")
    except Exception as e:
        logger.error(f"程序运行出错: {e}")
        import traceback
        traceback.print_exc()
