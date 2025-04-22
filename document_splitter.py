import os
import unittest
from typing import List, Optional
import easyocr
from PIL import Image
import cv2
import numpy as np
import chardet
from io import StringIO
import re

from langchain.docstore.document import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import (
    TextLoader, PDFMinerLoader, Docx2txtLoader, UnstructuredPowerPointLoader,
    UnstructuredEmailLoader
)
from langchain_community.document_loaders.base import BaseLoader

#from search_util import extract_keywords

class StringLoader(BaseLoader):
    def __init__(self, content: str):
        self.content = content

    def load(self):
        return [Document(page_content=self.content, metadata={'source':'string_data'})]

class ImageLoader:
    def __init__(self, file_path: str):
        self.file_path = file_path
        # 한번만 reader를 초기화하도록 클래스 변수로 설정
        if not hasattr(ImageLoader, 'reader'):
            ImageLoader.reader = easyocr.Reader(['ko', 'en'])  # 한글, 영어 지원

    def _validate_text(self, text: str) -> bool:
        """추출된 텍스트의 유효성을 검사합니다."""
        if not text:
            return False
            
        # 최소 텍스트 길이 검사
        if len(text.strip()) < 10:  # 10자 미만인 경우 제외
            return False
            
        # 의미 있는 텍스트인지 검사
        meaningful_chars = sum(1 for c in text if c.isalnum() or c.isspace())
        total_chars = len(text)
        if total_chars == 0 or meaningful_chars / total_chars < 0.3:  # 의미있는 문자 비율이 30% 미만이면 제외
            return False
            
        # 특수문자나 기호만 있는 경우 제외
        if not any(c.isalnum() for c in text):
            return False
            
        # 짧은 줄(5자 이하)이 많은 경우 제외
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        if lines:  # 빈 줄 제외
            short_lines = sum(1 for line in lines if len(line) <= 5)
            if short_lines / len(lines) >= 0.5:  # 짧은 줄이 50% 이상이면 제외
                return False
        # 키워드가 2개 이하인 라인이 많은 경우 제외
        # if lines:
        #     short_lines = sum(1 for line in lines if len(extract_keywords(line)) <= 1)
        #     if short_lines / len(lines) >= 0.5:  # 키워드가 2개 이하인 라인이 50% 이상이면 제외
        #         return False

        return True

    def load(self) -> List[Document]:

        try:
            # PIL로 이미지 열기 및 검증
            with Image.open(self.file_path) as img:
                # PIL 이미지를 numpy 배열로 변환
                img_np = np.array(img)
                
                # RGB가 아닌 경우 변환
                if len(img_np.shape) == 2:  # 흑백 이미지
                    img_np = cv2.cvtColor(img_np, cv2.COLOR_GRAY2RGB)
                elif len(img_np.shape) == 3 and img_np.shape[2] == 4:  # RGBA 이미지
                    img_np = cv2.cvtColor(img_np, cv2.COLOR_RGBA2RGB)
                
                # OCR 수행
                result = self.reader.readtext(img_np)
                
                # 텍스트가 추출되지 않은 경우
                if not result:
                    raise ValueError("텍스트를 추출할 수 없는 이미지입니다.")
                
                # 추출된 텍스트 결합 및 검증
                text = '\n'.join([text for _, text, conf in result if conf > 0.5]) 
                
                if not self._validate_text(text):
                    raise ValueError("추출된 텍스트가 유효하지 않습니다.")
                
                # Document 객체 생성
                return [Document(
                    page_content=text,
                    metadata={
                        "source": self.file_path,
                        "ocr_confidence": sum(conf for _, _, conf in result) / len(result)  # 평균 신뢰도 추가
                    }
                )]
        except Exception as e:
            raise ValueError(f"이미지 처리 중 오류 발생: {str(e)}")

