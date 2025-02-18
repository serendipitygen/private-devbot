import easyocr
import shutil
import os

def prepare_easyocr():
    # easyocr Reader 초기화
    reader = easyocr.Reader(['ko', 'en'])
    
    # 소스 경로 확인 (실제 설치된 easyocr 모델 위치)
    source_path = os.path.join(os.path.dirname(easyocr.__file__), 'model')
    
    # 대상 경로 생성
    target_path = 'build/main.dist/easyocr_model'
    os.makedirs(target_path, exist_ok=True)
    
    # 모델 파일 복사
    shutil.copytree(source_path, target_path, dirs_exist_ok=True)
