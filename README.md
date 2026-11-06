# AI Assistant

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

## 실시간 RAG 시연 브랜치 (2026-11-06)

이 브랜치에는 `server/app.py` FastAPI가 추가되었습니다. 기존 `web/` 화면과 동일한 로그인/대화/SSE 계약으로 연결되며, 허용된 텍스트 PDF를 업로드하면 조항 중심 청킹 → Dense 임베딩 → 문서 검색 → 출처 기반 OpenAI 답변을 실시간으로 표시합니다. 관리자 화면은 등록 문서 수와 API 설정 상태를 보여줍니다.

**실행 방법:** [server/README.md](server/README.md)를 참고하세요. `web/.env.example`은 실제 API 사용이 기본이며 `VITE_USE_MOCK=true`일 때에만 기존 고정 예시 답변을 씁니다. 기존 `knowledge-mcp`의 파싱 문서는 `server/import_parsed.py`로 **이용 허용 여부를 검토한 뒤** 선택적으로 적재할 수 있습니다.

**구현되지 않은 부분:** Supabase pgvector(연결 계정의 프로젝트가 비활성), KTcs 내부 실사용 데이터, 정식 SSO/RBAC, OCR, 운영용 자동 변경감지·MCP 서비스. 본 기능은 단일 관리자·로컬 시연용이며 실서비스라고 주장할 수 없습니다.

## 현재 상태

현재 `web/`은 React 사용자 화면을, `server/`는 시연용 FastAPI RAG 서버를 담당합니다. SSE API는 작동 테스트를 통과했으며 모델 외부 호출과 데이터베이스 운영 연동은 실제 키와 허용된 자료가 구성된 환경에서 별도 검증해야 합니다. `knowledge-mcp`와 정식 검색 MCP 연결은 후속 작업입니다.

## 폴더 구조

```text
src/
  api/        브라우저에서 Assistant API를 호출하는 client 코드
  features/   질문, 답변, 출처 등 사용자 기능
  shared/     기능 간 공통 UI와 유틸리티
public/       정적 파일
tests/        화면 및 기능 테스트
docs/         화면 흐름, 연동 규격, 개발 문서
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
