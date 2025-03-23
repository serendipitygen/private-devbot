# 이 모듈은 private_devbot_admin에서 활용하기 위해 nuitka를 사용해 exe 파일을 만들때 사용됨
# exe 파일 생성 방법
# conda create -n doc_extract python=3.11
# conda activate doc_extract
# pip install -r requirements_doc.txt 
# python -m nuitka --standalone --onefile --follow-imports --enable-plugin=numpy --include-package=bs4,chardet,textract,PyPDF2,pandas,tabulate,openpyxl document_extractor_for_remote_server.py
# 생성된 document_extractor_for_remote_server.exe파일을 private_devbot_admin/assets 폴더 아래에 복사하가 flutter 재빌드

from email import policy
from email.parser import BytesParser
import base64
from bs4 import BeautifulSoup
import chardet 
import json

import textract
import io
from PyPDF2 import PdfReader
import sys
import os
import pandas as pd

# TODO: 다형성 적용 필요
class DocumentExtractor:
    def get_contents(self, file_path:str):
        if file_path.endswith("eml"):
            return self.get_eml_contents(filepath=file_path, type="EML")
        elif file_path.endswith("mht"):
            return self.get_eml_contents(filepath=file_path, type="MHT")
        elif file_path.endswith("doc") or file_path.endswith("docx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSWORD")
        elif file_path.endswith("ppt") or file_path.endswith("pptx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSPOWERPOINT")
        elif file_path.endswith("xls") or file_path.endswith("xlsx"):
            return self.get_excel_contents(filepath=file_path, contents_type="MSEXCEL")
        elif file_path.endswith("pdf"):
            return self.get_pdf_contents(filepath=file_path, contents_type="PDF")
        else:
            return self.get_text_contents(file_path)

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

    def get_eml_contents(self, filepath: str, type: str):
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
                    for tag in html_parser.find_all(['style', 'script']):
                        tag.decompose()

                    body += html_parser.get_text().strip()
                elif content_type == 'application/octet-stream': # TODO: 발생하는 경우가 있는지 테스트 필요
                    pass
                    #print("content_type is 'application/octet-stream'")
                    #print(part)
                elif content_type == 'multipart/related':
                    for related_part in part.iter_parts():
                        related_content_type = related_part.get_content_type()
                        if related_content_type == 'text/html':
                            try:
                                related_part_html = related_part.get_payload(decode=True)
                                if isinstance(related_part_html, bytes):
                                    related_part_html = related_part_html.decode()
                                html_parser = BeautifulSoup(related_part_html, "html.parser")
                                for tag in html_parser.find_all(['style', 'script']):
                                    tag.decompose()
                                body += html_parser.get_text().strip()
                            except Exception as e:
                                print(f"HTML 파싱 오류: {e}")
                        elif related_content_type.startswith('image/'): # TODO 추후 이미지 처리 필요
                            # 이미지 처리 (예: 저장, base64 인코딩 후 HTML에 삽입)
                            image_data = related_part.get_payload(decode=True)
                            image_name = related_part.get_filename() or 'image'  # 파일 이름이 없으면 기본 이름 사용
                            # 파일 이름이 없는 경우 Content-ID를 사용할 수도 있습니다.
                            content_id = related_part.get('Content-ID')
                            if content_id:
                                image_name = content_id.strip('<>') # Content-ID에서 꺾쇠 괄호 제거

                            if image_data:
                                pass
                                # TODO: 이미지를 파일로 저장하는 예시
                                # try:
                                #     with open(image_name, 'wb') as f:
                                #         f.write(image_data)
                                # except Exception as e:
                                #     pass
                        else: # TODO: 첨부파일 처리
                            pass
        else:
            body += msg.get_payload(decode=True).decode()

        contents['contents'] = body
        return contents
    
    def get_text_contents(self, filepath: str):
        with open(filepath, "rb") as f:
            raw_data = f.read()
            detection = chardet.detect(raw_data)
            encoding = detection.get('encoding')
            confidence = detection.get('confidence', 0)
            
        if encoding is None or encoding == 'Windows-1254':
            encoding = 'utf-8'

        with open(filepath, 'r', encoding=encoding, errors='replace') as f:
            text_contents = f.read()

        contents = {
            "contents_type":"TEXT",
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
        

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("컨텐츠를 추출한 파일의 전체 경로를 인자로 주세요.")
        exit(-1)

    file_path = sys.argv[1]
    #file_path = "D:\\4.Archive\\obsidian\\임시노트.md"
    file_name = os.path.basename(file_path)
    document_extractor = DocumentExtractor()
    
    try:
        result = document_extractor.get_contents(file_path=file_path)
        # 모든 출력을 일관된 JSON 형식으로 변환
        if isinstance(result, dict):
            if "contents" in result:
                print(json.dumps({"text": result["contents"]}, ensure_ascii=False))
            elif "contents_type" in result and "contents" in result:
                print(json.dumps({"text": result["contents"]}, ensure_ascii=False))
            else:
                # 다른 형태의 딕셔너리인 경우 전체를 JSON으로 변환
                print(json.dumps({"text": json.dumps(result, ensure_ascii=False)}, ensure_ascii=False))
        else:
            # 딕셔너리가 아닌 경우 문자열로 변환하여 JSON으로 출력
            print(json.dumps({"text": str(result)}, ensure_ascii=False))
    except Exception as e:
        # 에러가 발생한 경우도 JSON 형식으로 출력
        print(json.dumps({"error": str(e)}, ensure_ascii=False))