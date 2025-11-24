import os
import sys
import json
import yaml
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
    print(f"CRITICAL: 4_parser.py 无法导入模块: {e}")
    sys.exit(1)


# --- 2. 智能体 API 辅助函数 ---
def load_prompts():
    try:
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        if 'parser_definition_prompt' not in prompts or 'parser_formula_prompt' not in prompts:
            logger.error(f"错误：{settings.PROMPTS_FILE} 中缺少必要的 prompts。")
            return None
        return prompts
    except Exception as e:
        logger.error(f"错误：加载 Prompts 文件失败: {e}")
        return None


def get_api_client():
    """初始化 API 客户端 (动态获取 Token)"""
    try:
        # 🌟 [关键修改] 优先从环境变量读取
        current_api_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", "")
        
        if not current_api_key:
            logger.error("CRITICAL: parser 无法获取 API Key。")
            return None

        client = OpenAI(
            api_key=current_api_key,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        return client
    except Exception as e:
        logger.error(f"Error: 初始化 DeepSeek 客户端失败: {e}")
        return None


# --- 3. 解析器核心逻辑 ---

def call_parser_agent(client: OpenAI, content: str, prompt_templates: dict, model: str) -> str | None:
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
            timeout=120.0,
        )

        result_text = response.choices[0].message.content.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:].strip()
        if result_text.endswith("```"):
            result_text = result_text[:-3].strip()

        return result_text

    except Exception as e:
        logger.error(f"!!! 调用 API 解析时失败: {e}")
        return None


def save_parsed_json(item: dict, chunk_id: str, index: int, output_dir):
    try:
        if not item.get("title"):
            return False
        
        safe_chunk_id = chunk_id.replace(os.path.sep, '_').replace('/', '_')
        filename = f"{safe_chunk_id}_q{index}.json"
        output_path = output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(item, f, ensure_ascii=False, indent=4)
        return True

    except Exception as e:
        logger.error(f"!!! 保存文件失败: {e}")
        return False


def process_chunk(chunk: dict, client: OpenAI, prompts: dict, models: dict, output_dir: Path) -> int:
    content = chunk.get('content')
    content_type = chunk.get('content_type')
    chunk_id = chunk.get('chunk_id', 'unknown_chunk')

    source_metadata = {
        "source_document": chunk.get("source_document"),
        "page_number": chunk.get("page_number")
    }

    saved_count_for_this_chunk = 0

    try:
        if content_type == "DEFINITION" or content_type == "GENERAL":
            json_str = call_parser_agent(client, content, prompts['parser_definition_prompt'], models['def'])
            if json_str:
                try:
                    qa_list = json.loads(json_str)
                    if isinstance(qa_list, list):
                        for i, qa_pair in enumerate(qa_list):
                            final_json = {
                                "title": qa_pair.get("title"),
                                "content": qa_pair.get("content"),
                                "imageData": None,
                                "source_metadata": source_metadata
                            }
                            if save_parsed_json(final_json, chunk_id, i, output_dir):
                                saved_count_for_this_chunk += 1
                except json.JSONDecodeError:
                    logger.error(f"JSON 解析失败 (DEF): {chunk_id}")

        elif content_type == "FORMULA":
            json_str = call_parser_agent(client, content, prompts['parser_formula_prompt'], models['form'])
            if json_str:
                try:
                    formula_list = json.loads(json_str)
                    if isinstance(formula_list, list):
                        for i, formula_item in enumerate(formula_list):
                            latex_string = formula_item.get("latex")
                            title = formula_item.get("title")
                            explanation = formula_item.get("explanation")

                            if latex_string and title:
                                base64_image = render_latex_to_base64(latex_string)
                                final_json = {
                                    "title": title,
                                    "content": explanation,
                                    "imageData": base64_image,
                                    "source_metadata": source_metadata
                                }
                                if save_parsed_json(final_json, chunk_id, i, output_dir):
                                    saved_count_for_this_chunk += 1
                except json.JSONDecodeError:
                    logger.error(f"JSON 解析失败 (FORM): {chunk_id}")

    except Exception as e:
        logger.error(f"!!! Chunk 处理失败 {chunk_id}: {e}")

    return saved_count_for_this_chunk


# --- 4. 主函数 ---
def run_parsing():
    logger.info("--- 步骤 4: 解析 (Parsing) [V3: 多线程模式] ---")

    input_file = settings.OUTPUT_CLASSIFIED / 'catalog_smart.json'
    output_dir = settings.OUTPUT_PARSED

    if not input_file.exists():
        logger.error(f"错误：找不到“智能”目录文件 '{input_file}'。")
        return

    prompts = load_prompts()
    
    # 🌟 获取最新的 Client
    client = get_api_client()
    if not prompts or not client:
        return

    MODEL_DEFINITION = getattr(settings, 'AGENT_PARSER_MODEL_DEF', 'deepseek-chat')
    MODEL_FORMULA = getattr(settings, 'AGENT_PARSER_MODEL_FORMULA', 'deepseek-chat')
    MAX_WORKERS = getattr(settings, "PARSER_MAX_WORKERS", 10)

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            catalog_smart = json.load(f)
    except Exception as e:
        logger.error(f"读取输入失败: {e}")
        return

    if not catalog_smart:
        logger.info("目录为空。")
        return

    total_saved_count = 0
    futures = []
    models = {'def': MODEL_DEFINITION, 'form': MODEL_FORMULA}

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for chunk in catalog_smart:
            futures.append(
                executor.submit(process_chunk, chunk, client, prompts, models, output_dir)
            )

        pbar = tqdm(concurrent.futures.as_completed(futures), total=len(catalog_smart), desc="解析进度")
        for future in pbar:
            try:
                saved_count = future.result()
                total_saved_count += saved_count
                pbar.set_postfix({"已生成": total_saved_count})
            except Exception as e:
                logger.error(f"线程异常: {e}")

    logger.info(f"解析完成！生成 {total_saved_count} 个条目。")
    logger.info(f"保存至: {output_dir}")


if __name__ == "__main__":
    try:
        settings.setup_directories()
        run_parsing()
    except Exception as e:
        print(f"Error: {e}")