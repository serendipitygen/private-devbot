import kiwipiepy_model
import shutil
import os

def prepare_kiwipiepy():
    # 소스 경로 확인
    source_path = kiwipiepy_model.__path__[0]
    
    # 대상 경로 생성
    target_path = 'build/main.dist/kiwipiepy_model'
    os.makedirs(target_path, exist_ok=True)
    
    # 모델 파일 복사
    shutil.copytree(source_path, target_path, dirs_exist_ok=True)