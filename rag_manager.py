from typing import Dict, Optional
import re

from vector_store import VectorStore


class RAGManager:  # pragma: no cover (단순 싱글턴)
    """RAG 이름별 VectorStore 인스턴스를 캐싱/관리한다."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._stores: Dict[str, VectorStore] = {}
        return cls._instance

    def get_store(self, rag_name: Optional[str] = None) -> VectorStore:
        """rag_name가 없으면 "default" 를 사용한다."""
        key = rag_name or "default"
        if key not in self._stores:
            # 파일 시스템 안전한 디렉터리 이름 생성 (비 ASCII 문자는 _ 로 대체)
            safe_dir = re.sub(r"[^A-Za-z0-9_\-]", "_", key)
            if safe_dir == "":
                safe_dir = "default"
            self._stores[key] = VectorStore(rag_name=safe_dir)
        return self._stores[key]


# 전역 싱글턴 객체
rag_manager = RAGManager() 