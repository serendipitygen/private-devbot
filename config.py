import os
private_devbot_version = "v0.1.1"

MODEL_NAME = "nlpai-lab/KURE-v1" # 성능 아주 괜찮음
EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                        "embedding_model", "nlpai-lab","KURE-v1")


# MODEL_NAME = "sentence-transformers/distiluse-base-multilingual-cased-v2" # 성능 괜찮음
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "sentence-transformers","distiluse-base-multilingual-cased-v2")

# MODEL_NAME = "intfloat/multilingual-e5-large-instruct" # 성능 아주 괜찮음
# EMBEDDING_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
#                         "embedding_model", "intfloat","multilingual-e5-large-instruct")

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