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
            store = VectorStore(rag_name=safe_dir)
            # 벡터 스토어 및 임베딩 초기화 (없는 경우에만)
            try:
                store.initialize_embedding_model_and_vectorstore()
            except Exception as e:
                # 초기화 실패 시 로깅만 하고 빈 스토어로 유지 (status 호출 시 0으로 처리 가능)
                import logger_util
                logger_util.get_logger().exception(f"[RAGManager] VectorStore 초기화 실패: {e}")
            self._stores[key] = store
        return self._stores[key]


# 전역 싱글턴 객체
rag_manager = RAGManager() 