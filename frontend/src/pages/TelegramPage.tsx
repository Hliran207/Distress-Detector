import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { PostsListResponse, RedditPost, TelegramScanResponse } from '../lib/api'

const DEFAULT_LIMIT = 25
const ALERT_THRESHOLD = 0.7
const CHAT_ID_STORAGE_KEY = 'telegram.lastChatId'

function clamp(n: number, min: number, max: number) {
  return Math.max(min, Math.min(max, n))
}

/** Israel local time: DD/MM/YYYY-style date + 24h time (Asia/Jerusalem). */
const TELEGRAM_ALERTS_DATETIME = new Intl.DateTimeFormat('he-IL', {
  timeZone: 'Asia/Jerusalem',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
})

function formatDate(post: RedditPost): string {
  let d: Date | null = null
  if (post.timestamp) {
    const parsed = Date.parse(post.timestamp)
    if (!Number.isNaN(parsed)) d = new Date(parsed)
  }
  if (!d && typeof post.created_utc === 'number') {
    d = new Date(post.created_utc * 1000)
  }
  if (!d || Number.isNaN(d.getTime())) return '-'
  return TELEGRAM_ALERTS_DATETIME.format(d)
}

function formatScore(score: number | null | undefined): string {
  if (score === null || score === undefined) return '-'
  return `${Math.round(score * 1000) / 10}%`
}

function formatSender(post: RedditPost): string {
  const s = post.sender_info
  if (!s) return '—'
  if (s.username) return `@${s.username}`
  if (s.first_name) return s.first_name
  if (s.sender_id != null) return `User ${s.sender_id}`
  return '—'
}

