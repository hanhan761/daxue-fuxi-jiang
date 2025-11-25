# src/feiman/smart_flow/pipeline.py
import json
import logging
from .agents import SmartAgent
from . import prompts

logger = logging.getLogger(__name__)


def run_smart_quiz_pipeline(client, topic: str, model_name: str):
    """
    运行多智能体出题流水线
    流程：概念提取 -> 初步出题 -> (做题家验证 -> 裁判判断 -> 反馈修正) -> 格式化输出
    """
    logger.info(f"🚀 [SmartFlow] 启动多智能体出题流程，主题: {topic}")

    # --- 初始化智能体 ---
    # 为了省钱/速度，Solver 和 Judge 可以用普通模型，Generator 用好模型
    agent_extractor = SmartAgent("概念提取", prompts.PROMPT_CONCEPT_EXTRACTOR, client, model_name)
    agent_generator = SmartAgent("出题大师", prompts.PROMPT_GENERATOR, client, model_name)
    agent_solver = SmartAgent("做题家", prompts.PROMPT_SOLVER, client, model_name)
    agent_judge = SmartAgent("裁判", prompts.PROMPT_JUDGE, client, model_name)  # 用小模型即可
    agent_feedbacker = SmartAgent("反馈员", prompts.PROMPT_FEEDBACKER, client, model_name)
    agent_formatter = SmartAgent("格式化", prompts.PROMPT_JSON_FORMATTER, client, model_name)

    # 1. 确定考点 (Concept Extraction)
    logger.info("Step 1: 提取核心考点...")
    concept_pair = agent_extractor.work(f"复习主题：{topic}")
    logger.info(f"   -> 考点锚定: {concept_pair[:50]}...")

    # 2. 循环生成与验证 (Generation & Validation Loop)
    max_retries = 2  # 最大修正次数，避免死循环
    current_advice = ""
    final_question_text = ""

    # 初始 prompt
    gen_prompt = f"请基于此考点出题：\n{concept_pair}"

    for i in range(max_retries + 1):
        logger.info(f"Step 2 (Round {i + 1}): 正在生成/优化题目...")

        if current_advice:
            gen_prompt += f"\n\n⚠️ 上一轮反馈（请修正题目歧义）：{current_advice}"

        candidate_question = agent_generator.work(gen_prompt)

        # 3. 做题家盲测
        solver_response = agent_solver.work(candidate_question)

        # 4. 裁判判定
        judge_input = f"【题目考点/标准答案】：\n{concept_pair}\n\n【做题家回答】：\n{solver_response}"
        is_correct_str = agent_judge.work(judge_input)

        is_correct = "TRUE" in is_correct_str.upper()

        if is_correct:
            logger.info("   ✅ 裁判判定：做题家回答正确！题目逻辑清晰。")
            final_question_text = candidate_question
            break
        else:
            logger.info("   ❌ 裁判判定：做题家答错了/有偏差。题目可能存在歧义。")
            if i < max_retries:
                # 触发反馈
                feedback_input = f"【当前题目】\n{candidate_question}\n【考点】\n{concept_pair}\n【做题家错误理解】\n{solver_response}"
                current_advice = agent_feedbacker.work(feedback_input)
                logger.info(f"   💡 反馈建议: {current_advice}")
            else:
                logger.warning("   ⚠️ 达到最大重试次数，强制使用当前版本。")
                final_question_text = candidate_question

    # 5. 格式化输出 (Formatting)
    logger.info("Step 3: 格式化为 JSON...")
    format_input = f"【最终题干】：\n{final_question_text}\n\n【参考考点】：\n{concept_pair}"
    json_str = agent_formatter.work(format_input)

    # 清洗 JSON
    try:
        clean_json = json_str.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_json)
        return result
    except Exception as e:
        logger.error(f"JSON 解析失败: {e}\nRaw: {json_str}")
        return None