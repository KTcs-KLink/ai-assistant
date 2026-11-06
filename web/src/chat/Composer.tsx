import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { X } from 'lucide-react'
import { api, USE_MOCK } from '../api/client'
import type { Attachment } from '../api/types'
import { cx, MicIcon } from '../components/ui'
import { formatTimer } from '../lib/format'
import { useVoiceInput } from './useVoiceInput'

const ACCEPT = '.pdf'

interface PendingFile {
  key: string
  name: string
  attachment?: Attachment
  error?: boolean
}

interface Props {
  variant: 'hero' | 'dock'
  placeholder: string
  onSend: (text: string, attachments: Attachment[]) => void
  isStreaming?: boolean
  onStop?: () => void
}

export function Composer({ variant, placeholder, onSend, isStreaming, onStop }: Props) {
  const [text, setText] = useState('')
  const [files, setFiles] = useState<PendingFile[]>([])
  const fileInput = useRef<HTMLInputElement>(null)
  const textarea = useRef<HTMLTextAreaElement>(null)
  const voice = useVoiceInput()

  const uploading = files.some((f) => !f.attachment && !f.error)
  const ready = files.flatMap((f) => (f.attachment ? [f.attachment] : []))
  const canSend = !isStreaming && !uploading && (text.trim().length > 0 || ready.length > 0)

  // 내용에 맞춰 높이 조절
  useEffect(() => {
    const el = textarea.current
    if (!el) return
    el.style.height = '0px'
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`
  }, [text, voice.isRecording])

  const submit = () => {
    if (!canSend) return
    onSend(text.trim() || '첨부한 파일 요약해줘', ready)
    setText('')
    setFiles([])
  }

  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    // 한글 조합 중 Enter 는 무시
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  const addFiles = (list: FileList | null) => {
    for (const file of Array.from(list ?? [])) {
      const key = `${file.name}-${Date.now()}-${Math.random()}`
      setFiles((prev) => [...prev, { key, name: file.name }])
      api.uploadAttachment(file).then(
        (attachment) => setFiles((prev) => prev.map((f) => (f.key === key ? { ...f, attachment } : f))),
        () => setFiles((prev) => prev.map((f) => (f.key === key ? { ...f, error: true } : f))),
      )
    }
  }

  const finishVoice = () => {
    const t = voice.finish()
    if (t) setText((prev) => (prev ? `${prev} ${t}` : t))
    requestAnimationFrame(() => textarea.current?.focus())
  }

  const iconBtn = 'flex size-[34px] items-center justify-center rounded-lg'

  return (
    <div
      className={cx(
        'flex w-full flex-col rounded-[14px] border border-line-strong bg-panel',
        variant === 'hero' ? 'gap-3.5 px-4 py-3.5 shadow-[0_2px_8px_rgba(0,0,0,.04)]' : 'gap-2.5 px-3.5 py-3',
      )}
    >
      {files.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {files.map((f) => (
            <span
              key={f.key}
              className={cx(
                'flex items-center gap-1 rounded-md border py-1 pr-1 pl-2 text-xs',
                f.error ? 'border-err-bg bg-err-bg text-err' : 'border-line bg-side',
              )}
            >
              {f.name}
              {!f.attachment && !f.error && <span className="text-faint">· 올리는 중</span>}
              {f.error && <span>· 실패</span>}
              <button
                type="button"
                aria-label={`${f.name} 제거`}
                onClick={() => setFiles((prev) => prev.filter((x) => x.key !== f.key))}
                className="rounded p-0.5 text-faint hover:bg-line hover:text-ink"
              >
                <X size={12} />
              </button>
            </span>
          ))}
        </div>
      )}

      {voice.isRecording ? (
        <>
          <div className={cx('min-h-[24px] text-[15px] leading-[1.6]', voice.transcript ? 'text-ink' : 'text-faint')}>
            {voice.error ?? (voice.transcript || '듣고 있어요…')}
          </div>
          <div className="flex items-center justify-between gap-4">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <span className="size-2 flex-none rounded-full bg-rec" />
              <span className="font-mono text-[13px] font-medium text-ink-2">{formatTimer(voice.seconds)}</span>
              <Waveform />
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={voice.cancel}
                className="h-[34px] rounded-lg border border-line bg-panel px-3 text-[13px] font-medium text-ink-2 hover:bg-side"
              >
                취소
              </button>
              <button type="button" title="녹음 완료" aria-label="녹음 완료" onClick={finishVoice} className={cx(iconBtn, 'bg-brand hover:bg-brand-strong')}>
                <span className="size-2.5 rounded-[2px] bg-white" />
              </button>
            </div>
          </div>
        </>
      ) : (
        <>
          <textarea
            ref={textarea}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={placeholder}
            aria-label="메시지"
            autoFocus={variant === 'hero'}
            className="resize-none bg-transparent text-[15px] leading-[1.6] outline-none placeholder:text-faint"
          />
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={() => fileInput.current?.click()}
              className="rounded-md border border-line px-2.5 py-[5px] text-[13px] hover:bg-side"
            >
              파일 첨부
            </button>
            <input
              ref={fileInput}
              type="file"
              accept={ACCEPT}
              multiple
              hidden
              onChange={(e) => {
                addFiles(e.target.files)
                e.target.value = ''
              }}
            />
            <div className="flex items-center gap-2">
              {USE_MOCK && <button
                type="button"
                title="음성 입력 (모의 모드 전용)"
                aria-label="음성 입력"
                onClick={voice.start}
                disabled={isStreaming}
                className={cx(iconBtn, 'border border-line bg-panel text-ink-2 hover:bg-side')}
              >
                <MicIcon />
              </button>}
              {isStreaming ? (
                <button
                  type="button"
                  onClick={onStop}
                  className="flex h-[34px] items-center gap-1.5 rounded-lg bg-brand px-3 text-[13px] font-medium text-white hover:bg-brand-strong"
                >
                  <span className="size-2.5 rounded-[2px] bg-white" />
                  중지
                </button>
              ) : (
                <button
                  type="button"
                  title="보내기"
                  aria-label="보내기"
                  onClick={submit}
                  disabled={!canSend}
                  className={cx(iconBtn, 'bg-brand text-base text-white hover:bg-brand-strong disabled:opacity-40')}
                >
                  ↑
                </button>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

function Waveform() {
  const bars = useMemo(
    () =>
      Array.from({ length: 36 }, (_, i) => ({
        duration: 0.7 + ((i * 37) % 9) / 10,
        delay: ((i * 53) % 10) / 10,
      })),
    [],
  )
  return (
    <div className="flex h-6 flex-1 items-center gap-[3px] overflow-hidden" aria-hidden>
      {bars.map((b, i) => (
        <span
          key={i}
          className="h-5 w-[3px] flex-none origin-center rounded-sm bg-brand"
          style={{ animation: `klwave ${b.duration}s ease-in-out ${b.delay}s infinite alternate` }}
        />
      ))}
    </div>
  )
}
