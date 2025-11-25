import json
import logging
import re
from .agents import SmartAgent
from . import prompts

logger = logging.getLogger(__name__)


def extract_json(text):
    """辅助函数：从文本中提取 JSON"""
    try:
        return json.loads(text)
    except:
        # 清洗 Markdown 代码块
        clean = text.replace("```json", "").replace("```", "").strip()
        try:
            return json.loads(clean)
        except:
            # 正则提取最外层 {}
            match = re.search(r'\{.*\}', text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except:
                    return None
            return None


def run_smart_quiz_pipeline(client, title: str, content: str = "", model_name: str = None):
    """
    运行多智能体出题流水线 (v6.0 Single Shot Mode)
    优化点：仅保留出题人 (Generator)，一次生成，极致速度。
    """
    logger.info(f"🚀 [SmartFlow v6] 启动 (Topic: {title})")
    log_content = (content[:50] + "...") if content and len(content) > 50 else content
    logger.info(f"   -> 附加背景内容: {log_content if log_content else '无'}")

    # --- 初始化智能体 (单人模式) ---
    agent_generator = SmartAgent("出题大师", prompts.PROMPT_GENERATOR, client, model_name)

    # 构造 Prompt
    gen_prompt = f"【复习知识点标题】：{title}\n【复习知识点详情】：{content if content else '无'}"

    # 执行生成（简单的重试机制以防 JSON 格式错误）
    max_retries = 1

    for i in range(max_retries + 1):
        logger.info(f"   ⚡ 正在生成题目 (尝试 {i + 1}/{max_retries + 1})...")

        try:
            # 1. 调用 LLM
            raw_output = agent_generator.work(gen_prompt)

            # 2. 解析 JSON
            quiz_data = extract_json(raw_output)

            if not quiz_data:
                logger.warning("   ⚠️ 生成内容无法解析为 JSON，正在重试...")
                continue

            # 3. 简单校验字段
            required_fields = ["question", "options", "answer", "analysis"]
            if not all(field in quiz_data for field in required_fields):
                logger.warning(f"   ⚠️ 缺少必要字段 ({required_fields})，正在重试...")
                continue

            # 4. 成功返回
            logger.info("   🎉 生成成功！")
            return quiz_data

        except Exception as e:
            logger.error(f"   ❌ 发生未知错误: {e}")
            continue

    logger.error("达到最大重试次数，生成失败。")
    return None