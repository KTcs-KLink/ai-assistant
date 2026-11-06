import { ExternalLink } from 'lucide-react'

/**
 * The original KTCS HR RAG live demo runs on the user's own machine.
 * We do not copy its data, bypass its evidence approval checks, or proxy it
 * through the newer generic PDF demo API.
 */
const ORIGINAL_URL = import.meta.env.VITE_KTCS_ORIGINAL_DEMO_URL || 'http://127.0.0.1:8811/'

export function OriginalDataDemoPage() {
  return (
    <main className="flex min-w-0 flex-1 flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-6 py-4">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold">우리 데이터 RAG 실시간 시연</h1>
          <p className="mt-1 text-xs text-muted">
            한국전력 공개 규정 기반 K:LINK 인사 도메인 · 실제 KTcs 사규가 아닙니다
          </p>
        </div>
        <a
          href={ORIGINAL_URL}
          target="_blank"
          rel="noopener noreferrer"
          className="flex items-center gap-2 rounded-md bg-brand px-3 py-2 text-sm font-medium text-white hover:bg-brand-strong"
        >
          시연 앱 새 창에서 열기 <ExternalLink size={14} />
        </a>
      </header>

      <div className="flex flex-wrap items-start gap-4 border-b border-line bg-side px-6 py-3 text-xs text-ink-2">
        <span>기존 인사 RAG 평가: 개발용 질문 <strong>960개</strong></span>
        <span>검색 허용 원문 <strong>248구간</strong></span>
        <span>검색용 절/조 본문 <strong>123개</strong></span>
        <span>검색: BGE-M3 Dense 기반 실험</span>
      </div>
      <div className="border-b border-line px-6 py-3 text-xs leading-5 text-muted">
        아래 화면은 사용자 PC의 기존 시연 서버를 불러옵니다. 이 화면이 열리지 않으면 먼저 기존 로컬 RAG 앱을 실행하세요.
        이전 사용 주소는 <code className="mx-1">{ORIGINAL_URL}</code>이며 현재 실행 여부는 자동 보증되지 않습니다.
        브라우저 보안 설정에 따라 삽입이 차단될 수 있으므로 이때는 새 창으로 여세요.
        <strong className="ml-1">현재 새 서버의 PDF 인덱스와는 별개입니다.</strong>
      </div>
      <iframe
        title="KTcs K:LINK 기존 실제 데이터 기반 RAG 시연 화면"
        src={ORIGINAL_URL}
        className="min-h-0 w-full flex-1 border-0 bg-white"
        referrerPolicy="no-referrer"
      />
    </main>
  )
}
