from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from pydantic import BaseModel, Field
from starlette.responses import FileResponse
from starlette.background import BackgroundTask

import os
import uuid
import time
import subprocess
import glob
import base64
import requests
import shutil
import re
import traceback
import pymysql
import socket 
import hashlib
import random

from pathlib import Path

import boto3
from botocore.config import Config


app = FastAPI()


# 모든 JSON 응답을 UTF-8로 명시 (클라이언트/도구별 깨짐 확률 감소)
@app.middleware("http")
async def force_json_utf8(request, call_next):
    response = await call_next(request)
    ct = response.headers.get("content-type", "")
    if "application/json" in ct and "charset" not in ct:
        response.headers["Content-Type"] = "application/json; charset=utf-8"
    return response


def env(name: str, default: str | None = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"환경변수 {name} 가 비어있음")
    return v

SERVER_NAME = os.getenv("SERVER_NAME") or socket.gethostname()

@app.get("/health")
def health():
    return {"status": "ok", "server": SERVER_NAME}

@app.get("/v1/metrics/daily")
async def metrics_daily(days: int = 7):
    if days < 1 or days > 90:
        raise HTTPException(status_code=400, detail="days는 1~90 사이만 허용")

    try:
        data = db_get_metrics_daily(days)   # 직접 호출
        return {"days": days, "data": data}
    except Exception as e:
        # 에러를 숨기지 말고 바로 보이게
        raise HTTPException(status_code=500, detail=f"metrics query failed: {e}")




# =========================
# DB Logging (MySQL)
# =========================
def _db_conn():
    return pymysql.connect(
        host=env("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=env("DB_USER"),
        password=env("DB_PASSWORD"),
        database=env("DB_NAME"),
        charset="utf8mb4",
        autocommit=True,
    )


def safe_db(fn, *args, **kwargs):
    """
    DB 로깅 실패가 서비스 실패로 연결되지 않도록 보호.
    데모/발표 때 DB 이슈로 전체 API가 죽는 걸 방지.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        print("[DB ERROR]", e)
        traceback.print_exc()
        return None

def get_client_meta(request: Request):
    client_id = request.headers.get("X-Client-ID")

    # nginx 프록시 뒤라 XFF 우선
    xff = request.headers.get("X-Forwarded-For", "")
    client_ip = xff.split(",")[0].strip() if xff else (request.client.host if request.client else None)

    ua = request.headers.get("User-Agent")
    return client_id, client_ip, ua


def db_inc_usage_daily(client_id: str):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO usage_daily(day, client_id, request_count, last_request_at) "
                "VALUES (CURDATE(), %s, 1, NOW()) "
                "ON DUPLICATE KEY UPDATE request_count = request_count + 1, last_request_at = NOW()",
                (client_id,),
            )

def db_get_metrics_daily(days: int):
    # 최근 N일(오늘 포함) 일별 total + unique clients
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    day,
                    SUM(request_count) AS total_requests,
                    COUNT(DISTINCT client_id) AS unique_clients
                FROM usage_daily
                WHERE day >= CURDATE() - INTERVAL %s DAY
                GROUP BY day
                ORDER BY day ASC
                """,
                (days - 1,),
            )
            rows = cur.fetchall()

    # pymysql 기본 cursor면 튜플로 올 가능성이 높아서 매핑
    out = []
    for r in rows:
        if isinstance(r, dict):
            day = r["day"]
            total = r.get("total_requests", 0)
            uniq = r.get("unique_clients", 0)
        else:
            day, total, uniq = r[0], r[1], r[2]

        out.append({
            "day": str(day),
            "total_requests": int(total or 0),
            "unique_clients": int(uniq or 0),
        })
    return out

def db_create_request(request_id: str, client_id: str | None, client_ip: str | None, user_agent: str | None):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO requests(request_id, status, client_id, client_ip, user_agent) "
                "VALUES (%s, %s, %s, %s, %s)",
                (request_id, "RECEIVED", client_id, client_ip, user_agent),
            )

def db_update_request(request_id: str, status: str, error_message: str | None = None):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE requests SET status=%s, error_message=%s WHERE request_id=%s",
                (status, error_message, request_id),
            )
def db_set_input_hash(request_id: str, input_hash: str):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE requests SET input_hash=%s WHERE request_id=%s",
                (input_hash, request_id),
            )

def db_set_result_audio_key(request_id: str, result_audio_key: str):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE requests SET result_audio_key=%s WHERE request_id=%s",
                (result_audio_key, request_id),
            )

def db_find_cached_audio_key(cache_key: str, pdf_hash: str) -> str | None:
    with _db_conn() as conn:
        with conn.cursor() as cur:
            # 1순위: cache_key 매칭 (신규)
            cur.execute(
                """
                SELECT result_audio_key
                FROM requests
                WHERE cache_key=%s AND status='DONE' AND result_audio_key IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (cache_key,),
            )
            row = cur.fetchone()

            # 2순위(호환): 예전 데이터는 cache_key가 NULL이므로 input_hash로 fallback
            if not row:
                cur.execute(
                    """
                    SELECT result_audio_key
                    FROM requests
                    WHERE cache_key IS NULL
                      AND input_hash=%s
                      AND status='DONE'
                      AND result_audio_key IS NOT NULL
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (pdf_hash,),
                )
                row = cur.fetchone()

    if not row:
        return None
    if isinstance(row, dict):
        return row.get("result_audio_key")
    return row[0]


