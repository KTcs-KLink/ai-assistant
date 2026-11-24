"""근거 형식과 출처 번호 검증을 확인한다. API와 검색 모델은 호출하지 않는다."""
import unittest

from answer import build_context, validate_citations


class AnswerTests(unittest.TestCase):
    def test_context_numbers_hits_with_path_and_pages(self):
        hits = [{"heading_path": "취업규칙 > 제52조(휴직기간)", "page_start": 8, "page_end": 8, "text": "본문 A"},
                {"heading_path": "인사관리규정 > 제20조(보직과 정원)", "page_start": 5, "page_end": 6, "text": "본문 B"}]
        self.assertEqual(build_context(hits),
                         "[1] 취업규칙 > 제52조(휴직기간) (p.8)\n본문 A\n\n"
                         "[2] 인사관리규정 > 제20조(보직과 정원) (p.5-6)\n본문 B")

    def test_citations_outside_hits_are_reported(self):
        self.assertEqual(validate_citations("휴직은 1년이다 [1]. 다만 [3] 예외 [1]", 2), ([1], [3]))
        self.assertEqual(validate_citations("근거 없음", 2), ([], []))


if __name__ == "__main__":
    unittest.main()
