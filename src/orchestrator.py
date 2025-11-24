import os
import sys
import time
import shutil
from pathlib import Path

# --- 1. 关键：设置 sys.path ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError as e:
    print(f"!!! CRITICAL BOOTSTRAP FAILED !!!")
    sys.exit(1)

try:
    from src.agent.agent_preprocessor import run_preprocessing
    from src.agent.agent_integrator import run_integration
    from src.agent.agent_classifier import run_classification
    from src.agent.agent_parser import run_parsing
    from src.agent.agent_unifier import run_unification
    from src.agent.agent_merger import run_merging
except ImportError as e:
    logger.critical(f"!!! 严重错误：导入 agent 模块失败: {e}", exc_info=True)
    sys.exit(1)


def safe_clear_directory(dir_path: Path):
    """
    安全清理目录：尝试删除整个目录，如果被占用（WinError 32），则尝试清空内部文件。
    """
    if not dir_path.exists():
        return

    try:
        shutil.rmtree(dir_path)
        logger.info(f"    - 已删除目录: {dir_path.name}")
    except OSError as e:
        logger.warning(f"    ⚠️ 目录 {dir_path.name} 被占用，尝试仅清空内容...")
        # 备选方案：保留目录，删除内部文件
        for item in dir_path.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
            except Exception as sub_e:
                logger.error(f"    ❌ 无法删除文件 {item.name}: {sub_e}")


def cleanup_intermediate_files():
    """任务结束后清理中间文件"""
    logger.info("🧹 [收尾] 正在清理中间过程文件...")
    # 🌟 注意：这里绝对不包含 OUTPUT_FINAL (5_final)
    dirs_to_clean = [
        settings.OUTPUT_PREPROCESSED,
        settings.OUTPUT_INTEGRATED,
        settings.OUTPUT_CLASSIFIED,
        settings.OUTPUT_PARSED,
        settings.OUTPUT_UNIFIED
    ]
    for d in dirs_to_clean:
        safe_clear_directory(d)


def run_pipeline(input_dir=None):
    """主编排函数"""
    logger.info("=================================================")
    logger.info("===   🚀 Smart Review 知识库生成流水线 启动   ===")
    logger.info("=================================================")

    if input_dir:
        try:
            custom_input_path = Path(input_dir).resolve()
            settings.INPUTS_DIR = custom_input_path
            logger.info(f"🔄 [动态配置] 输入源: {settings.INPUTS_DIR}")
        except Exception as e:
             logger.error(f"❌ 设置自定义输入目录失败: {e}")

    total_start_time = time.time()

    try:
        # -----------------------------------------------------------------
        # [阶段 A] 预清理 (Pre-run Cleanup)
        # -----------------------------------------------------------------
        logger.info("[0/6] 正在初始化环境（清场模式）...")

        # 🌟 关键修改：加入 PREPROCESSED，确保不留任何旧数据
        dirs_to_reset = [
            settings.OUTPUT_PREPROCESSED, # <--- 之前为了缓存没加这个，现在必须加！
            settings.OUTPUT_INTEGRATED,
            settings.OUTPUT_CLASSIFIED,
            settings.OUTPUT_PARSED,
            settings.OUTPUT_UNIFIED,
            settings.OUTPUT_FINAL 
        ]

        for d in dirs_to_reset:
            safe_clear_directory(d)
        
        settings.setup_directories()
        logger.info("...环境准备就绪。")

        # -----------------------------------------------------------------
        # [阶段 B] 执行流水线
        # -----------------------------------------------------------------

        # 1. 预处理
        logger.info(f"\n--- [1/6] 运行【预处理器】 ---")
        step_start_time = time.time()
        run_preprocessing()
        logger.info(f"--- 耗时: {time.time() - step_start_time:.2f} s ---")

        # 2. 整合
        logger.info(f"\n--- [2/6] 运行【整合者】 ---")
        step_start_time = time.time()
        run_integration()
        logger.info(f"--- 耗时: {time.time() - step_start_time:.2f} s ---")

        # 3. 分类
        logger.info(f"\n--- [3/6] 运行【智能分类器】 ---")
        step_start_time = time.time()
        run_classification()
        logger.info(f"--- 耗时: {time.time() - step_start_time:.2f} s ---")

        # 4. 解析
        logger.info(f"\n--- [4/6] 运行【解析/提取器】 ---")
        step_start_time = time.time()
        run_parsing()
        logger.info(f"--- 耗时: {time.time() - step_start_time:.2f} s ---")

        # 5. 统一
        logger.info(f"\n--- [5/6] 运行【统一器】 ---")
        step_start_time = time.time()
        run_unification()
        logger.info(f"--- 耗时: {time.time() - step_start_time:.2f} s ---")

        # 6. 打包
        logger.info(f"\n--- [6/6] 运行【打包器】 ---")
        step_start_time = time.time()
        run_merging()
        logger.info(f"--- 耗时: {time.time() - step_start_time:.2f} s ---")

    except Exception as e:
        logger.critical(f"\n\n!!! 💥 流水线发生致命错误 💥 !!!")
        logger.critical(f"错误详情: {e}", exc_info=True)
        return None

    # -----------------------------------------------------------------
    # [阶段 C] 收尾 (Post-run Cleanup)
    # -----------------------------------------------------------------
    cleanup_intermediate_files()

    total_end_time = time.time()
    logger.info("\n=================================================")
    logger.info("===   ✅ 流水线全部执行完毕   ===")
    logger.info(f"    总耗时: {(total_end_time - total_start_time):.2f} 秒")
    
    try:
        final_file_path = settings.OUTPUT_FINAL / "Smart_Review_KB.json"
        if final_file_path.exists():
            return str(final_file_path.resolve())
        else:
            logger.error(f"❌ 错误：流程显示成功，但未找到文件: {final_file_path}")
            return None
    except Exception as e:
        logger.error(f"❌ 获取最终路径时出错: {e}")
        return None


if __name__ == "__main__":
    run_pipeline()