def db_insert_step(
    request_id: str,
    step: str,
    status: str,
    latency_ms: int | None = None,
    error_message: str | None = None,
):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO request_steps(request_id, step, status, latency_ms, error_message) VALUES (%s,%s,%s,%s,%s)",
                (request_id, step, status, latency_ms, error_message),
            )


# ====== 공통 유틸 ======
def clip_text_for_llm(t: str, max_chars: int = 12000) -> str:
    t = (t or "").replace("\r", " ").strip()
    lines = [ln.strip() for ln in t.split("\n") if ln.strip()]
    t = "\n".join(lines)
    if len(t) > max_chars:
        t = t[:max_chars] + "\n...(중략)"
    return t


def pdf_to_png(pdf_path: str, out_dir: str, dpi: int, max_pages: int | None = None, timeout_sec: int = 180) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    prefix = os.path.join(out_dir, "page")

    cmd = ["pdftoppm", "-png", "-r", str(dpi)]
    if max_pages is not None and max_pages > 0:
        cmd += ["-f", "1", "-l", str(max_pages)]
    cmd += [pdf_path, prefix]

    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,timeout=timeout_sec,)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"pdftoppm 타임아웃({timeout_sec}s)")
    except subprocess.CalledProcessError as e:
        err = (e.stderr or "").strip()
        raise RuntimeError(f"pdftoppm 실패: {err[:500]}")
    except FileNotFoundError:
        raise RuntimeError("pdftoppm 명령이 없음(poppler-utils 설치 필요)")

    images = sorted(glob.glob(os.path.join(out_dir, "page-*.png")))
    if not images:
        raise RuntimeError("변환 결과 이미지가 없음")
    return images


def pdf_total_pages(pdf_path: str) -> int:
    # poppler-utils의 pdfinfo 사용 (없거나 실패하면 -1)
    try:
        r = subprocess.run(
            ["pdfinfo", pdf_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        m = re.search(r"Pages:\s+(\d+)", r.stdout)
        return int(m.group(1)) if m else -1
    except Exception:
        return -1
    
def post_with_retry(
    url: str,
    *,
    headers=None,
    json=None,
    data=None,
    timeout: int = 30,
    max_attempts: int = 4,   # 총 시도 횟수(= 1회 + 재시도 3회)
    base_sleep: float = 2.0, # 2, 4, 8...
    max_sleep: float = 8.0,
):
    """
    재시도 대상:
      - requests Timeout/ConnectionError
      - HTTP 429
      - HTTP 5xx
    재시도 금지:
      - 그 외 4xx (잘못된 요청/인증 오류 등은 재시도해도 소용없음)
    """
    last_resp = None
    last_exc = None

    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, headers=headers, json=json, data=data, timeout=timeout)
            last_resp = resp

            # 성공
            if resp.status_code == 200:
                return resp, attempt

            # 재시도 대상(429, 5xx)
            if resp.status_code == 429 or (500 <= resp.status_code <= 599):
                if attempt == max_attempts:
                    break

                # backoff (2,4,8) + jitter
                sleep = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
                sleep *= random.uniform(0.8, 1.2)
                time.sleep(sleep)
                continue

            # 나머지 4xx는 즉시 실패
            break

        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if attempt == max_attempts:
                break
            sleep = min(max_sleep, base_sleep * (2 ** (attempt - 1)))
            sleep *= random.uniform(0.8, 1.2)
            time.sleep(sleep)

    # 여기까지 오면 최종 실패
    if last_resp is not None:
        raise RuntimeError(f"upstream retry exhausted: status={last_resp.status_code} body={last_resp.text[:300]}")
    raise RuntimeError(f"upstream retry exhausted: {str(last_exc)[:200]}")


def extract_text_pdftotext(pdf_path: str, max_pages: int, timeout_sec: int = 10) -> str:
    """
    텍스트 레이어 PDF면 잘 뽑힘.
    -f/-l로 max_pages까지만 추출.
    """
    cmd = ["pdftotext", "-enc", "UTF-8", "-f", "1", "-l", str(max_pages), pdf_path, "-"]
    try:
        r = subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
        )
        return (r.stdout or "").strip()
    except Exception:
        # 실패하면 빈 문자열 -> OCR fallback
        return ""


def analyze_text_quality(t: str) -> dict:
    t = (t or "").strip()
    if not t:
        return {"nonspace_len": 0, "hangul_ratio": 0.0, "repl_ratio": 0.0}

    nonspace_len = len(re.sub(r"\s+", "", t))

    hangul = sum(1 for ch in t if "가" <= ch <= "힣")
    hangul_ratio = hangul / max(1, nonspace_len)

    repl = t.count("�")
    repl_ratio = repl / max(1, len(t))

    return {
        "nonspace_len": nonspace_len,
        "hangul_ratio": hangul_ratio,
        "repl_ratio": repl_ratio,
    }
