import os
import sys
import json
import datetime
import hashlib
import time
from tqdm import tqdm
from pathlib import Path

# --- 1. 导入配置与 Logger ---
# 动态获取项目根目录，确保在任何层级运行都能找到
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# [新增日志] 打印环境路径信息，用于调试导入问题
print(f"🔍 [Merger] PROJECT_ROOT detected at: {PROJECT_ROOT}")

try:
    from configs import settings
    # 🌟 导入配置好的 logger 实例
    from src.utils.logger_config import logger
    logger.info(f"✅ [Merger] 配置与日志模块加载成功")
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
    
    start_time = time.time()
    
    # 🌟 V4.5 升级：更新日志和步骤编号
    logger.info("=================================================")
    logger.info("===    📦 步骤 6: 打包 (Merging) 启动    ===")
    logger.info("=================================================")

    #⬇️ 1. 【V4.5 升级：更改输入目录】 ⬇️
    input_dir = settings.OUTPUT_UNIFIED
    output_file = settings.OUTPUT_FINAL / "Smart_Review_KB.json"  # 最终文件名

    logger.info(f"📂 输入目录: {input_dir}")
    logger.info(f"💾 输出路径: {output_file}")

    # --- 启动前检查 ---
    if not input_dir.exists():
        # ⬇️ 2. 【V4.5 升级：更新错误消息】 ⬇️
        logger.error(f"❌ 错误：找不到“统一后”的目录 '{input_dir}'。")
        logger.error(f"   -> 请先确保步骤 5 (unifier) 已成功运行且有产出。")
        return

    # --- 收集所有已解析的 .json 文件 ---
    files_to_merge = []
    # ⬇️ 3. 【V4.5 升级：更新日志消息】 ⬇️
    logger.info(f"🔍 正在递归扫描 .json 文件...")
    
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                files_to_merge.append(os.path.join(root, filename))

    count = len(files_to_merge)
    if count == 0:
        logger.warning(f"⚠️  警告: 在 {input_dir} 中未找到任何 .json 文件。")
        logger.info("🛑 打包流程提前结束 (无数据)。")
        return

    logger.info(f"✅ 扫描完成，共找到 {count} 个文件准备合并。")

    # --- 准备最终的知识库结构 (适配 app.js V2 Graph Schema) ---
    kb_name = getattr(settings, "FINAL_KB_NAME", "自动生成的Smart Review知识库")
    logger.info(f"🏷️  知识库名称: {kb_name}")
    logger.info(f"⚙️  Schema版本: v2.0-generated")

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
    
    success_count = 0
    fail_count = 0
    skip_count = 0

    logger.info("🚀 开始合并数据...")
    
    # 使用 tqdm 显示进度条
    for file_path in tqdm(files_to_merge, desc="📦 打包进度", unit="file"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content:
                    logger.warning(f"   -> 跳过空文件: {Path(file_path).name}")
                    skip_count += 1
                    continue
                kp_data = json.loads(content)

            if not isinstance(kp_data, dict):
                logger.warning(f"   -> 跳过格式错误文件 (非Dict): {Path(file_path).name}")
                skip_count += 1
                continue

            # 注入默认统计数据 (如果缺失)
            if "stats" not in kp_data:
                kp_data["stats"] = default_stats

            # 生成唯一 ID (如果缺失)
            if "id" not in kp_data:
                # 使用标题哈希作为 ID，避免过长
                title_hash = hashlib.md5(kp_data.get("title", "untitled").encode()).hexdigest()[:10]
                kp_data["id"] = f"gen_{title_hash}"

            # 注入创建时间 (如果缺失)
            if "createdAt" not in kp_data:
                kp_data["createdAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # 🌟 [关键修改] 将数据添加到 'nodes' 列表
            final_knowledge_base["nodes"].append(kp_data)
            success_count += 1

        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON 解析失败 [{Path(file_path).name}]: {e}")
            fail_count += 1
        except Exception as e:
            logger.error(f"❌ 处理文件出错 [{Path(file_path).name}]: {e}", exc_info=True)
            fail_count += 1

    # --- 写入最终的知识库文件 ---
    try:
        logger.info(f"📝 正在构建最终 JSON 文件...")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_knowledge_base, f, ensure_ascii=False, indent=4)

        # 获取文件大小
        file_size_mb = output_file.stat().st_size / (1024 * 1024)

        # 🌟 [关键修改] 更新日志消息
        logger.info("-" * 40)
        logger.info(f"✅ 打包成功 (Success)")
        logger.info("-" * 40)
        logger.info(f"📊 统计:")
        logger.info(f"   - 扫描文件: {count}")
        logger.info(f"   - 成功合并: {success_count}")
        logger.info(f"   - 失败/跳过: {fail_count + skip_count}")
        logger.info("-" * 40)
        logger.info(f"📄 输出文件: {output_file.name}")
        logger.info(f"💾 文件大小: {file_size_mb:.2f} MB")
        logger.info(f"🔗 完整路径: {output_file.resolve()}")
        logger.info(f"⏱️  总耗时: {time.time() - start_time:.2f} 秒")
        logger.info("-" * 40)
        logger.info("💡 提示: 你现在可以将此 JSON 文件直接拖入 'Smart Review' 前端进行导入。")

    except Exception as e:
        logger.critical(f"!!! ❌ 写入最终知识库文件失败: {e}", exc_info=True)

    logger.info("=== 📦 步骤 6: 打包 结束 ===")


# --- 3. 独立运行 (用于测试) ---
if __name__ == "__main__":
    logger.info("\n🛠️  [独立调试模式] 启动 5_merger.py")

    try:
        settings.setup_directories()
        logger.info("✅ 目录结构检查完成")
    except AttributeError:
        logger.warning("⚠️  settings.setup_directories() 未找到，尝试手动创建目录...")
        os.makedirs(settings.OUTPUT_FINAL, exist_ok=True)
    except NameError:
        logger.critical("❌ settings 未导入，无法继续")
        sys.exit(1)

    # 运行打包流程
    run_merging()