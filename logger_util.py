import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta


LOG_DIR = os.path.join(os.path.dirname(__file__), 'log')
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)


#--- Private DevBOT UI Logger -----------------------------------------------------------------
ui_logger = logging.getLogger('private_devbot_ui')
ui_logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
console_handler.setFormatter(console_formatter)
ui_logger.addHandler(console_handler)

file_handler = TimedRotatingFileHandler(
    filename=os.path.join(LOG_DIR, 'private_devbot_ui.log'),
    when='midnight',
    interval=1,
    backupCount=10,
    encoding='utf-8'
)

file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s [%(name)s] %(filename)s:%(lineno)d - %(message)s'
)
file_handler.setFormatter(file_formatter)
ui_logger.addHandler(file_handler)

#--- Private DevBOT UI File Monitoring Logger ---------------------------------------------
monitoring_logger = logging.getLogger('private_devbot_ui_monitoring')
monitoring_logger.setLevel(logging.DEBUG)

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_formatter = logging.Formatter('[%(asctime)s] %(levelname)s in %(module)s: %(message)s')
console_handler.setFormatter(console_formatter)
monitoring_logger.addHandler(console_handler)

file_handler = TimedRotatingFileHandler(
    filename=os.path.join(LOG_DIR, 'private_devbot_ui_monitoring.log'),
    when='midnight',
    interval=1,
    backupCount=10,
    encoding='utf-8'
)

file_handler.setLevel(logging.DEBUG)
file_formatter = logging.Formatter(
    '%(asctime)s %(levelname)s [%(name)s] %(filename)s:%(lineno)d - %(message)s'
)
file_handler.setFormatter(file_formatter)
monitoring_logger.addHandler(file_handler)

def cleanup_old_logs(days: int = 10):
    cutoff = datetime.now() - timedelta(days=days)
    for fname in os.listdir(LOG_DIR):
        if fname.startswith("private_devbot_ui."):
            path = os.path.join(LOG_DIR, fname)
            mtime = datetime.fromtimestamp(os.path.getmtime(path))
            if mtime < cutoff:
                os.remove(path)

cleanup_old_logs()


# ========================================
# TODO: 로그는 하나로 통일
logger = None
file_handler2 = None
console_handler2 = None

def get_logger(level=logging.DEBUG):
    """
    Logger를 설정하고 반환하는 유틸리티 함수.
    
    :param logger_name: 로거 이름 (기본값: 'app_logger')
    :param log_file: 로그 파일 경로 (기본값: 'app.log')
    :param level: 로깅 레벨 (기본값: logging.DEBUG)
    :return: 설정된 logger 객체
    """
    global logger, file_handler2, console_handler2

    
    if logger is None:
        # 로거 생성 및 레벨 설정
        logger_name='private_devbot_datastore'
        log_file='./log/private_devbot_datastore.log'

        logger = logging.getLogger(logger_name)
        file_handler2 = logging.FileHandler(log_file, encoding='utf-8')
        console_handler2 = logging.StreamHandler()
            # 로그 포맷 설정
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # 각 핸들러에 포맷 적용
        file_handler2.setFormatter(formatter)
        console_handler2.setFormatter(formatter)

        # 로거에 핸들러 추가 (중복 추가 방지)
        if not logger.handlers:
            logger.addHandler(file_handler2)
            logger.addHandler(console_handler2)

    logger.setLevel(level)
    file_handler2.setLevel(level)
    console_handler2.setLevel(level)

    return logger