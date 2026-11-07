import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import {
  ArrowRight,
  BookOpen,
  ChevronRight,
  FileText,
  FolderOpen,
  Search,
  ShieldCheck,
  X,
} from 'lucide-react'
import { useWorkspace } from './WorkspaceContext'
import { handleTabKey, EmptyState, Modal, PageHeading, SourceContent } from './components'
import { formReferences } from './forms'
import type { FormReference } from './types'

export function LibraryPage() {
  const { benefits, announce, select } = useWorkspace()
  const [params, setParams] = useSearchParams()
  const [category, setCategory] = useState('전체'),
    [form, setForm] = useState<FormReference | null>(null),
    [sourceId, setSourceId] = useState<string | null>(null)
  const query = params.get('q') ?? '',
    tab = params.get('tab') ?? 'all'
  function update(key: string, value: string) {
    const next = new URLSearchParams(params)
    if (value) next.set(key, value)
    else next.delete(key)
    setParams(next, { replace: true })
  }
  const docs = benefits.filter(
    (b) =>
      (category === '전체' || b.category === category) &&
      `${b.title} ${b.category} ${b.section} 복지 규정`.includes(query),
  )
  const forms = formReferences.filter(
    (f) =>
      (category === '전체' || f.category === category) &&
      `${f.title} ${f.category} ${f.description}`.includes(query),
  )
  const count = (tab === 'forms' ? 0 : docs.length) + (tab === 'regulations' ? 0 : forms.length)
  const source = benefits.find((b) => b.id === sourceId)
  return (
    <>
      <PageHeading
        eyebrow="KNOWLEDGE LIBRARY"
        title="규정과 양식, 한곳에서"
        description="필요한 업무의 근거를 확인하고 신청 준비에 필요한 양식을 찾아보세요."
      />
      <div className="kl-library-hero">
        <span>
          <FolderOpen size={28} />
        </span>
        <div>
          <h2>이름을 몰라도, 업무로 찾아보세요.</h2>
          <p>‘휴가’, ‘출장’, ‘퇴직’처럼 하고 싶은 일을 검색해 보세요.</p>
        </div>
        <BookOpen className="kl-library-decoration" size={64} strokeWidth={1} />
      </div>
      <label className="kl-search-input library">
        <Search size={20} />
        <input
          aria-label="규정·양식 검색"
          placeholder="문서 이름이나 필요한 업무를 입력해 주세요"
          value={query}
          onChange={(e) => update('q', e.target.value)}
        />
        {query && (
          <button
            className="kl-icon-button"
            aria-label="자료 검색 지우기"
            onClick={() => update('q', '')}
          >
            <X size={16} />
          </button>
        )}
      </label>
      <div className="kl-tabbar" role="tablist" onKeyDown={handleTabKey} aria-label="자료 유형">
        {[
          { id: 'all', label: '전체 자료' },
          { id: 'regulations', label: '규정·기준' },
          { id: 'forms', label: '신청 양식' },
        ].map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            tabIndex={tab === t.id ? 0 : -1}
            onClick={() => update('tab', t.id)}
          >
            {t.label}
          </button>
        ))}
      </div>
      <div className="kl-library-categories kl-chip-row" role="group" aria-label="자료 분야">
        {[
          '전체',
          '가족·육아',
          '휴가·휴직',
          '성장·자기계발',
          '수당·지원',
          '출장·정산',
          '입사·퇴직',
        ].map((c) => (
          <button
            className={`kl-chip ${category === c ? 'active' : ''}`}
            key={c}
            aria-pressed={category === c}
            onClick={() => setCategory(c)}
          >
            {c}
          </button>
        ))}
      </div>
      <div className="kl-result-meta">
        <span>
          총 <strong>{count}개</strong> 자료
        </span>
        <span>규정은 예시 자료 · 회사 공식 양식은 연결 전</span>
      </div>
      <div className="kl-document-list">
        {tab !== 'forms' &&
          docs.map((b) => (
            <button key={b.id} className="kl-document-row" onClick={() => setSourceId(b.id)}>
              <span className="kl-doc-icon">
                <BookOpen size={22} />
              </span>
              <div>
                <div className="kl-document-labels">
                  <span>예시 규정</span>
                  <span>{b.category}</span>
                </div>
                <h3>{b.title} 운영 기준</h3>
                <p>
                  {b.section} · {b.description}
                </p>
              </div>
              <div className="kl-doc-date">
                <span>demo-2026.11.07</span>
                <small>실제 회사 승인 전</small>
              </div>
              <ChevronRight size={17} />
            </button>
          ))}
        {tab !== 'regulations' &&
          forms.map((f) => (
            <button key={f.id} className="kl-document-row" onClick={() => setForm(f)}>
              <span className="kl-doc-icon form">
                <FileText size={22} />
              </span>
              <div>
                <div className="kl-document-labels">
                  <span className="form">신청 양식</span>
                  <span>{f.category}</span>
                </div>
                <h3>{f.title}</h3>
                <p>{f.description}</p>
              </div>
              <div className="kl-doc-date">
                <span>공식 양식 확인 필요</span>
                <small>준비 항목만 확인 가능</small>
              </div>
              <ChevronRight size={17} />
            </button>
          ))}
      </div>
      {!count && (
        <EmptyState
          title="찾는 자료가 아직 없어요"
          description="다른 업무 이름으로 검색하거나 전체 자료를 살펴보세요."
        >
          <button
            className="kl-button secondary"
            onClick={() => {
              setParams({})
              setCategory('전체')
            }}
          >
            전체 자료 보기
            <ArrowRight size={15} />
          </button>
        </EmptyState>
      )}
      <div className="kl-library-help">
        <ShieldCheck size={20} />
        <div>
          <strong>확인된 자료로만 안내할 수 있어요.</strong>
          <p>실제 회사 규정과 공식 양식이 연결되면 원문·버전·적용 범위를 함께 확인할 수 있어요.</p>
        </div>
        <Link to="/workspace/assistant" className="kl-text-link">
          AI에게 물어보기
          <ArrowRight size={15} />
        </Link>
      </div>
      {form && (
        <Modal
          title={form.title}
          subtitle={form.category + ' · 양식 준비 안내'}
          close={() => setForm(null)}
        >
          <div className="kl-modal-body">
            <div className="kl-form-state">
              <FileText size={30} />
              <h3>회사 공식 양식은 아직 연결 전이에요.</h3>
              <p>
                아래 준비 항목은 살펴볼 수 있어요. 임의로 만든 문서를 공식 양식으로 제공하지
                않습니다.
              </p>
              <span className="kl-tag">다운로드·제출 연결 전</span>
            </div>
            <h3 className="kl-subheading">미리 준비할 내용</h3>
            <ol className="kl-numbered-list">
              {form.fields.map((f, i) => (
                <li key={f}>
                  <span>{i + 1}</span>
                  {f}
                </li>
              ))}
            </ol>
            <button
              className="kl-button secondary full"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(
                    `${form.title} 준비 항목\n${form.fields.map((f, i) => `${i + 1}. ${f}`).join('\n')}\n회사 공식 양식·신청 경로 확인 필요`,
                  )
                  announce('준비 항목을 복사했어요. 실제 회사 양식은 아니에요.')
                } catch {
                  announce('준비 항목을 직접 선택해 복사해 주세요.')
                }
              }}
            >
              준비 항목 복사하기
              <ArrowRight size={15} />
            </button>
          </div>
        </Modal>
      )}
      {source && (
        <Modal
          title="규정 근거 확인"
          subtitle={source.title}
          close={() => setSourceId(null)}
          drawer
        >
          <div className="kl-modal-body">
            <SourceContent benefit={source} />
            <button
              className="kl-button primary full"
              onClick={() => {
                setSourceId(null)
                select(source.id)
              }}
            >
              관련 혜택 보기
              <ArrowRight size={15} />
            </button>
          </div>
        </Modal>
      )}
    </>
  )
}
