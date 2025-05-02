import os
private_devbot_version = "v0.1.1"

# 상수 정의
server_port = 8123

# sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
# sentence-transformers/distiluse-base-multilingual-cased-v2
# sentence-transformers/xlm-r-100langs-bert-base-nli-stsb-mean-tokens
# jhgan/ko-sroberta-multilingual

# MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2" # 성능이 별로임
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "sentence-transformers","all-MiniLM-L6-v2")

# MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2" # all-MiniLM-L6-v2보다 나음
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "sentence-transformers","paraphrase-multilingual-MiniLM-L12-v2")

MODEL_NAME = "sentence-transformers/distiluse-base-multilingual-cased-v2" # 성능 괜찮음
EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                        "embedding_model", "sentence-transformers","distiluse-base-multilingual-cased-v2")

# MODEL_NAME = "jhgan/ko-sbert-multitask"
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "jhgan","ko-sbert-multitask")

# MODEL_NAME = "upskyy/bge-m3-korean"
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "upskyy","bge-m3-korean")

ALLOWED_EXTENSIONS = {
    "txt", "pdf", "png", "jpg", "jpeg", "gif", "csv", "md", 
    "html", "pptx", "docx", "epub", "odt"
}