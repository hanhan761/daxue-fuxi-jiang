import os
import sys
import json
import datetime
from tqdm import tqdm
import hashlib

# --- 1. 导入配置与 Logger ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    # 🌟 导入配置好的 logger 实例
    from src.utils.logger_config import logger
except ImportError as e:
    # 如果在 logger 启动前就出错，我们只能用 print
    print(f"CRITICAL: 5_merger.py 无法导入 settings 或 logger: {e}")
    sys.exit(1)


# --- 2. 核心打包逻辑 ---
def run_merging():
    """
    步骤 6 (原步骤5)：打包器主函数。
    - 🌟 读取: settings.OUTPUT_UNIFIED (所有 统一后 的 json 文件)
    - 写入: settings.OUTPUT_FINAL / 'Smart_Review_KB.json' (单一的、可导入的知识库)
    """

    # 🌟 V4.5 升级：更新日志和步骤编号
    logger.info("\n--- 步骤 6: 打包 (Merging) ---")

    #⬇️ 1. 【V4.5 升级：更改输入目录】 ⬇️
    input_dir = settings.OUTPUT_UNIFIED
    output_file = settings.OUTPUT_FINAL / "Smart_Review_KB.json"  # 最终文件名

    # --- 启动前检查 ---
    if not input_dir.exists():
        # ⬇️ 2. 【V4.5 升级：更新错误消息】 ⬇️
        logger.error(f"错误：找不到“统一后”的目录 '{input_dir}'。请先运行步骤 4.5 (unifier)。")
        return

    # --- 收集所有已解析的 .json 文件 ---
    files_to_merge = []
    # ⬇️ 3. 【V4.5 升级：更新日志消息】 ⬇️
    logger.info(f"正在扫描“统一后”的目录: {input_dir}")
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                files_to_merge.append(os.path.join(root, filename))

    if not files_to_merge:
        logger.info("未找到“统一后”的 .json 文件。")
        logger.info("完成: 打包。")
        return

    logger.info(f"扫描完成，找到 {len(files_to_merge)} 个 Q&A 条目准备打包。")

    # --- 准备最终的知识库结构 (适配 app.js V2 Graph Schema) ---
    kb_name = getattr(settings, "FINAL_KB_NAME", "自动生成的Smart Review知识库")

    # 🌟 [关键修改] 更改为符合前端要求的 V2 结构
    final_knowledge_base = {
        "graph_metadata": {
            "name": kb_name,
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "schema_version": "v2.0-generated"
        },
        "nodes": [],  # 原来是 knowledgePoints，现在改为 nodes
        "edges": []   # 必须包含 edges 数组，即使为空，否则前端可能会报错
    }

    # --- 循环处理并打包 ---
    default_stats = {"know": 0, "uncertain": 0, "dontKnow": 0}

    for file_path in tqdm(files_to_merge, desc="打包进度"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                kp_data = json.load(f)

            if not isinstance(kp_data, dict):
                logger.warning(f"文件 {file_path} 不包含有效的 JSON 对象，已跳过。")
                continue

            # 注入默认统计数据 (如果缺失)
            if "stats" not in kp_data:
                kp_data["stats"] = default_stats

            # 生成唯一 ID (如果缺失)
            if "id" not in kp_data:
                # 使用标题哈希作为 ID，避免过长
                title_hash = hashlib.md5(kp_data.get("title", "").encode()).hexdigest()[:10]
                kp_data["id"] = f"gen_{title_hash}"

            # 注入创建时间 (如果缺失)
            if "createdAt" not in kp_data:
                kp_data["createdAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 🌟 [关键修改] 将数据添加到 'nodes' 列表
            final_knowledge_base["nodes"].append(kp_data)

        except json.JSONDecodeError:
            logger.error(f"!!! 文件 {file_path} JSON 解码失败，已跳过。", exc_info=True)
        except Exception as e:
            logger.error(f"!!! 处理文件 {file_path} 时发生未知错误: {e}", exc_info=True)

    # --- 写入最终的知识库文件 ---
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_knowledge_base, f, ensure_ascii=False, indent=4)

        # 🌟 [关键修改] 更新日志消息
        logger.info(f"打包完成！共 {len(final_knowledge_base['nodes'])} 个知识点已合并。")
        logger.info(f"最终知识库文件已保存到:")
        logger.info(f"{output_file}")
        logger.info("你现在可以将此文件导入到 'Smart Review' 应用中 (前端将识别为 V2 格式)。")

    except Exception as e:
        logger.error(f"!!! 写入最终知识库文件 {output_file} 时失败: {e}", exc_info=True)

    logger.info("完成: 打包。")


# --- 3. 独立运行 (用于测试) ---
if __name__ == "__main__":
    logger.info("--- (独立运行 5_merger.py) ---")

    try:
        settings.setup_directories()
        logger.info("已调用 settings.setup_directories()。")
    except AttributeError:
        logger.warning("警告：'settings.setup_directories()' 函数未找到。")
        logger.warning("请确保 2_outputs 目录结构已手动创建。")
        os.makedirs(settings.OUTPUT_FINAL, exist_ok=True)
    except NameError:
        logger.critical("错误: settings 导入失败，无法运行测试。")
        sys.exit(1)

    # 运行打包流程
    run_merging()