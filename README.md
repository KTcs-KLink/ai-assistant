# AI Assistant

## 맞춤 혜택 작업 브랜치 (2026-11-07)

`feat/personalized-benefits-20261107`에서 개인 조건에 맞는 복지·수당·휴가 카드와 판정 이유, 근거, 동의 관리, 신청 준비 흐름을 구현했습니다. **현재 카탈로그와 직원은 가상이며 실제 KTcs 자격 검증이 아닙니다.**

로컬에서는 `start_benefits.cmd`를 더블클릭하거나 `python scripts/launch_benefits_demo.py`로 실행합니다. 새 화면은 `http://127.0.0.1:8821/benefits`, 전용 API는 `8820`을 사용합니다. 기존 `.env`를 서버에서 읽고 원문·기존 평가·색인·다른 실행 포트를 수정하지 않습니다. 최초 설치 및 연결 한계는 [실행·검증 안내](docs/benefits-verification-20261107.md)를 보세요.

- [제품 벤치마킹과 확인 범위](docs/benefits-benchmark-20261107.md)
- [우선순위·저장소·데이터 연결 백로그](docs/benefits-backlog-20261107.md)
- [단계별 검증 결과와 남은 연결](docs/benefits-verification-20261107.md)

Supabase 직원 인증과 본인 조건 CRUD 경로, RLS SQL을 준비했습니다. 실제 대상 프로젝트에서 스키마·사용자 간 접근 제한이 검증되기 전까지 운영 연동 완료로 표시하지 않습니다. `knowledge-mcp`와 직접 연결되는 MCP 검색 서비스는 아직 없으며, 이번 로컬 조회는 기존 자동 허용 본문을 해시 대조 후 읽는 별도 키워드 참고 조회입니다.

