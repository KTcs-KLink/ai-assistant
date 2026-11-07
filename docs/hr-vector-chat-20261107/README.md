# 로컬 벡터 챗봇 연결 검증

| 자료 | 확인한 범위 |
| --- | --- |
| [checks.json](checks.json) | 검사 종류별 집계와 변경/보류 범위 |
| [source-verification.json](source-verification.json) | 실제 원문/창/모델 호환, 새 검색 질문 2개, 범위 밖 질문 보류. GPT 호출 0회 |
| [concurrency.json](concurrency.json) | 병렬 준비 확인 4건과 새 질문 임베딩 4건. GPT 호출 0회 |
| [live-connection.json](live-connection.json) | 실제 브라우저 질문 1건 → 새 임베딩 → 청크 5개 → 지정 모델 생성 2회 → 답변/조건 원문 표시 |
| [ui-regression.json](ui-regression.json) | 기존 UI 13개 검사, 42개 화면/폭 조합. 3개 응답 가로채기 상태 구분 |
| [display-verification.json](display-verification.json) | 받은 실제 응답의 후속 표시 확인. 새 질문/모델 호출 없음 |
| [browser-guards.json](browser-guards.json) | 보존 실제 응답의 위치·해시·캐시 표시 변조 3건 차단. 응답 가로채기, 새 모델 호출 0회 |
| [initial-readiness-attempt.json](initial-readiness-attempt.json) | 질문 전송 전 멈춘 초기 준비 확인 실패 보존 |

실제 응답의 [PC 화면](hr-vector-final-1440.png)과 [모바일 화면](hr-vector-final-390.png), 검색 청크를 펼친 [PC](hr-vector-chunks-1440.png)·[모바일](hr-vector-chunks-390.png) 화면을 보존했다. 원래 실질문 검사의 [PC 전체](hr-vector-live-1440.png)·[모바일 전체](hr-vector-live-390.png) 캡처도 유지했다. 후속 표시 캡처를 새 모델 응답으로 세지 않는다.

원문 복사본 전체·질문 벡터·키·직원 쿠키 값을 이 폴더에 저장하지 않았다. 자료는 한국전력 참고자료이며 실제 KTcs 적용, 현행성, 사람 승인, SSO, 공식 양식 및 제출 완료를 뜻하지 않는다. 이번 숫자는 기능/호환 점검으로 검색 성능·답변 정확도 점수가 아니다.

구현·실행·역할·남은 사항은 [연결 기록](../hr-vector-chat-20261107.md)을 참조한다.
