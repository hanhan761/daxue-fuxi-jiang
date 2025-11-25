import json
import logging
from .agents import SmartAgent
from . import prompts

logger = logging.getLogger(__name__)


# [关键修改] 函数签名已更新，接收 title 和 content
def run_smart_quiz_pipeline(client, title: str, content: str = "", model_name: str = None):
    """
    运行多智能体出题流水线 (v2.1 Context Aware)
    """
    logger.info(f"🚀 [SmartFlow v2] 启动 (Topic: {title})")

    # 简单的日志截断处理
    log_content = (content[:50] + "...") if content and len(content) > 50 else content
    logger.info(f"   -> 附加背景内容: {log_content if log_content else '无'}")

    # --- 初始化智能体 ---
    agent_extractor = SmartAgent("概念提取", prompts.PROMPT_CONCEPT_EXTRACTOR, client, model_name)
    agent_generator = SmartAgent("出题大师", prompts.PROMPT_GENERATOR, client, model_name)

    # 3个做题家
    solvers = [
        SmartAgent(f"做题家_{i + 1}", prompts.PROMPT_SOLVER, client, model_name)
        for i in range(3)
    ]

    agent_judge = SmartAgent("裁判", prompts.PROMPT_JUDGE, client, model_name)
    agent_feedbacker = SmartAgent("反馈员", prompts.PROMPT_FEEDBACKER, client, model_name)
    agent_analyst = SmartAgent("解析员", prompts.PROMPT_ANALYST, client, model_name)
    agent_verifier = SmartAgent("审核员", prompts.PROMPT_VERIFIER, client, model_name)
    agent_formatter = SmartAgent("格式化", prompts.PROMPT_JSON_FORMATTER, client, model_name)

    # ==========================
    # Step 1: 确定考点 (输入加入 content)
    # ==========================
    logger.info("Step 1: 结合内容提取考点...")

    # 构造包含标题和内容的 Prompt
    extractor_input = f"【知识点标题】：{title}\n【知识点详情】：{content if content else '无（请仅根据标题推断）'}"
    concept_pair = agent_extractor.work(extractor_input)

    logger.info(f"   -> 考点锚定: {concept_pair[:50]}...")

    # ==========================
    # Step 2: 循环生成与对抗验证
    # ==========================
    max_retries = 3
    final_stem = ""
    final_internal_analysis = ""

    current_advice = ""

    # Generator 的 Prompt 也加入背景信息
    gen_base_prompt = f"【核心考点】：\n{concept_pair}\n\n【原始知识点背景】：\n标题：{title}\n内容：{content}"

    for round_idx in range(max_retries + 1):
        logger.info(f"Step 2 (Round {round_idx + 1}): 正在生成/优化题目...")

        current_gen_prompt = gen_base_prompt
        if current_advice:
            current_gen_prompt += f"\n\n⚠️ 上一轮反馈（需增加难度）：{current_advice}"

        raw_gen_output = agent_generator.work(current_gen_prompt)

        # 解析出题人的输出
        if "#####" in raw_gen_output:
            parts = raw_gen_output.split("#####")
            candidate_stem = parts[0].strip()
            candidate_internal = parts[1].strip()
        else:
            logger.warning("   ⚠️ 出题人格式有误，自动修复...")
            candidate_stem = raw_gen_output
            candidate_internal = "暂无详细内部解析"

        logger.info(f"   -> 候选题目: {candidate_stem[:30]}...")

        # --- 3个做题家进场盲测 ---
        any_solver_correct = False
        solver_traces = []

        logger.info("   ⚔️ 做题家团队正在盲测...")
        for solver in solvers:
            solver_res = solver.work(candidate_stem)

            # 提取答案
            if "#####" in solver_res:
                solver_ans_entity = solver_res.split("#####")[-1].strip()
            else:
                solver_ans_entity = solver_res

            # 裁判判定
            judge_input = f"【标准答案】：\n{concept_pair}\n(参考内部解析: {candidate_internal})\n\n【做题家回答】：\n{solver_ans_entity}"
            is_hit_str = agent_judge.work(judge_input)

            if "TRUE" in is_hit_str.upper():
                logger.info(f"   ❌ {solver.name} 做对了！(Too Easy)")
                any_solver_correct = True
                solver_traces.append(solver_res)
                break
            else:
                logger.info(f"   ✅ {solver.name} 没猜出来。")

        # --- 判定本轮结果 ---
        if any_solver_correct and round_idx < max_retries:
            feedback_input = f"【题目】\n{candidate_stem}\n【做题家破解思路】\n{solver_traces[0]}"
            current_advice = agent_feedbacker.work(feedback_input)
            logger.info(f"   💡 反馈建议: {current_advice}")
            continue
        else:
            if any_solver_correct:
                logger.warning("   ⚠️ 达到最大重试次数，强制锁定。")
            else:
                logger.info("   🎉 题目难度合格！")

            final_stem = candidate_stem
            final_internal_analysis = candidate_internal
            break

    # ==========================
    # Step 3: 解析员完善
    # ==========================
    logger.info("Step 3: 解析员生成选项...")
    analyst_input = f"【题干】：\n{final_stem}\n【标准答案与思路】：\n{concept_pair}\n{final_internal_analysis}"
    analyst_output = agent_analyst.work(analyst_input)

    try:
        a_parts = analyst_output.split("#####")
        raw_options = a_parts[0].strip()
        raw_correct_letter = a_parts[1].strip() if len(a_parts) > 1 else "A"
        raw_analysis = a_parts[2].strip() if len(a_parts) > 2 else "暂无解析"
    except Exception as e:
        logger.error(f"解析员输出格式错误: {e}")
        return None

    # ==========================
    # Step 4: 审核员把关
    # ==========================
    logger.info("Step 4: 审核员审查...")
    verifier_input = f"【题干】：\n{final_stem}\n【选项】：\n{raw_options}\n【正确答案】：{raw_correct_letter}\n【解析】：\n{raw_analysis}"
    verifier_output = agent_verifier.work(verifier_input).strip()

    final_analysis_text = raw_analysis

    if "REJECT" in verifier_output.upper():
        logger.error("🛑 审核员驳回 (REJECT)。")
        return None
    elif "PASS" in verifier_output.upper():
        logger.info("   ✅ 审核通过。")
    else:
        logger.info("   ⚠️ 审核员修正了解析。")
        final_analysis_text = verifier_output

        # ==========================
    # Step 5: 格式化输出
    # ==========================
    logger.info("Step 5: 格式化...")
    format_input = f"""
    【最终题干】：{final_stem}
    【最终选项列表】：\n{raw_options}
    【正确选项字母】：{raw_correct_letter}
    【最终解析】：{final_analysis_text}
    """

    json_str = agent_formatter.work(format_input)

    try:
        clean_json = json_str.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_json)
        return result
    except Exception as e:
        logger.error(f"JSON 解析失败: {e}")
        return None