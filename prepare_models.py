import os
import shutil
import easyocr
import kiwipiepy_model
from pathlib import Path
import pkg_resources
from sentence_transformers import SentenceTransformer

def prepare_easyocr():
    print("Preparing EasyOCR models...")
    reader = easyocr.Reader(['ko', 'en'])
    source_path = os.path.join(os.path.dirname(easyocr.__file__), 'model')
    target_path = 'build/main.dist/easyocr_model'
    os.makedirs(target_path, exist_ok=True)
    shutil.copytree(source_path, target_path, dirs_exist_ok=True)

def prepare_kiwipiepy():
    print("Preparing Kiwipiepy models...")
    source_path = kiwipiepy_model.__path__[0]
    target_path = 'build/main.dist/kiwipiepy_model'
    os.makedirs(target_path, exist_ok=True)
    shutil.copytree(source_path, target_path, dirs_exist_ok=True)

def prepare_embedding_model():
    print("Preparing Embedding models...")
    # 현재 프로젝트의 embedding_model 폴더 경로
    source_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "embedding_model")
    target_path = 'build/main.dist/embedding_model'
    
    if os.path.exists(source_path):
        print(f"Copying embedding models from {source_path}")
        shutil.copytree(source_path, target_path, dirs_exist_ok=True)
    else:
        print(f"Warning: Embedding model directory not found at {source_path}")

def prepare_distribution_metadata():
    print("Preparing distribution metadata...")
    packages = ['torchaudio', 'torch', 'transformers', 'sentence_transformers']
    metadata_dir = 'build/main.dist/distribution_metadata'
    os.makedirs(metadata_dir, exist_ok=True)
    
    for package in packages:
        try:
            dist = pkg_resources.get_distribution(package)
            if dist.has_metadata('METADATA'):
                metadata = dist.get_metadata('METADATA')
                with open(os.path.join(metadata_dir, f'{package}-METADATA'), 'w', encoding='utf-8') as f:
                    f.write(metadata)
            if dist.has_metadata('entry_points.txt'):
                entry_points = dist.get_metadata('entry_points.txt')
                with open(os.path.join(metadata_dir, f'{package}-entry_points.txt'), 'w', encoding='utf-8') as f:
                    f.write(entry_points)
        except Exception as e:
            print(f"Warning: Could not copy metadata for {package}: {str(e)}")

if __name__ == "__main__":
    prepare_easyocr()
    prepare_kiwipiepy()
    prepare_embedding_model()
    prepare_distribution_metadata()
    print("Model and metadata preparation completed!")