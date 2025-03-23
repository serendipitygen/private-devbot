from email import policy
from email.parser import BytesParser
import base64
from bs4 import BeautifulSoup
from fastapi import UploadFile
import chardet 

import textract
import io
from PyPDF2 import PdfReader

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
        elif filename.endswith("xls") or filename.endswith("xlsx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSEXCEL")
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
    
    async def get_text_contents(self, file: UploadFile, file_path:str):
        contents = await file.read()
        detection = chardet.detect(contents)
        encoding = detection.get('encoding')

        if encoding is None or encoding == 'Windows-1254':
            encoding = 'utf-8'

        with open(file_path, 'r', encoding=encoding, errors='replace') as f:
            text_contents = f.read()

        contents = {
            "contents_type":"TEXT",
            "contents": text_contents
        }

        # utf8_bom = b'\xef\xbb\xbf'
        # if contents.startswith(utf8_bom):
        #     has_bom = True
        # else:
        #     has_bom = False

        # if encoding == "utf-8" or encoding == 'Windows-1254':
        #     print(f"인코딩: {encoding}")
        #     text_contents = contents.decode('utf-8', errors='replace')
        # else:
        #     print(f"인코딩: {encoding}")
        #     decoded_contents = contents.decode(encoding, errors='replace')
        #     text_contents = decoded_contents.encode('utf-8')

        # if type(text_contents) == bytes:
        #     text_contents = text_contents.decode('utf-8')

        # contents = {
        #     "contents_type":"TEXT",
        #     "contents": text_contents
        # }

        return contents 


if __name__ == "__main__":
    file_path = sys.argv[1]
    result = extract_text(file_path)
    print(json.dumps({"text": result}))