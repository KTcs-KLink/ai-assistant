"""Check the delegated HR service; never start or replace another checkout's server."""
import json
from urllib.request import urlopen


def main():
    try:
        with urlopen("http://127.0.0.1:8846/api/benefits/hr/capabilities", timeout=5) as response:
            value = json.load(response)
        if (value.get("app") != "KLINK_HR_DOMAIN" or value.get("quality_version") != "hr-quality-closeout-20261107"
                or value.get("retrieval_mode") != "hybrid" or value.get("question_understanding") != "llm"
                or value.get("source_scope") != "expanded"):
            raise ValueError("Unexpected service version")
    except (OSError, ValueError):
        raise SystemExit("확장 자료 범위를 지원하는 한전 인사 서비스(8846)를 확인하지 못했어요. 원래 인사 개발 채팅의 실행기로 먼저 시작해 주세요. 기존 서비스는 변경하지 않았습니다.") from None
    print("한전 확장 답변 자료·검토 전용 발췌 서비스 연결 확인.")


if __name__ == "__main__":
    main()
