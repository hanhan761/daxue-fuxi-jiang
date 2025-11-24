import logging
import os
import sys
from logging.handlers import RotatingFileHandler

# --- 1. 导入配置 ---
# (同 agent 脚本, 需要将项目根目录添加到 sys.path)
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(PROJECT_ROOT)

try:
    from configs import settings

    LOG_FILE_PATH = settings.LOG_FILE
    LOG_DIR = settings.LOG_DIR

    # 【关键】在配置 logger 之前，必须确保日志目录存在
    os.makedirs(LOG_DIR, exist_ok=True)

except ImportError:
    print("CRITICAL: logger_config.py 无法导入 settings。")
    print("将使用备用日志配置 (logs/fallback.log)。")

    # 创建一个备用路径
    LOG_DIR = os.path.join(PROJECT_ROOT, "logs")
    LOG_FILE_PATH = os.path.join(LOG_DIR, "fallback.log")
    os.makedirs(LOG_DIR, exist_ok=True)
except Exception as e:
    print(f"CRITICAL: logger_config.py 在设置路径时出错: {e}")
    sys.exit(1)

# --- 2. 定义日志格式 ---
LOG_FORMATTER = logging.Formatter(
    "%(asctime)s [%(levelname)-5.5s] [%(name)-15.15s] : %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
LOG_LEVEL = logging.INFO  # 设置全局日志级别为 INFO


def setup_logger():
    """
    配置并返回一个全局 logger 实例。
    """
    # 1. 获取一个 logger 实例 (使用一个统一的名称)
    #    (在 python 中, 多次调用 getLogger(name) 会返回同一个实例)
    logger = logging.getLogger("SmartReviewGenerator")
    logger.setLevel(LOG_LEVEL)

    # 2. 【关键】防止重复添加 handler
    #    如果 logger.handlers 已经有内容, 说明已被配置, 直接返回
    if logger.handlers:
        return logger

    # 3. 配置 File Handler (写入文件)
    #    (使用 RotatingFileHandler 避免日志文件无限增大)
    file_handler = RotatingFileHandler(
        LOG_FILE_PATH,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=2,  # 保留 2 个备份
        encoding='utf-8'
    )
    file_handler.setFormatter(LOG_FORMATTER)
    file_handler.setLevel(LOG_LEVEL)

    # 4. 配置 Console Handler (打印到控制台)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(LOG_FORMATTER)
    console_handler.setLevel(LOG_LEVEL)

    # 5. 添加 Handlers
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # 6. (可选) 防止日志向上传播到 root logger
    logger.propagate = False

    logger.info("Logger setup complete. Logging to console and file.")
    return logger


# --- 3. 【核心】创建并导出 logger 实例 ---
# 当其他文件执行 'from src.utils.logger_config import logger' 时,
# 它们导入的是这个已经配置好的实例。
logger = setup_logger()

# --- 4. (可选) 独立运行测试 ---
if __name__ == "__main__":
    print("--- (独立运行 logger_config.py 进行测试) ---")
    logger.debug("这是一条 DEBUG 日志 (不应显示)")
    logger.info("这是一条 INFO 日志 (应显示)")
    logger.warning("这是一条 WARNING 日志 (应显示)")
    logger.error("这是一条 ERROR 日志 (应显示)")
    logger.critical("这是一条 CRITICAL 日志 (应显示)")
    print(f"\n测试完毕。请检查控制台输出，并查看日志文件：{LOG_FILE_PATH}")