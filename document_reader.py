from email import policy
from email.parser import BytesParser
import base64
from bs4 import BeautifulSoup
from fastapi import UploadFile
import chardet 

import textract
import io
import codecs
from PyPDF2 import PdfReader
import pandas as pd

# TODO: 다형성 적용 필요
class DocumentReader:
    async def get_contents(self, file: UploadFile, file_path:str):
        filename = file.filename.lower()
        if filename.endswith("eml"):
            return await self.get_eml_contents(filepath=file_path, type="EML")
        elif filename.endswith("mht"):
            return await self.get_eml_contents(filepath=file_path, type="MHT")
        elif filename.endswith("doc") or filename.endswith("docx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSWORD")
        elif filename.endswith("ppt") or filename.endswith("pptx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSPOWERPOINT")
        elif file_path.endswith("xls") or file_path.endswith("xlsx"):
            return self.get_excel_contents(filepath=file_path, contents_type="MSEXCEL")
        elif filename.endswith("pdf"):
            return self.get_pdf_contents(filepath=file_path, contents_type="PDF")
        else:
            return await self.get_text_contents(file=file, file_path=file_path)

    def get_msoffice_contents(self, filepath:str, contents_type:str):
        try:
            text = textract.process(filepath).decode('utf-8')
            contents = {
                "contents_type": contents_type,
                "contents": text
            }
            return contents
        except Exception as e:
            raise Exception(e)
        
    # TODO: 이미지 처리를 위해 PDF 전용 패키지 사용 필요
    def get_pdf_contents(self, filepath: str, contents_type:str):
        try:
            with open(filepath, 'rb') as f:
                pdf_data = f.read()
                
            pdf_stream = io.BytesIO(pdf_data)
            reader = PdfReader(pdf_stream)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text

            contents = {
                "contents_type": contents_type,
                "contents": text
            }
            return contents
        except Exception as e:
            raise Exception(e)

    async def get_eml_contents(self, filepath: str, type: str):
        with open(filepath, 'rb') as f:
            msg = BytesParser(policy=policy.default).parse(f)

        contents = {
            "contents_type": type,
            "title": msg['Subject'],
            "from": msg['From'],
            "to": msg['To'],
            "date": msg['Date'] 
        }

        body = ""
        
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    body += part.get_payload(decode=True).decode()
                elif content_type == "text/html":
                    part_html = base64.b64decode(part.get_payload())
                    html_parser = BeautifulSoup(part_html, "html.parser")
                    body += html_parser.get_text().strip()
                elif content_type == 'application/octet-stream': # 케이스가 발생하는지 확인 필요
                    pass
                elif content_type == 'multipart/related':
                    for related_part in part.iter_parts():
                        related_content_type = related_part.get_content_type()
                        if related_content_type == 'text/html':
                            try:
                                related_part_html = related_part.get_payload(decode=True)
                                if isinstance(related_part_html, bytes):
                                    related_part_html = related_part_html.decode()
                                html_parser = BeautifulSoup(related_part_html, "html.parser")
                                body += html_parser.get_text().strip()
                            except Exception as e:
                                print(f"HTML 파싱 오류: {e}")
                                # 오류 처리 (예: 로깅, 다른 방식으로 처리 시도)
                        elif related_content_type.startswith('image/'): # TODO: 이미지 처리 추가 필요
                            pass
                        else: # TODO: 첨부파일 처리
                            pass
        else:
            body += msg.get_payload(decode=True).decode()

        contents['contents'] = body
        return contents

    async def get_text_contents(self, file: UploadFile, file_path: str):
        contents = await file.read()
        detection = chardet.detect(contents)
        encoding = detection.get('encoding')

        if encoding is None or encoding == 'Windows-1254':
            encoding = 'utf-8'

        # codecs.iterdecode를 사용하여 파일 읽기
        try:
            text_contents = ''.join(codecs.iterdecode(io.BytesIO(contents), encoding, errors='replace'))
        except Exception as e:
            print(f"Error decoding file: {e}")
            text_contents = ""  # 에러 발생 시 빈 문자열 반환 또는 다른 에러 처리

        contents = {
            "contents_type": "TEXT",
            "contents": text_contents
        }

        return contents
    
    def read_excel_file(self, file_path:str, sheet_name:str=None):
        if sheet_name:
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            return df
        else:
            excel_data = pd.ExcelFile(file_path)
            sheet_names = excel_data.sheet_names
            
            dataframes = {sheet_name: excel_data.parse(sheet_name) for sheet_name in sheet_names}
            return dataframes

    def dataframe_to_markdown(self, df):
        markdown_table = df.to_markdown(index=False)
        return markdown_table

    def get_excel_contents(self, filepath: str, contents_type:str):
        excel_data = self.read_excel_file(filepath)

        contents_text = ""

        if isinstance(excel_data, dict):
            for sheet_name, df in excel_data.items():
                markdown_table = self.dataframe_to_markdown(df)
                contents_text += f"## Sheet: {sheet_name}\n"
                contents_text += markdown_table + "\n\n"
        else:
            markdown_table = self.dataframe_to_markdown(excel_data)
            contents_text += markdown_table

        contents = {
                "contents_type": contents_type,
                "contents": contents_text
            }

        return contents