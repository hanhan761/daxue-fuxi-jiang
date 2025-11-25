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
    logger.info(f"[DEBUG] 正在加载 Prompts 文件: {settings.PROMPTS_FILE}")
    try:
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            prompts = yaml.safe_load(f)
        
        # 🌟 [修改点 1] 检查新的 Prompt Key
        # 我们需要一个 'parser_master_prompt' 来处理大段文本的总结
        required_keys = ['parser_master_prompt', 'parser_formula_prompt']
        for key in required_keys:
            if key not in prompts:
                logger.error(f"错误：{settings.PROMPTS_FILE} 中缺少必要的 prompts: {key}")
                return None
            
        logger.info("[DEBUG] Prompts 加载成功。")
        return prompts
    except Exception as e:
        logger.error(f"错误：加载 Prompts 文件失败: {e}", exc_info=True)
        return None


def get_api_client():
    """初始化 API 客户端"""
    try:
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
        logger.error(f"Error: 初始化 DeepSeek 客户端失败: {e}", exc_info=True)
        return None


# --- 3. 解析器核心逻辑 ---

def call_parser_agent(client: OpenAI, content: str, prompt_templates: dict, model: str) -> str | None:
    try:
        # [DEBUG] 打印调用信息
        snippet = content[:50].replace('\n', ' ')
        # logger.info(f"[DEBUG] >>> 调用 LLM 解析: '{snippet}...'")

        system_prompt = prompt_templates['system']
        # 🌟 这里传入的内容现在包含了 [Page X] 标记，Prompt 需要能够理解这一点
        user_prompt = prompt_templates['user'].format(text_content=content)

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.1,
            # 🌟 [修改点 2] 增加超时时间，因为总结长文比较慢
            timeout=180.0, 
        )

        result_text = response.choices[0].message.content.strip()
        
        # 清洗 Markdown
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
        # 允许 title 为空的情况吗？最好不要，但如果 content 很棒，可以后续生成 title。
        # 这里保持严格检查
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
    content_type = chunk.get('content_type', 'GENERAL') # 默认为 GENERAL
    chunk_id = chunk.get('chunk_id', 'unknown_chunk')

    # 构造 Source Metadata，供后续追溯
    source_metadata = {
        "source_document": chunk.get("source_document"),
        "page_number": chunk.get("page_number") # 例如 "p1-p3"
    }

    saved_count = 0

    try:
        # 🌟 [修改点 3] 核心分发逻辑重构
        # 我们不再细分 DEFINITION vs GENERAL，统一走“大师级总结”模式
        # 只有 FORMULA (公式) 需要走特殊渲染通道
        
        if content_type == "FORMULA":
            # --- 公式处理通道 (保持不变) ---
            json_str = call_parser_agent(client, content, prompts['parser_formula_prompt'], models['form'])
            if json_str:
                try:
                    formula_list = json.loads(json_str)
                    if isinstance(formula_list, list):
                        for i, item in enumerate(formula_list):
                            latex = item.get("latex")
                            if latex:
                                base64_img = render_latex_to_base64(latex)
                                final_json = {
                                    "title": item.get("title", "数学公式"),
                                    "content": item.get("explanation", ""),
                                    "imageData": base64_img,
                                    "source_metadata": source_metadata,
                                    "type": "FORMULA"
                                }
                                if save_parsed_json(final_json, chunk_id, i, output_dir):
                                    saved_count += 1
                except:
                    logger.error(f"公式 JSON 解析失败: {chunk_id}")

        else:
            # --- 通用知识总结通道 (GENERAL, DEFINITION, TEXT...) ---
            # 使用 parser_master_prompt 进行深度阅读理解
            json_str = call_parser_agent(client, content, prompts['parser_master_prompt'], models['def'])
            
            if json_str:
                try:
                    # 预期返回: List[{"title": "知识点标题", "content": "详细解释..."}]
                    kb_items = json.loads(json_str)
                    
                    if isinstance(kb_items, list):
                        for i, item in enumerate(kb_items):
                            # 确保内容足够丰富，不仅仅是一句话
                            final_json = {
                                "title": item.get("title"),
                                "content": item.get("content"),
                                "imageData": None, # 文本类暂无图片
                                "source_metadata": source_metadata,
                                "type": "CONCEPT" # 标记为概念/知识点
                            }
                            if save_parsed_json(final_json, chunk_id, i, output_dir):
                                saved_count += 1
                    else:
                        logger.warning(f"Master Prompt 返回格式错误 (非 List): {chunk_id}")
                except json.JSONDecodeError:
                    logger.error(f"Master Prompt JSON 解析失败: {chunk_id}")

    except Exception as e:
        logger.error(f"Chunk 处理异常 {chunk_id}: {e}", exc_info=True)

    return saved_count


# --- 4. 主函数 ---
def run_parsing():
    logger.info("--- 步骤 4: 解析 (Parsing) [V3: Master Summary] ---")

    input_file = settings.OUTPUT_CLASSIFIED / 'catalog_smart.json'
    output_dir = settings.OUTPUT_PARSED

    # ... (前面的路径检查逻辑保持不变) ...
    if not input_file.exists(): return
    
    prompts = load_prompts()
    client = get_api_client()
    if not prompts or not client: return

    # 模型配置
    MODEL_MAIN = getattr(settings, 'AGENT_PARSER_MODEL_DEF', 'deepseek-chat')
    MODEL_FORMULA = getattr(settings, 'AGENT_PARSER_MODEL_FORMULA', 'deepseek-chat')
    MAX_WORKERS = getattr(settings, "PARSER_MAX_WORKERS", 5) # 稍微降低并发，因为每个任务更重了

    logger.info(f"配置: 主模型={MODEL_MAIN}, 线程数={MAX_WORKERS}")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            catalog_smart = json.load(f)
    except Exception: return

    total_saved = 0
    futures = []
    models = {'def': MODEL_MAIN, 'form': MODEL_FORMULA}

    logger.info(f"开始处理 {len(catalog_smart)} 个上下文块 (Sliding Windows)...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        for chunk in catalog_smart:
            futures.append(executor.submit(process_chunk, chunk, client, prompts, models, output_dir))

        pbar = tqdm(concurrent.futures.as_completed(futures), total=len(catalog_smart), desc="解析进度")
        for future in pbar:
            try:
                total_saved += future.result()
                pbar.set_postfix({"已生成": total_saved})
            except Exception: pass

    logger.info(f"解析完成！生成 {total_saved} 个知识节点。")

if __name__ == "__main__":
    settings.setup_directories()
    run_parsing()