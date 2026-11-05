import { useCallback, useEffect, useRef, useState } from 'react'
import { USE_MOCK } from '../api/client'

// TODO(보안): Chrome 의 Web Speech API 는 음성을 Google 서버로 보낸다.
// "대화 내용은 외부로 전송되지 않습니다" 정책과 맞지 않으므로, 운영 전에 사내 STT(예: 백엔드 WebSocket)로 교체해야 한다.
// 목 모드에서는 받아쓰기를 흉내만 낸다.
// Web Speech API (Chrome/Edge: webkitSpeechRecognition). 타입이 표준 lib 에 없어 최소한만 선언.
interface SpeechRecognitionLike {
  lang: string
  continuous: boolean
  interimResults: boolean
  onresult: ((e: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null
  onerror: ((e: { error: string }) => void) | null
  start(): void
  abort(): void
}
type SRConstructor = new () => SpeechRecognitionLike
const SR: SRConstructor | undefined =
  (window as unknown as { SpeechRecognition?: SRConstructor }).SpeechRecognition ??
  (window as unknown as { webkitSpeechRecognition?: SRConstructor }).webkitSpeechRecognition

const DEMO_TEXT = '올해 연차 이월 신청은 어디서 하나요?'

/** 음성 입력: 녹음 상태, 경과 시간, 실시간 받아쓰기 */
export function useVoiceInput() {
  const [isRecording, setRecording] = useState(false)
  const [seconds, setSeconds] = useState(0)
  const [transcript, setTranscript] = useState('')
  const [error, setError] = useState<string | null>(null)
  const textRef = useRef('')
  const timers = useRef<number[]>([])
  const recRef = useRef<SpeechRecognitionLike | null>(null)

  const update = (t: string) => {
    textRef.current = t
    setTranscript(t)
  }

  const cleanup = useCallback(() => {
    timers.current.forEach(clearInterval)
    timers.current = []
    if (recRef.current) {
      recRef.current.onresult = null
      recRef.current.onerror = null
      recRef.current.abort()
      recRef.current = null
    }
  }, [])

  useEffect(() => cleanup, [cleanup])

  /** 음성 인식을 쓸 수 없는 환경(목 모드)에서 받아쓰기를 흉내 낸다 */
  const simulate = () => {
    let i = 0
    timers.current.push(window.setInterval(() => {
      if (i < DEMO_TEXT.length) update(DEMO_TEXT.slice(0, ++i))
    }, 140))
  }

  const start = useCallback(() => {
    cleanup()
    update('')
    setError(null)
    setSeconds(0)
    setRecording(true)
    timers.current.push(window.setInterval(() => setSeconds((s) => s + 1), 1000))

    if (USE_MOCK) return simulate()
    if (!SR) {
      setError('이 브라우저는 음성 입력을 지원하지 않아요')
      return
    }
    const rec = new SR()
    rec.lang = 'ko-KR'
    rec.continuous = true
    rec.interimResults = true
    rec.onresult = (e) => update(Array.from(e.results, (r) => r[0].transcript).join(''))
    rec.onerror = (e) => {
      recRef.current = null
      setError(e.error === 'not-allowed' ? '마이크 권한이 필요해요' : '음성을 인식하지 못했어요')
    }
    recRef.current = rec
    rec.start()
  }, [cleanup])

  const cancel = useCallback(() => {
    cleanup()
    setRecording(false)
    update('')
  }, [cleanup])

  /** 녹음을 끝내고 받아쓴 텍스트를 돌려준다 */
  const finish = useCallback(() => {
    const text = textRef.current
    cancel()
    return text
  }, [cancel])

  return { isRecording, seconds, transcript, error, start, cancel, finish }
}
