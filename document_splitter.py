import os
import unittest
from typing import List, Optional

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader, PDFMinerLoader, Docx2txtLoader, UnstructuredPowerPointLoader,
    UnstructuredEmailLoader
)

class DocumentSplitter:
    def __init__(self, chunk_size: int = 1000, chunk_overlap: int = 200, chunk_separators: Optional[List[str]] = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_separators = chunk_separators or ["\n\n", "\n", " ", ""]

    def split_document(self, file_path: str) -> List[Document]:
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower()

        if file_extension in ['.txt', '.py', '.java', '.cpp', '.md', '.c', 'cpp', '.h', '.hpp', 'cs']:
            loader = TextLoader(file_path)
        elif file_extension == '.pdf':
            loader = PDFMinerLoader(file_path)
        elif file_extension in ['.docx', '.doc']:
            loader = Docx2txtLoader(file_path)
        elif file_extension in ['.pptx', '.ppt']:
            loader = UnstructuredPowerPointLoader(file_path)
        elif file_extension in ['.msg', '.eml']:
            loader = UnstructuredEmailLoader(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        documents = loader.load()
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.chunk_separators,
            length_function=len,
        )
        return text_splitter.split_documents(documents)

class TestDocumentSplitter(unittest.TestCase):
    def setUp(self):
        self.splitter = DocumentSplitter()

    def test_split_text_file(self):
        # 테스트용 텍스트 파일 생성
        with open('test.txt', 'w') as f:
            f.write("This is a test document.\n" * 100)

        chunks = self.splitter.split_document('test.txt')
        self.assertTrue(len(chunks) > 1)
        self.assertIsInstance(chunks[0], Document)

        # 테스트 파일 삭제
        os.remove('test.txt')

    def test_custom_chunk_size(self):
        custom_splitter = DocumentSplitter(chunk_size=50, chunk_overlap=0)
        
        # 테스트용 텍스트 파일 생성
        with open('test_custom.txt', 'w') as f:
            f.write("This is a test document.\n" * 10)

        chunks = custom_splitter.split_document('test_custom.txt')
        self.assertTrue(len(chunks) > 1)
        self.assertTrue(all(len(chunk.page_content) <= 50 for chunk in chunks))

        # 테스트 파일 삭제
        os.remove('test_custom.txt')

    def test_unsupported_file_type(self):
        with open('test.unsupported', 'w') as f:
            f.write("This is an unsupported file type.")

        with self.assertRaises(ValueError):
            self.splitter.split_document('test.unsupported')

        # 테스트 파일 삭제
        os.remove('test.unsupported')

    def test_custom_separators(self):
        custom_splitter = DocumentSplitter(chunk_size=30, chunk_overlap=0, chunk_separators=[". "])
        
        # 테스트용 텍스트 파일 생성
        with open('test_separators.txt', 'w') as f:
            f.write("Short sentence one. Longer sentence two. Even longer sentence three. The end.")

        chunks = custom_splitter.split_document('test_separators.txt')
        self.assertEqual(len(chunks), 4)  # 4개의 문장으로 분리되어야 함

        # 테스트 파일 삭제
        os.remove('test_separators.txt')

if __name__ == '__main__':
    unittest.main()
