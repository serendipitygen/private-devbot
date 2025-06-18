import threading
import queue
import os
import time
import asyncio
from typing import Callable, Dict, Any, List, Optional
from datetime import datetime
import logging

class UploadQueueManager:
    def __init__(self, max_queue_size: int = 10000):
        self.max_queue_size = max_queue_size
        self.upload_queue = queue.Queue(maxsize=max_queue_size)
        self.subscribers: Dict[str, List[Callable[[Dict[str, Any]], None]]] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._worker_thread = None
        self._processing_callback = None
        self.current_processing_file = None  # 현재 처리 중인 파일 정보
        self.logger = logging.getLogger(__name__)
        
    def set_processing_callback(self, callback: Callable[[Dict[str, Any]], Dict[str, Any]]):
        """파일 처리 콜백 함수를 설정합니다."""
        self._processing_callback = callback
        
    def start_worker(self):
        """백그라운드 워커 스레드를 시작합니다."""
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self._stop_event.clear()
            self._worker_thread = threading.Thread(target=self._process_queue, daemon=True)
            self._worker_thread.start()
            self.logger.info("업로드 큐 워커 스레드가 시작되었습니다.")
    
    def stop_worker(self):
        """백그라운드 워커 스레드를 중지합니다."""
        if self._worker_thread and self._worker_thread.is_alive():
            self._stop_event.set()
            self._worker_thread.join(timeout=3)
            self.logger.info("업로드 큐 워커 스레드가 중지되었습니다.")
    
    def add_file(self, file_path: str) -> Dict[str, Any]:
        """파일을 업로드 큐에 추가합니다."""
        try:
            if not os.path.exists(file_path):
                return {
                    "success": False,
                    "message": f"파일을 찾을 수 없습니다: {file_path}",
                    "remaining_capacity": self.get_remaining_capacity()
                }
            
            if self.upload_queue.full():
                return {
                    "success": False,
                    "message": f"업로드 대기열이 가득 찼습니다. 현재 업로드 가능한 파일 개수: {self.get_remaining_capacity()}개",
                    "remaining_capacity": self.get_remaining_capacity()
                }
            
            last_modified = os.path.getmtime(file_path)
            file_info = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'status': 'pending',
                'added_time': datetime.now().timestamp(),
                'last_modified': last_modified
            }
            
            self.upload_queue.put_nowait(file_info)
            self._notify_subscribers('file_added', file_info)
            
            return {
                "success": True,
                "message": f"파일이 업로드 대기열에 추가되었습니다.",
                "remaining_capacity": self.get_remaining_capacity()
            }
            
        except Exception as e:
            error_info = {
                'file_path': file_path,
                'file_name': os.path.basename(file_path),
                'status': 'failed',
                'error': str(e),
                'failed_time': datetime.now().timestamp()
            }
            self._notify_subscribers('file_failed', error_info)
            return {
                "success": False,
                "message": f"파일 추가 실패: {str(e)}",
                "remaining_capacity": self.get_remaining_capacity()
            }
    
    def add_files(self, file_paths: List[str]) -> Dict[str, Any]:
        """여러 파일을 업로드 큐에 추가합니다."""
        if len(file_paths) > self.get_remaining_capacity():
            return {
                "success": False,
                "message": f"추가하려는 파일 개수({len(file_paths)}개)가 남은 용량({self.get_remaining_capacity()}개)을 초과합니다.",
                "remaining_capacity": self.get_remaining_capacity()
            }
        
        added_count = 0
        failed_files = []
        
        for file_path in file_paths:
            result = self.add_file(file_path)
            if result["success"]:
                added_count += 1
            else:
                failed_files.append({"file_path": file_path, "error": result["message"]})
        
        return {
            "success": added_count > 0,
            "message": f"{added_count}개 파일이 추가되었습니다. {len(failed_files)}개 파일 추가 실패.",
            "added_count": added_count,
            "failed_files": failed_files,
            "remaining_capacity": self.get_remaining_capacity()
        }
    
    def get_queue_size(self) -> int:
        """현재 큐의 크기를 반환합니다."""
        return self.upload_queue.qsize()
    
    def get_remaining_capacity(self) -> int:
        """남은 큐 용량을 반환합니다."""
        return self.max_queue_size - self.upload_queue.qsize()
    
    def get_status(self) -> Dict[str, Any]:
        """큐 상태 정보를 반환합니다."""
        return {
            "queue_size": self.get_queue_size(),
            "remaining_capacity": self.get_remaining_capacity(),
            "max_capacity": self.max_queue_size,
            "worker_active": self._worker_thread is not None and self._worker_thread.is_alive(),
            "current_processing_file": self.current_processing_file
        }
    
    def get_current_processing_file(self) -> Optional[Dict[str, Any]]:
        """현재 처리 중인 파일 정보를 반환합니다."""
        return self.current_processing_file
    
    def subscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """이벤트 구독을 등록합니다."""
        with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable[[Dict[str, Any]], None]):
        """이벤트 구독을 해제합니다."""
        with self._lock:
            if event_type in self.subscribers and callback in self.subscribers[event_type]:
                self.subscribers[event_type].remove(callback)
    
    def _notify_subscribers(self, event_type: str, data: Dict[str, Any]):
        """구독자들에게 이벤트를 알립니다."""
        with self._lock:
            callbacks = self.subscribers.get(event_type, []).copy()
        
        for callback in callbacks:
            try:
                callback(data)
            except Exception as e:
                self.logger.error(f"이벤트 알림 오류 ({event_type}): {e}")
    
    def _process_queue(self):
        """백그라운드에서 큐를 처리합니다."""
        self.logger.info("업로드 큐 처리 시작")
        
        while not self._stop_event.is_set():
            try:
                file_info = self.upload_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            
            try:
                self.logger.debug(f"파일 처리 시작: {file_info['file_path']}")
                
                # 현재 처리 중인 파일 정보 업데이트
                self.current_processing_file = file_info.copy()
                self.current_processing_file['status'] = 'processing'
                self.current_processing_file['processing_time'] = datetime.now().timestamp()
                
                # 파일 처리 시작 이벤트 발행
                processing_info = file_info.copy()
                processing_info['status'] = 'processing'
                processing_info['processing_time'] = datetime.now().timestamp()
                self._notify_subscribers('file_processing', processing_info)
                
                # 실제 파일 처리 (콜백 함수 사용)
                if self._processing_callback:
                    result = self._processing_callback(file_info)
                    
                    if result.get('status') == 'success':
                        completed_info = file_info.copy()
                        completed_info['status'] = 'completed'
                        completed_info['completed_time'] = datetime.now().timestamp()
                        completed_info['result'] = result
                        self._notify_subscribers('file_completed', completed_info)
                        self.logger.debug(f"파일 처리 완료: {file_info['file_path']}")
                    else:
                        failed_info = file_info.copy()
                        failed_info['status'] = 'failed'
                        failed_info['error'] = result.get('message', '알 수 없는 오류')
                        failed_info['failed_time'] = datetime.now().timestamp()
                        self._notify_subscribers('file_failed', failed_info)
                        self.logger.error(f"파일 처리 실패: {file_info['file_path']} - {failed_info['error']}")
                else:
                    # 콜백이 없으면 실패로 처리
                    failed_info = file_info.copy()
                    failed_info['status'] = 'failed'
                    failed_info['error'] = '처리 콜백이 설정되지 않았습니다.'
                    failed_info['failed_time'] = datetime.now().timestamp()
                    self._notify_subscribers('file_failed', failed_info)
                    self.logger.error(f"파일 처리 실패: 콜백 없음 - {file_info['file_path']}")
                    
            except Exception as e:
                failed_info = file_info.copy()
                failed_info['status'] = 'failed'
                failed_info['error'] = str(e)
                failed_info['failed_time'] = datetime.now().timestamp()
                self._notify_subscribers('file_failed', failed_info)
                self.logger.exception(f"파일 처리 중 예외 발생: {file_info['file_path']}")
            finally:
                # 현재 처리 중인 파일 정보 초기화
                self.current_processing_file = None
                self.upload_queue.task_done()
        
        self.logger.info("업로드 큐 처리 종료")