def make_cache_key(pdf_bytes: bytes, *, force_ocr: int, force_regen: int) -> tuple[str, str]:
    # 1) 원본 식별용(그대로 유지)
    pdf_hash = hashlib.sha256(pdf_bytes).hexdigest()

    # 2) 캐시 버전(프롬프트 바꾸면 꼭 올려)
    prompt_ver = os.getenv("PROMPT_VERSION", "v1")

    # 3) 결과에 영향을 주는 옵션만 “명시적으로” 포함
    #    (너 지금 구조에서 최소 이 정도는 넣어야 정당함)
    opts = {
        "prompt_ver": prompt_ver,
        "studio_temp": os.getenv("STUDIO_TEMPERATURE", "0.7"),
        "studio_max_tokens": os.getenv("STUDIO_MAX_TOKENS", "10000"),
        "tts_speaker": os.getenv("TTS_SPEAKER", "nara"),
        "tts_speed": os.getenv("TTS_SPEED", "0"),
        "tts_max_chars": os.getenv("TTS_TEXT_MAX_CHARS", "10000"),
        "ocr_lang": os.getenv("OCR_LANG", "ko"),
        "ocr_max_pages": os.getenv("OCR_MAX_PAGES", "10"),
        "ocr_dpi": os.getenv("OCR_DPI", "350"),
        "force_ocr": str(force_ocr),
        # force_regen은 캐시 키에 굳이 포함할 필요 없음(동작 플래그라서)
    }

    # 옵션 정렬해서 문자열로 고정(같은 옵션이면 항상 같은 키)
    opt_str = "&".join([f"{k}={opts[k]}" for k in sorted(opts.keys())])

    # 최종 캐시 키
    cache_key = hashlib.sha256((pdf_hash + "|" + opt_str).encode("utf-8")).hexdigest()
    return pdf_hash, cache_key

def db_set_cache_key(request_id: str, cache_key: str):
    with _db_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE requests SET cache_key=%s WHERE request_id=%s",
                (cache_key, request_id),
            )

def should_use_pdf_text(metrics: dict) -> bool:
    """
    판단 기준(기본값은 안전/보수적으로):
    - 텍스트가 거의 없으면 OCR
    - 깨짐문자 많으면 OCR
    - 한글 비율 너무 낮으면 OCR(한국어 자료 기준)
    """
    min_chars = int(os.getenv("PDF_TEXT_MIN_CHARS", "200"))
    min_hangul = float(os.getenv("PDF_TEXT_MIN_HANGUL_RATIO", "0.05"))
    max_repl = float(os.getenv("PDF_TEXT_MAX_REPL_RATIO", "0.01"))

    if metrics["nonspace_len"] < min_chars:
        return False
    if metrics["repl_ratio"] > max_repl:
        return False
    if metrics["hangul_ratio"] < min_hangul:
        return False
    return True

def file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


# ====== CLOVA OCR 호출 ======
def _call_clova_ocr_payload(payload: dict, timeout_sec: int) -> dict:
    invoke_url = env("OCR_INVOKE_URL")
    secret = env("OCR_SECRET")

    headers = {
        "Content-Type": "application/json",
        "X-OCR-SECRET": secret,
    }

    r = requests.post(invoke_url, headers=headers, json=payload, timeout=timeout_sec)
    r.encoding = "utf-8"

    if r.status_code != 200:
        raise RuntimeError(f"OCR 호출 실패: {r.status_code} {r.text[:300]}")
    return r.json()


def call_clova_ocr_image(image_path: str, request_id: str, lang: str, timeout_sec: int = 60) -> dict:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "version": "V2",
        "requestId": request_id,
        "timestamp": int(time.time() * 1000),
        "lang": lang,
        "images": [
            {
                "format": "png",
                "name": os.path.basename(image_path),
                "data": b64,
            }
        ],
    }
    return _call_clova_ocr_payload(payload, timeout_sec=timeout_sec)


def call_clova_ocr_pdf(pdf_path: str, request_id: str, lang: str, timeout_sec: int = 120) -> dict:
    with open(pdf_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "version": "V2",
        "requestId": request_id,
        "timestamp": int(time.time() * 1000),
        "lang": lang,
        "images": [
            {
                "format": "pdf",
                "name": os.path.basename(pdf_path),
                "data": b64,
            }
        ],
    }
    return _call_clova_ocr_payload(payload, timeout_sec=timeout_sec)


def extract_text_from_clova_response(ocr_json: dict) -> str:
    """
    OCR 응답(images 배열)을 모두 순회해서 텍스트를 합침.
    PDF OCR은 페이지별로 images가 여러 개 올 수 있어서 필수.
    """
    images = ocr_json.get("images", []) or []
    if not images:
        return ""

    page_texts: list[str] = []
    for img in images:
        fields = img.get("fields", []) or []
        words: list[str] = []
        for f in fields:
            t = f.get("inferText")
            if t:
                words.append(t)
        txt = " ".join(words).strip()
        if txt:
            page_texts.append(txt)

    return "\n".join(page_texts).strip()


# ====== PDF 분할/합치기 유틸 (poppler pdfseparate/pdfunite) ======
def split_pdf_to_single_pages(pdf_path: str, out_dir: str) -> list[str]:
    os.makedirs(out_dir, exist_ok=True)
    pattern = os.path.join(out_dir, "page-%04d.pdf")

    try:
        subprocess.run(
            ["pdfseparate", pdf_path, pattern],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"pdfseparate 실패: {e.stderr.strip()[:500]}")
    except FileNotFoundError:
        raise RuntimeError("pdfseparate 명령이 없음(poppler-utils 확인 필요)")

    pages = sorted(glob.glob(os.path.join(out_dir, "page-*.pdf")))
    if not pages:
        raise RuntimeError("PDF 분할 결과가 없음")
    return pages


