import { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { ArrowRight, Bookmark, ChevronDown, Search, SlidersHorizontal, X } from 'lucide-react'
import { handleTabKey, BenefitCard, EmptyState, PageHeading } from './components'
import { useWorkspace } from './WorkspaceContext'

export function BenefitsBrowsePage() {
  const { benefits, saved } = useWorkspace()
  const [params, setParams] = useSearchParams()
  const [query, setQuery] = useState(''),
    [category, setCategory] = useState('전체')
  const filter = params.get('status') ?? 'all'
  const [sort, setSort] = useState('recommended')
  const counts = {
    all: benefits.length,
    eligible: benefits.filter((b) => b.status === 'eligible').length,
    needs_review: benefits.filter((b) => b.status === 'needs_review').length,
    ineligible: benefits.filter((b) => b.status === 'ineligible').length,
    saved: saved.length,
  }
  const filtered = benefits.filter(
    (b) =>
      (filter === 'all' || (filter === 'saved' ? saved.includes(b.id) : b.status === filter)) &&
      (category === '전체' || b.category === category) &&
      `${b.title} ${b.category} ${b.description}`.includes(query.trim()),
  )
  if (sort === 'deadline') filtered.sort((a, b) => (a.daysLeft ?? 999) - (b.daysLeft ?? 999))
  else if (sort === 'recommended')
    filtered.sort(
      (a, b) =>
        ['eligible', 'needs_review', 'ineligible'].indexOf(a.status) -
        ['eligible', 'needs_review', 'ineligible'].indexOf(b.status),
    )
  function reset() {
    setParams({})
    setCategory('전체')
    setQuery('')
  }
  return (
    <>
      <PageHeading
        eyebrow="MY BENEFITS"
        title="나를 위한 혜택"
        description="내 조건에 맞는 복지·휴가·지원 혜택을 빠짐없이 살펴보세요."
        action={
          <Link className="kl-button secondary" to="/workspace/profile">
            <SlidersHorizontal size={16} />
            추천 조건 수정
          </Link>
        }
      />
      <div className="kl-benefits-intro">
        <span className="kl-intro-icon">
          <Bookmark size={20} />
        </span>
        <p>
          <strong>필요한 혜택은 저장해 두세요.</strong> 조건과 규정을 확인한 뒤 신청 준비로 이어갈
          수 있어요.
        </p>
        <Link className="kl-text-link" to="/workspace/preparations">
          내 준비 목록
          <ArrowRight size={14} />
        </Link>
      </div>
      <div
        className="kl-tabbar benefit-status"
        role="tablist"
        onKeyDown={handleTabKey}
        aria-label="혜택 상태"
      >
        {[
          { id: 'all', label: '전체 혜택' },
          { id: 'eligible', label: '조건 충족' },
          { id: 'needs_review', label: '추가 확인' },
          { id: 'ineligible', label: '해당 없음' },
          { id: 'saved', label: '저장한 혜택' },
        ].map(({ id, label }) => (
          <button
            role="tab"
            key={id}
            aria-selected={filter === id}
            tabIndex={filter === id ? 0 : -1}
            onClick={() => setParams(id === 'all' ? {} : { status: id })}
          >
            {label}
            <span>{counts[id as keyof typeof counts]}</span>
          </button>
        ))}
      </div>
      <div className="kl-filter-panel">
        <label className="kl-search-input">
          <Search size={17} />
          <input
            aria-label="혜택 검색"
            placeholder="혜택 이름이나 관심 주제로 찾아보세요"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          {query && (
            <button
              aria-label="혜택 검색 지우기"
              className="kl-icon-button"
              onClick={() => setQuery('')}
            >
              <X size={15} />
            </button>
          )}
        </label>
        <div className="kl-filter-bottom">
          <div className="kl-chip-row" role="group" aria-label="혜택 분야">
            {['전체', '가족·육아', '휴가·휴직', '성장·자기계발', '수당·지원'].map((c) => (
              <button
                key={c}
                className={`kl-chip ${category === c ? 'active' : ''}`}
                aria-pressed={category === c}
                onClick={() => setCategory(c)}
              >
                {c}
              </button>
            ))}
          </div>
          <label className="kl-sort">
            <select aria-label="혜택 정렬" value={sort} onChange={(e) => setSort(e.target.value)}>
              <option value="recommended">추천순</option>
              <option value="deadline">마감 가까운 순</option>
              <option value="default">기본순</option>
            </select>
            <ChevronDown size={13} />
          </label>
        </div>
      </div>
      <div className="kl-result-meta">
        <span>
          총 <strong>{filtered.length}개</strong> 혜택
        </span>
        <span>예시 조건에 따른 안내 · 실제 회사 자격 확인 전</span>
      </div>
      <div className="kl-benefit-grid" aria-live="polite">
        {filtered.map((b) => (
          <BenefitCard key={b.id} benefit={b} />
        ))}
      </div>
      {!filtered.length && (
        <EmptyState
          title={
            filter === 'saved' && !saved.length
              ? '아직 저장한 혜택이 없어요'
              : '찾는 혜택이 보이지 않아요'
          }
          description={
            filter === 'saved'
              ? '혜택 카드의 저장 버튼을 눌러 나중에 다시 확인하세요.'
              : '검색어나 분야를 바꾸어 다시 찾아보세요.'
          }
          icon={filter === 'saved' ? Bookmark : Search}
        >
          <button className="kl-button secondary" onClick={reset}>
            전체 혜택 보기
            <ArrowRight size={15} />
          </button>
        </EmptyState>
      )}
      <p className="kl-bottom-caption">
        카드의 금액·일수·일정은 화면 검토용 예시입니다. 조건에 맞는다는 안내가 지급·휴가 승인을
        뜻하지 않아요.
      </p>
    </>
  )
}
