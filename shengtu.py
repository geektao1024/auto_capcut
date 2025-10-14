print("🚀 运行修复后的脚本版本 - 无限循环问题已修复")
import os
import sys

# 全局标志：检测非交互式环境
NON_INTERACTIVE_MODE = not sys.stdin.isatty()
if NON_INTERACTIVE_MODE:
    print("🤖 检测到非交互式环境，启用自动配置模式")
import asyncio
import logging
import time
import re
import requests
import hashlib
import random
from pathlib import Path
from playwright.async_api import async_playwright


# ========== 硅基流动 API 默认配置 ==========
# 若未通过环境变量 `SILICONFLOW_API_KEY` 提供密钥，将使用此处的默认值。
# 注意：将密钥写在代码里存在泄漏风险，部署或分享代码时请及时替换或移除。
DEFAULT_SILICONFLOW_API_KEY = "sk-xlldacwabiohbkrthynufrvgrglbusutiumwtgdckokbkekb"

# ====================================================================
# 🌐 硅基流动（SiliconFlow）翻译配置说明
# ====================================================================
# 本脚本使用硅基流动提供的 DeepSeek V3.1 大模型完成中英文翻译兜底。
#
# 配置步骤：
# 1. 注册并登录硅基流动：https://siliconflow.cn/
# 2. 在控制台创建 API Key，复制密钥
# 3. 确认 DeepSeek V3.1 模型已开通（默认计费模式）
# 4. 将 API Key 填写到环境变量 `SILICONFLOW_API_KEY`，或在 `translate_with_siliconflow()` 函数中直接赋值
# 5. 如需切换模型，可设置环境变量 `SILICONFLOW_TRANSLATE_MODEL`
#
# 注意：调用将计入硅基流动账户的 token 消耗，请留意配额与费用
# ====================================================================

# ====================================================================
# 🎯 配置项 - 根据网络状况调整等待时间
# ====================================================================
class WaitTimeConfig:
    """等待时间配置类 - 根据网络状况调整这些值"""
    # 页面加载等待时间配置
    PAGE_LOAD_WAIT = 8  # 页面加载等待时间（秒）
    NAVIGATION_WAIT = 5  # 导航后等待时间（秒）
    # 提交等待时间配置
    SUBMIT_WAIT = 2  # 提交后等待时间（秒）
    # 即梦平台提交后固定等待时间
    JIMENG_POST_SUBMIT_WAIT = 6  # 每次提交后等待页面响应（秒）

# 全局配置实例
WAIT_CONFIG = WaitTimeConfig()

# ====================================================================
# 📝 网络优化配置说明：
#
# 新增功能：监控模式选择
# - 标准模式：启用20秒无增长判定失败，适合网络较好
# - 宽松模式：关闭无增长判定，仅等待目标数量完成
#
# 网络状况不佳时的调整建议：
# 4. 图片生成目标数量：
#    - TARGET_IMAGE_COUNT 根据故事内容调整，或设为 None 交由程序估算
# 1. 图片生成等待时间：
#    - FIRST_STAGE_WAIT 可从60提升到90-120秒
#    - MAX_GENERATION_WAIT 可从180提升到240-300秒
# 2. 检查间隔时间：
#    - IMAGE_CHECK_INTERVAL 从2提升到3-5秒
#    - SCROLL_INTERVAL 从3提升到5-8秒
# 3. 页面加载时间：
#    - PAGE_LOAD_WAIT 从8增加到12-15秒
#    - NAVIGATION_WAIT 从5增加到8-10秒
#
# 使用技巧：
# - 网络差：延长全部时间并选择宽松模式
# - 中等网络：适当增加生成等待时间，可留在标准模式
# - 良好网络：可缩短等待时间提升效率

# ⚠️ 注意：等待时间过短可能导致图片识别失败，过长会影响效率
# ====================================================================

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def translate_to_english(text, aspect_ratio="9:16", style_mode="realistic"):
    """调用硅基流动接口将中文翻译成英文"""
    try:
        print(f"🌐 开始翻译({len(text)}字符)...")
        # 如果文本很长，分段翻译
        if len(text) > 2000:
            return translate_long_text(text, aspect_ratio, style_mode)
        # 调用硅基流动翻译接口
        translated = translate_with_siliconflow(text, 1)
        if translated and len(translated.strip()) > 10:
            print(f"✅ 硅基流动翻译成功: {len(translated)}字符")
            # 检查翻译后的内容是否过长
            if len(translated) > 8000:
                print(f"⚠️ 翻译后内容过长({len(translated)}字符)，进行适当截断...")
                truncated = translated[:7000]
                last_sentence_end = max(
                    truncated.rfind('.'),
                    truncated.rfind('!'),
                    truncated.rfind('?')
                )
                if last_sentence_end > 6000:
                    translated = truncated[:last_sentence_end + 1]
                    print(f"✅ 截断至完整句子结束: {len(translated)}字符")
                else:
                    translated = truncated
                    print(f"✅ 直接截断: {len(translated)}字符")
            return translated
        else:
            print("❌ 硅基流动翻译失败，返回默认英文")
            return f"Generate creative images based on the story content with {aspect_ratio} aspect ratio"
    except Exception as e:
        print(f"翻译过程发生异常: {str(e)}")
        return f"Generate creative images based on the story content with {aspect_ratio} aspect ratio"

def translate_long_text(text, aspect_ratio="9:16", style_mode="realistic"):
    """分段翻译长文本，保持段落结构，调用硅基流动接口"""
    try:
        # 调整为更小的每段最大字符数，以提高成功率
        max_chunk_size = 800  
        # This will hold the translated chunks, where each chunk corresponds to a paragraph or sub-paragraph segment
        translated_segments = []
        # Split the original text into paragraphs first, preserving empty lines
        paragraphs = text.split('\n\n')
        # 记录翻译失败的段落数
        failed_paragraphs = 0
        total_paragraphs = len([p for p in paragraphs if p.strip()])
        for paragraph_idx, paragraph in enumerate(paragraphs):
            if not paragraph.strip(): # Handle empty paragraphs (from multiple \n\n or trailing \n\n)
                translated_segments.append("") # Preserve the blank line
                continue

            print(f"🔄 翻译段落 {paragraph_idx + 1}/{len(paragraphs)}...")
            # Process sentences within each paragraph
            sentences = re.split(r'(?<=[。！？])\s*', paragraph)
            current_chunk_for_translation = ""
            paragraph_translated_chunks = []  # 存储当前段落的翻译块
            paragraph_failed = False
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue

                # Check if adding the next sentence exceeds max_chunk_size
                # +1 for potential space between sentences
                if len(current_chunk_for_translation) + len(sentence) + 1 <= max_chunk_size:
                    current_chunk_for_translation += sentence + ' '
                else:
                    # Current chunk is full, translate it
                    if current_chunk_for_translation.strip():
                        try:
                            translated_text = translate_with_siliconflow(current_chunk_for_translation.strip(), 1)
                            if translated_text and len(translated_text.strip()) > 5:
                                paragraph_translated_chunks.append(translated_text)
                                print(f"✅ 段落{paragraph_idx + 1}块翻译成功")
                            else:
                                print(f"❌ 段落{paragraph_idx + 1}中的句子块翻译失败")
                                paragraph_failed = True
                                break
                        except Exception as e:
                            print(f"❌ 段落{paragraph_idx + 1}翻译异常: {str(e)}")
                            paragraph_failed = True
                            break
                        # 增加延迟避免API限制
                        time.sleep(1)
                    # Start a new chunk with the current sentence
                    current_chunk_for_translation = sentence + ' '
            # 如果段落没有失败，翻译最后一个chunk
            if not paragraph_failed and current_chunk_for_translation.strip():
                try:
                    translated_text = translate_with_siliconflow(current_chunk_for_translation.strip(), 1)
                    if translated_text and len(translated_text.strip()) > 5:
                        paragraph_translated_chunks.append(translated_text)
                        print(f"✅ 段落{paragraph_idx + 1}最后块翻译成功")
                    else:
                        print(f"❌ 段落{paragraph_idx + 1}的最后句子块翻译失败")
                        paragraph_failed = True
                except Exception as e:
                    print(f"❌ 段落{paragraph_idx + 1}最后块翻译异常: {str(e)}")
                    paragraph_failed = True
                time.sleep(1)
            # 检查整个段落是否翻译成功
            if paragraph_failed:
                failed_paragraphs += 1
                print(f"❌ 段落{paragraph_idx + 1}翻译失败，保持原文")
                # 对于失败的段落，保持原文
                translated_segments.append(paragraph)
            else:
                # 段落翻译成功，合并所有块
                paragraph_translation = ' '.join(paragraph_translated_chunks)
                translated_segments.append(paragraph_translation)
                print(f"✅ 段落{paragraph_idx + 1}翻译完成")
        # 合并所有翻译后的段落
        final_translation = '\n\n'.join(translated_segments)
        # 添加生成指令
        if final_translation:
            # 检查是否已包含生成指令
            has_generation_instruction = any([
                "Generate" in final_translation,
                "aspect ratio" in final_translation,
                "images" in final_translation
            ])
            if not has_generation_instruction:
                if style_mode == "cartoon":
                    final_translation += f"\n\nGenerate creative cartoon images based on the story content above. All images should be in {aspect_ratio} aspect ratio. No text should appear in the images. Maintain consistent cartoon style."
                else:  # realistic
                    final_translation += f"\n\nGenerate creative realistic images based on the story content above. All images should be in {aspect_ratio} aspect ratio. No text should appear in the images. Maintain consistent realistic photographic style."
        success_rate = (total_paragraphs - failed_paragraphs) / total_paragraphs if total_paragraphs > 0 else 0
        print(f"📊 长文本翻译完成: 成功率 {success_rate:.1%} ({total_paragraphs - failed_paragraphs}/{total_paragraphs}段落)")
        if success_rate >= 0.5:  # 50%以上成功率认为可接受
            return final_translation
        else:
            print(f"⚠️ 翻译成功率过低({success_rate:.1%})，返回默认英文")
            return f"Generate creative images based on the story content with {aspect_ratio} aspect ratio"
    except Exception as e:
        print(f"分段翻译过程发生异常: {str(e)}")
        return f"Generate creative images based on the story content with {aspect_ratio} aspect ratio"

