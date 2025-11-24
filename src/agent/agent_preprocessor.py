import os
import sys
import json
from tqdm import tqdm
import nltk
from unstructured.partition.auto import partition
from unstructured.cleaners.core import clean, clean_extra_whitespace

# --- 1. 导入配置与 Logger ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    # 🌟 导入配置好的 logger 实例
    from src.utils.logger_config import logger
except ImportError as e:
    print(f"CRITICAL: 1_preprocessor.py 无法导入 settings 或 logger: {e}")
    sys.exit(1)


# --- 2. NLTK 依赖检查 ---
def download_nltk_data():
    """
    检查并下载 'nltk' 的 'punkt' 模块，用于句子分割。
    """
    try:
        nltk.data.find('tokenizers/punkt')
        logger.debug("NLTK 'punkt' 模块已安装。")
    except LookupError:
        logger.info("NLTK 'punkt' 模块未找到，正在下载...")
        nltk.download('punkt', quiet=True)
        logger.info("NLTK 'punkt' 下载完成。")


# --- 3. 核心预处理逻辑 ---
def run_preprocessing():
    """
    步骤1：预处理器主函数。
    - 读取: settings.INPUTS_DIR (递归)
    - 写入: settings.OUTPUT_PREPROCESSED (保持目录结构)
    """
    logger.info("--- 步骤 1: 预处理 (Pre-processing) ---")
    download_nltk_data()

    input_dir = settings.INPUTS_DIR
    output_dir = settings.OUTPUT_PREPROCESSED

    # --- 收集所有输入文件 (递归扫描) ---
    files_to_process = []
    logger.info(f"正在扫描输入目录 (递归): {input_dir}")
    
    if not input_dir.exists():
        logger.error(f"输入目录不存在: {input_dir}")
        return

    for root, dirs, files in os.walk(input_dir):
        for filename in files:
            if filename.startswith('.'): continue

            file_path = os.path.join(root, filename)
            relative_path = os.path.relpath(file_path, input_dir)
            base_json_name = os.path.splitext(relative_path)[0] + '.json'
            output_path = output_dir / base_json_name

            files_to_process.append((file_path, output_path))

    if not files_to_process:
        logger.info("未找到需要处理的新文件。")
        logger.info("完成: 预处理。")
        return

    logger.info(f"扫描完成，找到 {len(files_to_process)} 个新文件需要处理。")

    # --- 开始处理 ---
    success_count = 0
    for file_path, output_path in tqdm(files_to_process, desc="预处理进度"):
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_data = []

            # 🌟 [关键修复] 针对 txt 文件的特殊处理
            # 解决 Windows 下 libmagic 缺失导致 partition 报错的问题
            if file_path.lower().endswith('.txt'):
                try:
                    logger.debug(f"检测到 TXT 文件，使用手动读取模式: {file_path}")
                    with open(file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                    
                    # 手动构造 element 结构
                    output_data = [{
                        "id": "txt_manual_read",
                        "type": "NarrativeText",
                        "text": text_content,
                        "metadata": {"filename": os.path.basename(file_path)}
                    }]
                except Exception as txt_e:
                    logger.error(f"手动读取 TXT 文件失败: {txt_e}")
                    continue
            else:
                # 对于 PDF/PPT/DOCX，继续使用 unstructured partition
                try:
                    elements = partition(
                        filename=file_path,
                        strategy="auto",
                        languages=['chi_sim', 'eng']
                    )

                    for el in elements:
                        if hasattr(el, 'text') and el.text:
                            el.text = clean(el.text, bullets=True)
                            el.text = clean_extra_whitespace(el.text)

                        element_dict = {
                            "id": str(el.id),
                            "type": str(el.category),
                            "text": el.text,
                            "metadata": el.metadata.to_dict() if hasattr(el, 'metadata') else {}
                        }
                        output_data.append(element_dict)
                except Exception as part_e:
                    # 如果 unstructured 失败，不要崩溃，记录错误并跳过
                    logger.error(f"Unstructured 解析失败: {part_e}")
                    continue

            # 只有当 output_data 不为空时才写入
            if output_data:
                with open(output_path, 'w', encoding='utf-8') as f:
                    json.dump(output_data, f, ensure_ascii=False, indent=4)
                success_count += 1
            else:
                logger.warning(f"文件处理后无内容: {file_path}")

        except Exception as e:
            # 🌟 捕获单个文件错误，避免整个流程崩溃
            logger.error(f"!!! 处理文件 {file_path} 时发生严重错误: {e}")

    logger.info(f"完成: 预处理。成功处理 {success_count}/{len(files_to_process)} 个文件。")
    logger.info(f"所有输出均已保存到 {output_dir}")


if __name__ == "__main__":
    try:
        settings.setup_directories()
        run_preprocessing()
    except Exception as e:
        print(f"运行失败: {e}")