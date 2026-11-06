# K:LINK Live RAG 시연 서버

기존 `web/` 화면에 맞춘 **실제 HTTP/SSE API**입니다. 관리자 계정으로 PDF를 업로드하면 텍스트 추출 → 조항 기반 청킹 → Dense 임베딩 → SQLite 벡터 저장을 진행합니다. 검색 시 코사인(정규화된 벡터 내적) Top 5를 OpenAI 모델에 전달해 응답을 토큰 단위로 SSE 전송하고, 문서명/조항/쪽을 표시합니다. 고정 답변을 반환하지 않습니다.

> **중요:** 단일 관리자용 개발·발표 시연입니다. KTcs SSO, 권한별 필터링, 운영용 멀티테넌시, Supabase pgvector, 완전 자동 변경 감지, OCR, MCP 검색 서버는 아직 연결되지 않았습니다. 조직의 사용 승인 없이 내부 자료를 업로드하거나 외부 LLM API로 전송하지 마세요. 공개 대체 자료는 KTcs의 현행 사규가 아닙니다.

## 실행

Python 3.11+ 환경을 권장합니다.

```bash
cd server
python -m venv .venv
# Windows: .venv\Scripts\activate / macOS·Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # Windows PowerShell: Copy-Item .env.example .env
# .env에 KLINK_DEMO_PASSWORD 및 OPENAI_API_KEY를 기입
uvicorn app:app --reload --port 8000
```

다른 터미널에서:

```bash
cd web
npm ci
cp .env.example .env
npm run dev
```

`http://localhost:5173`에서 `.env`의 시연 계정으로 로그인합니다. `/admin/documents`에서 **텍스트가 포함된 PDF**를 선택하고 해당 도메인으로 업로드합니다. 상태가 `ready`로 바뀌면 질문할 수 있습니다. 채팅에 PDF를 첨부하면 해당 대화용 PDF가 먼저 색인됩니다.

`GET http://localhost:8000/health`는 데이터/LLM 설정 여부를 반환합니다. `OPENAI_API_KEY`가 없으면 문서 색인 또는 생성 기능이 실패하는 것이 정상입니다. 이 상태를 모의 답변으로 숨기지 않습니다.

## 기존 knowledge-mcp 파싱 문서 가져오기

`knowledge-mcp/data/manifests/sources.csv`에 있는 문서 18건은 현재 재배포 허용 여부가 `unknown`으로 표시되어 있습니다. 승인된 문서에 대해서만 아래처럼 명시적으로 가져오세요. 미승인 문서는 임베딩/외부 LLM 전송을 하지 마세요.

```bash
cd server
python import_parsed.py --repo ../../knowledge-mcp --source SRC-0004 --collection hr --confirm-authorized
```

원래 파싱된 `parsing.md`에서 장/조 제목을 유지해 청킹하며 PDF 페이지 정보가 없다면 조항 경로만 출처로 표시합니다. `--source`를 반복하거나 허가된 전체 문서만 `--all`로 선택할 수 있습니다.

## 실제 사용 동작

- `POST /api/conversations/{id}/messages` → `text/event-stream`: `meta`(근거) → `delta`(실시간 토큰) → `done`.
- 관리 화면은 등록된 **실제** 문서·질문 수만 집계하며 부정적 답변 피드백은 검토·분류·처리할 수 있습니다. 조직/사용자 디렉터리·권한 제어는 미연동이며 가짜 데이터를 제공하지 않습니다.
- 문서별 400쪽, 20MB, 1,200청크 제한이 있습니다. 스캔 이미지 PDF의 OCR은 미지원입니다.
- 벡터는 SQLite에 저장하고 단일 서버에서 전수 코사인 비교합니다. 대규모 자료는 `knowledge-mcp`와 pgvector 검색 API로 교체해야 합니다.
- `KLINK_EMBED_PROVIDER=local`은 `requirements-local-embeddings.txt` 설치 후 `BAAI/bge-m3`를 사용합니다. OpenAI와 로컬 모델 간 전환 시 기존 문서를 **재색인**해야 합니다.
- `server/.data`에 PDF, 인덱스, 시연 대화가 저장됩니다. Git에 포함되지 않습니다.

## 보안 및 알려진 제약

**인터넷 공개 서버로 그대로 배포하지 마세요.** 시연용 단일 비밀번호·공용 문서 공간이며 운영용 RBAC/SSO, 업로드 악성코드 검사, rate limit, 사용자별 데이터 분리, 암호화/보존기간 정책이 없습니다. 로그인 쿠키는 HTTPOnly이며 HTTPS 배포에서는 `KLINK_SECURE_COOKIE=true`가 필요합니다.

답변 모델을 사용할 경우 관련 질문·근거 텍스트가 OpenAI API로 전달됩니다. '모든 데이터가 회사 서버에만 저장된다'고 안내하지 않습니다. 실제 KTcs 직원의 사용 전 정보보호 승인과 SSO/RLS가 필요합니다.

기존 Supabase 연결은 확인된 프로젝트가 비활성 상태이므로 **쓰기 작업을 하지 않았습니다**. 이 시연 서버는 Supabase를 사용하지 않습니다.