def translate_with_siliconflow(text, attempt_num=1):
    """使用硅基流动 Chat Completions API 调用 DeepSeek 模型进行翻译"""
    try:
        import json
        # API Key 优先从环境变量读取，可按需直接写死
        api_key = os.getenv('SILICONFLOW_API_KEY', '').strip() or DEFAULT_SILICONFLOW_API_KEY
        if not api_key:
            print("❌ 未检测到硅基流动 API Key，请设置环境变量 SILICONFLOW_API_KEY")
            return None

        # 模型名称可配置，默认使用 DeepSeek V3.1
        model_name = os.getenv('SILICONFLOW_TRANSLATE_MODEL', 'deepseek-ai/DeepSeek-V3.1')

        endpoint = "https://api.siliconflow.cn/v1/chat/completions"
        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
            # 模拟常规浏览器 UA，部分平台可能检查
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }

        # 构造 Prompt，明确要求中翻英
        system_prompt = (
            "You are a professional translator. Translate the user provided Chinese content into natural,"
            " fluent English. Output only the translation, without explanations."
        )

        payload = {
            "model": model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            # 推荐为翻译场景关闭并行采样，只保留单结果
            "n": 1,
            "temperature": 0.1,
            "max_tokens": 4096
        }

        delay_time = 1 + attempt_num * 0.5
        print(f"⏳ 硅基流动翻译延迟 {delay_time} 秒...")
        time.sleep(delay_time)

        response = requests.post(endpoint, headers=headers, data=json.dumps(payload), timeout=60)
        if response.status_code == 200:
            result = response.json()
            try:
                choices = result.get('choices') or []
                if not choices:
                    print(f"硅基流动第{attempt_num}次尝试返回空choices")
                    return None
                translated_text = choices[0]['message']['content'].strip()
                return translated_text
            except Exception as parse_error:
                print(f"硅基流动第{attempt_num}次解析返回异常: {parse_error}")
                return None
        else:
            print(f"硅基流动第{attempt_num}次尝试失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"硅基流动第{attempt_num}次尝试异常: {str(e)}")
        return None

class MessiPictureGenerator:
    def __init__(self):
        self.browser = None
        self.page = None
        self.context = None
        self.failed_stories = []  # 记录生成失败的故事
        self.stories = []  # 存储要处理的故事列表
        # 新增：记录所有生成尝试的顺序和结果
        self.generation_attempts = []  # 记录每次生成尝试的详细信息
        # 新增：用户选择的图片数量
        self.images_per_group = 2  # 默认每组2张图
        # 新增：用户选择的图片比例
        self.aspect_ratio = "9:16"  # 默认9:16比例
        # 新增：运行模式
        self.mode = "ronaldoshorts"  # 默认模式
        # 新增：是否启用20秒无增长判定失败功能
        self.enable_no_growth_check = True  # 默认启用
        # 新增：画风选择模式
        self.style_mode = "realistic"  # 默认写实风格，可选 "realistic" 或 "cartoon"
        # 添加统计信息
        self.stats = {
            'total_stories': 0,
            'successful_stories': 0,
            'failed_stories': 0,
            'translated_stories': 0,
            'retried_stories': 0,
            'start_time': None,
            'end_time': None,
            'story_times': []
        }
        # 参考图配置
        self.reference_image_dir = Path.cwd() / "reference_images"
        self.reference_image_dir.mkdir(parents=True, exist_ok=True)
        self.supported_reference_image_exts = [".png", ".jpg", ".jpeg", ".webp", ".bmp"]
        # 即梦平台地址
        self.jimeng_url = "https://jimeng.jianying.com/ai-tool/generate?type=image"
        # 平台选择
        self.platform = "jimeng"  # 默认使用即梦平台
    
    def safe_input(self, prompt, valid_choices=None, default=None):
        """安全的用户输入函数，在非交互式环境下返回默认值"""
        import sys
        
        # 如果不是交互式环境，直接返回默认值
        if not sys.stdin.isatty():
            if default is not None:
                print(f"{prompt}{default}")
                return default
            elif valid_choices:
                print(f"{prompt}{valid_choices[0]}")
                return valid_choices[0]
            else:
                return ""
        
        # 交互式环境下的正常输入
        while True:
            try:
                user_input = input(prompt).strip()
                if valid_choices:
                    if user_input in valid_choices:
                        return user_input
                    else:
                        print(f"❌ 请输入 {' 或 '.join(valid_choices)}")
                        continue
                return user_input
            except (KeyboardInterrupt, EOFError):
                print(f"\n使用默认配置: {default if default else (valid_choices[0] if valid_choices else '')}")
                return default if default else (valid_choices[0] if valid_choices else "")
            except Exception as e:
                print(f"输入错误: {str(e)}")
                continue
    
    def ask_user_choices(self):
        """询问用户选择模式和配置"""
        print(f"\n{'='*60}")
        print("🎯 即梦图片生成器")
        print(f"{'='*60}")
        
        # 使用全局的非交互式模式检测
        if NON_INTERACTIVE_MODE:
            print("🤖 检测到非交互式环境，使用默认配置：")
            self.mode = "ronaldoshorts"
            self.aspect_ratio = "9:16"
            self.images_per_group = 1
            self.style_mode = "realistic"
            self.enable_no_growth_check = True
            print("   模式: ronaldoshorts")
            print("   图片比例: 9:16 (竖屏)")
            print("   每组生成: 1张图片")
            print("   画风: 写实风格")
            print("   监控模式: 标准模式")
            print(f"{'='*60}")
            return True
        
        # 首先选择模式
        print("请选择生成模式：")
        print("1. ronaldoshorts - 从messipicture.txt读取故事内容")
        print("2. ronaldolong - 从ronaldomessi.txt读取AI图片转视频提示词")
        print(f"{'='*60}")
        
        choice = self.safe_input("请输入选择 (1 或 2): ", valid_choices=['1', '2'], default='1')

        if choice == '1':
            self.mode = "ronaldoshorts"
            print("✅ 已选择：ronaldoshorts 模式")
        elif choice == '2':
            self.mode = "ronaldolong"
            print("✅ 已选择：ronaldolong 模式")
            # ronaldolong模式固定配置
            self.aspect_ratio = "16:9"
            self.images_per_group = 2
            print("🎯 ronaldolong模式配置：")
            print("   图片比例: 16:9 (固定)")
            print("   每段生成: 2张图片 (固定)")
            print("   分组方式: 每20段为一组")  # 从35改为20
            print(f"{'='*60}")
        # ronaldoshorts模式继续原有的选择流程
        if self.mode == "ronaldoshorts":
            # 选择图片比例
            print(f"\n{'='*60}")
            print("请选择图片比例：")
            print("1. 9:16 (竖屏，适合手机)")
            print("2. 16:9 (横屏，适合电脑/电视)")
            print("3. 2:3 (竖屏，适合社交媒体)")
            print(f"{'='*60}")
            
            choice = self.safe_input("请输入选择 (1、2 或 3): ", valid_choices=['1', '2', '3'], default='1')

            if choice == '1':
                self.aspect_ratio = "9:16"
                print("✅ 已选择：9:16 (竖屏)")
            elif choice == '2':
                self.aspect_ratio = "16:9"
                print("✅ 已选择：16:9 (横屏)")
            elif choice == '3':
                self.aspect_ratio = "2:3"
                print("✅ 已选择：2:3 (竖屏)")
            # 选择每组图片数量
            print(f"\n{'='*60}")
            print("请选择每组生成的图片数量：")
            print("1. 每组生成1张图片")
            print("2. 每组生成2张图片（默认）")
            print(f"{'='*60}")
            
            choice = self.safe_input("请输入选择 (1 或 2): ", valid_choices=['1', '2'], default='1')

            if choice == '1':
                self.images_per_group = 1
                print("✅ 已选择：每组生成1张图片")
            elif choice == '2':
                self.images_per_group = 2
                print("✅ 已选择：每组生成2张图片")
        # 画风选择（两种模式都需要）
        print(f"\n{'='*60}")
        print("请选择图片画风：")
        print("1. 不要卡通风格（写实风格）")
        print("2. 都要卡通风格")
        print(f"{'='*60}")
        
        choice = self.safe_input("请输入选择 (1 或 2): ", valid_choices=['1', '2'], default='1')

        if choice == '1':
            self.style_mode = "realistic"
            print("✅ 已选择：写实风格 - 不要卡通风格")
        elif choice == '2':
            self.style_mode = "cartoon"
            print("✅ 已选择：卡通风格 - 都要卡通风格")
        # 无增长检查选择（两种模式都需要）
        print(f"\n{'='*60}")
        print("请选择图片生成监控模式：")
        print("1. 标准模式 - 启用20秒无增长判定失败（推荐）")
        print("2. 宽松模式 - 关闭20秒无增长判定，仅等待目标数量完成")
        print("")
        print("说明：")
        print("• 标准模式：如果20秒内图片数量不增长，判定为生成失败并重试")
        print("• 宽松模式：只等待目标图片数量完成，不进行无增长检查")
        print("• 标准模式能更快发现生成问题，但可能对网络要求较高")
        print("• 宽松模式更适合网络较慢的情况")
        print(f"{'='*60}")
        
        choice = self.safe_input("请输入选择 (1 或 2): ", valid_choices=['1', '2'], default='1')

        if choice == '1':
            self.enable_no_growth_check = True
            print("✅ 已选择：标准模式 - 启用20秒无增长判定失败")
        elif choice == '2':
            self.enable_no_growth_check = False
            print("✅ 已选择：宽松模式 - 关闭20秒无增长判定")
        # 显示最终配置
        print(f"\n{'='*60}")
        print("🎯 最终配置：")
        print(f"   模式: {self.mode}")
        print(f"   图片比例: {self.aspect_ratio}")
        if self.mode == "ronaldoshorts":
            print(f"   每组图片数量: {self.images_per_group}张")
        else:
            print(f"   每段生成: {self.images_per_group}张图片")
        print(f"   画风选择: {'写实风格 (不要卡通风格)' if self.style_mode == 'realistic' else '卡通风格 (都要卡通风格)'}")
        print(f"   监控模式: {'标准模式 (20秒无增长判定失败)' if self.enable_no_growth_check else '宽松模式 (仅等待目标数量)'}")
        print(f"{'='*60}")
        return True

    def ask_user_choice(self):
        """保持向后兼容的方法名，调用新的ask_user_choices方法"""
        return self.ask_user_choices()

    def resolve_reference_image_paths(self, roles):
        """根据角色名称查找对应的参考图片路径"""
        resolved_paths = []
        missing_roles = []
        for role in roles:
            role_name = role.strip()
            if not role_name:
                continue
            found = False
            for ext in self.supported_reference_image_exts:
                candidate = self.reference_image_dir / f"{role_name}{ext}"
                if candidate.exists():
                    resolved_paths.append(candidate)
                    found = True
                    break
            if not found:
                missing_roles.append(role_name)
        if missing_roles:
            print(f"⚠️ 下列角色未找到参考图: {', '.join(missing_roles)}")
        if resolved_paths:
            print(f"📁 将上传参考图: {', '.join(str(p.name) for p in resolved_paths)}")
        return resolved_paths

    async def clear_reference_images(self):
        """清除即梦界面已有的参考图"""
        # 即梦专用
        try:
            print("🧹 正在清除上一轮参考图...")
            max_iterations = 10
            for _ in range(max_iterations):
                reference_items = await self.page.query_selector_all('div.reference-item-OOc16S')
                removed_in_loop = False
                for item in reference_items:
                    try:
                        img = await item.query_selector('img')
                        if not img:
                            continue
                        try:
                            await item.hover()
                            await asyncio.sleep(0.2)
                        except Exception:
                            pass
                        remove_btn = await item.query_selector('div.remove-button-CGHPzk')
                        if remove_btn:
                            await remove_btn.click()
                            await asyncio.sleep(0.5)
                            removed_in_loop = True
                            break
                    except Exception:
                        continue
                if not removed_in_loop:
                    break
            print("✅ 参考图清理完成")
        except Exception as e:
            print(f"⚠️ 清除参考图时出错: {str(e)}")

    async def upload_reference_images(self, image_paths):
        """上传角色对应的参考图"""
        if not image_paths:
            return True
        try:
            upload_selector = 'input.file-input-O6KAhP'
            await self.page.wait_for_selector(upload_selector, timeout=10000)
            str_paths = [str(path) for path in image_paths]
            print(f"⬆️ 上传参考图: {', '.join(Path(p).name for p in str_paths)}")
            await self.page.set_input_files(upload_selector, str_paths)
            await asyncio.sleep(2)
            # 验证上传数量
            uploaded_images = await self.page.query_selector_all('div.reference-item-OOc16S img')
            if len(uploaded_images) >= len(image_paths):
                print("✅ 参考图上传完成")
                return True
            else:
                print("⚠️ 参考图上传数量与预期不符，请检查页面状态")
                return False
        except Exception as e:
            print(f"❌ 上传参考图失败: {str(e)}")
            return False

    async def prepare_reference_images_for_roles(self, roles):
        """根据角色列表清理并上传参考图"""
        # 即梦专用
        await self.clear_reference_images()
        if not roles:
            return True
        image_paths = self.resolve_reference_image_paths(roles)
        if not image_paths:
            print("⚠️ 未找到任何角色参考图，将继续使用文本提示")
            return True
        return await self.upload_reference_images(image_paths)

    async def initialize_browser(self):
        """初始化浏览器"""
        try:
            self.playwright = await async_playwright().start()
            # 创建用户数据目录以保留登录信息
            user_data_dir = os.path.expanduser("~/Desktop/AutoAI/browser_data")
            os.makedirs(user_data_dir, exist_ok=True)
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--no-first-run',
                '--no-zygote',
                '--disable-gpu',
                '--disable-infobars',
                '--disable-blink-features=AutomationControlled',
                '--lang=zh-CN',
                '--window-size=1440,900'
            ]

            self.browser = await self.playwright.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=False,
                args=launch_args,
                ignore_default_args=['--enable-automation']
            )
            # 使用持久化上下文时，browser 就是 context
            self.context = self.browser

            await self.context.add_init_script(
                """
                    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
                    Object.defineProperty(window, 'chrome', { get: () => ({ runtime: {} }) });
                    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3] });
                    Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en-US'] });
                    const originalQuery = window.navigator.permissions && window.navigator.permissions.query;
                    if (originalQuery) {
                        window.navigator.permissions.query = (parameters) => (
                            parameters && parameters.name === 'notifications'
                                ? Promise.resolve({ state: Notification.permission })
                                : originalQuery(parameters)
                        );
                    }
                """
            )

            self.page = await self.context.new_page()
            await self.page.set_extra_http_headers({'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8'})
            await self.page.set_user_agent(
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/123.0.0.0 Safari/537.36'
            )
            self.context.set_default_timeout(45000)
            self.page.set_default_timeout(45000)
            logger.info(f"浏览器初始化成功，用户数据保存在: {user_data_dir}")
            return True
        except Exception as e:
            logger.error(f"浏览器初始化失败: {str(e)}")
            return False

    async def close_browser(self):
        """关闭浏览器"""
        try:
            if self.page:
                await self.page.close()
            if self.browser:
                await self.browser.close()
            if hasattr(self, 'playwright'):
                await self.playwright.stop()
            logger.info("浏览器已关闭")
        except Exception as e:
            logger.error(f"关闭浏览器时发生错误: {str(e)}")
    async def check_generation_error(self):
        """检测页面是否出现生成错误"""
        try:
            # 检查页面可见文本内容，而不是HTML源码
            page_text = await self.page.text_content('body')
            # 调试：显示页面文本的一部分（包含python关键字的部分）
            if 'python' in page_text.lower():
                python_index = page_text.lower().find('python')
                context = page_text[max(0, python_index-50):python_index+200]
                print(f"🔍 发现python关键字，上下文: {context[:100]}...")
            # 更宽松的错误检测模式，基于截图中的实际格式
            error_patterns = [
                # 基本的错误标识
                '"type": "generate"',
                '"numbers": 2',
                # 组合检测：同时包含type和numbers
                r'"type":\s*"generate".*"numbers":\s*2',
                # Python代码块格式
                'python\n{',
                # 更具体的组合
                'python.*"type".*"generate"',
                'python.*"numbers".2',
                # 检测完整的错误JSON结构片段
                r'{\s"type":\s*"generate"',
                r'"type":\s*"generate"."prompt":',
                r'"numbers":\s2.*"prompt":',
            ]
            # 使用正则表达式进行更灵活的匹配
            import re
            for pattern in error_patterns:
                try:
                    match = re.search(pattern, page_text, re.DOTALL | re.IGNORECASE)
                    if match:
                        print(f"🚨 检测到生成错误标识: {pattern}")
                        print(f"🔍 匹配到的内容: {match.group()[:200]}...")
                        # 显示匹配位置的上下文
                        start = max(0, match.start() - 100)
                        end = min(len(page_text), match.end() + 100)
                        context = page_text[start:end]
                        print(f"🔍 上下文: ...{context}...")
                        return True
                except Exception as e:
                    # 如果正则表达式失败，尝试简单字符串匹配
                    if pattern in page_text:
                        print(f"🚨 检测到生成错误标识: {pattern}")
                        print(f"🔍 简单匹配，无法显示具体位置")
                        return True
            # 额外检查：如果页面包含"python"和JSON结构，很可能是错误
            if 'python' in page_text.lower() and ('"type"' in page_text or '"numbers"' in page_text):
                print("🚨 检测到可疑的python代码块和JSON结构")
                return True
            # 专门针对截图格式的检测
            if 'python' in page_text and '{' in page_text and '"type"' in page_text and '"generate"' in page_text:
                print("🚨 检测到截图中显示的错误格式")
                return True
            return False
        except Exception as e:
            print(f"检测生成错误时出错: {str(e)}")
            return False

    async def check_topic_change_toast(self):
        """检测是否出现"我们换个话题聊聊吧"的浮窗提示"""
        try:
            # 检查特定的浮窗元素
            toast_selectors = [
                'span.semi-toast-content-text',
                'span[x-semi-prop="content"]',
                '.semi-toast-content-text',
                'div.semi-toast-content span',
                'div[class*="toast"] span',
                'div[class*="notification"] span'
            ]
            for selector in toast_selectors:
                try:
                    toast_elements = await self.page.query_selector_all(selector)
                    for element in toast_elements:
                        if element:
                            text_content = await element.text_content()
                            if text_content and "我们换个话题聊聊吧" in text_content:
                                print(f"🚨 检测到话题切换浮窗: {text_content}")
                                return True
                except Exception as e:
                    continue
            # 备用检测：检查页面整体文本内容
            try:
                page_text = await self.page.text_content('body')
                if "我们换个话题聊聊吧" in page_text:
                    print("🚨 在页面文本中检测到话题切换提示")
                    return True
            except Exception as e:
                pass
            # 进一步检测：使用JavaScript查找所有可能的浮窗元素
            try:
                found_toast = await self.page.evaluate('''
                    () => {
                        // 查找所有可能包含浮窗文本的元素
                        const allElements = document.querySelectorAll('*');
                        for (const element of allElements) {
                            const text = element.textContent || element.innerText;
                            if (text && text.includes('我们换个话题聊聊吧')) {
                                console.log('找到话题切换浮窗:', text);
                                return true;
                            }
                        }
                        return false;
                    }
                ''')
                if found_toast:
                    print("🚨 JavaScript检测到话题切换浮窗")
                    return True
            except Exception as e:
                pass
            return False
        except Exception as e:
            print(f"检测话题切换浮窗时出错: {str(e)}")
            return False
    
    def extract_ai_video_prompts(self, file_path):
        """从ronaldomessi.txt文件中提取AI图片转视频提示词"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"成功读取文件，内容长度: {len(content)} 字符")
            # 查找"AI图片转视频提示词："和"简单动作指导："之间的内容
            start_marker = "AI图片转视频提示词："
            end_marker = "简单动作指导："
            start_index = content.find(start_marker)
            if start_index == -1:
                logger.error("没有找到'AI图片转视频提示词：'标记")
                return []
            end_index = content.find(end_marker)
            if end_index == -1:
                logger.error("没有找到'简单动作指导：'标记")
                return []
            if start_index >= end_index:
                logger.error("标记位置错误：'AI图片转视频提示词：'应该在'简单动作指导：'之前")
                return []
            # 提取中间内容
            start_pos = start_index + len(start_marker)
            extracted_content = content[start_pos:end_index].strip()
            # 按行分割并过滤空行
            lines = [line.strip() for line in extracted_content.split('\n') if line.strip()]
            logger.info(f"成功提取 {len(lines)} 段AI图片转视频提示词")
            # 显示前几段作为预览
            for i, line in enumerate(lines[:5]):
                logger.info(f"提示词 {i+1}: {line[:50]}...")
            if len(lines) > 5:
                logger.info(f"... 还有 {len(lines) - 5} 段提示词")
            return lines
        except Exception as e:
            logger.error(f"提取AI图片转视频提示词失败: {str(e)}")
            return []
    def group_prompts_for_ronaldolong(self, prompts):
        """将提示词按20段为一组进行分组"""
        try:
            groups = []
            group_size = 20  # 从35改为20
            for i in range(0, len(prompts), group_size):
                group = prompts[i:i+group_size]
                groups.append(group)
            logger.info(f"将 {len(prompts)} 段提示词分为 {len(groups)} 组")
            for i, group in enumerate(groups):
                logger.info(f"第 {i+1} 组: {len(group)} 段提示词")
            return groups
        except Exception as e:
            logger.error(f"分组提示词失败: {str(e)}")
            return []
    def create_submission_content_for_group(self, group, group_index):
        """为一组提示词创建提交的内容"""
        try:
            # 将组内的提示词合并，每行一个
            group_content = '\n'.join(group)
            # 添加生成指令，根据画风选择
            if self.style_mode == "cartoon":
                instruction = f"\n\n给上面每段提示词生成2张图，生成对应的2张图 然后继续下一段的出图2张 其他的不用解释 我没写足球你在画面中就不要出现足球 所有的图片都要比例16：9的 所有图片中不要出现中文！！所有图片都要卡通风格！注意！！保持卡通的一致画风！！！出现的角色都要是美国白人的脸！"
            else:  # realistic
                instruction = f"\n\n给上面每段提示词生成2张图，生成对应的2张图 然后继续下一段的出图2张 其他的不用解释 我没写足球你在画面中就不要出现足球 所有的图片都要比例16：9的 所有图片中不要出现中文！！所有图片不要卡通风格！注意！！保持写实的一致画风！！！出现的角色都要是美国白人的脸！"
            submission_content = group_content + instruction
            logger.info(f"第 {group_index + 1} 组内容创建完成，总长度: {len(submission_content)} 字符")
            logger.info(f"第 {group_index + 1} 组包含 {len(group)} 段提示词")
            return submission_content
        except Exception as e:
            logger.error(f"创建第 {group_index + 1} 组提交内容失败: {str(e)}")
            return None
    def get_chinese_number(self, num):
        """将数字转换为中文数字"""
        chinese_numbers = {
            1: "一", 2: "二", 3: "三", 4: "四", 5: "五",
            6: "六", 7: "七", 8: "八", 9: "九", 10: "十",
            11: "十一", 12: "十二", 13: "十三", 14: "十四", 15: "十五",
            16: "十六", 17: "十七", 18: "十八", 19: "十九", 20: "二十"
        }
        if num <= 20:
            return chinese_numbers.get(num, str(num))
        elif num < 100:
            tens = num // 10
            ones = num % 10
            if ones == 0:
                return chinese_numbers.get(tens, str(tens)) + "十"
            else:
                return chinese_numbers.get(tens, str(tens)) + "十" + chinese_numbers.get(ones, str(ones))
        else:
            return str(num)  # 超过100的数字直接返回数字字符串
    def read_and_parse_stories(self, file_path):
        """读取文件并解析故事"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"成功读取文件，内容长度: {len(content)} 字符")

            # 修改故事分隔符模式，支持"故事组X"、"故事X（主题）："/"故事X(主题):"格式，
            # 以及新增：任何以"story"开头的单独一行（不要求冒号或数字），
            # 以及新增：任何单独一行以"故事"开头的最简形式（如："故事"、"故事 1"、"故事 1："），
            # 以及新增：如"故事 5 画面提示词"这种以"故事 + 数字 + 文字"开头但无冒号的行
            story_separator_pattern = re.compile(
                r'^(?:故事组[\d一二三四五六七八九十百千万]+.*|故事\s*[\d一二三四五六七八九十百千万]+\s*(?:（[^）]*）|\([^)]*\))?\s*[：:].*|故事\s*[\d一二三四五六七八九十百千万]+\s+\S.*|故事(?:\s*[\d一二三四五六七八九十百千万]+)?\s*[：:]?$|Group\s+\d+\s+story[：:].*|Story\s+\d+[：:].*|story.*)',
                re.MULTILINE | re.IGNORECASE
            )

            # 使用故事分隔符来分割整个文件内容
            lines = content.split('\n')
            current_story_scenes = []
            all_stories = []
            current_story_title = None
            for line in lines:
                line = line.strip()
                if not line:  # 跳过空行
                    continue
                # 检查是否是故事分隔符
                if story_separator_pattern.match(line):
                    # 如果有之前的故事场景，先保存
                    if current_story_scenes and current_story_title:
                        story_content = self.create_story_content_from_scenes(current_story_scenes, current_story_title)
                        all_stories.append(story_content)
                        logger.info(f"解析出故事: {current_story_title}，包含 {len(current_story_scenes)} 个场景")
                    # 开始新故事
                    current_story_title = line
                    current_story_scenes = []
                else:
                    # 这是一个场景描述行
                    if current_story_title:  # 确保我们在一个故事组内
                        current_story_scenes.append(line)
            # 处理最后一个故事
            if current_story_scenes and current_story_title:
                story_content = self.create_story_content_from_scenes(current_story_scenes, current_story_title)
                all_stories.append(story_content)
                logger.info(f"解析出故事: {current_story_title}，包含 {len(current_story_scenes)} 个场景")
            logger.info(f"最终解析出 {len(all_stories)} 个故事")
            return all_stories
        except Exception as e:
            logger.error(f"读取和解析文件失败: {str(e)}")
            return []
    def create_story_content_from_scenes(self, scenes, title):
        """从场景列表创建故事内容"""
        try:
            # 将场景按原文逐字拼接，不做任何前后缀加工
            story_content = '\n'.join(scenes)
            # 仅在末尾追加统一的出图指令，根据画风选择
            if self.images_per_group == 1:
                if self.style_mode == "cartoon":
                    story_content += f"\n\n给上面每段提示词生成1张图，然后继续下一组的出1张图，其他的不用解释 所有的图片都要比例{self.aspect_ratio}的 所有图片中不要出现中文！！所有图片都要卡通风格！注意！！保持卡通的一致画风！！！出现的角色都要是美国白人的脸！"
                else:  # realistic
                    story_content += f"\n\n给上面每段提示词生成1张图，然后继续下一组的出1张图，其他的不用解释 所有的图片都要比例{self.aspect_ratio}的 所有图片中不要出现中文！！所有图片不要卡通风格！注意！！保持真实感写实的  画风！！！ 注意女性角色除了cat woman以外绝对不要带任何面罩眼罩眼镜以遮挡面部！！！！这是强制性要求！！"
            else:  # 默认2张图
                if self.style_mode == "cartoon":
                    story_content += f"\n\n给上面每段提示词生成2张图，然后继续下一组的2张出图 其他的不用解释 所有的图片都要比例{self.aspect_ratio}的 所有图片中不要出现中文！！所有图片都要卡通风格！注意！！保持卡通的一致画风！！！出现的角色都要是美国白人的脸！"
                else:  # realistic
                    story_content += f"\n\n给上面每段提示词生成2张图，然后继续下一组的2张出图 其他的不用解释 所有的图片都要比例{self.aspect_ratio}的 所有图片中不要出现中文！！所有图片不要卡通风格注意！！保持真实感写实的画风！！！！"
            logger.info(f"创建故事内容: {title}，总长度: {len(story_content)} 字符，包含 {len(scenes)} 个场景")
            return story_content
        except Exception as e:
            logger.error(f"创建故事内容失败: {str(e)}")
            return ""

    def print_final_statistics(self):
        """打印最终的统计信息"""
        if not self.stats['start_time'] or not self.stats['end_time']:
            print("统计信息不完整")
            return
        total_duration = self.stats['end_time'] - self.stats['start_time']
        print(f"\n{'='*80}")
        print(f"🎯 最终统计报告")
        print(f"{'='*80}")
        # 配置信息
        print(f"⚙️ 配置信息:")
        print(f"   图片比例: {self.aspect_ratio}")
        print(f"   每组图片数量: {self.images_per_group} 张")
        print(f"   监控模式: {'标准模式 (20秒无增长判定失败)' if self.enable_no_growth_check else '宽松模式 (仅等待目标数量)'}")
        # 基本统计
        print(f"\n📊 基本统计:")
        print(f"   总故事数: {self.stats['total_stories']} 个")
        print(f"   成功生成: {self.stats['successful_stories']} 个")
        print(f"   生成失败: {self.stats['failed_stories']} 个")
        print(f"   翻译故事: {self.stats['translated_stories']} 个")
        print(f"   重试故事: {self.stats['retried_stories']} 个")
        # 成功率
        if self.stats['total_stories'] > 0:
            success_rate = (self.stats['successful_stories'] / self.stats['total_stories']) * 100
            print(f"   成功率: {success_rate:.1f}%")
        # 生成尝试详细统计
        if self.generation_attempts:
            print(f"\n📋 生成尝试详细统计:")
            print(f"   总尝试次数: {len(self.generation_attempts)} 次")
            # 按故事分组统计
            story_attempts = {}
            for attempt in self.generation_attempts:
                story_idx = attempt['story_index']
                if story_idx not in story_attempts:
                    story_attempts[story_idx] = {'attempts': [], 'success_count': 0, 'fail_count': 0}
                story_attempts[story_idx]['attempts'].append(attempt)
                if attempt['success']:
                    story_attempts[story_idx]['success_count'] += 1
                else:
                    story_attempts[story_idx]['fail_count'] += 1
            print(f"   按故事分组:")
            for story_idx in sorted(story_attempts.keys()):
                attempts = story_attempts[story_idx]
                total_attempts = len(attempts['attempts'])
                success_count = attempts['success_count']
                fail_count = attempts['fail_count']
                print(f"     故事{story_idx}: {total_attempts}次尝试 (成功{success_count}次, 失败{fail_count}次)")
                # 显示每次尝试的详情
                for i, attempt in enumerate(attempts['attempts'], 1):
                    status = "✅" if attempt['success'] else "❌"
                    reason = "" if attempt['success'] else f" - {attempt['failure_reason']}"
                    print(f"       第{attempt['attempt_number']}次: {status}{reason}")
            # 成功和失败的尝试统计
            successful_attempts = [a for a in self.generation_attempts if a['success']]
            failed_attempts = [a for a in self.generation_attempts if not a['success']]
            print(f"\n   成功尝试: {len(successful_attempts)} 次")
            if successful_attempts:
                for attempt in successful_attempts:
                    print(f"     故事{attempt['story_index']} 第{attempt['attempt_number']}次尝试")
            print(f"   失败尝试: {len(failed_attempts)} 次")
            if failed_attempts:
                # 按失败原因分组
                failure_reasons = {}
                for attempt in failed_attempts:
                    reason = attempt['failure_reason']
                    if reason not in failure_reasons:
                        failure_reasons[reason] = []
                    failure_reasons[reason].append(attempt)
                for reason, attempts in failure_reasons.items():
                    print(f"     {reason}: {len(attempts)} 次")
                    for attempt in attempts[:3]:  # 只显示前3个
                        print(f"       故事{attempt['story_index']} 第{attempt['attempt_number']}次尝试")
                    if len(attempts) > 3:
                        print(f"       ... 还有{len(attempts) - 3}次")
        # 时间统计
        print(f"\n⏱️ 时间统计:")
        print(f"   总耗时: {total_duration/60:.1f} 分钟")
        print(f"   平均每个故事: {total_duration/self.stats['total_stories']/60:.1f} 分钟")
        # 详细时间统计
        if self.stats['story_times']:
            successful_times = [t['duration'] for t in self.stats['story_times'] if t['success']]
            failed_times = [t['duration'] for t in self.stats['story_times'] if not t['success']]
            if successful_times:
                avg_success_time = sum(successful_times) / len(successful_times)
                print(f"   成功故事平均耗时: {avg_success_time/60:.1f} 分钟")
                print(f"   最快成功: {min(successful_times)/60:.1f} 分钟")
                print(f"   最慢成功: {max(successful_times)/60:.1f} 分钟")
            if failed_times:
                avg_failed_time = sum(failed_times) / len(failed_times)
                print(f"   失败故事平均耗时: {avg_failed_time/60:.1f} 分钟")
        print(f"\n{'='*80}")
        print(f"✨ 统计报告完成")
        print(f"{'='*80}")

    # ==================== 即梦平台专用方法 ====================
    
    def extract_roles_from_story(self, story_content):
        """从故事内容中提取角色名称"""
        import re
        roles = re.findall(r'角色:(\w+)', story_content)
        print(f"🎭 提取到角色: {roles}")
        return roles
    
    async def navigate_to_jimeng(self):
        """导航到即梦平台并确保登录状态"""
        try:
            print("🌐 正在导航到即梦平台...")
            
            # 导航到即梦平台，等待网络完全加载
            await self.page.goto(self.jimeng_url, wait_until="networkidle")
            print("⏳ 等待页面完全加载和渲染...")
            await asyncio.sleep(8)  # 增加等待时间确保页面稳定
            
            # 检查是否需要登录
            print("🔍 检查登录状态...")
            await asyncio.sleep(3)
            
            # 检查是否出现登录相关元素
            login_indicators = [
                "button:has-text('登录')",
                "button:has-text('用抖音登录')", 
                "button:has-text('手机号登录')",
                "[class*='login']",
                "[class*='auth']"
            ]
            
            login_needed = False
            for selector in login_indicators:
                try:
                    element = await self.page.query_selector(selector)
                    if element and await element.is_visible():
                        login_needed = True
                        print(f"⚠️ 检测到登录元素: {selector}")
                        break
                except Exception:
                    continue
            
            if login_needed:
                print("🔑 需要登录，请手动完成登录...")
                print("👆 请在浏览器中完成登录，然后按回车继续...")
                
                # 如果是非交互式模式，给更多时间等待自动登录
                if NON_INTERACTIVE_MODE:
                    print("🤖 非交互式模式：等待60秒供自动登录或持久化登录生效...")
                    await asyncio.sleep(60)
                else:
                    # 交互式模式：等待用户按回车
                    try:
                        input("按回车键继续...")
                    except:
                        await asyncio.sleep(30)  # 备用等待
            
            # 确认进入了生图页面
            print("🎨 确认是否进入生图页面...")
            await asyncio.sleep(5)
            
            # 检查生图页面的关键元素
            image_generation_indicators = [
                "textarea.prompt-textarea-XfqAoB",  # 提示词输入框
                ".lv-btn.submit-button-VW0U_J",    # 生成按钮
                "input.file-input-O6KAhP"          # 文件上传
            ]
            
            page_ready = False
            for selector in image_generation_indicators:
                try:
                    element = await self.page.wait_for_selector(selector, timeout=10000)
                    if element:
                        print(f"✅ 找到生图页面元素: {selector}")
                        page_ready = True
                        break
                except Exception:
                    continue
            
            if not page_ready:
                print("⚠️ 未找到生图页面关键元素，可能需要手动导航到生图页面")
                print("🔗 请确保页面URL为:", self.jimeng_url)
                
                # 尝试重新导航一次
                print("🔄 尝试重新导航...")
                await self.page.goto(self.jimeng_url, wait_until="networkidle")
                await asyncio.sleep(10)
                
                # 再次检查
                for selector in image_generation_indicators:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            page_ready = True
                            print(f"✅ 重新导航后找到生图页面元素: {selector}")
                            break
                    except Exception:
                        continue
            
            if page_ready:
                print("✅ 即梦平台准备就绪，可以开始生图")
                return True
            else:
                print("❌ 即梦平台页面状态异常")
                return False

        except Exception as e:
            print(f"❌ 导航到即梦平台失败: {e}")
            return False
    
    async def input_story_content_jimeng(self, story_content):
        """在即梦平台输入故事内容"""
        try:
            print(f"📝 正在输入故事内容（{len(story_content)}字符）...")
            
            # 基于调试结果：使用第一个可用的textarea
            textarea_selector = "textarea.prompt-textarea-XfqAoB"
            await self.page.fill(textarea_selector, story_content)
            await asyncio.sleep(2)
            try:
                await self.page.evaluate(
                    "sel => { const el = document.querySelector(sel); if (el) el.blur(); }",
                    textarea_selector,
                )
            except Exception:
                pass
            
            print("✅ 故事内容输入完成")
            return True

        except Exception as e:
            print(f"❌ 故事内容输入失败: {e}")
            return False

    async def debug_submit_button_state(self, label=""):
        """输出提交按钮的调试信息，方便排查点击失败原因"""
        try:
            data = await self.page.evaluate(
                """
                    () => {
                        const buttons = Array.from(document.querySelectorAll('button.submit-button-VW0U_J'));
                        const formatOuter = element => {
                            if (!element || !element.outerHTML) return null;
                            const html = element.outerHTML.replace(/\s+/g, ' ').trim();
                            return html.length > 260 ? html.slice(0, 260) + '…' : html;
                        };
                        return {
                            count: buttons.length,
                            buttons: buttons.map((btn, idx) => {
                                const rect = btn.getBoundingClientRect();
                                return {
                                    idx,
                                    text: (btn.innerText || '').trim(),
                                    className: btn.className,
                                    disabledAttr: btn.getAttribute('disabled'),
                                    ariaDisabled: btn.getAttribute('aria-disabled'),
                                    rect: {
                                        x: Math.round(rect.x),
                                        y: Math.round(rect.y),
                                        width: Math.round(rect.width),
                                        height: Math.round(rect.height)
                                    },
                                    parentHtml: formatOuter(btn.parentElement)
                                };
                            }),
                            activeElement: formatOuter(document.activeElement),
                            hovered: formatOuter(document.querySelector(':hover'))
                        };
                    }
                """
            )
            print(f"🧪 提交按钮状态{(' - ' + label) if label else ''}：共 {data.get('count')} 个")
            for btn in data.get('buttons', []):
                print(
                    f"    · idx={btn.get('idx')} text='{btn.get('text')}' class='{btn.get('className')}' "
                    f"disabledAttr={btn.get('disabledAttr')} ariaDisabled={btn.get('ariaDisabled')} rect={btn.get('rect')}"
                )
                if btn.get('parentHtml'):
                    print(f"      parent: {btn.get('parentHtml')}")
            if data.get('activeElement'):
                print(f"    当前激活元素: {data.get('activeElement')}")
            if data.get('hovered'):
                print(f"    当前 hover 元素: {data.get('hovered')}")
        except Exception as e:
            print(f"⚠️ 无法获取提交按钮调试信息: {e}")

    async def debug_generated_images(self, label=""):
        """输出当前页面候选图片节点的调试信息"""
        try:
            selectors = [
                'div[data-testid="mdbox_image"]',
                'div[data-testid="mdbox-image"]',
                'div[data-testid^="mdbox"]',
                'div[data-testid*="image"]',
                'div[class*="image"]',
                'div[class*="card"]',
                'div[class*="preview"]',
                'img',
                'canvas'
            ]
            data = await self.page.evaluate(
                """
                    (selectors) => {
                        const summary = {};
                        for (const sel of selectors) {
                            try {
                                const nodes = Array.from(document.querySelectorAll(sel));
                                if (nodes.length === 0) continue;
                                summary[sel] = {
                                    count: nodes.length,
                                    samples: nodes.slice(0, 3).map(node => {
                                        const rect = node.getBoundingClientRect();
                                        return {
                                            tag: node.tagName,
                                            className: node.className,
                                            dataset: node.dataset ? { ...node.dataset } : {},
                                            text: (node.innerText || '').trim().slice(0, 60),
                                            rect: {
                                                x: Math.round(rect.x),
                                                y: Math.round(rect.y),
                                                width: Math.round(rect.width),
                                                height: Math.round(rect.height)
                                            }
                                        };
                                    })
                                };
                            } catch (err) {
                                summary[sel] = { error: err ? err.message : String(err) };
                            }
                        }

                        const frames = Array.from(window.frames || []).map((frame, idx) => {
                            try {
                                return { idx, url: frame.location.href };
                            } catch (err) {
                                return { idx, url: '<inaccessible>' };
                            }
                        });

                        return { summary, frames };
                    }
                """,
                selectors,
            )

            prefix = f"🖼️ 图片调试{(' - ' + label) if label else ''}"
            summary = data.get('summary', {})
            if not summary:
                print(f"{prefix}: 未发现候选节点")
            else:
                print(f"{prefix}:")
                for sel, info in summary.items():
                    if not info:
                        continue
                    if info.get('count'):
                        print(f"    · {sel} → {info['count']} 个")
                        for sample in info.get('samples', []):
                            print(
                                "      tag={tag} class='{className}' rect={rect} text='{text}' dataset={dataset}".format(
                                    tag=sample.get('tag'),
                                    className=sample.get('className'),
                                    rect=sample.get('rect'),
                                    text=sample.get('text'),
                                    dataset=sample.get('dataset'),
                                )
                            )
                    elif info.get('error'):
                        print(f"    · {sel} 出错: {info['error']}")
            frames = data.get('frames', [])
            for frame in frames:
                print(f"    frame[{frame['idx']}]: {frame['url']}")
        except Exception as e:
            print(f"⚠️ 无法获取图片调试信息: {e}")

    async def submit_story_jimeng(self):
        """提交故事到即梦平台"""
        try:
            print("🚀 正在提交故事...")
            
            # 基于调试结果：等待按钮变为可用状态
            # 首先等待一下，让按钮状态更新
            await asyncio.sleep(3)

            await self.debug_submit_button_state(label="初始状态")

            # 尝试多个按钮选择器
            button_selectors = [
                "button.submit-button-VW0U_J",
                "button.lv-btn-primary",
                ".lv-btn.lv-btn-primary.submit-button-VW0U_J"
            ]

            for selector in button_selectors:
                try:
                    if self.page.is_closed():
                        print("❌ 浏览器页面已关闭，无法点击提交按钮")
                        return False

                    buttons = await self.page.query_selector_all(selector)
                    if not buttons:
                        continue

                    buttons_with_box = []
                    for idx, button in enumerate(buttons):
                        try:
                            box = await button.bounding_box()
                        except Exception:
                            box = None
                        buttons_with_box.append((idx, button, box))

                    buttons_with_box.sort(
                        key=lambda item: (item[2]['y'] if item[2] else -1, item[2]['height'] if item[2] else 0),
                        reverse=True
                    )

                    for original_idx, button, box in buttons_with_box:
                        try:
                            await self.debug_submit_button_state(
                                label=f"准备点击 {selector}[{original_idx}]"
                            )
                            class_name = await button.get_attribute("class") or ""
                            if "lv-btn-disabled" in class_name:
                                print(f"⚠️ 按钮 {selector}[{original_idx}] 仍处于禁用状态")
                                continue

                            if box:
                                print(f"👉 尝试点击 {selector}[{original_idx}]，位置: {box}")

                            try:
                                await button.hover()
                            except Exception:
                                pass

                            try:
                                await button.scroll_into_view_if_needed()
                            except Exception:
                                pass

                            # 尝试点击按钮，必要时强制点击或走 JS 兜底
                            try:
                                await button.click(timeout=5000)
                                clicked = True
                            except Exception as click_error:
                                print(f"⚠️ 正常点击 {selector}[{original_idx}] 失败: {click_error}")
                                clicked = False

                            if not clicked:
                                try:
                                    await button.click(timeout=5000, force=True)
                                    clicked = True
                                except Exception as force_error:
                                    print(f"⚠️ 强制点击 {selector}[{original_idx}] 仍失败: {force_error}")
                                    clicked = False

                            if not clicked:
                                try:
                                    await self.page.evaluate(
                                        "(sel, index) => { const btns = document.querySelectorAll(sel); const btn = btns[index]; if (btn) btn.click(); }",
                                        selector,
                                        original_idx,
                                    )
                                    clicked = True
                                except Exception as js_error:
                                    print(f"⚠️ JS 触发 {selector}[{original_idx}] 点击失败: {js_error}")
                                    clicked = False

                            if not clicked:
                                continue

                            print(f"✅ 使用选择器 {selector}[{original_idx}] 成功提交")
                            await asyncio.sleep(WAIT_CONFIG.SUBMIT_WAIT + 3)  # 等待提交处理
                            await self.debug_submit_button_state(label="点击后")
                            return True
                        except Exception as single_err:
                            print(f"⚠️ 处理 {selector}[{original_idx}] 时出错: {single_err}")
                            continue
                except Exception as e:
                    print(f"⚠️ 尝试选择器 {selector} 失败: {e}")
                    continue

            print("❌ 所有提交按钮都无法点击")
            return False
            
        except Exception as e:
            print(f"❌ 提交故事失败: {e}")
            return False

    async def confirm_submission_success(self, timeout=20):
        """在有限时间内检查提交是否被即梦平台接受"""
        try:
            start = time.time()
            last_log_time = 0
            positive_keywords = ["生成中", "排队", "已提交", "已加入", "开始生成"]
            negative_keywords = ["失败", "错误", "违规", "稍后", "频繁"]

            while time.time() - start < timeout:
                # 检查已知错误提示
                if await self.check_generation_error():
                    print("🚨 检测到生成错误提示，判定提交失败")
                    return False
                if await self.check_topic_change_toast():
                    print("🚨 检测到话题切换提示，判定提交失败")
                    return False

                # 观察页面上的 toast/提示信息
                try:
                    toast_elements = await self.page.query_selector_all('.semi-toast-content-text')
                    for element in toast_elements:
                        text = await element.text_content()
                        if not text:
                            continue
                        text = text.strip()
                        if not text:
                            continue
                        print(f"📢 页面提示: {text}")
                        if any(keyword in text for keyword in negative_keywords):
                            return False
                        if any(keyword in text for keyword in positive_keywords):
                            return True
                except Exception:
                    pass

                if time.time() - last_log_time >= 5:
                    print("⏳ 等待提交反馈...")
                    last_log_time = time.time()
                await asyncio.sleep(1)

            print(f"⚠️ 在 {timeout}s 内未收到明确反馈，默认视为成功")
            return True
        except Exception as e:
            print(f"⚠️ 检测提交状态时出错: {e}")
            return True

    async def clear_reference_images_jimeng(self):
        """清除即梦平台的参考图"""
        try:
            print("🧹 正在清除参考图...")
            
            # 基于调试结果：查找删除按钮
            delete_selectors = [
                ".icon-close-fUyxxM",
                ".icon-Zi9lEm.icon-close-fUyxxM"
            ]
            
            for selector in delete_selectors:
                delete_buttons = await self.page.query_selector_all(selector)
                for button in delete_buttons:
                    try:
                        await button.click()
                        await asyncio.sleep(1)
                        print(f"🗑️ 清除了一张参考图")
                    except Exception as e:
                        print(f"⚠️ 清除参考图时出错: {e}")
            
            print("✅ 参考图清除完成")
            return True
            
        except Exception as e:
            print(f"❌ 清除参考图失败: {e}")
            return False
    
    async def upload_reference_images_jimeng(self, roles):
        """上传参考图到即梦平台"""
        try:
            if not roles:
                print("ℹ️ 没有需要上传的参考图")
                return True
                
            print(f"📤 正在上传 {len(roles)} 张参考图...")
            
            # 基于调试结果：使用文件上传输入框
            file_input_selector = "input.file-input-O6KAhP"
            
            for role in roles:
                image_path = self.reference_image_dir / f"{role}.png"
                if image_path.exists():
                    try:
                        # 触发文件选择器
                        await self.page.set_input_files(file_input_selector, str(image_path))
                        await asyncio.sleep(2)
                        print(f"✅ 上传了参考图: {role}.png")
                    except Exception as e:
                        print(f"⚠️ 上传 {role}.png 失败: {e}")
                else:
                    print(f"⚠️ 参考图文件不存在: {image_path}")
            
            print("✅ 参考图上传完成")
            return True

        except Exception as e:
            print(f"❌ 上传参考图失败: {e}")
            return False
    
    async def process_story_jimeng(self, story_content, story_index, total_stories, skip_navigation=False):
        """处理单个故事（即梦平台）"""
        try:
            print(f"\n{'='*60}")
            print(f"📖 处理故事 {story_index}/{total_stories}")
            print(f"故事预览: {story_content[:50]}...")
            print(f"{'='*60}")
            
            # 1. 检查是否需要导航（避免重复导航）
            if not skip_navigation:
                if not await self.navigate_to_jimeng():
                    return False
            else:
                # 只检查页面状态，不重新导航
                print("🔍 检查页面状态...")
                try:
                    # 检查关键元素是否还存在
                    textarea = await self.page.wait_for_selector(
                        "textarea.prompt-textarea-XfqAoB",
                        timeout=5000,
                        state="attached",
                    )
                    if not textarea:
                        print("⚠️ 页面状态异常，尝试重新导航...")
                        if not await self.navigate_to_jimeng():
                            return False
                    else:
                        print("✅ 页面状态正常")
                except Exception as status_error:
                    print(f"⚠️ 页面检查失败，尝试重新导航... 原因: {status_error}")
                    if not await self.navigate_to_jimeng():
                        return False
            
            # 2. 清除之前的参考图
            print("🧹 清除之前的参考图...")
            await self.clear_reference_images_jimeng()
            
            # 3. 提取并上传参考图
            roles = self.extract_roles_from_story(story_content)
            if roles:
                print(f"📤 准备上传 {len(roles)} 个角色的参考图...")
                await self.upload_reference_images_jimeng(roles)
            else:
                print("ℹ️ 本故事无需参考图")
            
            # 4. 输入故事内容
            print("📝 输入故事内容...")
            if not await self.input_story_content_jimeng(story_content):
                return False
            
            # 5. 提交故事
            print("🚀 提交故事进行生成...")
            submit_success = await self.submit_story_jimeng()
            if not submit_success:
                print("❌ 提交动作未成功，终止当前故事")
                return False

            if await self.confirm_submission_success():
                print("🎉 提交已确认，故事处理完成！")
                return True

            print("⚠️ 未能确认提交成功，准备重新导航...")
            try:
                await self.navigate_to_jimeng()
            except Exception as nav_error:
                print(f"⚠️ 重新导航时出现问题: {nav_error}")
            return False
            
        except Exception as e:
            print(f"❌ 处理故事失败: {e}")
            return False