export function TelegramPage() {
  const [params, setParams] = useSearchParams()

  const chatIdParam = params.get('chat_id') ?? ''
  const minScoreParam = params.get('min_score') ?? ''
  const offsetParam = Number(params.get('offset') ?? '0')
  const limitParam = Number(params.get('limit') ?? String(DEFAULT_LIMIT))

  const offset = Number.isFinite(offsetParam) ? Math.max(0, offsetParam) : 0
  const limit = Number.isFinite(limitParam) ? clamp(limitParam, 1, 200) : DEFAULT_LIMIT

  const chatId = chatIdParam === '' ? undefined : chatIdParam
  const minScore = minScoreParam === '' ? undefined : Number(minScoreParam)

  const [data, setData] = useState<PostsListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const [scanChatId, setScanChatId] = useState<string>(() => {
    if (chatIdParam) return chatIdParam
    const cached = typeof window !== 'undefined' ? window.localStorage.getItem(CHAT_ID_STORAGE_KEY) : null
    return cached ?? ''
  })
  const [scanLimit, setScanLimit] = useState<number>(50)
  const [scanning, setScanning] = useState(false)
  const [scanError, setScanError] = useState<string | null>(null)
  const [scanResult, setScanResult] = useState<TelegramScanResponse | null>(null)
  const [refreshKey, setRefreshKey] = useState(0)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .listTelegramMessages({ limit, offset, chat_id: chatId, min_score: minScore })
      .then((d) => {
        if (!cancelled) setData(d)
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(e instanceof Error ? e.message : String(e))
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [limit, offset, chatIdParam, minScoreParam, refreshKey])

  const pageInfo = useMemo(() => {
    const total = data?.total ?? 0
    const start = total === 0 ? 0 : offset + 1
    const end = Math.min(offset + limit, total)
    const canPrev = offset > 0
    const canNext = offset + limit < total
    return { total, start, end, canPrev, canNext }
  }, [data, offset, limit])

  function updateFilters(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const nextChatId = String(form.get('chat_id') ?? '').trim()
    const nextMinScore = String(form.get('min_score') ?? '').trim()

    const next = new URLSearchParams(params)
    next.set('limit', String(limit))
    next.set('offset', '0')
    nextChatId ? next.set('chat_id', nextChatId) : next.delete('chat_id')
    nextMinScore ? next.set('min_score', nextMinScore) : next.delete('min_score')
    setParams(next)
  }

  function goToOffset(nextOffset: number) {
    const next = new URLSearchParams(params)
    next.set('offset', String(Math.max(0, nextOffset)))
    next.set('limit', String(limit))
    setParams(next)
  }

  async function runScan(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    setScanError(null)
    setScanResult(null)

    const parsed = Number(scanChatId.trim())
    if (!Number.isFinite(parsed) || scanChatId.trim() === '') {
      setScanError('chat_id must be a valid number (negative for groups).')
      return
    }

    setScanning(true)
    try {
      const result = await api.scanTelegram({ chat_id: parsed, limit: scanLimit })
      setScanResult(result)
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(CHAT_ID_STORAGE_KEY, scanChatId.trim())
      }
      setRefreshKey((k) => k + 1)
    } catch (e) {
      setScanError(e instanceof Error ? e.message : String(e))
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold">Telegram Alerts</h1>
        {data && (
          <div className="text-sm text-slate-500">
            Showing {pageInfo.start}-{pageInfo.end} of {pageInfo.total.toLocaleString()}
          </div>
        )}
      </div>

      <form onSubmit={runScan} className="rounded-lg border border-slate-200 p-4 grid gap-4 md_grid-cols-3">
        <div>
          <label className="block text-sm text-slate-600">Chat ID to scan</label>
          <input
            value={scanChatId}
            onChange={(e) => setScanChatId(e.target.value)}
            placeholder="e.g. -1001234567890"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
          />
          <div className="mt-1 text-xs text-slate-500">
            Group/supergroup ids are negative. Saved locally for next visit.
          </div>
        </div>

        <div>
          <label className="block text-sm text-slate-600">Limit (messages)</label>
          <input
            type="number"
            min={1}
            max={500}
            value={scanLimit}
            onChange={(e) => setScanLimit(clamp(Number(e.target.value) || 1, 1, 500))}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex items-end">
          <button
            type="submit"
            disabled={scanning}
            className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover_bg-slate-800 disabled_opacity-50"
          >
            {scanning ? 'Scanning…' : 'Scan Now'}
          </button>
        </div>

        {scanError && (
          <div className="md_col-span-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-800 text-sm">
            {scanError}
          </div>
        )}

        {scanResult && (
          <div className="md_col-span-3 text-sm text-slate-600">
            Fetched {scanResult.fetched} · processed {scanResult.processed} · inserted{' '}
            <span className="font-semibold text-slate-900">{scanResult.inserted}</span> · duplicates{' '}
            {scanResult.skipped_duplicates} · empty {scanResult.skipped_empty}
          </div>
        )}
      </form>

      <form onSubmit={updateFilters} className="rounded-lg border border-slate-200 p-4 grid gap-4 md_grid-cols-3">
        <div>
          <label className="block text-sm text-slate-600">Filter by chat ID</label>
          <input
            name="chat_id"
            defaultValue={chatIdParam}
            placeholder="(any)"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm font-mono"
          />
        </div>

        <div>
          <label className="block text-sm text-slate-600">Min distress score (0–1)</label>
          <input
            name="min_score"
            type="number"
            min={0}
            max={1}
            step={0.05}
            defaultValue={minScoreParam}
            placeholder="(any)"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
        </div>

        <div className="flex items-end">
          <button
            type="submit"
            className="w-full rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover_bg-slate-800"
          >
            Apply filters
          </button>
        </div>
      </form>

      {loading && <div className="text-slate-600">Loading…</div>}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-800">{error}</div>
      )}

      {data && (
        <div className="rounded-lg border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-slate-500 bg-slate-50">
                <tr>
                  <th className="py-2 px-3">Date</th>
                  <th className="py-2 px-3">Chat ID</th>
                  <th className="py-2 px-3">Sender</th>
                  <th className="py-2 px-3">Message</th>
                  <th className="py-2 px-3">Score</th>
                  <th className="py-2 px-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 && (
                  <tr>
                    <td colSpan={6} className="py-6 px-3 text-center text-slate-500">
                      No Telegram messages stored yet. Use Scan Now above to pull recent updates.
                    </td>
                  </tr>
                )}
                {data.items.map((p) => {
                  const score = p.distress_score ?? null
                  const isAlert = score !== null && score >= ALERT_THRESHOLD
                  return (
                    <tr
                      key={p.post_id}
                      className={`border-t border-slate-100 ${isAlert ? 'alert-row' : ''}`}
                    >
                      <td className="py-2 px-3 whitespace-pre-wrap">{formatDate(p)}</td>
                      <td className="py-2 px-3 font-mono break-all">{p.subreddit ?? '-'}</td>
                      <td className="py-2 px-3 break-words">{formatSender(p)}</td>
                      <td className="py-2 px-3">
                        <div className={`line-clamp-2 ${isAlert ? 'text-red-800' : 'text-slate-900'}`}>
                          {p.body || '(no text)'}
                        </div>
                      </td>
                      <td className="py-2 px-3">
                        <span className={isAlert ? 'font-semibold text-red-700' : 'text-slate-700'}>
                          {formatScore(score)}
                        </span>
                      </td>
                      <td className="py-2 px-3">
                        <span className={`badge ${isAlert ? 'badge-alert' : 'badge-ok'}`}>
                          {isAlert ? 'Alert' : 'OK'}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between p-3 bg-white">
            <button
              className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled_opacity-50"
              disabled={!pageInfo.canPrev}
              onClick={() => goToOffset(offset - limit)}
              type="button"
            >
              Previous
            </button>
            <button
              className="rounded-md border border-slate-300 px-3 py-2 text-sm disabled_opacity-50"
              disabled={!pageInfo.canNext}
              onClick={() => goToOffset(offset + limit)}
              type="button"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
