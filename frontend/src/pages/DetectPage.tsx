import { useRef, useState } from 'react'
import { predictPost } from '../lib/api'
import type { PredictResponse } from '../lib/api'

const MIN_LEN = 10
const MAX_LEN = 10000

function LoadingSpinner() {
  return (
    <svg width="28" height="28" viewBox="0 0 24 24" className="text-slate-600" aria-hidden>
      <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" fill="none" opacity="0.2" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        fill="none"
        strokeLinecap="round"
      >
        <animateTransform
          attributeName="transform"
          type="rotate"
          from="0 12 12"
          to="360 12 12"
          dur="0.9s"
          repeatCount="indefinite"
        />
      </path>
    </svg>
  )
}

function formatScore(p: number | null): string {
  if (p === null) return '—'
  return `${Math.round(p * 1000) / 10}%`
}

export function DetectPage() {
  const requestGen = useRef(0)
  const [text, setText] = useState('')
  const [result, setResult] = useState<PredictResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const trimmed = text.trim()
  const len = text.length
  const canAnalyze = trimmed.length >= MIN_LEN && len <= MAX_LEN && !loading

  async function analyze() {
    const gen = ++requestGen.current
    setError(null)
    setResult(null)
    setLoading(true)
    try {
      const data = await predictPost(trimmed)
      if (gen !== requestGen.current) return
      setResult(data)
    } catch (e: unknown) {
      if (gen !== requestGen.current) return
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      if (gen === requestGen.current) setLoading(false)
    }
  }

  function clear() {
    requestGen.current += 1
    setText('')
    setResult(null)
    setError(null)
    setLoading(false)
  }

  const isDistress = result?.label === 'distress'
  const theme =
    result &&
    (isDistress
      ? {
          cardBg: '#fef2f2',
          cardBorder: '#fecaca',
          text: '#b91c1c',
          barFill: '#b91c1c',
          barTrack: '#fee2e2',
        }
      : {
          cardBg: '#f0fdf4',
          cardBorder: '#bbf7d0',
          text: '#15803d',
          barFill: '#15803d',
          barTrack: '#dcfce7',
        })

  const confidencePct = result ? Math.round(result.confidence * 1000) / 10 : 0

  const escalationLine =
    result &&
    (result.escalated
      ? `Escalated to transformer — reason: ${result.escalation_reason}`
      : 'Fast model only — transformer not needed')

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Distress Detector</h1>

      <div className="rounded-lg border border-slate-200 p-4 space-y-3">
        <label className="block text-sm text-slate-600" htmlFor="detect-text">
          Post text
        </label>
        <textarea
          id="detect-text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={MAX_LEN}
          rows={12}
          placeholder="Paste post content here (at least 10 characters)…"
          className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm leading-relaxed"
          style={{ minHeight: '14rem', resize: 'vertical' }}
        />
        <div className="flex items-center justify-between text-sm text-slate-500">
          <span>
            {len} / {MAX_LEN} characters · minimum {MIN_LEN} to analyze
          </span>
        </div>
        <div className="flex gap-3 items-center" style={{ flexWrap: 'wrap' }}>
          <button
            type="button"
            onClick={analyze}
            disabled={!canAnalyze}
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover_bg-slate-800 disabled_opacity-50"
          >
            Analyze
          </button>
          <button
            type="button"
            onClick={clear}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover_bg-slate-100"
          >
            Clear
          </button>
        </div>
      </div>

      {loading && (
        <div className="flex items-center gap-3 text-slate-600">
          <LoadingSpinner />
          <span>Analyzing…</span>
        </div>
      )}

      {error && (
        <div
          className="rounded-md border px-4 py-3"
          style={{ borderColor: '#fecaca', backgroundColor: '#fef2f2', color: '#991b1b' }}
        >
          {error}
        </div>
      )}

      {result && theme && (
        <div
          className="rounded-lg border p-4 space-y-6"
          style={{
            backgroundColor: theme.cardBg,
            borderColor: theme.cardBorder,
            color: theme.text,
          }}
        >
          <div className="flex items-center justify-between gap-4" style={{ flexWrap: 'wrap' }}>
            <span className="text-3xl font-semibold" style={{ color: theme.text }}>
              {isDistress ? 'DISTRESS' : 'NOT DISTRESS'}
            </span>
          </div>

          <div>
            <div className="flex items-center justify-between gap-2 text-sm font-medium">
              <span>Confidence</span>
              <span>{confidencePct}%</span>
            </div>
            <div className="mt-3">
              <div
                className="w-full rounded-md overflow-hidden border"
                style={{ height: '0.75rem', borderColor: theme.cardBorder, backgroundColor: theme.barTrack }}
              >
                <div
                  style={{
                    width: `${Math.min(100, Math.max(0, confidencePct))}%`,
                    height: '100%',
                    backgroundColor: theme.barFill,
                    transition: 'width 0.2s ease',
                  }}
                />
              </div>
            </div>
          </div>

          <p className="text-sm leading-relaxed" style={{ color: theme.text }}>
            {escalationLine}
          </p>

          <div
            className="grid gap-4"
            style={{ gridTemplateColumns: 'repeat(2, minmax(0, 1fr))' }}
          >
            <div className="rounded-lg border border-slate-200 p-4 bg-white">
              <div className="text-sm text-slate-500">Fast model score (p_fast)</div>
              <div className="text-2xl font-semibold text-slate-900 mt-1">{formatScore(result.p_fast)}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-4 bg-white">
              <div className="text-sm text-slate-500">Transformer score (p_transformer)</div>
              <div className="text-2xl font-semibold text-slate-900 mt-1">
                {formatScore(result.p_transformer)}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