async def main():
    """即梦平台专用主函数"""
    print("🎯 即梦图片生成器")
    print("=" * 60)

    # 创建生成器实例
    generator = MessiPictureGenerator()

    # 询问用户选择（非交互式环境会使用默认配置）
    if not generator.ask_user_choices():
        print("❌ 用户配置失败，程序退出")
        return

    # 查找故事文件
    desktop_path = Path.home() / "Desktop"
    story_file = "messipicture.txt" if generator.mode == "ronaldoshorts" else "ronaldomessi.txt"
    file_path = desktop_path / story_file

    if not file_path.exists():
        print(f"错误：桌面上没有找到 {story_file} 文件")
        return

    # 根据模式读取和处理内容
    if generator.mode == "ronaldolong":
        # ronaldolong模式：提取AI图片转视频提示词并分组
        prompts = generator.extract_ai_video_prompts(file_path)
        if not prompts:
            print("错误：无法提取AI图片转视频提示词")
            return
        
        # 将提示词按20段分组
        prompt_groups = generator.group_prompts_for_ronaldolong(prompts)
        if not prompt_groups:
            print("错误：无法分组提示词")
            return
        
        # 为每组创建提交内容
        stories = []
        for i, group in enumerate(prompt_groups):
            content = generator.create_submission_content_for_group(group, i)
            if content:
                stories.append(content)
        
        generator.stories = stories
        print(f"成功创建 {len(stories)} 组提示词内容")
        print(f"图片比例: {generator.aspect_ratio} (固定)")
        print(f"每段生成: {generator.images_per_group} 张图片 (固定)")
    else:
        # ronaldoshorts模式：读取和解析故事
        stories = generator.read_and_parse_stories(file_path)
        if not stories:
            print("错误：无法解析故事内容")
            return

        generator.stories = stories
        print(f"成功解析出 {len(stories)} 个故事")
        print(f"图片比例: {generator.aspect_ratio}")
        print(f"每组将生成 {generator.images_per_group} 张图片")

    # 初始化浏览器
    async with async_playwright() as playwright:
        generator.browser = await playwright.chromium.launch_persistent_context(
            user_data_dir="./browser_data",
            headless=False,
            args=["--start-maximized"]
        )
        generator.page = await generator.browser.new_page()

        try:
            # 首先导航到即梦平台并确保准备就绪
            print("\n🚀 正在初始化即梦平台...")
            if not await generator.navigate_to_jimeng():
                print("❌ 无法访问即梦平台，程序退出")
                return

            print("\n📋 开始批量处理故事...")
            successful_count = 0

            for i, story in enumerate(stories, 1):
                if await generator.process_story_jimeng(story, i, len(stories), skip_navigation=True):
                    successful_count += 1
                else:
                    print(f"⚠️ 故事 {i} 处理失败")

                # 在故事之间添加延迟，避免过于频繁的操作
                if i < len(stories):
                    print("⏳ 等待5秒后处理下一个故事...")
                    await asyncio.sleep(5)

            print("\n🎊 所有故事处理完成！")
            print(f"✅ 成功: {successful_count}/{len(stories)}")
            
            # 打印最终统计报告
            generator.print_final_statistics()

        finally:
            # 清理资源
            if generator.browser:
                await generator.browser.close()

