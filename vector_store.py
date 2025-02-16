import os
import pickle
import tempfile
from typing import List, Dict
from langchain.docstore.document import Document
from document_splitter import DocumentSplitter
from faiss_vector_store import FAISS_VECTOR_STORE, DummyEmbeddings
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer
import config
import logger_util

logger = logger_util.get_logger()

class VectorStore:
    def __init__(self, chunk_size=700, chunk_overlap=10):
        self.splitter = DocumentSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.dimension = 1024
        #self.embedding = DummyEmbeddings(dim=1536)  # OpenAI 임베딩의 기본 차원
        self.embeddings = self._get_embedding_model()

        self.store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store")
        self.vector_store = FAISS_VECTOR_STORE(embedding=self.embeddings, dimension=self.dimension, store_path=self.store_path)

        self.indexed_files = dict()
        self.load_indexed_files_if_exist()
        

    def _get_embedding_model(self):
        try:
            if not os.path.exists(config.EMBEDDING_MODEL_PATH):
                embeddings = HuggingFaceEmbeddings(model_name=config.MODEL_NAME)
                os.makedirs(config.EMBEDDING_MODEL_PATH, exist_ok=True)
                model = SentenceTransformer(config.MODEL_NAME)
                model.save(config.EMBEDDING_MODEL_PATH)
            else:
                message = f"[DEBUG] 저장된 임베딩 모델을 로딩: {config.EMBEDDING_MODEL_PATH}"
                logger.info(message)
                embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_PATH)

            emb = embeddings.embed_query("Hello")
            self.dimension = len(emb) if len(emb) <= 1536 else 1536

            return embeddings
            
            if self.embeddings is None:
                raise ValueError("Failed to initialize embeddings")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {str(e)}")
            raise

    # 파일 1건 업로드
    async def upload(self, file_path: str, file_name: str, content: bytes) -> Dict:
        try:
            # 지원되지 않는 파일 타입은 제거
            if not self.splitter.is_supported_file_type(file_path):
                return {"status": "fail", "message": f"File {file_name} is not supported file type"}
            
            # 동일 파일 존재 시 벡터스토어 및 파일 목록에서 삭제
            if file_path in self.indexed_files.keys():
                self.delete_documents(list(file_path))

            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_name)[1]) as temp_file:
                temp_file.write(content)
                temp_file_path = temp_file.name
                creation_time = os.path.getctime(temp_file_path)

            # 문서 분할
            chunks = self.splitter.split_document(file_path, temp_file_path)
            
            # 분할된 청크를 벡터 스토어에 추가
            for chunk in chunks:
                self.vector_store.add_document(chunk)

            # 임시 파일 삭제
            os.unlink(temp_file_path)

            # 파일 타입 추출
            _, file_extension = os.path.splitext(file_path)
            file_type = file_extension.replace(".", "").upper()

            # 인덱싱된 파일 추가
            file_metadata = {
                "file_name": file_name,
                "file_type": file_type,
                "file_path": file_path,
                "last_updated": creation_time,
                "chunk_count": len(chunks)
            }
            self.indexed_files[file_path] = file_metadata

            return {"status": "success", "message": f"File {file_name} uploaded and indexed successfully"}
        except Exception as e:
            logger.exception(f"Upload failed: {str(e)}")
            return {"status": "fail", "message": str(e)}

    def search(self, query: str, k: int = 5) -> List[Dict]:
        try:
             result = self.vector_store.search(query, k=k)

             added_result = []
             for data in result:
                info = self.indexed_files[data['file_path']]
                for key, value in info.items():
                    data['metadata'][key] = value
                added_result.append(data)              

             return added_result
        except Exception as e:
            logger.exception(f"Search failed: {str(e)}")
            return []

    def get_documents(self) -> List[Dict]:
        return list(self.indexed_files.values()) if len(self.indexed_files) > 0 else []
    
    def get_document_chunks(self, file_path: str) -> List[str]:
        """
        주어진 file_path에 대한 모든 문서 청크를 반환합니다.
        
        :param file_path: 문서의 파일 경로
        :return: 문서 청크 리스트
        """
        return self.vector_store.get_document_chunks(file_path)

    def get_indexed_file_count(self) -> int:
        file_count = len(self.indexed_files)
        return file_count

    def get_db_size(self) -> int:
        return self.vector_store.get_db_size()

    def get_vector_db_path(self) -> str:
        return self.store_path

    def save_vector_db(self):
        self.vector_store.save_local(self.store_path)

    def empty_vector_store(self):
        self.vector_store.delete_all()
        self.indexed_files = {}

    def delete_documents(self, file_paths: List[str]):
        self.vector_store.delete_files(file_paths)
        for file_path in file_paths:
            if file_path in self.indexed_files:
                del self.indexed_files[file_path]
        

    def delete_all_documents(self):
        self.vector_store.delete_all()
        self.indexed_files = {}
        
    def load_indexed_files_if_exist(self):
        indexed_files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store") + "/indexed_files.pickle" 

        if os.path.exists(indexed_files_path):
            with open(indexed_files_path, 'rb') as f:
                self.indexed_files = pickle.load(f)
    
    def save_indexed_files_and_vector_db(self):
        os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), "store"), exist_ok=True)
        indexed_files_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store") + "/indexed_files.pickle"

        with open(indexed_files_path, 'wb') as f:
            pickle.dump(self.indexed_files, f)

        self.vector_store.save_local(self.store_path)

