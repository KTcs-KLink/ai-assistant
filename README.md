# AI Assistant

사용자가 업무 질문을 입력하고 AI 답변과 참고 출처를 확인하는 client 프로젝트입니다. 지식 검색·답변과 MCP 도구는 `knowledge-mcp` 저장소에서 관리합니다.

## 폴더 구조

```text
src/
  api/        서버 API 연결과 요청·응답 처리
  features/   질문, 답변, 출처 등 사용자 기능
  shared/     여러 기능이 함께 쓰는 UI와 유틸리티
public/       정적 파일
tests/        화면·기능 확인 코드
docs/         화면 흐름, API 연동 메모
```

기술 스택이 정해지면 실행·설치 방법과 실제 파일 구조를 이 README에 추가합니다. `main`에 직접 커밋하지 말고 조직 공통 [협업 가이드](https://github.com/KTcs-KLink/.github/blob/main/CONTRIBUTING.md)를 따라 주세요.

## API 연동 원칙

- client는 server 또는 MCP 저장소의 내부 파일을 직접 가져다 쓰지 않습니다.
- API의 요청·응답 규격에 맞춰 통신하며, 규격 변경은 양쪽 저장소에 영향을 주는 결정으로 공유합니다.
- 화면에서는 답변과 함께 출처를 확인할 수 있도록 합니다.
