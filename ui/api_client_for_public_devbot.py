"""Client for registering this private DevBot instance to the PUBLIC DevBot
service so that it can be discovered globally.

This module intentionally does NOT throw exceptions to the caller – all
unexpected conditions are logged through ``ui_logger`` and the
application continues to run.

A single helper function ``registerOrUpdateToPublicDevbot`` is exposed.
It can be called at application start-up with the default RAG (``"default"``)
name and later whenever the user creates another RAG.

The implementation mirrors the behaviour of the original Flutter method
``registerOrUpdatePrivateRag``:

1.  Build a request payload containing ``name``, ``api_url``,
    ``description`` and ``knox_ids``.
2.  Check whether a RAG with identical ``name`` + ``api_url`` is already
    present on the server.  If present we issue a **PUT** request,
    otherwise we issue a **POST** request.
3.  All network errors are captured and written to the UI log – the UI
    must never crash because of a failed registration attempt.

NOTE:
-----
•  The base-URL of the public DevBot registry is defined in
   ``ui.ui_setting.PRIVATE_DEVBOT_REGISTER_URL``.
•  Information such as the local *client IP*, *port* and *knox_id* are
   read from the UI configuration file via ``config_util.load_json_config``.
"""
from __future__ import annotations

import json
import os
import warnings
from typing import List

import requests

from ui.ui_setting import PRIVATE_DEVBOT_REGISTER_URL
from ui.config_util import load_json_config
from logger_util import ui_logger

# Disable only the InsecureRequestWarning that we get when verify=False.
with warnings.catch_warnings():
    warnings.simplefilter("ignore", category=requests.packages.urllib3.exceptions.InsecureRequestWarning)  # type: ignore[attr-defined]


def _request_with_http_fallback(session: requests.Session, method: str, url: str, **kwargs):
    """Make a request and transparently retry with *http://* when an SSL handshake
    fails for a *https://* URL.

    이 함수는 로컬/사내 망에서 HTTPS 인증서가 제대로 설정되지 않은 경우를
    대비해 한 번 더 HTTP 로 자동 재시도합니다. (예: self-signed 인증서 없이
    8001 포트로 구동 중인 서버)
    """
    try:
        return session.request(method=method, url=url, **kwargs)
    except requests.exceptions.SSLError as e:
        if url.lower().startswith("https://"):
            fallback_url = "http://" + url[len("https://"):]
            ui_logger.warning(
                f"[PublicApiClient] SSL 오류로 {url} 요청 실패 → {fallback_url} 로 재시도"
            )
            return session.request(method=method, url=fallback_url, **kwargs)
        raise

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _split_knox_ids(knox_ids: str | List[str] | None) -> List[str]:
    """Convert a comma-separated *knox_ids* string to a list and sanitise."""
    if knox_ids is None:
        return []
    if isinstance(knox_ids, list):
        return [str(i).strip() for i in knox_ids if str(i).strip()]
    # Otherwise assume string – may contain commas.
    return [part.strip() for part in str(knox_ids).split(',') if part.strip()]


def _get_local_api_url(client_ip: str | None, port: str | int | None) -> str | None:
    """Build local search endpoint →  "http://<ip>:<port>/search"."""
    if not client_ip or not port:
        return None
    return f"http://{client_ip}:{port}/search"


def _is_duplicated(session: requests.Session, name: str, api_url: str) -> bool:
    """Return *True* if the RAG already exists on the server."""
    try:
        resp = _request_with_http_fallback(session, "GET", PRIVATE_DEVBOT_REGISTER_URL, timeout=10, verify=False)
        if resp.status_code != 200:
            ui_logger.debug(
                f"[PublicApiClient] GET list failed – status {resp.status_code}: {resp.text[:200]}"
            )
            return False
        data = resp.json()
        if isinstance(data, list):
            return any(item.get("name") == name and item.get("api_url") == api_url for item in data)
        # If the API returns dict with "results"
        if isinstance(data, dict) and isinstance(data.get("results"), list):
            return any(
                item.get("name") == name and item.get("api_url") == api_url for item in data["results"]
            )
    except Exception as e:
        ui_logger.exception(f"[PublicApiClient] Duplication check failed: {e}")
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def registerOrUpdateToPublicDevbot(rag_name: str = "default") -> bool:
    """Register (or update) the *rag_name* to the public DevBot registry.

    Parameters
    ----------
    rag_name: str
        The name of the RAG (document store group). Defaults to ``"default"``.

    Returns
    -------
    bool
        *True* when the server responded with *200 OK*, otherwise *False*.
    """
    try:
        # ------------------------------------------------------------------
        # 1. Collect local configuration data
        # ------------------------------------------------------------------
        cfg = load_json_config() or {}
        client_ip: str | None = cfg.get("client_ip")
        port: str | int | None = cfg.get("port")
        knox_cfg: str | List[str] | None = cfg.get("knox_id")  # May be comma separated string

        api_url = _get_local_api_url(client_ip, port)
        if api_url is None:
            ui_logger.error("[PublicApiClient] Cannot build api_url – missing client_ip or port in config.")
            return False

        knox_ids = _split_knox_ids(knox_cfg)
        description = f"{rag_name} 문서 저장소"

        payload = {
            "name": rag_name,
            "api_url": api_url,
            "description": description,
            "knox_ids": knox_ids,
        }

        ui_logger.debug(
            "[PublicApiClient] Register/Update data: " + json.dumps(payload, ensure_ascii=False)
        )

        # ------------------------------------------------------------------
        # 2. Determine HTTP method (POST for create, PUT for update)
        # ------------------------------------------------------------------
        session = requests.Session()
        is_dup = _is_duplicated(session, rag_name, api_url)
        method = "PUT" if is_dup else "POST"

        # ------------------------------------------------------------------
        # 3. Make the request
        # ------------------------------------------------------------------
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "PrivateDevBotAdmin/1.0",
        }

        ui_logger.info(
            f"[PublicApiClient] {method} {PRIVATE_DEVBOT_REGISTER_URL} for RAG '{rag_name}' (dup={is_dup})"
        )
        resp = _request_with_http_fallback(
            session,
            method,
            PRIVATE_DEVBOT_REGISTER_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=30,
            verify=False,  # Allow self-signed certs on intranet
        )

        if resp.status_code != 200:
            ui_logger.error(
                f"[PublicApiClient] Failed to register/update RAG '{rag_name}'. "
                f"Status={resp.status_code} Body={resp.text[:200]}"
            )
            return False

        ui_logger.info(f"[PublicApiClient] RAG '{rag_name}' successfully registered/updated.")
        return True

    except Exception as e:
        # Any unhandled exception must not crash the UI.
        ui_logger.exception(f"[PublicApiClient] Unexpected error: {e}")
        return False
