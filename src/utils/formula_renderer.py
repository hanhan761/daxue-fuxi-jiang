import base64
import io
import subprocess
import tempfile
import fitz  # PyMuPDF
import os
import sys
from pathlib import Path
import logging
from typing import Optional  # 兼容 Python 3.9

# --- 导入配置与 Logger (保持你的项目结构) ---
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings
    from src.utils.logger_config import logger
except ImportError:
    # 建立一个备用 logger
    logger = logging.getLogger("formula_renderer_fallback")
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s [%(levelname)-5s] : %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    logger.warning("无法导入 logger 或 settings。已回退到基础 logger。")


# -----------------------------------------------------------------


def render_latex_to_base64(latex_string: str) -> Optional[str]:
    """
    使用一个完整的 LaTeX 编译器 (pdflatex) 和 PyMuPDF 将 LaTeX 字符串渲染为
    一个高DPI的 PNG 图片。
    """
    if not latex_string:
        return None

    # 1. 动态创建 .tex 文件内容
    #
    #    --- 🌟 【第二次关键修复】 🌟 ---
    #    在 f-string 中，我们必须用 {{ 和 }} 来转义 { 和 } 字符。
    #    所有 LaTeX 包和环境都需要双花括号。
    #
    tex_content = rf"""
    \documentclass[preview, border=2pt]{{standalone}}
    \usepackage{{amsmath}}
    \usepackage{{amssymb}}
    \usepackage[UTF8]{{ctex}}
    \begin{{document}}
    $${latex_string}$$
    \end{{document}}
    """

    try:
        # 2. 使用 tempfile.TemporaryDirectory() 创建一个临时工作区
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_dir_path = Path(temp_dir)
            tex_file_path = temp_dir_path / "formula.tex"
            pdf_file_path = temp_dir_path / "formula.pdf"

            # 3. 将 .tex 字符串保存到临时文件
            with open(tex_file_path, "w", encoding="utf-8") as f:
                f.write(tex_content)

            # 4. 准备调用 pdflatex 进程
            process_args = [
                "pdflatex",
                "-interaction=nonstopmode",
                f"-output-directory={temp_dir}",
                str(tex_file_path)
            ]

            # 5. 执行编译
            completed_process = subprocess.run(
                process_args,
                capture_output=True,  # 捕获 stdout 和 stderr
                text=True,
                encoding="utf-8"
            )

            # 6. 错误处理 (编译失败)
            if completed_process.returncode != 0 or not pdf_file_path.exists():
                logger.error("!!! pdflatex 编译失败 !!!")
                logger.error(f"    原始 LaTeX: {latex_string}")
                logger.error(f"    --- STDOUT (编译日志) ---")
                logger.error(completed_process.stdout)
                logger.error(f"    --- STDERR ---")
                logger.error(completed_process.stderr)
                return None  # 返回 None，通知调用者渲染失败

            # 7. 使用 PyMuPDF (fitz) 转换 PDF -> PNG
            doc = fitz.open(pdf_file_path)
            page = doc.load_page(0)  # 加载第一页 (也是唯一一页)

            # 8. 使用高 DPI (300) 渲染为 pixmap
            pix = page.get_pixmap(dpi=300)
            doc.close()

            # 9. 将 pixmap 转换为 PNG 字节
            img_bytes = pix.tobytes("png")

            # 10. 输出 Base64 Data URL
            base64_str = base64.b64encode(img_bytes).decode('utf-8')
            return f"data:image/png;base64,{base64_str}"

    except FileNotFoundError:
        logger.critical("=" * 60)
        logger.critical("CRITICAL: 'pdflatex' 可执行文件未找到。")
        logger.critical("=" * 60)
        return None
    except Exception as e:
        logger.error(f"!!! 渲染 LaTeX 时发生未知错误: {e}", exc_info=True)
        return None


# --- 独立测试模块 ---
if __name__ == "__main__":
    logger.info("--- (独立运行) 开始测试 pdflatex (TeX Live) + PyMuPDF 渲染器 ---")

    # 测试用例 (包含旧版失败的矩阵)
    test_cases = {
        "简单中文": r"\text{纵向弹性模量}",
        "中英混合": r"E_c = V_f E_f + \text{中文注释}",
        "!!!! 矩阵测试 (旧版会失败) !!!!": r"A = \begin{pmatrix} 1 & \frac{a}{b} \\ 3 & 4 \end{pmatrix}",
        "!!!! 复杂公式 (旧版会失败) !!!!": r"\frac{\partial u}{\partial t} + u \cdot \nabla u = -\frac{1}{\rho} \nabla p + \nu \nabla^2 u"
    }

    html_out = "<h1>pdflatex (TeX Live) + PyMuPDF 渲染测试</h1>"
    html_out += "<h3>如果能看到矩阵和复杂公式，说明新版渲染器工作正常</h3>"
    html_out += "<style>body { background-color: #f0f0f0; } img { background-color: #fff; border: 1px solid #ddd; margin: 10px 0; max-width: 100%; }</style>"

    for name, latex in test_cases.items():
        logger.info(f"正在渲染: {name} -> {latex}")
        b64 = render_latex_to_base64(latex)
        if b64:
            html_out += f"<h3>{name}</h3><p><code>{latex}</code></p><img src='{b64}' /><hr>"
        else:
            logger.error(f"{name} 失败")
            html_out += f"<h3>{name} - <span style='color:red;'>渲染失败</span></h3><p><code>{latex}</code></p><hr>"

    # 更改测试输出文件名
    output_path = os.path.join(os.path.dirname(__file__), "formula_test_pdflatex.html")
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_out)

    logger.info(f"测试完成！请打开以下文件查看结果 (可能需要复制-粘贴到浏览器):\nfile://{output_path}")