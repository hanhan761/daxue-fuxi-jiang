import os
import sys
import json
import yaml
from tqdm import tqdm
from openai import OpenAI

# --- 1. 导入配置与 Logger ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    # 🌟 导入配置好的 logger 实例
    from src.utils.logger_config import logger
except ImportError as e:
    print(f"CRITICAL: 3_classifier.py 无法导入 settings 或 logger: {e}")
    sys.exit(1)

# --- 2. 定义分类器智能体 ---
VALID_TYPES = {"DEFINITION", "FORMULA", "CODE_EXAMPLE", "GENERAL"}


def load_prompts():
    try:
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except Exception as e:
        logger.error(f"错误：加载 Prompts 文件失败: {e}", exc_info=True)
        return None


def get_api_client():
    """初始化 API 客户端 (动态获取 Token)"""
    try:
        # 🌟 [关键修改] 优先从 os.environ 获取，确保拿到的是 server.py 刚刚注入的 Token
        # 只有当环境变量为空时，才回退到 settings 中的配置
        current_api_key = os.environ.get("DEEPSEEK_API_KEY") or getattr(settings, "DEEPSEEK_API_KEY", "")
        
        if not current_api_key:
            logger.error("CRITICAL: 未检测到 API Key。请在前端输入 Token。")
            return None

        client = OpenAI(
            api_key=current_api_key,
            base_url=settings.DEEPSEEK_BASE_URL
        )
        return client
    except Exception as e:
        logger.error(f"Error: 初始化 DeepSeek 客户端失败: {e}", exc_info=True)
        return None


def classify_chunk_content(client: OpenAI, content: str, prompt_templates: dict) -> str:
    if not content or not prompt_templates:
        return "GENERAL"

    try:
        system_prompt = prompt_templates['system']
        user_prompt = prompt_templates['user'].format(text_content=content[:4000])

        response = client.chat.completions.create(
            model=settings.AGENT_CLASSIFIER_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            temperature=0.1,
            timeout=30.0
        )

        result = response.choices[0].message.content.strip().upper()

        if result in VALID_TYPES:
            return result
        else:
            return "GENERAL"

    except Exception as e:
        logger.error(f"!!! 调用 API 分类时失败: {e}")
        return "GENERAL"


# --- 3. 核心分类逻辑 ---
def run_classification():
    logger.info("--- 步骤 3: 分类 (Classifying) ---")

    input_file = settings.OUTPUT_INTEGRATED / 'catalog_raw.json'
    output_file = settings.OUTPUT_CLASSIFIED / 'catalog_smart.json'

    if not input_file.exists():
        logger.error(f"错误：找不到“哑”目录文件 '{input_file}'。")
        return

    prompts = load_prompts()
    if not prompts or 'classifier_prompt' not in prompts:
        logger.error("错误：无法加载 'classifier_prompt'。")
        return

    # 🌟 每次运行时重新获取 Client，确保 Token 是最新的
    client = get_api_client()
    if client is None:
        logger.error("错误：无法初始化 API 客户端 (Token 无效或缺失)。")
        return

    logger.info("API 客户端和 Prompts 加载成功，准备开始分类...")

    try:
        with open(input_file, 'r', encoding='utf-8') as f:
            catalog_raw = json.load(f)
    except Exception as e:
        logger.error(f"错误：读取 {input_file} 失败: {e}")
        return

    if not catalog_raw:
        logger.info("“哑”目录为空，无需分类。")
        return

    catalog_smart = []

    for chunk in tqdm(catalog_raw, desc="智能分类进度"):
        content = chunk.get('content')
        content_type = classify_chunk_content(client, content, classifier_prompt_templates=prompts['classifier_prompt'])
        smart_chunk = {**chunk, "content_type": content_type}
        catalog_smart.append(smart_chunk)

    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(catalog_smart, f, ensure_ascii=False, indent=4)

        logger.info(f"分类完成！共处理 {len(catalog_smart)} 个知识块。")
        logger.info(f"“智能”目录文件已保存到: {output_file}")

    except Exception as e:
        logger.error(f"!!! 写入最终“智能”目录文件 {output_file} 时失败: {e}")

    logger.info("完成: 分类。")


if __name__ == "__main__":
    try:
        settings.setup_directories()
        run_classification()
    except Exception as e:
        print(f"Error: {e}")