KTcs 업무지식에 질문하고 답변과 근거 출처를 확인하는 AI 어시스턴트 프로젝트입니다. 이 저장소는 사용자 화면과 Assistant 서버·오케스트레이터를 함께 담당합니다. 지식 데이터 처리, 검색 및 MCP 서버는 [`knowledge-mcp`](https://github.com/KTcs-KLink/knowledge-mcp) 저장소에서 관리합니다.

> KTcs가 제공한 데이터는 아직 없습니다. 실제 KTcs 내부 정보가 포함된 기능은 승인된 데이터와 접근 방식이 준비된 뒤에만 구현합니다.

## 프로젝트 목표

- 자연어 질문을 입력하고 AI 답변을 확인할 수 있는 흐름을 제공합니다.
- 답변의 근거가 되는 문서와 위치를 함께 보여줍니다.
- 검색 중, 결과 없음, 오류 등 각 상태를 사용자가 이해할 수 있게 안내합니다.
- 데이터나 검색 근거가 부족하면 추측을 사실처럼 표현하지 않고 한계를 알립니다.

## 저장소 역할

| 저장소 | 담당 |
| --- | --- |
| `ai-assistant` | 사용자 화면, Assistant API·오케스트레이션, 모델 연동, MCP Client, 답변·출처 검증 |
| [`knowledge-mcp`](https://github.com/KTcs-KLink/knowledge-mcp) | 허가된 지식 자료, 출처 manifest, 청크 형식, 검색 API 및 MCP Server |
| [`.github`](https://github.com/KTcs-KLink/.github) | 조직 공통 협업 규칙, 이슈·PR 템플릿, 조직 소개 |

## 내 PC에서 기존 960문항 인사 RAG 화면 바로 열기 (Windows)

다음 명령을 **PowerShell에서 한 번에 실행**하세요. 이전 로컬 KTCS 폴더의 원본 인덱스를 수정하지 않고, 8811번 기존 RAG 앱과 5173번 K:LINK 웹을 실행한 다음 기본 브라우저를 엽니다.

```powershell
$ROOT = "C:\Users\hjy10\OneDrive\문서\ChatGPT\KTCS"
$REPO = Join-Path $ROOT "klink-demo-ui"
if (-not (Test-Path (Join-Path $REPO ".git"))) {
    git clone https://github.com/KTcs-KLink/ai-assistant.git $REPO
}
git -C $REPO fetch origin
git -C $REPO switch feat/live-rag-chat-20261106
git -C $REPO pull --ff-only origin feat/live-rag-chat-20261106
& (Join-Path $REPO "start_klink.cmd")
```

또는 해당 저장소 폴더에서 `start_klink.cmd`를 더블클릭해도 됩니다. 서버가 정상 실행되면 `http://127.0.0.1:5173/original-data-demo`를 열게 됩니다.

**중요한 제한:** 이 런처가 연결하는 기존 8811번 앱의 Python 실행 진입점과 실제 인덱스 로딩은 사용자 PC에서만 확인할 수 있습니다. 자동 실행이 실패하면 `klink-demo-ui/.demo-logs/original-rag.stderr.log`에서 실제 오류를 확인하세요. 검색 가능한 Python 앱이 여러 개이면 임의로 선택하지 않고 실패합니다. 비밀키 또는 내부 자료는 로그를 그대로 공유하기 전에 가려 주세요.

`py scripts/launch_local_demo.py --inspect-only`를 실행하면 원본 파일을 변경하지 않고 파일 구조만 확인할 수 있습니다. 화면이 열려도 **기존 인덱스로 정확하게 답변하는지**는 질문을 실제 입력하고 검색 로그를 확인해야 합니다. Supabase 적재나 원본 `app_core.py` 수정까지 완료된 것은 아닙니다.

## 실시간 RAG 시연 브랜치 (2026-11-06)

이 브랜치에는 `server/app.py` FastAPI가 추가되었습니다. 기존 `web/` 화면과 동일한 로그인/대화/SSE 계약으로 연결되며, 허용된 텍스트 PDF를 업로드하면 조항 중심 청킹 → Dense 임베딩 → 문서 검색 → 출처 기반 OpenAI 답변을 실시간으로 표시합니다. 관리자 화면은 등록 문서 수와 API 설정 상태를 보여줍니다.

**실행 방법:** [server/README.md](server/README.md)를 참고하세요. `web/.env.example`은 실제 API 사용이 기본이며 `VITE_USE_MOCK=true`일 때에만 기존 고정 예시 답변을 씁니다. 기존 `knowledge-mcp`의 파싱 문서는 `server/import_parsed.py`로 **이용 허용 여부를 검토한 뒤** 선택적으로 적재할 수 있습니다.

**구현되지 않은 부분:** Supabase pgvector(연결 계정의 프로젝트가 비활성), KTcs 내부 실사용 데이터, 정식 SSO/RBAC, OCR, 운영용 자동 변경감지·MCP 서비스. 본 기능은 단일 관리자·로컬 시연용이며 실서비스라고 주장할 수 없습니다.

## 현재 상태

현재 `web/`은 React 사용자 화면을, `server/`는 시연용 FastAPI RAG 서버를 담당합니다. SSE API는 작동 테스트를 통과했으며 모델 외부 호출과 데이터베이스 운영 연동은 실제 키와 허용된 자료가 구성된 환경에서 별도 검증해야 합니다. `knowledge-mcp`와 정식 검색 MCP 연결은 후속 작업입니다.

## 폴더 구조

```text
web/
  src/api/    서버 API 및 SSE 클라이언트
  src/chat/   질문/답변 스트리밍, 인용 출처
  src/admin/  문서 관리, 피드백, 실행 상태
server/
  app.py      FastAPI 인증/대화/임베딩/검색/생성/색인
  import_parsed.py  승인된 knowledge-mcp 마크다운 적재
  tests/      API 실동작 회귀 테스트
docs/         화면 흐름, 연동 규격, ADR
```

서버 측 오케스트레이터의 디렉터리와 기술 스택은 아직 정해지지 않았습니다. 구현 위치가 합의되면 실제 구조를 이 표에 추가합니다.

## 연동 원칙

- 브라우저 client는 지식 저장소의 소스 파일이나 데이터 파일을 직접 참조하지 않고 Assistant API를 사용합니다.
- Assistant 서버는 모델·도구 호출 흐름과 MCP Client 연결을 담당하고, Knowledge MCP는 검색 도구와 근거가 포함된 응답을 제공합니다.
- Assistant API와 MCP 도구의 요청·응답 규격, 오류 형식, 인증 방식은 각 저장소 담당자가 함께 합의하고 문서화합니다.
- 답변에는 확인 가능한 출처 정보를 연결하고, 출처를 찾지 못한 경우 이를 사용자에게 표시합니다.
- 승인되지 않은 내부 데이터, 비밀키, 개인정보를 코드·이슈·로그·화면 캡처에 포함하지 않습니다.

## 개발 및 기여

기술 스택과 설치 절차가 확정되면 이곳에 실행 방법을 추가합니다. 브랜치, 커밋, PR 작성 방식은 조직 [협업 가이드](https://github.com/KTcs-KLink/.github/blob/main/CONTRIBUTING.md)를 따릅니다. 기능 작업은 작은 단위로 나누고, 화면 동작이나 API 규격에 영향을 주는 변경은 PR에 확인 방법과 영향을 적어 주세요.

## 관련 문서

- [조직 소개 및 프로젝트 개요](https://github.com/KTcs-KLink/.github)
- [조직 협업 가이드](https://github.com/KTcs-KLink/.github/blob/main/CONTRIBUTING.md)
- [Knowledge MCP](https://github.com/KTcs-KLink/knowledge-mcp)
