# 최신 인사 API UI 검증 자료

| 파일 | 범위 |
| --- | --- |
| [upstream-capabilities.json](upstream-capabilities.json) | 8842가 반환한 품질 버전·검색 모드·실사용 미승인 상태 |
| [live-connection.json](live-connection.json) | 실제 새 질문 1건, 모델 생성 2회, 답변 1문단·원문 5개·조건 원문 3개 |
| [ui-replay.json](ui-replay.json) | 보존 응답/보류 응답과 합성 플래그/변조 검사 6개. 새 모델 생성 0회 |
| [ui-regression.json](ui-regression.json) | 기존 기능 13개, 화면/폭 42개 조합. 실패/보류 응답 가로채기 구분 |

실제 응답의 [PC](hr-closeout-portal-1440.png)·[390px 모바일](hr-closeout-portal-390.png) 화면을 보존했다. UI 재생용 원문 복사본·키·직원 쿠키 값은 이 폴더에 저장하지 않았다.

한국전력 참고자료와 KTcs 적용 미확인 상태를 유지했다. 이 결과는 UI 기능 검사이며 독립 의미 평가·사람 승인·회사 업무 제출 완료가 아니다. [연결 기록](../hr-closeout-ui-20261107.md)을 함께 참조한다.
