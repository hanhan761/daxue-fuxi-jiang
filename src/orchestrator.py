import os
import sys
import time
import shutil
from pathlib import Path

# --- 1. 关键：设置 sys.path ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.append(PROJECT_ROOT)

# [新增日志] 打印环境路径信息，用于调试导入问题
print(f"🔍 [Boot] PROJECT_ROOT detected at: {PROJECT_ROOT}")
print(f"🔍 [Boot] Python Executable: {sys.executable}")

try:
    from configs import settings
    from src.utils.logger_config import logger
    logger.info(f"✅ [Boot] 配置与日志模块加载成功")
except ImportError as e:
    print(f"!!! CRITICAL BOOTSTRAP FAILED !!!")
    print(f"Error details: {e}")
    sys.exit(1)

try:
    from src.agent.agent_preprocessor import run_preprocessing
    from src.agent.agent_integrator import run_integration
    from src.agent.agent_classifier import run_classification
    from src.agent.agent_parser import run_parsing
    from src.agent.agent_unifier import run_unification
    from src.agent.agent_merger import run_merging
    ##v5.5新增
    from src.agent.agent_graph import run_graph_building
    ##v5.5新增结束
    logger.info(f"✅ [Boot] 所有 Agent 核心模块导入成功")
except ImportError as e:
    logger.critical(f"!!! 严重错误：导入 agent 模块失败: {e}", exc_info=True)
    sys.exit(1)


def count_files(dir_path: Path):
    """[新增辅助函数] 仅用于日志：统计目录下文件数量"""
    if not dir_path.exists():
        return 0
    return len([p for p in dir_path.iterdir() if p.is_file()])


def safe_clear_directory(dir_path: Path):
    """
    安全清理目录：尝试删除整个目录，如果被占用（WinError 32），则尝试清空内部文件。
    """
    logger.info(f"🧹 [清理] 正在检查目录: {dir_path}")
    
    if not dir_path.exists():
        logger.info(f"    -> 目录不存在，跳过: {dir_path}")
        return

    try:
        shutil.rmtree(dir_path)
        logger.info(f"    -> ✅ 已完全删除目录: {dir_path.name}")
    except OSError as e:
        logger.warning(f"    ⚠️ 目录 {dir_path.name} 被占用 (Error: {e})，尝试进入目录仅清空内容...")
        # 备选方案：保留目录，删除内部文件
        deleted_count = 0
        failed_count = 0
        for item in dir_path.iterdir():
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                deleted_count += 1
            except Exception as sub_e:
                failed_count += 1
                logger.error(f"    ❌ 无法删除文件 {item.name}: {sub_e}")
        
        logger.info(f"    -> 目录内清理完成: 删除 {deleted_count} 项, 失败 {failed_count} 项")


def cleanup_intermediate_files():
    """任务结束后清理中间文件"""
    logger.info("=================================================")
    logger.info("🧹 [收尾] 正在启动中间过程文件清理程序...")
    
    # 🌟 注意：这里绝对不包含 OUTPUT_FINAL (5_final)
    dirs_to_clean = [
        settings.OUTPUT_PREPROCESSED,
        settings.OUTPUT_INTEGRATED,
        settings.OUTPUT_CLASSIFIED,
        settings.OUTPUT_PARSED,
        settings.OUTPUT_UNIFIED
    ]
    
    for i, d in enumerate(dirs_to_clean, 1):
        logger.info(f"  -> [Step {i}/{len(dirs_to_clean)}] 清理: {d.name}")
        safe_clear_directory(d)
    logger.info("✅ [收尾] 中间文件清理完毕")


