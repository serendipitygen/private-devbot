# -*- coding: utf-8 -*-

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
import sys
import os
import json
import re
from pathlib import Path

# TODO: 다형성 적용 필요
class DocumentReader:
    async def get_contents(self, file: UploadFile, file_path:str):
        filename = file.filename.lower()
        if filename.endswith("eml"):
            return self.get_eml_contents(filepath=file_path, type="EML")
        elif filename.endswith("mht"):
            return self.get_eml_contents(filepath=file_path, type="MHT")
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
    
    def get_contents_on_pc(self, file_path:str):
        filename = Path(file_path).name
        if filename.endswith("eml"):
            return self.get_eml_contents(filepath=file_path, type="EML")
        elif filename.endswith("mht"):
            return self.get_eml_contents(filepath=file_path, type="MHT")
        elif filename.endswith("doc") or filename.endswith("docx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSWORD")
        elif filename.endswith("ppt") or filename.endswith("pptx"):
            return self.get_msoffice_contents(filepath=file_path, contents_type="MSPOWERPOINT")
        elif file_path.endswith("xls") or file_path.endswith("xlsx"):
            return self.get_excel_contents(filepath=file_path, contents_type="MSEXCEL")
        elif filename.endswith("pdf"):
            return self.get_pdf_contents(filepath=file_path, contents_type="PDF")
        else:
            return self.get_text_contents_on_pc(file_path=file_path)

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
        html_content = ""
        plain_text = ""
        
        # HTML과 TEXT 컨텐츠를 따로 저장
        if msg.is_multipart():
            for part in msg.iter_parts():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        decoded_payload = part.get_payload(decode=True)
                        # 인코딩 추정 및 디코딩 시도
                        encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1', 'cp1252']
                        for encoding in encodings_to_try:
                            try:
                                plain_text += decoded_payload.decode(encoding)
                                break
                            except UnicodeDecodeError:
                                continue
                        # 모든 인코딩 실패 시 대체 문자 사용
                        if not plain_text:
                            plain_text += decoded_payload.decode('utf-8', errors='replace')
                    except Exception as e:
                        print(f"텍스트 디코딩 오류: {e}")
                        plain_text += part.get_payload(decode=True).decode('utf-8', errors='replace')
                elif content_type == "text/html":
                    try:
                        # base64로 디코딩 시도, 실패하면 일반 payload 사용
                        try:
                            part_html = base64.b64decode(part.get_payload())
                        except:
                            part_html = part.get_payload(decode=True)
                            
                        # 인코딩 추정 및 디코딩
                        html_text = ""
                        encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1', 'cp1252']
                        for encoding in encodings_to_try:
                            try:
                                if isinstance(part_html, bytes):
                                    html_text = part_html.decode(encoding)
                                else:
                                    html_text = part_html
                                break
                            except UnicodeDecodeError:
                                continue
                                
                        # 모든 인코딩 실패 시
                        if not html_text and isinstance(part_html, bytes):
                            html_text = part_html.decode('utf-8', errors='replace')
                        
                        html_content += html_text
                    except Exception as e:
                        print(f"HTML 파싱 오류: {e}")
                elif content_type == 'multipart/related':
                    for related_part in part.iter_parts():
                        related_content_type = related_part.get_content_type()
                        if related_content_type == 'text/html':
                            try:
                                related_part_html = related_part.get_payload(decode=True)
                                # 인코딩 추정 및 디코딩
                                related_html_text = ""
                                encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1', 'cp1252']
                                
                                if isinstance(related_part_html, bytes):
                                    for encoding in encodings_to_try:
                                        try:
                                            related_html_text = related_part_html.decode(encoding)
                                            break
                                        except UnicodeDecodeError:
                                            continue
                                    
                                    # 모든 인코딩 실패 시
                                    if not related_html_text:
                                        related_html_text = related_part_html.decode('utf-8', errors='replace')
                                else:
                                    related_html_text = related_part_html
                                    
                                html_content += related_html_text
                            except Exception as e:
                                print(f"HTML 파싱 오류: {e}")
        else:
            try:
                decoded_payload = msg.get_payload(decode=True)
                content_type = msg.get_content_type()
                
                # 인코딩 추정 및 디코딩 시도
                encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1', 'cp1252']
                decoded_text = ""
                
                for encoding in encodings_to_try:
                    try:
                        decoded_text = decoded_payload.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                
                # 모든 인코딩 실패 시
                if not decoded_text:
                    decoded_text = decoded_payload.decode('utf-8', errors='replace')
                    
                if content_type == 'text/html':
                    html_content += decoded_text
                else:
                    plain_text += decoded_text
            except Exception as e:
                print(f"이메일 본문 디코딩 오류: {e}")
                # 오류 발생 시 대체 문자 사용
                try:
                    decoded_text = msg.get_payload(decode=True).decode('utf-8', errors='replace')
                    if msg.get_content_type() == 'text/html':
                        html_content += decoded_text
                    else:
                        plain_text += decoded_text
                except:
                    plain_text += "이메일 내용을 디코딩할 수 없습니다."
        
        # HTML 내용이 있으면 BeautifulSoup으로 깔끔하게 텍스트만 추출
        if html_content:
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                
                # 불필요한 태그 제거
                for script in soup(["script", "style", "iframe", "meta", "link", "img"]):
                    script.extract()
                
                # 본문 내용에 해당하는 태그만 선택적으로 추출하기
                main_content = None
                
                # 1. 일반적인 메일 본문 컨테이너 찾기
                for container in ['div#content', 'div#main', 'div.content', 'div.main', 'div#body', 'div.body']:
                    if main_content is None:
                        main_content = soup.select_one(container)
                
                # 2. 아직 못 찾았으면 가장 텍스트가 많은 div 찾기
                if main_content is None:
                    max_text_len = 0
                    for div in soup.find_all('div'):
                        text_len = len(div.get_text(strip=True))
                        if text_len > max_text_len and text_len > 50:  # 최소 길이 조건
                            max_text_len = text_len
                            main_content = div
                
                # 3. 여전히 못 찾았으면 body 또는 전체 HTML 사용
                if main_content is None:
                    main_content = soup.body or soup
                
                # 추출된 내용의 텍스트만 가져오기
                extracted_text = main_content.get_text(separator='\n', strip=True)
                
                # 여러 줄 공백 제거
                extracted_text = re.sub(r'\n\s*\n', '\n\n', extracted_text)
                
                # 공백 라인이 3개 이상 연속되면 2개로 제한
                extracted_text = re.sub(r'\n{3,}', '\n\n', extracted_text)
                
                body = extracted_text
            except Exception as e:
                print(f"HTML 파싱 중 오류 발생: {e}")
                # HTML 파싱에 실패하면 일반 텍스트 사용
                if plain_text:
                    body = plain_text
                else:
                    # 간단한 HTML 태그 제거 시도
                    body = re.sub(r'<[^>]*>', ' ', html_content)
                    body = re.sub(r'\s+', ' ', body).strip()
        else:
            # HTML이 없으면 일반 텍스트만 사용
            body = plain_text
                
        contents['contents'] = body
        return contents
    
    async def get_text_contents(self, file: UploadFile, file_path: str):
        contents = await file.read()
        return self._make_text_contents(contents)
    
    def get_text_contents_on_pc(self, file_path: str):
        with open(file_path, "rb") as f:
            contents = f.read()

        return self._make_text_contents(contents)

    def _make_text_contents(self, contents: bytes):        
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

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("컨텐츠를 추출한 파일의 전체 경로를 인자로 주세요.")
        exit(-1)

    file_path = sys.argv[1]
    #file_path = "D:\\4.Archive\\obsidian\\임시노트.md"
    file_name = os.path.basename(file_path)
    document_reader = DocumentReader()
    
    try:
        with open(file_path, 'rb') as f:
            # UploadFile 객체 대신 파일 경로를 기반으로 처리
            if file_path.lower().endswith("eml"):
                result = document_reader.get_eml_contents(filepath=file_path, type="EML")
            elif file_path.lower().endswith("mht"):
                result = document_reader.get_eml_contents(filepath=file_path, type="MHT")
            elif file_path.lower().endswith("doc") or file_path.lower().endswith("docx"):
                result = document_reader.get_msoffice_contents(filepath=file_path, contents_type="MSWORD")
            elif file_path.lower().endswith("ppt") or file_path.lower().endswith("pptx"):
                result = document_reader.get_msoffice_contents(filepath=file_path, contents_type="MSPOWERPOINT")
            elif file_path.lower().endswith("xls") or file_path.lower().endswith("xlsx"):
                result = document_reader.get_excel_contents(filepath=file_path, contents_type="MSEXCEL")
            elif file_path.lower().endswith("pdf"):
                result = document_reader.get_pdf_contents(filepath=file_path, contents_type="PDF")
            else:
                # 텍스트 파일 처리
                contents = f.read()
                
                # 인코딩 감지 및 다양한 인코딩 시도
                text_contents = ""
                try:
                    # 먼저 chardet로 인코딩 감지 시도
                    detection = chardet.detect(contents)
                    encoding = detection.get('encoding')
                    
                    # 감지된 인코딩이 신뢰할 수 있는지 확인
                    if encoding is None or detection.get('confidence', 0) < 0.6:
                        # 일반적인 인코딩 순서대로 시도
                        encodings_to_try = ['utf-8', 'cp949', 'euc-kr', 'latin1', 'cp1252']
                    else:
                        # 감지된 인코딩을 우선 시도하고 실패 시 다른 인코딩 시도
                        encodings_to_try = [encoding, 'utf-8', 'cp949', 'euc-kr', 'latin1', 'cp1252']
                    
                    # 여러 인코딩 시도
                    for encoding in encodings_to_try:
                        try:
                            text_contents = contents.decode(encoding, errors='replace')
                            break  # 성공하면 루프 종료
                        except (UnicodeDecodeError, LookupError):
                            continue
                    
                    # 모든 인코딩이 실패하면 latin1으로 강제 디코딩 (항상 성공)
                    if not text_contents:
                        text_contents = contents.decode('latin1', errors='replace')
                
                except Exception as e:
                    print(f"디코딩 오류: {e}")
                    # 최후의 수단으로 errors='replace'를 사용하여 latin1으로 디코딩
                    text_contents = contents.decode('latin1', errors='replace')
                
                result = {
                    "contents_type": "TEXT",
                    "contents": text_contents
                }
                
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