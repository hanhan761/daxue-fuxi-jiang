import os
import sys
import json
import yaml
import hashlib
import shutil
from tqdm import tqdm
from openai import OpenAI
import concurrent.futures
from pathlib import Path

# --- 1. 导入配置和工具 ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
    from src.utils.formula_renderer import render_latex_to_base64
except ImportError as e:
    print(f"CRITICAL: 4.5_unifier.py 无法导入模块: {e}")
    sys.exit(1)

# --- 2. 智能体 API 辅助函数 ---

def load_prompts():
    try:
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        if 'unifier_grouping_prompt' not in prompts:
            logger.error("缺少 unifier prompts")
            return None
        return prompts
    except Exception as e:
        logger.error(f"Prompts 加载失败: {e}")
        return None


def get_api_client():
    """初始化 API 客户端 (动态获取 Token)"""
    try:
        # 🌟 [关键修改] 优先从环境变量读取
        current_api_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", "")
        
        if not current_api_key:
            logger.error("CRITICAL: unifier 无法获取 API Key。")
            return None

        client = OpenAI(
            api_key=current_api_key,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        return client
    except Exception as e:
        logger.error(f"Error: 初始化 DeepSeek 客户端失败: {e}")
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
        if result_text.startswith("```json"):
            result_text = result_text[7:].strip()
        if result_text.endswith("```"):
            result_text = result_text[:-3].strip()

        return result_text

    except Exception as e:
        logger.error(f"!!! 调用 Unifier API 时失败: {e}")
        return None


# --- 3. 统一器 (Unifier) 核心逻辑 ---

def process_synthesis_group(unified_title: str, old_titles: list, all_titles_map: dict, client: OpenAI, prompts: dict, model: str, output_dir: Path) -> int:
    try:
        fragmented_content = []
        source_metadatas = []
        for old_title in old_titles:
            file_path = all_titles_map.get(old_title)
            if not file_path: continue
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    fragmented_content.append(data)
                    if data.get("source_metadata"):
                        page_str = str(data['source_metadata'].get('page_number', '?'))
                        source_metadatas.append(f"P{page_str}")
            except Exception: pass

        if not fragmented_content: return 0

        synthesis_input = {
            "new_title": unified_title,
            "fragmented_json": fragmented_content
        }
        synthesis_input_str = json.dumps(synthesis_input, ensure_ascii=False)

        synthesis_response_str = call_unifier_agent(
            client,
            synthesis_input_str,
            prompts['unifier_synthesis_prompt'],
            model
        )
        if not synthesis_response_str: return 0

        try:
            new_data = json.loads(synthesis_response_str)
        except json.JSONDecodeError:
            logger.error(f"合成 JSON 解析失败: {unified_title}")
            return 0

        base64_image = None
        new_latex = new_data.get("latex")
        if new_latex and new_latex.strip():
            base64_image = render_latex_to_base64(new_latex)

        first_doc = fragmented_content[0].get("source_metadata", {}).get("source_document", "Unified Concept")
        unified_metadata = {
            "source_document": first_doc,
            "page_number": f"(From {', '.join(sorted(list(set(source_metadatas))))})"
        }
        
        final_json = {
            "title": new_data.get("title"),
            "content": new_data.get("content"),
            "imageData": base64_image,
            "source_metadata": unified_metadata
        }

        safe_filename = hashlib.md5(unified_title.encode()).hexdigest()[:16] + ".json"
        output_path = output_dir / safe_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, ensure_ascii=False, indent=4)
        
        return 1

    except Exception as e:
        logger.error(f"合成线程异常: {e}")
        return 0


# --- 4. 主函数 ---
def run_unification():
    logger.info("--- 步骤 4.5: 统一 (Unifying) ---")

    input_dir = settings.OUTPUT_PARSED
    output_dir = settings.OUTPUT_UNIFIED

    if not input_dir.exists():
        logger.error(f"错误：找不到“解析后”的目录 '{input_dir}'。")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)

    prompts = load_prompts()
    
    # 🌟 获取最新 Client
    client = get_api_client()
    if not prompts or not client:
        return

    MODEL_UNIFIER = getattr(settings, "AGENT_UNIFIER_MODEL", "deepseek-chat")
    MAX_WORKERS = getattr(settings, "PARSER_MAX_WORKERS", 10)

    # ... (分组逻辑) ...
    all_titles_map = {}
    all_files_set = set()
    parsed_files = list(input_dir.glob("*.json"))
    
    if not parsed_files:
        logger.info("未找到文件。")
        return

    for file_path in parsed_files:
        all_files_set.add(file_path)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                title = data.get("title")
                if title: all_titles_map[title] = file_path
        except Exception: pass

    if not all_titles_map:
        return

    all_titles_list_json = json.dumps(list(all_titles_map.keys()), ensure_ascii=False)
    grouping_response_str = call_unifier_agent(client, all_titles_list_json, prompts['unifier_grouping_prompt'], MODEL_UNIFIER)
    
    grouping_json = {}
    if grouping_response_str:
        try:
            grouping_json = json.loads(grouping_response_str)
        except json.JSONDecodeError: pass

    # ... (合成逻辑) ...
    logger.info("阶段 2: 合成...")
    grouped_files_set = set()
    total_synthesized = 0
    futures = []
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for unified_title, old_titles_list in grouping_json.items():
            for old_title in old_titles_list:
                if old_title in all_titles_map:
                    grouped_files_set.add(all_titles_map[old_title])
            
            futures.append(executor.submit(process_synthesis_group, unified_title, old_titles_list, all_titles_map, client, prompts, MODEL_UNIFIER, output_dir))

        pbar = tqdm(concurrent.futures.as_completed(futures), total=len(futures), desc="合成进度")
        for future in pbar:
            try:
                total_synthesized += future.result()
                pbar.set_postfix({"已合成": total_synthesized})
            except Exception: pass

    # ... (传递逻辑) ...
    logger.info("阶段 3: 复制...")
    passthrough_files = all_files_set - grouped_files_set
    for file_path in tqdm(passthrough_files, desc="复制"):
        try:
            shutil.copy2(file_path, output_dir / file_path.name)
        except Exception: pass

    logger.info("统一完成。")


if __name__ == "__main__":
    try:
        settings.setup_directories()
        run_unification()
    except Exception as e:
        print(f"Error: {e}")