def run_pipeline(input_dir=None):
    """主编排函数"""
    logger.info("=================================================")
    logger.info("===    🚀 Smart Review 知识库生成流水线 启动    ===")
    logger.info("=================================================")
    logger.info(f"📅 当前时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"📂 项目根目录: {PROJECT_ROOT}")

    if input_dir:
        try:
            custom_input_path = Path(input_dir).resolve()
            settings.INPUTS_DIR = custom_input_path
            logger.info(f"🔄 [动态配置] 检测到自定义输入路径")
            logger.info(f"    -> 输入源已更新为: {settings.INPUTS_DIR}")
        except Exception as e:
             logger.error(f"❌ 设置自定义输入目录失败: {e}")
    else:
        logger.info(f"ℹ️  [默认配置] 使用默认输入源: {settings.INPUTS_DIR}")

    # [新增日志] 检查输入目录是否有文件
    input_count = count_files(settings.INPUTS_DIR)
    logger.info(f"📊 [检查] 输入目录下现有文件数: {input_count} 个")
    if input_count == 0:
        logger.warning("⚠️  警告: 输入目录为空，流水线可能无法产出结果！")

    total_start_time = time.time()

    try:
        # -----------------------------------------------------------------
        # [阶段 A] 预清理 (Pre-run Cleanup)
        # -----------------------------------------------------------------
        logger.info("\n-------------------------------------------------")
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
        logger.info("✅ 环境准备就绪，输出目录已重建。")

        # -----------------------------------------------------------------
        # [阶段 B] 执行流水线
        # -----------------------------------------------------------------

        # 1. 预处理
        logger.info(f"\n>>> [1/6] 启动【预处理器 (Preprocessor)】")
        logger.info(f"    -> 目标: 清洗原始数据 -> {settings.OUTPUT_PREPROCESSED.name}")
        step_start_time = time.time()
        run_preprocessing()
        duration = time.time() - step_start_time
        count = count_files(settings.OUTPUT_PREPROCESSED)
        logger.info(f"    ✅ [完成] 预处理耗时: {duration:.2f} s | 产出文件: {count} 个")

        # 2. 整合
        logger.info(f"\n>>> [2/6] 启动【整合者 (Integrator)】")
        logger.info(f"    -> 目标: 整合清洗后的数据 -> {settings.OUTPUT_INTEGRATED.name}")
        step_start_time = time.time()
        run_integration()
        duration = time.time() - step_start_time
        count = count_files(settings.OUTPUT_INTEGRATED)
        logger.info(f"    ✅ [完成] 整合耗时: {duration:.2f} s | 产出文件: {count} 个")

        # 3. 分类
        logger.info(f"\n>>> [3/6] 启动【智能分类器 (Classifier)】")
        logger.info(f"    -> 目标: 对内容进行语义分类 -> {settings.OUTPUT_CLASSIFIED.name}")
        step_start_time = time.time()
        run_classification()
        duration = time.time() - step_start_time
        count = count_files(settings.OUTPUT_CLASSIFIED)
        logger.info(f"    ✅ [完成] 分类耗时: {duration:.2f} s | 产出文件: {count} 个")

        # 4. 解析
        logger.info(f"\n>>> [4/6] 启动【解析/提取器 (Parser)】")
        logger.info(f"    -> 目标: 提取结构化知识点 -> {settings.OUTPUT_PARSED.name}")
        step_start_time = time.time()
        run_parsing()
        duration = time.time() - step_start_time
        count = count_files(settings.OUTPUT_PARSED)
        logger.info(f"    ✅ [完成] 解析耗时: {duration:.2f} s | 产出文件: {count} 个")

        # 5. 统一
        logger.info(f"\n>>> [5/6] 启动【统一器 (Unifier)】")
        logger.info(f"    -> 目标: 统一格式标准 -> {settings.OUTPUT_UNIFIED.name}")
        step_start_time = time.time()
        run_unification()
        duration = time.time() - step_start_time
        count = count_files(settings.OUTPUT_UNIFIED)
        logger.info(f"    ✅ [完成] 统一耗时: {duration:.2f} s | 产出文件: {count} 个")

        # ⬇️ [新增] 5.5 构建图谱
        logger.info(f"\n>>> [5.5/6] 启动【绘图师 (Graph Builder)】")
        logger.info(f"    -> 目标: 分析知识关联 -> {settings.OUTPUT_GRAPH_EDGES.name}")
        step_start_time = time.time()
        run_graph_building()
        duration = time.time() - step_start_time
        logger.info(f"    ✅ [完成] 绘图耗时: {duration:.2f} s")


        # 6. 打包
        logger.info(f"\n>>> [6/6] 启动【打包器 (Merger)】")
        logger.info(f"    -> 目标: 生成最终 JSON 知识库 -> {settings.OUTPUT_FINAL.name}")
        step_start_time = time.time()
        run_merging()
        duration = time.time() - step_start_time
        logger.info(f"    ✅ [完成] 打包耗时: {duration:.2f} s")

    except Exception as e:
        logger.critical(f"\n\n!!! 💥 流水线发生致命错误 💥 !!!")
        logger.critical(f"错误发生阶段: 正在运行中...")
        logger.critical(f"错误详情: {e}", exc_info=True)
        return None

    # -----------------------------------------------------------------
    # [阶段 C] 收尾 (Post-run Cleanup)
    # -----------------------------------------------------------------
    cleanup_intermediate_files()

    total_end_time = time.time()
    total_duration = total_end_time - total_start_time

    logger.info("\n=================================================")
    logger.info("===    ✅ 流水线全部执行完毕 (SUCCESS)    ===")
    logger.info("=================================================")
    logger.info(f"⏱️  总耗时: {total_duration:.2f} 秒")
    
    try:
        final_file_path = settings.OUTPUT_FINAL / "Smart_Review_KB.json"
        if final_file_path.exists():
            size_mb = final_file_path.stat().st_size / (1024 * 1024)
            logger.info(f"📄 最终产物: {final_file_path.name}")
            logger.info(f"💾 文件大小: {size_mb:.2f} MB")
            logger.info(f"🔗 绝对路径: {final_file_path.resolve()}")
            return str(final_file_path.resolve())
        else:
            logger.error(f"❌ 错误：流程显示成功，但未找到最终文件: {final_file_path}")
            # 尝试列出输出目录内容，辅助调试
            if settings.OUTPUT_FINAL.exists():
                logger.info(f"   OUTPUT_FINAL 目录内容: {list(settings.OUTPUT_FINAL.glob('*'))}")
            return None
    except Exception as e:
        logger.error(f"❌ 获取最终路径时出错: {e}")
        return None


if __name__ == "__main__":
    logger.info(f"🏁 主程序入口启动 (PID: {os.getpid()})")
    run_pipeline()
    logger.info(f"🏁 主程序结束")