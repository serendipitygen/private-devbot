import os
import config
import time
import chardet
import unicodedata
import tempfile
from typing import List, Dict, Any

from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer
from langchain_community.vectorstores import FAISS
from langchain.text_splitter import RecursiveCharacterTextSplitter

from utils import process_file, get_directory_size
from search_util import extract_keywords
from file_path_converter import  path_to_filename

from logger_util import get_logger

logger = get_logger()

class VectorStore():
    def __init__(self):
        self.vector_store = None
        self.embeddings = None
        #self.vector_store_lock = asyncio.Lock()
        #self.indexed_file_list = {}
        self._chunk_size = 1000
        self._chunk_overlap = 200
        self._chunk_separators = ["\n\n", "\n", " ", ""]
        self.faiss_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faiss_index")

        self._get_embedding_model()
        #self.load_indexed_file_list()
        self.initialize_vector_store()

    def _get_embedding_model(self):
        try:
            if not os.path.exists(config.EMBEDDING_MODEL_PATH):
                self.embeddings = HuggingFaceEmbeddings(model_name=config.MODEL_NAME)
                os.makedirs(config.EMBEDDING_MODEL_PATH, exist_ok=True)
                model = SentenceTransformer(config.MODEL_NAME)
                model.save(config.EMBEDDING_MODEL_PATH)
            else:
                message = f"[DEBUG] 저장된 임베딩 모델을 로딩: {config.EMBEDDING_MODEL_PATH}"
                logger.info(message)
                self.embeddings = HuggingFaceEmbeddings(model_name=config.EMBEDDING_MODEL_PATH)
            
            if self.embeddings is None:
                raise ValueError("Failed to initialize embeddings")
        except Exception as e:
            logger.error(f"Error initializing embedding model: {str(e)}")
            raise

    # def load_indexed_file_list(self):
    #     try:
    #         if os.path.exists(config.INDEXED_FILE_LIST):
    #             with open(config.INDEXED_FILE_LIST, 'rb') as f:
    #                 self.indexed_file_list = pickle.load(f)
    #             logger.info(f"[INFO] Loaded {len(self.indexed_file_list)} indexed files")
    #         else:
    #             self.indexed_file_list = {}
    #             logger.info("[INFO] Created new indexed file list")
    #     except Exception as e:
    #         message = f"[ERROR] Failed to load indexed file list: {e}"
    #         logger.exception(message)
    #         raise Exception(message)

    # def save_indexed_file_list(self):
    #     if self.indexed_file_list:
    #         with open(config.INDEXED_FILE_LIST, 'wb') as f:
    #             pickle.dump(self.indexed_file_list, f)
    #         logger.info("[INFO] Saved indexed file list")

    # 니라f.indexed_file_list is None or len(self.indexed_file_list) == 0
    
    def get_indexed_file_count(self):
        if self.vector_store and hasattr(self.vector_store.docstore, "_dict"):
            return len(set(doc.metadata.get('source') for doc in self.vector_store.docstore._dict.values()))
        return 0

    def is_vector_store_initialized(self):
        return self.vector_store is not None
    
    def initialize_vector_store(self):
        try:
            logger.info(f"[INFO] Loading FAISS index from: {self.faiss_dir}")

            if not os.path.exists(self.faiss_dir):                
                self.create_new_vector_store()
                self.save_vector_db()
            else:                
                self.vector_store = FAISS.load_local(
                    self.faiss_dir,
                    self.embeddings,
                    allow_dangerous_deserialization=True
                )

            if self.vector_store:
                logger.info(f"[INFO] Successfully loaded FAISS index")
            else:
                raise Exception("[ERROR] Failed to load FAISS index")
        except Exception as e:
            message = f"[ERROR] Failed to load FAISS index: {str(e)}"
            logger.exception(message)
            raise Exception(message)
    
    def create_new_vector_store(self):
        with open("introduction_private_devbot.md", "r", encoding="utf-8") as f:
            text = f.read()

        text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
        texts = text_splitter.split_text(text)

        self.vector_store = FAISS.from_texts(texts, self.embeddings)

        self.empty_vector_store()

    def get_db_size(self):
        return get_directory_size(self.faiss_dir) / (1024 * 1024)  # MB로 변환
    
    def get_vector_db_path(self):
        return self.faiss_dir

    def empty_vector_store(self):        
        try:
            logger.info("[INFO] removing all documents on vector store")
            
            self.vector_store.docstore._dict.clear()
            
            logger.info(f"[INFO] removed all document on vector store at {self.faiss_dir}")
        except Exception as e:
            message = f"[ERROR] Failed to remove all documents on vector store: {str(e)}"
            logger.exception(message)
            self.vector_store = None
            raise Exception(message)

    def save_vector_db(self):
        # vector_store_lock이 정의되어 있지 않아 동기 방식으로 처리
        if self.vector_store:
            self.vector_store.save_local(self.faiss_dir)
            logger.info("[INFO] Saved vector store")

    async def upload(self, file_name, content, file_path):
        try:
            last_updated = int(time.time())  # 현재 시간으로 수정 시간 설정
            logger.debug(f"[DEBUG] Upload request - Path: {file_path}, Modified: {last_updated}")
                        
            # 기존 문서 삭제 (업데이트가 필요한 경우만) TODO: 문서 목록 관리를 통해 아래 코드 실행 여부 결정
            await self.delete_file(file_path)
            
            texts = await self._process_and_add_documents(content, file_name, file_path, last_updated)
            
            logger.info(f"[INFO] Updated index timestamp for {file_path}: {time.ctime(last_updated)}")
            
            return {
                "message": "File uploaded successfully",
                "filename": file_path,
                "chunks": len(texts) if texts else 0
            }
        except Exception as e:
            logger.exception(e)
            raise e
        
        
    async def reindex_documents(self, chunk_size: int, chunk_overlap: int, chunk_separators: List[str]):
        try:
            # 1. 기존 벡터 스토어에 저장된 모든 청크들을 파일단위로 메타데이터 임시 저장
            file_contents = {}
            for doc in self.vector_store.docstore._dict.values():
                file_path = doc.metadata.get('source')
                converted_file_name = path_to_filename(file_path)
                if file_path not in file_contents:
                    file_contents[converted_file_name] = {
                        'content': [],
                        'metadata': doc.metadata
                    }
                file_contents[converted_file_name]['content'].append(doc.page_content)

            logger.debug(f"File contents: {file_contents}")
            # 2. 기존 벡터 스토어에 저장된 모든 청크들을 임시 폴더에 임시 파일 단위로 생성
            with tempfile.TemporaryDirectory() as temp_dir:
                for converted_file_name, data in file_contents.items():
                    temp_file_path = os.path.join(temp_dir, os.path.basename(converted_file_name))
                    with open(temp_file_path, 'w', encoding='utf-8') as f:
                        f.write('\n\n'.join(data['content']))

                # 3. 벡터 스토어 초기화
                self.empty_vector_store()

                # 4. 새로운 설정으로 임시 파일들을 다시 인덱싱
                for file_name in os.listdir(temp_dir):
                    file_path = os.path.join(temp_dir, file_name)
                    logger.debug(f"Reindexing file: {file_path}")
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    original_metadata = file_contents[file_name]['metadata']
                    await self._process_and_add_documents(
                        content, 
                        original_metadata['file_name'],
                        original_metadata['source'],
                        original_metadata['timestamp'],
                        chunk_size,
                        chunk_overlap,
                        chunk_separators
                    )
                print("---------------------------------------------")
                print(self.indexed_file_list)
                print(self.vector_store.docstore._dict)
                print("---------------------------------------------")


            # 5. indexed_file_list 업데이트
            self.indexed_file_list = {doc.metadata['source']: doc.metadata['timestamp'] for doc in self.vector_store.docstore._dict.values()}

            # 6. 성공 여부 반환
            return {"status": "success", "message": "Documents reindexed successfully"}

        except Exception as e:
            logger.exception(f"Error during reindexing: {str(e)}")
            return {"status": "error", "message": f"Reindexing failed: {str(e)}"}   
            
    async def _process_and_add_documents(
            self, content: bytes, file_name: str, file_path: str, last_updated: int,
            chunk_size: int = 1000, chunk_overlap: int = 200, chunk_separators: List[str] = ["\n\n", "\n", " ", ""]):
        try:
            texts = process_file(
                file_content=content, 
                file_name=file_name, 
                file_path=file_path, 
                last_updated=last_updated
            )
            logger.debug(f"[DEBUG] Processed {len(texts)} documents")

            # TODO: 문서 종류에 따라 다른 TextSplitter 사용해야 함 => 별도 클래스로
            # 청크 생성
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=chunk_separators
            )
            chunks = text_splitter.split_documents(texts)
            self.vector_store.add_documents(chunks)

            # 저장
            self.save_vector_db()
            logger.debug(f"[DEBUG] Saved vector store with {len(self.vector_store.docstore._dict)} total documents")
            
            return texts
        except Exception as e:
            message = f"[ERROR] Document processing failed: {str(e)}"
            logger.exception(message)
            raise Exception(message)

    def _decode_text(self, text):
        if isinstance(text, str):
            return text

        encodings = ['utf-8', 'iso-8859-1', 'euc-kr', 'cp949']
        
        for encoding in encodings:
            try:
                decoded = text.decode(encoding)
                return unicodedata.normalize('NFC', decoded)
            except UnicodeDecodeError:
                continue

        # If all known encodings fail, use chardet to detect encoding
        detected = chardet.detect(text)
        try:
            decoded = text.decode(detected['encoding'])
            return unicodedata.normalize('NFC', decoded)
        except:
            # If all else fails, return the original text
            return text

    def search(self, query, k):
        logger.info(f"[DEBUG] Searching with query: {query}")

        keywords = extract_keywords(query)
        logger.debug(f"[DEBUG] keywords: {keywords}")
            
        docs = self.vector_store.similarity_search_with_score(
            query=query, 
            k=k
        )
        logger.debug(f"[DEBUG] Found {len(docs)} documents")
        
        results = []
        for doc, distance in docs:
            similarity = 1. / (1. + float(distance))
            logger.debug(f"[DEBUG] Doc: {doc.metadata['source']}, Doc id: {doc.id}, Distance: {distance}, Similarity: {similarity}")
            
            results.append({
                "content": self._decode_text(doc.page_content),
                "score": similarity,
                "keywords": keywords,
                "file_path": doc.metadata['source'],
                "metadata": {
                    key: self._decode_text(value) if isinstance(value, bytes) else value
                    for key, value in doc.metadata.items()
                }
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        logger.debug(f"[DEBUG] Returning {len(results)} sorted results")
        
        return {"results": results}

    def get_documents(self):
        try:
            documents = []
            doc_paths = {}  # 파일 경로별 청크 수 집계
            
            # 먼저 벡터 스토어에서 문서 정보 수집
            if self.vector_store and hasattr(self.vector_store.docstore, '_dict'):
                for doc in self.vector_store.docstore._dict.values():
                    path = doc.metadata.get("source")
                    if path:
                        if path not in doc_paths:
                            doc_paths[path] = {
                                "file_name": doc.metadata.get("file_name", os.path.basename(path)),
                                "file_type": doc.metadata.get("file_type", "unknown"),
                                "last_updated": doc.metadata.get("timestamp", 0),
                                "chunk_count": 1
                            }
                        else:
                            doc_paths[path]["chunk_count"] += 1

            # 문서 목록 생성
            documents = [
                {
                    "file_name": info["file_name"],
                    "file_type": info["file_type"],
                    "last_updated": info["last_updated"],
                    "chunk_count": info["chunk_count"],
                    "file_path": path
                }
                for path, info in doc_paths.items()
            ]
            
            if len(documents) > 0:
                return {"documents": sorted(documents, key=lambda x: x["last_updated"])}
            else:
                return []
        except Exception as  e:
            logger.exception(e)
            return []

    async def reset_storage(self):
        self.empty_vector_store()
    
    async def delete_file(self, file_path: str):
        logger.debug(f"[DEBUG] Deleting file: {file_path}")

        if not self.vector_store:
            return {
                "status": "fail",
                "message": f"File {file_path} is not on the vector store",
                "removed_documents": 0
            }
            
        docs_to_remove = [
            doc_id for doc_id, doc in self.vector_store.docstore._dict.items()
            if doc.metadata.get("source") == file_path
        ]

        for doc_id in docs_to_remove:
            del self.vector_store.docstore._dict[doc_id]

        # Rebuild the FAISS index
        # remaining_docs = list(self.vector_store.docstore._dict.values())
        # if remaining_docs:
        #     temp_store = FAISS.from_documents(remaining_docs, self.embeddings)
        #     self.vector_store = temp_store
        # else:
        #     self.empty_vector_store()

        # Save changes
        self.save_vector_db()

        logger.info(f"[INFO] Successfully deleted file: {file_path}")
        
        return {
            "status": "success",
            "message": f"File {file_path} has been deleted from the index and vector store",
            "removed_documents": len(docs_to_remove) if self.vector_store else 0
        }
        
    async def delete_all_files(self):
        try:
            self.empty_vector_store()
            self.save_vector_db

            return {
                "status": "success",
                "message": "All files have been deleted from the vector store and index"
            }
        except Exception as e:
            message = f"[ERROR] Failed to delete all files: {str(e)}"
            logger.exception(message)
            raise Exception(message)

