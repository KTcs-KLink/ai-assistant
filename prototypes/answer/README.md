# 답변 생성 프로토타입

검색 결과를 근거로 LLM이 답변하고, 답변의 근거 번호가 실제 검색 결과와 맞는지 확인하는 실험용 코드입니다. 서버 모듈의 위치와 기술 스택이 정해지면 그쪽으로 옮기고 이 폴더는 지웁니다.

- 답변 규칙: 근거에 있는 내용만 사용, 문장마다 `[1]` 형식 근거 번호, 문서명·조 번호 명시, 근거가 없으면 "제공된 규정에서 찾을 수 없습니다."
- 출처 검증: 답변에 쓰인 근거 번호가 넘긴 검색 결과 범위 안에 있는지 확인하고, 벗어나면 경고합니다 (ADR-0001의 출처 ID 검증).
- 검색: MCP 서버가 아직 없어 `knowledge-mcp/src/retrieval/search.py`를 직접 불러옵니다. MCP 서버가 생기면 `load_search_index()` 부분을 MCP 호출로 바꿉니다.

## 실행

1. 이 폴더에 `.env`를 만들고 `OPENAI_API_KEY=...`를 넣습니다. 모델은 `OPENAI_MODEL`로 바꿀 수 있습니다(기본 `gpt-4.1-mini`). `.env`는 저장소 루트의 `.gitignore`로 제외됩니다.
2. knowledge-mcp의 `requirements.txt`를 설치하고 청크·임베딩을 만들어 둡니다(`chunker.py`, `embedder.py`). 저장소가 같은 상위 폴더에 있지 않으면 `KNOWLEDGE_MCP_DIR`로 경로를 지정합니다.
3. 실행합니다.

```powershell
python -m pip install -r requirements.txt
python answer.py
```

검색된 규정 원문이 OpenAI API로 전송됩니다.