def unite_pdfs(inputs: list[str], out_path: str) -> None:
    try:
        subprocess.run(
            ["pdfunite", *inputs, out_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"pdfunite 실패: {e.stderr.strip()[:500]}")
    except FileNotFoundError:
        raise RuntimeError("pdfunite 명령이 없음(poppler-utils 확인 필요)")


def build_source_text(
    *,
    pdf_path: str,
    image_dir: str,
    req_id: str,
    dpi: int,
    max_pages: int,
    lang: str,
    ocr_timeout: int,
    max_chars: int,
    force_ocr: bool = False,
) -> dict:
    """
    새 플로우
    1) 텍스트 추출 우선(pdftotext) → 품질 통과하면 사용
    2) 실패/품질미달/강제OCR이면 OCR
       - PDF가 max_pages 이하: General OCR에 PDF 직접 1회
       - max_pages 초과: PDF 분할 → max_pages 단위로 chunk pdf 생성 → 각 chunk를 PDF OCR → 합침
       - 위가 환경/명령 문제로 실패하면 최후에 PNG 변환 방식으로 fallback
    """
    total_pages_pdf = pdf_total_pages(pdf_path)  # -1이면 모름

    # 기본값
    method = "ocr"
    source_text = ""
    metrics = {"nonspace_len": 0, "hangul_ratio": 0.0, "repl_ratio": 0.0}
    truncated = False
    pages_processed = 0
    ocr_pages = 0

    # 1) 텍스트 추출 시도
    use_text_first = (os.getenv("PDF_TEXT_FIRST", "1") == "1") and (not force_ocr)

    if use_text_first:
        pdf_text = extract_text_pdftotext(pdf_path, max_pages=max_pages)
        pdf_text = clip_text_for_llm(pdf_text, max_chars=max_chars)
        metrics = analyze_text_quality(pdf_text)

        print(f"[{req_id}] pdf_text metrics={metrics}")

        if should_use_pdf_text(metrics):
            method = "pdf_text"
            source_text = pdf_text

            if total_pages_pdf > 0:
                truncated = total_pages_pdf > max_pages
                pages_processed = min(total_pages_pdf, max_pages)
            else:
                pages_processed = max_pages if metrics["nonspace_len"] > 0 else 0

            return {
                "method": method,
                "source_text": source_text,
                "metrics": metrics,
                "total_pages": total_pages_pdf if total_pages_pdf > 0 else None,
                "pages_processed": pages_processed,
                "truncated": truncated,
                "ocr_pages": 0,
            }

    # 2) OCR
    # (A) total_pages를 알고, max_pages 이하라면 PDF direct OCR 1방
    try:
        if total_pages_pdf > 0 and total_pages_pdf <= max_pages:
            ocr_json = call_clova_ocr_pdf(pdf_path, req_id, lang, timeout_sec=max(ocr_timeout, 120))
            source_text = extract_text_from_clova_response(ocr_json)
            source_text = clip_text_for_llm(source_text, max_chars=max_chars)

            return {
                "method": "ocr",
                "source_text": source_text,
                "metrics": metrics,
                "total_pages": total_pages_pdf,
                "pages_processed": total_pages_pdf,
                "truncated": False,
                "ocr_pages": total_pages_pdf,
            }

        # (B) max_pages 초과거나 total_pages를 모르면: PDF 분할 → chunk OCR
        split_dir = os.path.join(image_dir, "pdf_pages")
        chunk_dir = os.path.join(image_dir, "pdf_chunks")
        os.makedirs(chunk_dir, exist_ok=True)

        single_pages = split_pdf_to_single_pages(pdf_path, split_dir)
        total_pages_real = len(single_pages)

        chunks: list[tuple[str, int]] = []  # (chunk_path, page_count)
        for i in range(0, total_pages_real, max_pages):
            part = single_pages[i : i + max_pages]
            out_chunk = os.path.join(chunk_dir, f"chunk-{(i // max_pages) + 1:03d}.pdf")
            unite_pdfs(part, out_chunk)
            chunks.append((out_chunk, len(part)))

        full_texts: list[str] = []
        processed_pages = 0

        for cidx, (chunk_path, page_count) in enumerate(chunks, start=1):
            chunk_req_id = f"{req_id}-c{cidx}"
            ocr_json = call_clova_ocr_pdf(chunk_path, chunk_req_id, lang, timeout_sec=max(ocr_timeout, 120))
            text = extract_text_from_clova_response(ocr_json)
            if text:
                full_texts.append(text)
            processed_pages += page_count

        source_text = "\n".join(full_texts).strip()
        source_text = clip_text_for_llm(source_text, max_chars=max_chars)

        return {
            "method": "ocr",
            "source_text": source_text,
            "metrics": metrics,
            "total_pages": total_pages_real,
            "pages_processed": processed_pages,
            "truncated": False,
            "ocr_pages": processed_pages,
        }

    except Exception as e:
        # (C) 최후: PDF direct/split이 실패하면 PNG로 fallback
        print(f"[{req_id}] PDF direct/split OCR 실패 -> PNG fallback: {str(e)[:200]}")

        images = pdf_to_png(pdf_path, image_dir, dpi=dpi, max_pages=max_pages, timeout_sec=ocr_timeout)
        ocr_pages = len(images)

        if total_pages_pdf > 0:
            truncated = total_pages_pdf > max_pages
            pages_processed = min(total_pages_pdf, max_pages)
        else:
            truncated = False
            pages_processed = len(images)

        full_texts: list[str] = []
        for idx, img in enumerate(images, start=1):
            page_req_id = f"{req_id}-p{idx}"
            ocr_json = call_clova_ocr_image(img, page_req_id, lang, timeout_sec=ocr_timeout)
            text = extract_text_from_clova_response(ocr_json)
            if text:
                full_texts.append(text)

        source_text = "\n".join(full_texts).strip()
        source_text = clip_text_for_llm(source_text, max_chars=max_chars)

        return {
            "method": "ocr",
            "source_text": source_text,
            "metrics": metrics,
            "total_pages": total_pages_pdf if total_pages_pdf > 0 else None,
            "pages_processed": pages_processed,
            "truncated": truncated,
            "ocr_pages": ocr_pages,
        }


# ====== Studio ======
def call_clova_studio_script(source_text: str, request_id: str, timeout_sec: int = 60) -> str:
    url = env("STUDIO_CHAT_URL")
    key = env("STUDIO_API_KEY")

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 한국어 팟캐스트 대본 생성기다. "
                    "규칙: "
                    "핵심 위주로 재구성 할 필요 없다"
                    "청자에게 말을 걸고, 중간중간 질문을 던지고, 짧은 감탄과 완곡한 농담을 섞어라."
                    "각 줄은 한 문장만 쓰고, 문장 끝마다 줄바꿈을 넣어라."
                    "최소 60줄 이상 작성해라."
                    "출력은 대본 부분만 출력한다,"
                    "첫 줄부터 바로 본문으로 시작한다."
                    "제목, 주제, 팟캐스트, 에피소드, 회차, 대본, 스크립트 같은 단어로 시작하는 머리말을 절대 쓰지 않는다."
                )
            },
            {
                "role": "user",
                "content": f"다음 텍스트를 참고해서 낭독 대본을 작성해줘:\n\n{source_text}"
            },
        ],
        "temperature": float(os.getenv("STUDIO_TEMPERATURE", "0.7")),
        "maxCompletionTokens": int(os.getenv("STUDIO_MAX_TOKENS", "10000"))
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": request_id,
        "Content-Type": "application/json",
    }
    
    r, used_attempt = post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=timeout_sec,
    )
    r.encoding = "utf-8"
    if r.status_code != 200:
        raise RuntimeError(f"Studio 호출 실패: {r.status_code} {r.text[:300]} (attempt={used_attempt})")

    data = r.json()
    return data["result"]["message"]["content"]


