import logging
import os

logger = None
file_handler = None
console_handler = None

def get_logger(level=logging.DEBUG):
    """
    Logger를 설정하고 반환하는 유틸리티 함수.
    
    :param logger_name: 로거 이름 (기본값: 'app_logger')
    :param log_file: 로그 파일 경로 (기본값: 'app.log')
    :param level: 로깅 레벨 (기본값: logging.DEBUG)
    :return: 설정된 logger 객체
    """
    global logger, file_handler, console_handler

    
    if logger is None:
        # 로거 생성 및 레벨 설정
        logger_name='private_devbot_logger'
        log_file='./private_devbot.log'

        logger = logging.getLogger(logger_name)
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        console_handler = logging.StreamHandler()
            # 로그 포맷 설정
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # 각 핸들러에 포맷 적용
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # 로거에 핸들러 추가 (중복 추가 방지)
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)

    logger.setLevel(level)
    file_handler.setLevel(level)
    console_handler.setLevel(level)

    return logger