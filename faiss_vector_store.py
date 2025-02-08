import os
import shutil
import json
import unittest
from typing import List
import numpy as np
import unicodedata
import chardet
import pickle

import faiss
from langchain.docstore.document import Document
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.embeddings.base import Embeddings

from search_util import extract_keywords
from logger_util import get_logger

logger = get_logger()

class FAISS_VECTOR_STORE:
    """
    FAISS_VECTOR_STORE는 langchain_community의 FAISS 벡터스토어를 감싸는 클래스입니다.
    주요 기능:
      - 빈 벡터스토어 생성
      - 문서(청크) 추가 (단일/복수)
      - 전체 문서 삭제
      - 유사도 검색
      - 인덱스 저장/로딩
    """

    def __init__(self, embedding: HuggingFaceEmbeddings, store_path, dimension=1536):
        """
        :param embedding: 임베딩 객체 (예: OpenAIEmbeddings, DummyEmbeddings 등)
        :param dimension: 임베딩 차원 (기본값: 1536)
        """
        self.embedding = embedding
        self.dimension = dimension
        self.vectorstore = None
        self.load_vectorstore(store_path)


    def load_vectorstore(self, store_path: str):
        """
        지정된 폴더에 저장된 FAISS 인덱스 파일을 로드하여 vector store를 초기화합니다.
        파일이 존재하지 않으면 새로운 인덱스와 문서 저장소를 생성합니다.
        
        :param store_path: FAISS 인덱스 파일이 위치한 폴더 경로
        :return: 복구되거나 새로 생성된 FAISS vector store 객체
        """
        index_file = os.path.join(store_path, "index.faiss")
        if os.path.exists(index_file):
            index = faiss.read_index(index_file)
        else:
            index = faiss.IndexFlatL2(self.dimension)
        
        store_file = os.path.join(store_path, "store.pkl")
        if os.path.exists(store_file): 
            logger.debug("[DEBUG] 기존에 존재하는 벡터스토어를 로딩합니다.")    
            with open(store_file, "rb") as f:
                store_file_data = pickle.load(f)
                store_data = store_file_data["docstore"]
                index_to_docstore_id = store_file_data["index_to_docstore_id"]
        else:
            logger.debug("[DEBUG] 벡터 DB를 새로 생성합니다.")
            store_data = InMemoryDocstore()
            index_to_docstore_id = {}
            
        self.vectorstore = FAISS(
            embedding_function=self.embedding, 
            index=index, 
            docstore=store_data, 
            index_to_docstore_id=index_to_docstore_id
        )
    
    def add_document(self, doc: Document):
        """문서 1건을 인덱싱합니다."""
        self.vectorstore.add_documents([doc])

    def add_documents(self, docs: List[Document]):
        """문서 여러 건(리스트)을 인덱싱합니다."""
        self.vectorstore.add_documents(docs)

    def delete_all(self):
        """벡터스토어 내의 모든 문서를 삭제합니다."""
        new_index = faiss.IndexFlatL2(self.dimension)
        new_docstore = InMemoryDocstore()
        self.vectorstore = FAISS(self.embedding, new_index, new_docstore, {})
    
    def delete_files(self, file_paths):
        """
        지정된 파일 경로에 해당하는 모든 문서를 벡터스토어에서 삭제합니다.
        
        :param file_paths: 삭제할 파일 경로 리스트
        """
        # 삭제할 문서 ID 리스트
        ids_to_delete = []
        
        # 각 문서의 메타데이터를 확인하여 삭제할 문서 ID 수집
        for doc_id, doc in self.vectorstore.docstore._dict.items():
            if doc.metadata.get('source') in file_paths:
                ids_to_delete.append(doc_id)
        
        # 수집된 ID에 해당하는 문서들을 벡터스토어에서 삭제
        if ids_to_delete:
            self.vectorstore.delete(ids_to_delete)

    def similarity_search(self, query: str, filter: dict = None, k: int = 4):
        """
        유사도 검색을 수행합니다.
        :param query: 검색 쿼리 텍스트
        :param filter: 메타데이터 필터 (선택사항)
        :param k: 반환할 문서 최대 건수 (기본: 4)
        :return: 검색 결과 Document 리스트
        """
        return self.vectorstore.similarity_search(query, filter=filter, k=k)
    
    def search(self, query: str, filter: dict = None, k: int = 4):
        """
        유사도 검색을 수행합니다.
        :param query: 검색 쿼리 텍스트
        :param filter: 메타데이터 필터 (선택사항)
        :param k: 반환할 문서 최대 건수 (기본: 4)
        :return: 검색 결과 Document 리스트 (추가된 metadata 포함)
            {
                "content": self._decode_text(doc.page_content),
                "score": similarity,
                "keywords": keywords,
                "file_path": doc.metadata['source'],
                "metadata": {
                    key: self._decode_text(value) if isinstance(value, bytes) else value
                    for key, value in doc.metadata.items()
                }
            }
        """
        # 기존 유사도 검색 결과를 가져옴
        results = self.vectorstore.similarity_search_with_score(query, filter=filter, k=k)
        
        # 결과를 반환할 리스트
        enhanced_results = []
        
        keywords = extract_keywords(query)

        for doc, similarity in results:
            similarity = 1. / (1. + float(similarity))
            # 기존에는 json.dumps와 json.loads를 사용하여 metadata를 변환하였으나,
            # 이를 대신하여 아래와 같이 처리하는 것이 더 효율적입니다.
            processed_metadata = {
                key: value.decode('utf-8') if isinstance(value, bytes) else value
                for key, value in doc.metadata.items()
            }
            enhanced_doc = {
                "content": self._decode_text(doc.page_content),
                "score": float(similarity),
                "keywords": keywords,
                "file_path": processed_metadata.get("source", ""),
                "metadata": processed_metadata
            }
            enhanced_results.append(enhanced_doc)
        
        return enhanced_results

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

    def save_local(self, save_path: str):
        """
        현재 벡터스토어를 로컬 파일 시스템에 저장합니다.
        :param save_path: 저장할 폴더 경로
        """
        #self.vectorstore.save_local(save_path)    
        try:
            if self.vectorstore is None or self.vectorstore.docstore is None or len(self.vectorstore.index_to_docstore_id) == 0:
                return
            
            os.makedirs(save_path, exist_ok=True)
            
            # FAISS 인덱스 저장
            faiss.write_index(self.vectorstore.index, os.path.join(save_path, "index.faiss"))
            
            # 나머지 데이터 저장
            store_data = {
                "docstore": self.vectorstore.docstore,
                "index_to_docstore_id": self.vectorstore.index_to_docstore_id
            }
            
            with open(os.path.join(save_path, "store.pkl"), "wb") as f:
                pickle.dump(store_data, f)
                
        except Exception as e:
            print(f"벡터스토어 저장 중 오류 발생: {str(e)}")
            raise

    def get_db_size(self) -> int:
        # FAISS doesn't provide a direct way to get the size, so we'll estimate
        db_size = len(self.vectorstore.index_to_docstore_id) * 1536 * 4  # 4 bytes per float
        return db_size