class DocumentSplitter:
    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 100, chunk_separators: Optional[List[str]] = None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunk_separators = chunk_separators or ["\n\n", "\n", " ", ""]

    def split_document(self, file_extension: str, contents: str, file_path: str) -> List[Document]:
        if file_extension in ['.txt', '.py', '.java', '.cpp', '.md', '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.eml', '.mht',
        '.c', 'cpp', '.h', '.hpp', '.cs', '.yaml', '.yml', '.java', 'js', 'ts', 'dart', '.dart', '.devbot']:
            loader = StringLoader(contents)
            
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.chunk_separators,
                length_function=len,
            )
            for doc in documents:
                doc.metadata['source'] = file_path

            docs = text_splitter.split_documents(documents)
            
        elif file_extension in ['.xls', '.xlsx']:
            # 엑셀 파일의 경우 "## Sheet" 문자열을 기준으로 분할
            docs = []
            
            # "## Sheet:" 문자열로 분할
            sheets = re.split(r'## Sheet: ', contents)
            
            for i, sheet_content in enumerate(sheets):
                if i == 0 and not sheet_content.strip():  # 첫 번째 항목이 비어있으면 건너뛰기
                    continue
                
                # 시트 이름과 내용 추출
                if i > 0 and '\n' in sheet_content:
                    sheet_name = sheet_content.split('\n', 1)[0].strip()
                    sheet_text = sheet_content.split('\n', 1)[1].strip()
                else:
                    sheet_name = f"Sheet{i}" if i > 0 else "Main"
                    sheet_text = sheet_content.strip()
                
                # 각 시트를 하나의 Document 객체로 생성 (청크로 분할하지 않음)
                doc = Document(
                    page_content=sheet_text,
                    metadata={
                        'source': file_path,
                        'sheet_name': sheet_name,
                        'file_type': 'excel'
                    }
                )
                docs.append(doc)
            
        elif file_extension in ['.png', '.jpg', '.jpeg', '.gif', '.bmp', 'webp']:
            loader = ImageLoader(file_path)
            
            documents = loader.load()
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
                separators=self.chunk_separators,
                length_function=len,
            )
            for doc in documents:
                doc.metadata['source'] = file_path

            docs = text_splitter.split_documents(documents)
            
        else:
            raise ValueError(f"Unsupported file type: {file_extension}")

        return docs
    
    def _detect_encoding(self, file_path: str) -> str:
        """
        파일의 인코딩을 감지합니다.
        
        :param file_path: 파일 경로
        :return: 감지된 인코딩
        """
        with open(file_path, 'rb') as file:
            raw = file.read()

            detection = chardet.detect(raw)
            encoding = detection.get('encoding')
            confidence = detection.get('confidence')

            if encoding == "utf-8" or (encoding == 'Windows-1254' and confidence <= 0.5):
                return "utf-8"
            elif encoding and encoding.lower() in ['cp949', 'euc-kr', 'ms949']:
                return 'cp949'
            else:
                return encoding

    def is_supported_file_type(self, file_path: str) -> bool:
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower()

        """ TODO: 사내 보안 문서 적용 가능하면 추가 필요
            '.docx', '.doc',
            '.pptx', '.ppt',
            '.msg', '.eml',
            '.pst', '.ost',
        """
        supported_type = [
            '.txt', '.py', '.java', '.cpp', '.md', '.c', 'cpp', '.h', '.hpp', '.cs', '.yaml', '.yml', '.java', 'js', 'ts', 'dart', '.dart',
            '.png', '.jpg', '.jpeg', '.gif', '.bmp', 'webp', '.devbot', '.eml', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.pdf', '.mht'
        ]
        
        return file_extension in supported_type

    def is_convertable_file_type(self, file_path: str) -> bool:
        _, file_extension = os.path.splitext(file_path)
        file_extension = file_extension.lower()

        convertable_type = [
            '.eml', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.pdf', '.mht'
        ]
        
        return file_extension in convertable_type


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