def call_clova_studio_summary(source_text: str, request_id: str, timeout_sec: int = 60) -> str:
    url = env("STUDIO_CHAT_URL")
    key = env("STUDIO_API_KEY")

    payload = {
        "messages": [
            {
                "role": "system",
                "content": (
                    "너는 강의자료를 요약노트로 압축하는 도우미야. "
                )
            },
            {
                "role": "user",
                "content": f"다음 OCR 텍스트를 요약해줘:\n\n{source_text}"
            },
        ],
        "temperature": float(os.getenv("SUMMARY_TEMPERATURE", "0.3")),
    }

    headers = {
        "Authorization": f"Bearer {key}",
        "X-NCP-CLOVASTUDIO-REQUEST-ID": request_id,
        "Content-Type": "application/json",
    }
    
    r, used_attempt = post_with_retry(
        url,
        headers=headers,
        json=payload,
        timeout=timeout_sec,
    )
    r.encoding = "utf-8"
    if r.status_code != 200:
        raise RuntimeError(f"Studio 호출 실패: {r.status_code} {r.text[:300]} (attempt={used_attempt})")

    data = r.json()
    return data["result"]["message"]["content"]


# ====== endpoints ======
@app.post("/v1/summary/pdf")
async def summary_from_pdf(file: UploadFile = File(...), force_ocr: int = 0):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="pdf만 업로드 가능")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일")

    max_mb = int(os.getenv("OCR_MAX_MB", "20"))
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"파일이 너무 큼(>{max_mb}MB)")

    req_id = str(uuid.uuid4())
    base_dir = f"/tmp/ocr/{req_id}"
    image_dir = os.path.join(base_dir, "images")
    pdf_path = os.path.join(base_dir, "input.pdf")

    dpi = int(os.getenv("OCR_DPI", "350"))
    max_pages = int(os.getenv("OCR_MAX_PAGES", "10"))  # OCR chunk 크기 기준
    lang = os.getenv("OCR_LANG", "ko")
    ocr_timeout = int(os.getenv("OCR_TIMEOUT_SEC", "60"))
    studio_timeout = int(os.getenv("SUMMARY_TIMEOUT_SEC", os.getenv("STUDIO_TIMEOUT_SEC", "60")))
    ocr_max_chars = int(os.getenv("OCR_TEXT_MAX_CHARS", "12000"))

    t0 = time.time()

    try:
        os.makedirs(base_dir, exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(data)

        info = build_source_text(
            pdf_path=pdf_path,
            image_dir=image_dir,
            req_id=req_id,
            dpi=dpi,
            max_pages=max_pages,
            lang=lang,
            ocr_timeout=ocr_timeout,
            max_chars=ocr_max_chars,
            force_ocr=(force_ocr == 1),
        )

        summary = call_clova_studio_summary(info["source_text"], request_id=req_id, timeout_sec=studio_timeout)
        elapsed_ms = int((time.time() - t0) * 1000)

        return {
            "request_id": req_id,
            "method": info["method"],                 # pdf_text | ocr
            "total_pages": info["total_pages"],       # 모르면 None
            "pages_processed": info["pages_processed"],
            "ocr_pages": info["ocr_pages"],           # ocr일 때만 >0
            "truncated": info["truncated"],
            "max_pages": max_pages,
            "pdf_text_metrics": info["metrics"] if info["method"] == "pdf_text" else None,
            "summary": summary,
            "elapsed_ms": elapsed_ms,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)[:300]}")
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