class DummyEmbeddings(Embeddings):
    """
    테스트를 위한 더미 임베딩 클래스.
    """

    def __init__(self, dim=4):
        self.dim = dim

    def embed_query(self, text: str) -> List[float]:
        return [float(len(text) + i) for i in range(self.dim)]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(text) for text in texts]


class TestFAISSVectorStore(unittest.TestCase):
    def setUp(self):
        self.embedding = DummyEmbeddings(dim=4)
        self.store = FAISS_VECTOR_STORE(embedding=self.embedding, dimension=4)

    def test_add_and_search_single_document(self):
        """문서 1건 추가 후 유사도 검색 테스트"""
        doc = Document(
            page_content="테스트 문서 내용",
            metadata={"file_path": "test/file1.txt"}
        )
        self.store.add_document(doc)
        results = self.store.similarity_search("테스트", k=1)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].metadata.get("file_path"), "test/file1.txt")

    def test_add_multiple_documents(self):
        """문서 5건 추가 테스트"""
        docs = [
            Document(page_content="문서 내용 1", metadata={"file_path": "test/file2.txt"}),
            Document(page_content="문서 내용 2", metadata={"file_path": "test/file2.txt"}),
            Document(page_content="문서 내용 3", metadata={"file_path": "test/file3.txt"}),
            Document(page_content="문서 내용 4", metadata={"file_path": "test/file4.txt"}),
            Document(page_content="문서 내용 5", metadata={"file_path": "test/file5.txt"}),
        ]
        self.store.add_documents(docs)
        results = self.store.similarity_search("문서", k=5)
        self.assertEqual(len(results), 5)

    def test_delete_all(self):
        """전체 문서 삭제 테스트"""
        docs = [
            Document(page_content="문서 A", metadata={"file_path": "A.txt"}),
            Document(page_content="문서 B", metadata={"file_path": "B.txt"}),
        ]
        self.store.add_documents(docs)
        self.store.delete_all()
        results = self.store.similarity_search("문서", k=2)
        self.assertEqual(len(results), 0)

    def test_save_and_load(self):
        """벡터스토어 저장 후 로딩 테스트"""
        docs = [
            Document(page_content="영속성 테스트 문서", metadata={"file_path": "persist.txt"})
        ]
        self.store.add_documents(docs)
        save_path = "test_faiss_index"
        self.store.save_local(save_path)
        loaded_store = FAISS_VECTOR_STORE.load_local(save_path, embedding=self.embedding)
        results = loaded_store.similarity_search("영속성", k=1)
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0].metadata.get("file_path"), "persist.txt")
        if os.path.exists(save_path):
            shutil.rmtree(save_path)


if __name__ == '__main__':
    unittest.main()
