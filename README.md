시스템 실행 방법
백엔드 서버 실행

bash
Copy
cd private_rag_backend
uvicorn main:app --port 8123 --reload --log-level debug
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