@app.post("/v1/ocr/pdf")
async def ocr_pdf(file: UploadFile = File(...)):
    # ✅ 이 엔드포인트는 "항상 OCR" 컨셉 유지 (텍스트 추출 스킵)
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="pdf만 업로드 가능")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일")

    max_mb = int(os.getenv("OCR_MAX_MB", "20"))
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"파일이 너무 큼(>{max_mb}MB)")

    req_id = str(uuid.uuid4())
    base_dir = f"/tmp/ocr/{req_id}"
    image_dir = os.path.join(base_dir, "images")
    pdf_path = os.path.join(base_dir, "input.pdf")

    dpi = int(os.getenv("OCR_DPI", "350"))
    max_pages = int(os.getenv("OCR_MAX_PAGES", "10"))  # OCR chunk 크기 기준
    lang = os.getenv("OCR_LANG", "ko")
    ocr_timeout = int(os.getenv("OCR_TIMEOUT_SEC", "60"))
    ocr_max_chars = int(os.getenv("OCR_TEXT_MAX_CHARS", "12000"))

    t0 = time.time()

    try:
        os.makedirs(base_dir, exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(data)

        info = build_source_text(
            pdf_path=pdf_path,
            image_dir=image_dir,
            req_id=req_id,
            dpi=dpi,
            max_pages=max_pages,
            lang=lang,
            ocr_timeout=ocr_timeout,
            max_chars=ocr_max_chars,
            force_ocr=True,   # 항상 OCR
        )

        elapsed_ms = int((time.time() - t0) * 1000)

        return {
            "request_id": req_id,
            "method": info["method"],  # 항상 ocr
            "total_pages": info["total_pages"],
            "pages_processed": info["pages_processed"],
            "truncated": info["truncated"],
            "max_pages": max_pages,
            "ocr_pages": info["ocr_pages"],
            "text": info["source_text"],
            "elapsed_ms": elapsed_ms,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)[:300]}")
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


@app.post("/v1/script/pdf")
async def script_from_pdf(file: UploadFile = File(...), force_ocr: int = 0):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="pdf만 업로드 가능")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일")

    max_mb = int(os.getenv("OCR_MAX_MB", "20"))
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"파일이 너무 큼(>{max_mb}MB)")

    req_id = str(uuid.uuid4())
    base_dir = f"/tmp/ocr/{req_id}"
    image_dir = os.path.join(base_dir, "images")
    pdf_path = os.path.join(base_dir, "input.pdf")

    dpi = int(os.getenv("OCR_DPI", "350"))
    max_pages = int(os.getenv("OCR_MAX_PAGES", "10"))
    lang = os.getenv("OCR_LANG", "ko")
    ocr_timeout = int(os.getenv("OCR_TIMEOUT_SEC", "60"))
    studio_timeout = int(os.getenv("STUDIO_TIMEOUT_SEC", "60"))
    ocr_max_chars = int(os.getenv("OCR_TEXT_MAX_CHARS", "12000"))

    t0 = time.time()

    try:
        os.makedirs(base_dir, exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(data)

        info = build_source_text(
            pdf_path=pdf_path,
            image_dir=image_dir,
            req_id=req_id,
            dpi=dpi,
            max_pages=max_pages,
            lang=lang,
            ocr_timeout=ocr_timeout,
            max_chars=ocr_max_chars,
            force_ocr=(force_ocr == 1),
        )

        script = call_clova_studio_script(info["source_text"], request_id=req_id, timeout_sec=studio_timeout)
        elapsed_ms = int((time.time() - t0) * 1000)

        return {
            "request_id": req_id,
            "method": info["method"],
            "total_pages": info["total_pages"],
            "pages_processed": info["pages_processed"],
            "ocr_pages": info["ocr_pages"],
            "truncated": info["truncated"],
            "max_pages": max_pages,
            "pdf_text_metrics": info["metrics"] if info["method"] == "pdf_text" else None,
            "script": script,
            "elapsed_ms": elapsed_ms,
        }

    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)[:300]}")
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


