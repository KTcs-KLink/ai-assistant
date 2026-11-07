"""Check the delegated HR service; never start or replace another checkout's server."""
import json
from urllib.request import urlopen


def main():
    try:
        with urlopen("http://127.0.0.1:8844/api/benefits/hr/capabilities", timeout=5) as response:
            value = json.load(response)
        if (value.get("app") != "KLINK_HR_DOMAIN" or value.get("quality_version") != "hr-quality-closeout-20261107"
                or value.get("retrieval_mode") != "hybrid" or value.get("question_understanding") != "llm"):
            raise ValueError("Unexpected service version")
    except (OSError, ValueError):
        raise SystemExit("질문 의미 분석을 지원하는 한전 인사 서비스(8844)를 확인하지 못했어요. 원래 인사 개발 채팅의 실행기로 먼저 시작해 주세요. 기존 서비스는 변경하지 않았습니다.") from None
    print("한전 질문 의미 분석·검색·원문 구간 인용 서비스 연결 확인.")


if __name__ == "__main__":
    main()