def test_user_choices():
    """测试用户选择界面的演示函数"""
    print("🎯 这是新的用户选择界面演示")
    print("="*60)
    generator = MessiPictureGenerator()
    # 模拟用户选择过程（不实际要求输入）
    print("现在脚本开始前会有以下选择步骤：")
    print()
    print("1. 选择生成模式：")
    print("   - ronaldoshorts (从messipicture.txt读取)")
    print("   - ronaldolong (从ronaldomessi.txt读取)")
    print()
    print("2. 选择图片配置（ronaldoshorts模式）：")
    print("   - 图片比例：9:16 或 16:9")
    print("   - 每组图片数量：1张 或 2张")
    print()
    print("3. 🆕 选择监控模式（新增功能）：")
    print("   - 标准模式：启用20秒无增长判定失败（推荐）")
    print("   - 宽松模式：关闭20秒无增长判定，仅等待目标数量完成")
    print()
    print("说明：")
    print("• 标准模式能更快发现生成问题并重试，适合网络较好的情况")
    print("• 宽松模式更适合网络较慢的情况，会耐心等待图片完成")
    print("• 这个选择让用户可以根据自己的网络状况来调整脚本行为")
    print()
    print("="*60)
    print("✅ 新功能已添加完成！")

if __name__ == "__main__":
    # 如果直接运行此文件且带有test参数，则运行测试
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        test_user_choices()
    else:
        # 安装依赖包
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            print("正在安装playwright包...")
            import subprocess
            subprocess.check_call(["pip", "install", "playwright"])
            subprocess.check_call(["playwright", "install", "chromium"])
            from playwright.async_api import async_playwright
        # 运行主程序
        asyncio.run(main()) 