# ====== Object Storage (S3 호환) 유틸: 비공개 업로드 + Presigned URL ======
def get_s3_client():
    cfg = Config(
        signature_version="s3v4",
        s3={"addressing_style": "path"},
        request_checksum_calculation="when_required",
        response_checksum_validation="when_required",
    )

    return boto3.client(
        "s3",
        endpoint_url=env("OBJ_ENDPOINT"),
        region_name=os.getenv("OBJ_REGION", "kr-standard"),
        aws_access_key_id=env("OBJ_ACCESS_KEY"),
        aws_secret_access_key=env("OBJ_SECRET_KEY"),
        config=cfg,
    )


def upload_mp3_and_presign(local_path: str, object_key: str) -> str:
    s3 = get_s3_client()
    bucket = env("OBJ_BUCKET")
    expire = int(os.getenv("OBJ_PRESIGN_EXPIRE_SEC", "900"))

    s3.upload_file(
        local_path,
        bucket,
        object_key,
        ExtraArgs={"ContentType": "audio/mpeg"},
    )

    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=expire,
    )

def presign_only(object_key: str) -> str:
    s3 = get_s3_client()
    bucket = env("OBJ_BUCKET")
    expire = int(os.getenv("OBJ_PRESIGN_EXPIRE_SEC", "900"))
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket, "Key": object_key},
        ExpiresIn=expire,
    )


# ====== TTS: 텍스트 -> mp3 반환 (A안: FastAPI가 바로 파일 내려줌) ======
TTS_URL = "https://naveropenapi.apigw.ntruss.com/tts-premium/v1/tts"
TTS_OUT_DIR = Path("/opt/app/output/tts")
TTS_OUT_DIR.mkdir(parents=True, exist_ok=True)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000)
    speaker: str = Field("nara")
    speed: int = Field(0, ge=-5, le=5)


@app.post("/v1/tts")
def tts(req: TTSRequest):
    try:
        key_id = env("CLOVA_VOICE_CLIENT_ID")
        key = env("CLOVA_VOICE_CLIENT_SECRET")
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    headers = {
        "X-NCP-APIGW-API-KEY-ID": key_id,
        "X-NCP-APIGW-API-KEY": key,
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }

    data = {
        "speaker": req.speaker,
        "speed": str(req.speed),
        "text": req.text,
    }

    try:
        r = requests.post(TTS_URL, headers=headers, data=data, timeout=30)
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"TTS 요청 실패: {str(e)[:200]}")

    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=f"TTS upstream error {r.status_code}: {r.text[:500]}")

    filename = f"{uuid.uuid4().hex}.mp3"
    out_path = TTS_OUT_DIR / filename
    out_path.write_bytes(r.content)

    def _cleanup():
        try:
            out_path.unlink(missing_ok=True)
        except Exception:
            pass

    return FileResponse(
        path=str(out_path),
        media_type="audio/mpeg",
        filename=filename,
        background=BackgroundTask(_cleanup),
    )


