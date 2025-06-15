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
import datetime

# 전역 임베딩 캐시: 모델 경로(또는 모델 이름)를 키로 하여 재사용
_EMBEDDING_MODEL_CACHE = {}  # type: dict[str, HuggingFaceEmbeddings]

logger = logger_util.get_logger()

class VectorStore:
    def __init__(self, rag_name: str | None = None, chunk_size=500, chunk_overlap=100):
        self.splitter = DocumentSplitter(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.dimension = 1024
        #self.embedding = DummyEmbeddings(dim=1536)  # OpenAI 임베딩의 기본 차원
        self.embeddings = None

        # RAG 별로 독립적인 벡터 스토어 디렉터리를 구성
        base_store_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "store")
        rag_name = rag_name or "default"
        self.store_path = os.path.join(base_store_path, rag_name)
        os.makedirs(self.store_path, exist_ok=True)

        self.vector_store = None

        self.indexed_files = dict()
        self.load_indexed_files_if_exist()
    
    def initialize_embedding_model_and_vectorstore(self):
        """임베딩/벡터스토어를 초기화한다. 이미 초기화된 경우 재사용한다."""
        # 1) Embeddings 객체 재사용
        if self.embeddings is None:
            self.embeddings = self._get_embedding_model()

        # 2) VectorStore 객체 재사용
        if self.vector_store is None:
            self.vector_store = FAISS_VECTOR_STORE(embedding=self.embeddings, store_path=self.store_path, dimension=self.dimension)

    def sync_indexed_files_and_vector_db(self):
        file_list = self.vector_store.get_unique_file_paths()
        no_existing_file_list = []
        for file_path in self.indexed_files.keys():
            if file_path not in file_list:
                no_existing_file_list.append(file_path)

        for file_path in no_existing_file_list:
            if file_path in self.indexed_files:
                del self.indexed_files[file_path]
                logger.error(f"deleted file_path in indexed_files : {file_path}")

        self.save_indexed_files_and_vector_db()
        

    def _get_embedding_model(self):
        # 전역 캐시 확인 -> 이미 로드된 경우 즉시 반환하여 중복 로딩 방지
        cached = _EMBEDDING_MODEL_CACHE.get(config.EMBEDDING_MODEL_PATH)
        if cached is not None:
            # dimension은 최초 계산된 값으로 세팅
            self.dimension = len(cached.embed_query("Hello"))
            logger.debug(f"[VectorStore] Reusing cached embeddings for {config.EMBEDDING_MODEL_PATH}")
            return cached

        try:
            if not os.path.exists(config.EMBEDDING_MODEL_PATH):
                embeddings = HuggingFaceEmbeddings(model_name=config.MODEL_NAME)
                os.makedirs(config.EMBEDDING_MODEL_PATH, exist_ok=True)
                model = SentenceTransformer(config.MODEL_NAME)
                model.save(config.EMBEDDING_MODEL_PATH)
            else:
                message = f"[DEBUG] Loading the saved embedding mode: {config.EMBEDDING_MODEL_PATH}"
                logger.info(message)
                embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_PATH)

            emb = embeddings.embed_query("Hello")
            self.dimension = len(emb) if len(emb) <= 1536 else 1536

            # 캐시에 저장하여 재사용
            _EMBEDDING_MODEL_CACHE[config.EMBEDDING_MODEL_PATH] = embeddings
            return embeddings
            
            if self.embeddings is None:
                raise ValueError("Failed to initialize embeddings")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {str(e)}")
            raise

    # 파일 1건 업로드
    async def upload(self, file_path: str, file_name: str, contents: dict) -> Dict:
        # 벡터 스토어가 아직 초기화되지 않은 경우(예: 초기 임베딩 모델 로드 실패 후 재시도 시)
        # 여기서 Lazy 초기화를 시도하여 업로드 실패 확률을 최소화한다.
        if self.vector_store is None:
            try:
                self.initialize_embedding_model_and_vectorstore()
            except Exception as e:
                logger.exception(f"[VectorStore] Failed to initialise vector store lazily: {e}")
                return {"status": "fail", "message": f"Vector store initialisation failed: {e}"}
        try:
            # 지원되지 않는 파일 타입은 제거
            if not self.splitter.is_supported_file_type(file_path):
                return {"status": "fail", "message": f"File {file_name} is not supported file type"}
            
            # 동일 파일 존재 시 벡터스토어 및 파일 목록에서 삭제
            if file_path in self.indexed_files.keys():
                self.delete_documents([file_path])

            _, file_extension = os.path.splitext(file_path)
            file_type = file_extension.lower()
            chunks = self.splitter.split_document(file_extension=file_type, contents=contents['contents'], file_path=file_path)
            
            # 분할된 청크를 벡터 스토어에 추가
            for chunk in chunks:
                chunk.page_content = chunk.page_content.strip()
                if len(chunk.page_content) == 0:
                    continue

                if contents['contents_type'] in ["EML", "MHT"]:
                    if len(contents["to"]) > 50: # 수신자 목록이 너무 긴 경우 앞에 수신자를 중심으로만 남김
                        contents["to"] = contents["to"][:50]

                    chunk.page_content = f"""이메일 제목: {contents['title']}\n보낸사람:{contents["from"]}\n받는사람:{contents["to"]}\n날짜:{contents['date']}\n{chunk.page_content}"""
                else:
                    chunk.page_content = f"""문서명: {file_name}\n{chunk.page_content}"""


                if len(chunk.page_content) > 5000:
                    logger.error("[ERROR] Cut the size of contents under 5,000 due to performance : {file_path}")
                    chunk.page_content = chunk.page_content[:4985] + "... (truncated)"
                
            self.vector_store.add_documents(chunks)

            # 인덱싱된 파일 추가
            file_metadata = {
                "file_name": file_name,
                "file_type": file_type,
                "file_path": file_path,
                "last_updated": int(datetime.datetime.now().timestamp()),
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
        """Return current vector store DB size in bytes.

        If the underlying vector store hasn't been initialised yet (self.vector_store is None)
        we simply return 0 so that API callers such as `/status` can succeed instead of raising
        an AttributeError.
        """
        if self.vector_store is None:
            return 0
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
        indexed_files_path = os.path.join(self.store_path, "indexed_files.pickle")

        if os.path.exists(indexed_files_path):
            with open(indexed_files_path, 'rb') as f:
                self.indexed_files = pickle.load(f)
    
    def save_indexed_files_and_vector_db(self):
        os.makedirs(self.store_path, exist_ok=True)
        indexed_files_path = os.path.join(self.store_path, "indexed_files.pickle")

        with open(indexed_files_path, 'wb') as f:
            pickle.dump(self.indexed_files, f)

        self.vector_store.save_local(self.store_path)