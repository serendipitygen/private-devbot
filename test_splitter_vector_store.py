import unittest
import os
from document_splitter import DocumentSplitter
from faiss_vector_store import FAISS_VECTOR_STORE, DummyEmbeddings

class TestSplitterVectorStore(unittest.TestCase):
    def setUp(self):
        self.splitter = DocumentSplitter(chunk_size=100, chunk_overlap=20)
        self.embedding = DummyEmbeddings(dim=4)
        self.vector_store = FAISS_VECTOR_STORE(embedding=self.embedding, dimension=4)

    def test_split_and_add_to_vector_store(self):
        # 테스트용 텍스트 파일 생성
        with open('test_integration.txt', 'w') as f:
            f.write("This is a test document for integration.\n" * 20)

        # 문서 분할
        chunks = self.splitter.split_document('test_integration.txt')
        
        # 분할된 청크를 벡터 스토어에 추가
        for chunk in chunks:
            self.vector_store.add_document(chunk)

        # 벡터 스토어에서 유사도 검색 수행
        results = self.vector_store.similarity_search("test document", k=1)

        # 검증
        self.assertTrue(len(results) > 0)
        self.assertIn("test document", results[0].page_content)

        # 청크 수와 벡터 스토어의 문서 수가 일치하는지 확인
        self.assertEqual(len(chunks), len(self.vector_store.vectorstore.docstore._dict))

        # 테스트 파일 삭제
        os.remove('test_integration.txt')

    def test_split_and_add_multiple_documents(self):
        # 여러 테스트 파일 생성
        file_contents = [
            "This is the first test document.\n" * 10,
            "This is the second test document.\n" * 15,
            "This is the third test document.\n" * 20
        ]
        file_names = ['test1.txt', 'test2.txt', 'test3.txt']

        for name, content in zip(file_names, file_contents):
            with open(name, 'w') as f:
                f.write(content)

        total_chunks = 0
        for file_name in file_names:
            chunks = self.splitter.split_document(file_name)
            total_chunks += len(chunks)
            for chunk in chunks:
                self.vector_store.add_document(chunk)

        # 벡터 스토어에서 유사도 검색 수행
        results = self.vector_store.similarity_search("test document", k=3)

        # 검증
        self.assertEqual(len(results), 3)
        for result in results:
            self.assertIn("test document", result.page_content)

        # 총 청크 수와 벡터 스토어의 문서 수가 일치하는지 확인
        self.assertEqual(total_chunks, len(self.vector_store.vectorstore.docstore._dict))

        # 테스트 파일들 삭제
        for file_name in file_names:
            os.remove(file_name)

if __name__ == '__main__':
    unittest.main()
