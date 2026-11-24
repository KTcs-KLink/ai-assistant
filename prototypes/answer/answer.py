"""검색 결과를 근거로 OpenAI 모델이 답변하게 하는 프로토타입.

서버 모듈 위치와 기술 스택이 정해지기 전에 답변 프롬프트와 출처 검증을 시험하는 용도다.
MCP 서버가 아직 없으므로 knowledge-mcp의 검색 모듈을 직접 불러온다(ADR-0001의 대체 방식:
서버가 먼저 검색하고 결과를 모델 입력에 넣는다). MCP 서버가 생기면 search() 부분만 MCP 호출로 바꾼다.
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-4.1-mini"
# 리랭커 점수가 이보다 낮은 조항은 관련 없다고 보고 근거에서 뺀다.
MIN_SCORE = 0.05

SYSTEM_PROMPT = """당신은 사내 규정을 안내하는 어시스턴트입니다.

- 아래 [근거]에 있는 내용만 사용해 답합니다. 근거에 없는 내용은 추측하지 않습니다.
- 근거로 답할 수 없으면 "제공된 규정에서 찾을 수 없습니다."라고 답하고, 관련해 찾은 조항이 있으면 함께 안내합니다.
- 사실을 말한 문장 끝에 근거 번호를 [1], [2]처럼 붙입니다.
- 답변 안에서 문서명과 조 번호(예: 취업규칙 제52조)를 밝힙니다.
- 여러 규정이 다르게 정하면 각각 구분해 설명합니다.
- 한국어로 간결하게 답합니다."""

CITATION = re.compile(r"\[(\d+)\]")


def build_context(hits):
    blocks = []
    for number, hit in enumerate(hits, 1):
        pages = f"p.{hit['page_start']}" + (f"-{hit['page_end']}" if hit["page_end"] != hit["page_start"] else "")
        blocks.append(f"[{number}] {hit['heading_path']} ({pages})\n{hit['text']}")
    return "\n\n".join(blocks)


def validate_citations(text, hit_count):
    """답변의 근거 번호가 실제로 넘긴 검색 결과 범위 안에 있는지 확인한다.

    반환: (사용한 번호 목록, 범위를 벗어난 번호 목록)
    """
    numbers = sorted({int(number) for number in CITATION.findall(text)})
    return ([n for n in numbers if 1 <= n <= hit_count],
            [n for n in numbers if not 1 <= n <= hit_count])


def generate(client, model, question, hits):
    """근거를 넣어 답변을 스트리밍으로 출력하고 전체 답변을 반환한다."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"[근거]\n{build_context(hits)}\n\n[질문]\n{question}"}]
    stream = client.chat.completions.create(model=model, messages=messages, stream=True)
    parts = []
    for event in stream:
        delta = event.choices[0].delta.content if event.choices else None
        if delta:
            parts.append(delta)
            print(delta, end="", flush=True)
    print()
    return "".join(parts)


def load_search_index():
    """MCP 서버가 생기기 전까지 knowledge-mcp의 검색 모듈을 직접 불러온다."""
    root = Path(os.getenv("KNOWLEDGE_MCP_DIR") or HERE.parents[2] / "knowledge-mcp")
    module_dir = root / "src" / "retrieval"
    if not (module_dir / "search.py").exists():
        raise SystemExit(f"knowledge-mcp 검색 모듈을 찾지 못했습니다. KNOWLEDGE_MCP_DIR를 지정하세요: {root}")
    sys.path.insert(0, str(module_dir))
    from search import Index
    return Index()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("question", nargs="?", help="생략하면 질문을 계속 입력하는 대화형 모드로 실행한다")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--model", default=None, help=f"기본값: OPENAI_MODEL 또는 {DEFAULT_MODEL}")
    args = parser.parse_args()

    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(HERE / ".env")
    if not os.getenv("OPENAI_API_KEY"):
        parser.error(f"{HERE / '.env'}에 OPENAI_API_KEY가 없습니다.")
    model = args.model or os.getenv("OPENAI_MODEL") or DEFAULT_MODEL
    client = OpenAI()
    index = load_search_index()

    def run(question):
        hits = [hit for hit in index.search(question, top_k=args.top_k) if hit["score"] >= MIN_SCORE]
        if not hits:
            print("관련 규정을 찾지 못했습니다.")
            return
        print()
        text = generate(client, model, question, hits)
        used, invalid = validate_citations(text, len(hits))
        print("\n근거")
        for number, hit in enumerate(hits, 1):
            mark = "*" if number in used else " "
            print(f" {mark}[{number}] {hit['heading_path']} (p.{hit['page_start']}-{hit['page_end']}, 관련도 {hit['score']:.2f})")
        if invalid:
            print(f"경고: 검색 결과에 없는 근거 번호를 사용했습니다: {invalid}")
        elif not used:
            print("경고: 답변에 근거 번호가 없습니다.")

    if args.question:
        run(args.question)
        return 0
    print(f"모델: {model}. 첫 질문은 검색 모델을 불러오느라 1분 정도 걸립니다. 끝내려면 빈 줄에서 Enter.")
    while True:
        try:
            question = input("\n질문> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not question:
            break
        run(question)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
