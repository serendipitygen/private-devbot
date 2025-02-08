시스템 실행 방법
백엔드 서버 실행

bash
Copy
cd private_rag_backend
# API 호출 시 localhost:8123으로만 접속 가능
uvicorn main:app --port 8123 --reload --log-level debug 
# API 호출 시 외부에서도 접속 가능 (0.0.0.0)
uvicorn main:app --host 0.0.0.0 --port 8123 --reload --log-level debug
uvicorn main:app --port 8123 --log-level debug
관리자 UI 실행

bash
Copy
cd private_rag_ui
streamlit run app.py
streamlit run .\private_rag_ui\app.py
챗봇 서비스 실행 (별도 터미널)

bash
Copy
cd private_rag_chatbot
chainlit run chatbot.py -w --port 8001

# 백엔드
# GPU 사용 시 :  torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
pip install torch torchvision torchaudio


pip install fastapi uvicorn python-multipart pydantic langchain langchain-community langchain-huggingface PyPDF2 docx2txt pandas openpyxl python-pptx faiss-cpu sentence-transformers transformers fastapi watchdog requests chardet kiwipiepy

# kss # 윈도즈에 설치할 수 없는 python-mecab-kor의존성 때문에 사용 불가함

# 프론트엔드
pip install streamlit requests kss kiwipiepy streamlit_js_eval