# ====== PDF 업로드 -> (텍스트추출 or OCR) -> Studio 대본 -> TTS -> Object Storage 업로드(Presigned URL 반환) ======
@app.post("/v1/podcast/pdf")
async def podcast_from_pdf(request: Request, file: UploadFile = File(...), force_ocr: int = 0, force_regen: int = 0):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="pdf만 업로드 가능")

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="빈 파일")

    max_mb = int(os.getenv("OCR_MAX_MB", "20"))
    if len(data) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"파일이 너무 큼(>{max_mb}MB)")

    req_id = str(uuid.uuid4())
    base_dir = f"/tmp/ocr/{req_id}"
    image_dir = os.path.join(base_dir, "images")
    pdf_path = os.path.join(base_dir, "input.pdf")

    dpi = int(os.getenv("OCR_DPI", "350"))
    max_pages = int(os.getenv("OCR_MAX_PAGES", "10"))
    lang = os.getenv("OCR_LANG", "ko")
    ocr_timeout = int(os.getenv("OCR_TIMEOUT_SEC", "60"))
    studio_timeout = int(os.getenv("STUDIO_TIMEOUT_SEC", "60"))
    ocr_max_chars = int(os.getenv("OCR_TEXT_MAX_CHARS", "12000"))
    tts_max_chars = int(os.getenv("TTS_TEXT_MAX_CHARS", "10000"))

    t0 = time.time()
    
    client_id, client_ip, ua = get_client_meta(request)

    safe_db(db_create_request, req_id, client_id, client_ip, ua)
    if client_id:
        safe_db(db_inc_usage_daily, client_id)

    safe_db(db_update_request, req_id, "PROCESSING", None)

    # ===== STEP: HASH/CACHE =====
    pdf_hash, cache_key = make_cache_key(data, force_ocr=force_ocr, force_regen=force_regen)

    safe_db(db_set_input_hash, req_id, pdf_hash)
    safe_db(db_set_cache_key, req_id, cache_key)

    cached_key = None

    if force_regen == 1:
        # 강제 재생성: 캐시를 "조회하지 않음" -> MISS 찍으면 안 됨
        safe_db(db_insert_step, req_id, "CACHE", "SKIP", 0, "force_regen=1")
    else:
        cached_key = safe_db(db_find_cached_audio_key, cache_key, pdf_hash)

        if cached_key:
            safe_db(db_insert_step, req_id, "CACHE", "OK", 0, f"hit cache_key={cache_key} key={cached_key}")
            safe_db(db_set_result_audio_key, req_id, cached_key)
            safe_db(db_update_request, req_id, "DONE", None)

            audio_url = presign_only(cached_key)
            return {"request_id": req_id, "audio_url": audio_url, "cached": True}
        else:
            safe_db(db_insert_step, req_id, "CACHE", "MISS", 0, f"miss cache_key={cache_key}")  
      

    try:
        os.makedirs(base_dir, exist_ok=True)
        with open(pdf_path, "wb") as f:
            f.write(data)

        # ===== STEP: OCR(or PDF_TEXT) =====
        s0 = time.time()
        try:
            info = build_source_text(
                pdf_path=pdf_path,
                image_dir=image_dir,
                req_id=req_id,
                dpi=dpi,
                max_pages=max_pages,
                lang=lang,
                ocr_timeout=ocr_timeout,
                max_chars=ocr_max_chars,
                force_ocr=(force_ocr == 1),
            )
            # method 정보를 OK 로그에 남겨서 "OCR인지 pdf_text인지"도 DB에서 확인 가능
            meta = f"method={info.get('method')} ocr_pages={info.get('ocr_pages')} pages={info.get('pages_processed')}/{info.get('total_pages')}"
            safe_db(db_insert_step, req_id, "OCR", "OK", int((time.time() - s0) * 1000), meta[:1000])
        except Exception:
            safe_db(db_insert_step, req_id, "OCR", "FAIL", int((time.time() - s0) * 1000), traceback.format_exc()[:800])
            raise

        # ===== STEP: STUDIO =====
        s0 = time.time()
        try:
            script_req_id = f"{req_id}-script"
            script = call_clova_studio_script(info["source_text"], request_id=script_req_id, timeout_sec=studio_timeout)

            safe_db(db_insert_step, req_id, "STUDIO", "OK", int((time.time() - s0) * 1000), "input=source_text")
        except Exception:
            safe_db(db_insert_step, req_id, "STUDIO", "FAIL", int((time.time() - s0) * 1000), traceback.format_exc()[:800])
            raise

        # TTS용 텍스트 클립
        tts_text = (script or "").strip()
        if len(tts_text) > tts_max_chars:
            tts_text = tts_text[:tts_max_chars] + "\n...(중략)"

        # TTS 호출 준비
        key_id = env("CLOVA_VOICE_CLIENT_ID")
        key = env("CLOVA_VOICE_CLIENT_SECRET")

        headers = {
            "X-NCP-APIGW-API-KEY-ID": key_id,
            "X-NCP-APIGW-API-KEY": key,
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        speaker = os.getenv("TTS_SPEAKER", "nara")
        speed = os.getenv("TTS_SPEED", "0")

        # ===== STEP: VOICE(TTS) =====
        s0 = time.time()
        try:
            r, used_attempt = post_with_retry(
                TTS_URL,
                headers=headers,
                data={"speaker": speaker, "speed": str(speed), "text": tts_text},
                timeout=30,
                )

            safe_db(db_insert_step, req_id, "VOICE", "OK", int((time.time() - s0) * 1000), f"attempt={used_attempt}")
        except Exception:
            safe_db(db_insert_step, req_id, "VOICE", "FAIL", int((time.time() - s0) * 1000), traceback.format_exc()[:800])
            raise

        # 로컬 임시 저장(업로드용)
        filename = f"{req_id}.mp3"
        out_path = TTS_OUT_DIR / filename
        out_path.write_bytes(r.content)

        # Object Storage 업로드 + Presigned URL 발급
        prefix = os.getenv("OBJ_PREFIX", "podcast/")
        object_key = f"{prefix}{req_id}.mp3"

        # ===== STEP: STORE =====
        s0 = time.time()
        try:
            audio_url = upload_mp3_and_presign(str(out_path), object_key)
            safe_db(db_insert_step, req_id, "STORE", "OK", int((time.time() - s0) * 1000), object_key[:1000])
            safe_db(db_set_result_audio_key, req_id, object_key)
        except Exception:
            safe_db(db_insert_step, req_id, "STORE", "FAIL", int((time.time() - s0) * 1000), traceback.format_exc()[:800])
            raise
        finally:
            #  로컬 파일 삭제 (디스크 누수 방지)
            try:
                out_path.unlink()
            except FileNotFoundError:
                pass
            except Exception:
                pass

        elapsed_ms = int((time.time() - t0) * 1000)

        # DB: 성공 종료
        safe_db(db_update_request, req_id, "DONE", None)

        return {
            "request_id": req_id,
            "method": info["method"],
            "pdf_text_metrics": info["metrics"] if info["method"] == "pdf_text" else None,
            "audio_url": audio_url,
            "expires_in_sec": int(os.getenv("OBJ_PRESIGN_EXPIRE_SEC", "900")),
            "total_pages": info["total_pages"],
            "pages_processed": info["pages_processed"],
            "ocr_pages": info["ocr_pages"],
            "truncated": info["truncated"],
            "elapsed_ms": elapsed_ms,
        }

    except RuntimeError as e:
        safe_db(db_update_request, req_id, "FAILED", str(e)[:2000])
        raise HTTPException(status_code=502, detail=str(e))
    except Exception as e:
        safe_db(db_update_request, req_id, "FAILED", traceback.format_exc()[:2000])
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)[:300]}")
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)
