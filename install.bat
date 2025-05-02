import os

# 상수 정의
private_devbot_version = "v0.1.1"
server_port = 8123

# 저성능 PC용
# MODEL_NAME = "sentence-transformers/distiluse-base-multilingual-cased-v2" # 성능 괜찮음
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "sentence-transformers","distiluse-base-multilingual-cased-v2")

# 고성능 PC용
MODEL_NAME = "scottsuk0306/bge-m3-ko-v1.1"
EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                         "embedding_model", "scottsuk0306","bge-m3-ko-v1.1")

# 아래 사용하지 않으므로 삭제
ALLOWED_EXTENSIONS = {
    "txt", "pdf", "png", "jpg", "jpeg", "gif", "csv", "md", 
    "html", "pptx", "docx", "epub", "odt"
}