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
    logger.info(f"[DEBUG] 正在加载提示词文件: {settings.PROMPTS_FILE}")
    try:
        with open(settings.PROMPTS_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            logger.info("[DEBUG] 提示词文件加载成功。")
            return data
    except Exception as e:
        logger.error(f"错误：加载 Prompts 文件失败: {e}", exc_info=True)
        return None


def get_api_client():
    """初始化 API 客户端 (动态获取 Token)"""
    try:
        # 🌟 [关键修改] 优先从 os.environ 获取
        current_api_key = os.environ.get("DEEPSEEK_API_KEY")
        source = "环境变量 (os.environ)"
        
        if not current_api_key:
            current_api_key = getattr(settings, "DEEPSEEK_API_KEY", "")
            source = "配置文件 (settings)"
        
        if not current_api_key:
            logger.error("CRITICAL: 未检测到 API Key。请在前端输入 Token。")
            return None

        # [DEBUG] 打印 API Key 信息 (脱敏)
        masked_key = current_api_key[:8] + "***" + current_api_key[-4:] if len(current_api_key) > 12 else "***"
        logger.info(f"[DEBUG] API 客户端初始化中... 来源: {source}, Key: {masked_key}")
        logger.info(f"[DEBUG] API Base URL: {settings.DEEPSEEK_BASE_URL}")

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
        logger.warning("[DEBUG] 内容为空或模板为空，跳过分类，默认为 GENERAL")
        return "GENERAL"

    try:
        # [DEBUG] 打印当前正在处理的内容片段
        snippet = content[:50].replace('\n', ' ')
        logger.info(f"[DEBUG] >>> 请求 API 分类片段: '{snippet}...'")

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

        # [DEBUG] 打印 API 原始返回结果
        logger.info(f"[DEBUG] <<< API 响应内容: [{result}]")

        if result in VALID_TYPES:
            return result
        else:
            logger.warning(f"[DEBUG] API 返回类型 '{result}' 不在合法列表中 {VALID_TYPES}，归类为 GENERAL")
            return "GENERAL"

    except Exception as e:
        logger.error(f"!!! 调用 API 分类时失败: {e}")
        return "GENERAL"


# --- 3. 核心分类逻辑 ---
def run_classification():
    logger.info("--- 步骤 3: 分类 (Classifying) ---")

    input_file = settings.OUTPUT_INTEGRATED / 'catalog_raw.json'
    output_file = settings.OUTPUT_CLASSIFIED / 'catalog_smart.json'

    logger.info(f"[DEBUG] 输入文件路径: {input_file}")
    logger.info(f"[DEBUG] 输出文件路径: {output_file}")

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
        logger.info(f"[DEBUG] 成功读取 Raw Catalog，共包含 {len(catalog_raw)} 个块。")
    except Exception as e:
        logger.error(f"错误：读取 {input_file} 失败: {e}")
        return

    if not catalog_raw:
        logger.info("“哑”目录为空，无需分类。")
        return

    catalog_smart = []

    # 使用 tqdm 显示进度，同时内部会打印 debug 信息
    for i, chunk in enumerate(tqdm(catalog_raw, desc="智能分类进度")):
        content = chunk.get('content')
        
        # [Fix] 修正了参数名: 原代码是 classifier_prompt_templates，定义是 prompt_templates
        # 这里改为 prompt_templates 以匹配函数定义
        content_type = classify_chunk_content(
            client, 
            content, 
            prompt_templates=prompts['classifier_prompt']
        )
        
        smart_chunk = {**chunk, "content_type": content_type}
        catalog_smart.append(smart_chunk)
        
        # [DEBUG] 每处理 5 个打印一次当前状态，防止刷屏太快，但又能看到进度
        if (i + 1) % 5 == 0:
            logger.info(f"[DEBUG] 已处理 {i + 1}/{len(catalog_raw)} 个块...")

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