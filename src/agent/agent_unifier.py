import os
import sys
import json
import yaml
import hashlib
import shutil
import time
from tqdm import tqdm
from openai import OpenAI
import concurrent.futures
from pathlib import Path

# --- 1. 导入配置和工具 ---
# 动态获取项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# [新增日志] 打印环境路径信息
print(f"🔍 [Unifier] PROJECT_ROOT detected at: {PROJECT_ROOT}")

try:
    from configs import settings
    from src.utils.logger_config import logger
    from src.utils.formula_renderer import render_latex_to_base64
    logger.info(f"✅ [Unifier] 配置、日志及渲染模块加载成功")
except ImportError as e:
    print(f"CRITICAL: 4.5_unifier.py 无法导入模块: {e}")
    sys.exit(1)

# --- 2. 智能体 API 辅助函数 ---

def load_prompts():
    try:
        if not os.path.exists(settings.PROMPTS_FILE):
            logger.error(f"❌ Prompts 文件不存在: {settings.PROMPTS_FILE}")
            return None
            
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        
        if 'unifier_grouping_prompt' not in prompts:
            logger.error("❌ Prompts 文件中缺少 'unifier_grouping_prompt'")
            return None
        return prompts
    except Exception as e:
        logger.error(f"❌ Prompts 加载失败: {e}")
        return None


def get_api_client():
    """初始化 API 客户端 (动态获取 Token)"""
    try:
        # 🌟 [关键修改] 优先从环境变量读取
        current_api_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", "")
        
        if not current_api_key:
            logger.error("❌ CRITICAL: unifier 无法获取 API Key (环境变量 DEEPSEEK_API_KEY 或 settings 配置缺失)。")
            return None

        client = OpenAI(
            api_key=current_api_key,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        return client
    except Exception as e:
        logger.error(f"❌ Error: 初始化 DeepSeek 客户端失败: {e}")
        return None

def call_unifier_agent(client: OpenAI, content: str, prompt_templates: dict, model: str) -> str | None:
    try:
        system_prompt = prompt_templates['system']
        user_prompt = prompt_templates['user'].format(text_content=content)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.1,
            timeout=180.0,
        )

        result_text = response.choices[0].message.content.strip()
        
        # 清理 Markdown 代码块标记
        if result_text.startswith("```json"):
            result_text = result_text[7:].strip()
        elif result_text.startswith("```"):
            result_text = result_text[3:].strip()
            
        if result_text.endswith("```"):
            result_text = result_text[:-3].strip()

        return result_text

    except Exception as e:
        logger.error(f"❌ 调用 Unifier API 时失败: {e}")
        return None


# --- 3. 统一器 (Unifier) 核心逻辑 ---

def process_synthesis_group(unified_title: str, old_titles: list, all_titles_map: dict, client: OpenAI, prompts: dict, model: str, output_dir: Path) -> int:
    """
    处理单个分组的合成任务
    返回: 1 (成功), 0 (失败/跳过)
    """
    try:
        fragmented_content = []
        source_metadatas = []
        
        # 收集该组所有旧文件的内容
        for old_title in old_titles:
            file_path = all_titles_map.get(old_title)
            if not file_path: continue
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    fragmented_content.append(data)
                    # 收集页码信息用于合并来源
                    if data.get("source_metadata"):
                        page_str = str(data['source_metadata'].get('page_number', '?'))
                        source_metadatas.append(f"P{page_str}")
            except Exception: pass

        if not fragmented_content:
            return 0

        # 构建合成请求
        synthesis_input = {
            "new_title": unified_title,
            "fragmented_json": fragmented_content
        }
        synthesis_input_str = json.dumps(synthesis_input, ensure_ascii=False)

        # 调用 LLM 进行合成
        synthesis_response_str = call_unifier_agent(
            client,
            synthesis_input_str,
            prompts['unifier_synthesis_prompt'],
            model
        )
        if not synthesis_response_str: 
            return 0

        try:
            new_data = json.loads(synthesis_response_str)
        except json.JSONDecodeError:
            logger.error(f"⚠️  合成 JSON 解析失败: {unified_title}")
            return 0

        # 处理 LaTeX 图片渲染
        base64_image = None
        new_latex = new_data.get("latex")
        if new_latex and new_latex.strip():
            # 简单校验，防止渲染空内容
            base64_image = render_latex_to_base64(new_latex)

        # 合并 Source Metadata
        first_doc = fragmented_content[0].get("source_metadata", {}).get("source_document", "Unified Concept")
        
        # 去重并排序页码
        unique_pages = sorted(list(set(source_metadatas)))
        unified_metadata = {
            "source_document": first_doc,
            "page_number": f"(From {', '.join(unique_pages)})"
        }
        
        final_json = {
            "title": new_data.get("title"),
            "content": new_data.get("content"),
            "imageData": base64_image,
            "source_metadata": unified_metadata,
            "original_titles": old_titles # [可选] 保留原始标题记录
        }

        # 生成安全的文件名
        safe_filename = hashlib.md5(unified_title.encode()).hexdigest()[:16] + ".json"
        output_path = output_dir / safe_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, ensure_ascii=False, indent=4)
        
        return 1

    except Exception as e:
        logger.error(f"❌ 合成线程异常 [{unified_title}]: {e}")
        return 0


