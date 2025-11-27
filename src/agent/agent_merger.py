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
    步骤 6: 打包器主函数 (支持图谱连线版)
    """
    start_time = time.time()
    
    logger.info("=================================================")
    logger.info("===    📦 步骤 6: 打包 (Merging) 启动    ===")
    logger.info("=================================================")

    # 1. 定义路径
    input_dir = settings.OUTPUT_UNIFIED
    # ⬇️ [新增] 读取绘图师生成的连线文件
    edges_file = settings.OUTPUT_GRAPH_EDGES / "relationships.json"
    output_file = settings.OUTPUT_FINAL / "Smart_Review_KB.json"

    logger.info(f"📂 输入目录: {input_dir}")
    logger.info(f"🕸️ 连线文件: {edges_file}") # [新增日志]

    # --- 启动前检查 ---
    if not input_dir.exists():
        logger.error(f"❌ 错误：找不到“统一后”的目录 '{input_dir}'。")
        return

    # --- 收集所有已解析的 .json 文件 ---
    files_to_merge = []
    logger.info(f"🔍 正在递归扫描 .json 文件...")
    
    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.endswith('.json'):
                files_to_merge.append(os.path.join(root, filename))

    count = len(files_to_merge)
    if count == 0:
        logger.warning(f"⚠️  警告: 在 {input_dir} 中未找到任何 .json 文件。")
        return

    # --- 准备工作 ---
    kb_name = getattr(settings, "FINAL_KB_NAME", "自动生成的Smart Review知识库")
    
    # ⬇️ [关键修改] 准备一个映射表，用于把标题转换成 ID
    title_to_id_map = {} 
    
    final_knowledge_base = {
        "graph_metadata": {
            "name": kb_name,
            "createdAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "schema_version": "v2.0-generated"
        },
        "nodes": [], 
        "edges": [] 
    }

    default_stats = {"know": 0, "uncertain": 0, "dontKnow": 0}
    success_count = 0
    fail_count = 0

    logger.info("🚀 开始合并节点数据...")
    
    # --- 阶段 1: 处理节点 (Nodes) ---
    for file_path in tqdm(files_to_merge, desc="📦 打包节点", unit="file"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
                if not content: continue
                kp_data = json.loads(content)

            if not isinstance(kp_data, dict): continue

            # 补全数据
            if "stats" not in kp_data: kp_data["stats"] = default_stats
            if "createdAt" not in kp_data: kp_data["createdAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            
            # 生成 ID
            if "id" not in kp_data:
                title_hash = hashlib.md5(kp_data.get("title", "untitled").encode()).hexdigest()[:10]
                kp_data["id"] = f"gen_{title_hash}"

            # ⬇️ [关键逻辑] 记录 "标题 -> ID" 的映射，供后续连线使用
            if kp_data.get("title"):
                title_to_id_map[kp_data["title"]] = kp_data["id"]

            final_knowledge_base["nodes"].append(kp_data)
            success_count += 1

        except Exception as e:
            logger.error(f"❌ 处理节点失败 [{Path(file_path).name}]: {e}")
            fail_count += 1

    # --- 阶段 2: 处理连线 (Edges) [新增] ---
    logger.info("🕸️  正在处理图谱连线...")
    edges_list = []
    
    if edges_file.exists():
        try:
            with open(edges_file, 'r', encoding='utf-8') as f:
                raw_edges = json.loads(f.read())
            
            for edge in raw_edges:
                src_title = edge.get("source")
                tgt_title = edge.get("target")
                relation = edge.get("desc", "related")

                # 只有当起点和终点都在我们的节点库里时，才创建连线
                if src_title in title_to_id_map and tgt_title in title_to_id_map:
                    edges_list.append({
                        "id": f"edge_{len(edges_list)}",
                        "source": title_to_id_map[src_title], # 转换成 ID
                        "target": title_to_id_map[tgt_title], # 转换成 ID
                        "relation": relation
                    })
            
            logger.info(f"✅ 成功映射并合并 {len(edges_list)} 条连线。")
        except Exception as e:
            logger.error(f"❌ 合并连线失败: {e}")
    else:
        logger.warning(f"⚠️  未找到连线文件: {edges_file} (将生成无连线图谱)")

    # 把处理好的连线放进最终结果
    final_knowledge_base["edges"] = edges_list

    # --- 写入最终文件 ---
    try:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_knowledge_base, f, ensure_ascii=False, indent=4)

        file_size_mb = output_file.stat().st_size / (1024 * 1024)

        logger.info("-" * 40)
        logger.info(f"✅ 打包成功 (Success)")
        logger.info("-" * 40)
        logger.info(f"📊 统计:")
        logger.info(f"   - 节点数量: {success_count}")
        logger.info(f"   - 连线数量: {len(edges_list)}") # [新增]
        logger.info(f"📄 输出文件: {output_file.name}")
        logger.info(f"💾 文件大小: {file_size_mb:.2f} MB")
        logger.info(f"⏱️  总耗时: {time.time() - start_time:.2f} 秒")
        logger.info("-" * 40)

    except Exception as e:
        logger.critical(f"!!! ❌ 写入最终文件失败: {e}", exc_info=True)

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