# --- 4. 主函数 ---
def run_unification():
    start_time = time.time()
    logger.info("=================================================")
    logger.info("===   🧠 步骤 4.5: 统一 (Unifying) 启动   ===")
    logger.info("=================================================")

    input_dir = settings.OUTPUT_PARSED
    output_dir = settings.OUTPUT_UNIFIED

    logger.info(f"📂 输入目录: {input_dir}")
    logger.info(f"💾 输出目录: {output_dir}")

    if not input_dir.exists():
        logger.error(f"❌ 错误：找不到“解析后”的目录 '{input_dir}'。")
        return
    
    # 清理并重建输出目录
    # output_dir.mkdir(parents=True, exist_ok=True) # 假设 pipeline 已经清理过，这里只负责写

    # 加载资源
    prompts = load_prompts()
    client = get_api_client()
    
    if not prompts:
        logger.error("🛑 终止：Prompts 加载失败。")
        return
    if not client:
        logger.error("🛑 终止：API Client 初始化失败。")
        return

    MODEL_UNIFIER = getattr(settings, "AGENT_UNIFIER_MODEL", "deepseek-chat")
    MAX_WORKERS = getattr(settings, "PARSER_MAX_WORKERS", 10)
    logger.info(f"🤖 使用模型: {MODEL_UNIFIER}")
    logger.info(f"🧵 线程池大小: {MAX_WORKERS}")

    # --- 阶段 1: 扫描与映射 ---
    logger.info("\n>>> [阶段 1/3] 扫描文件与建立映射...")
    all_titles_map = {}
    all_files_set = set()
    parsed_files = list(input_dir.glob("*.json"))
    
    if not parsed_files:
        logger.warning("⚠️  未找到任何已解析的 JSON 文件，流程结束。")
        return

    for file_path in parsed_files:
        all_files_set.add(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                title = data.get("title")
                if title: 
                    all_titles_map[title] = file_path
        except Exception: 
            pass

    if not all_titles_map:
        logger.warning("⚠️  无法从文件中提取标题，流程结束。")
        return

    logger.info(f"✅ 扫描完成: {len(parsed_files)} 个文件，识别到 {len(all_titles_map)} 个标题。")

    # --- 阶段 2: 语义分组 ---
    logger.info("\n>>> [阶段 2/3] 调用 LLM 进行语义分组...")
    all_titles_list_json = json.dumps(list(all_titles_map.keys()), ensure_ascii=False)
    
    # 调用 LLM 分组
    grouping_start = time.time()
    grouping_response_str = call_unifier_agent(client, all_titles_list_json, prompts['unifier_grouping_prompt'], MODEL_UNIFIER)
    
    grouping_json = {}
    if grouping_response_str:
        try:
            grouping_json = json.loads(grouping_response_str)
        except json.JSONDecodeError: 
            logger.error("❌ 分组响应 JSON 解析失败")
            pass
    
    # 统计分组情况
    grouped_files_set = set() # 被分到组里的所有文件的路径
    total_groups = len(grouping_json)
    
    for unified_title, old_titles_list in grouping_json.items():
        for old_title in old_titles_list:
            if old_title in all_titles_map:
                grouped_files_set.add(all_titles_map[old_title])

    logger.info(f"✅ 分组完成 (耗时 {time.time() - grouping_start:.2f}s):")
    logger.info(f"   -> 发现 {total_groups} 个聚合组 (涉及 {len(grouped_files_set)} 个文件)")
    logger.info(f"   -> 剩余 {len(all_files_set) - len(grouped_files_set)} 个独立文件将直接通过。")

    # --- 阶段 3: 并行合成 ---
    logger.info("\n>>> [阶段 3/3] 执行合成与迁移...")
    
    total_synthesized = 0
    futures = []
    
    if total_groups > 0:
        with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            for unified_title, old_titles_list in grouping_json.items():
                futures.append(executor.submit(process_synthesis_group, unified_title, old_titles_list, all_titles_map, client, prompts, MODEL_UNIFIER, output_dir))

            # 显示进度条
            pbar = tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="🔄 合成进度", unit="grp")
            for future in pbar:
                try:
                    res = future.result()
                    total_synthesized += res
                except Exception as e: 
                    logger.error(f"线程执行异常: {e}")
    else:
        logger.info("ℹ️  没有需要合成的组。")

    # --- 阶段 4: Pass-through (复制未分组文件) ---
    logger.info("\n>>> [收尾] 复制未分组的独立文件...")
    passthrough_files = all_files_set - grouped_files_set
    copied_count = 0
    
    for file_path in tqdm(passthrough_files, desc="🚚 复制进度", unit="file"):
        try:
            shutil.copy2(file_path, output_dir / file_path.name)
            copied_count += 1
        except Exception as e:
            logger.error(f"❌ 复制文件失败 {file_path.name}: {e}")

    # --- 总结 ---
    total_duration = time.time() - start_time
    output_count = len(list(output_dir.glob("*.json")))

    logger.info("-" * 40)
    logger.info(f"✅ 统一流程完成 (Success)")
    logger.info("-" * 40)
    logger.info(f"📊 统计:")
    logger.info(f"   - 原始文件数: {len(all_files_set)}")
    logger.info(f"   - 聚合生成数: {total_synthesized} (来自 {len(grouped_files_set)} 个原文件)")
    logger.info(f"   - 直接复制数: {copied_count}")
    logger.info(f"   - 最终产出数: {output_count}")
    logger.info(f"⏱️  总耗时: {total_duration:.2f} 秒")
    logger.info("-" * 40)


if __name__ == "__main__":
    logger.info("\n🛠️  [独立调试模式] 启动 4.5_unifier.py")
    try:
        settings.setup_directories()
        # 确保输出目录存在 (独立运行时可能没有被 pipeline 清理/创建)
        settings.OUTPUT_UNIFIED.mkdir(parents=True, exist_ok=True)
        run_unification()
    except Exception as e:
        logger.critical(f"❌ 运行失败: {e}", exc_info=True)