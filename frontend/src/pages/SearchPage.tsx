import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { PostsListResponse } from '../lib/api'

const DEFAULT_LIMIT = 25

export function SearchPage() {
  const [params, setParams] = useSearchParams()

  const q = params.get('q') ?? ''
  const labelParam = params.get('label') ?? ''
  const offsetParam = Number(params.get('offset') ?? '0')
  const limitParam = Number(params.get('limit') ?? String(DEFAULT_LIMIT))

  const offset = Number.isFinite(offsetParam) ? Math.max(0, offsetParam) : 0
  const limit = Number.isFinite(limitParam) ? Math.max(1, Math.min(200, limitParam)) : DEFAULT_LIMIT

  const label = labelParam === '' ? undefined : (Number(labelParam) as 0 | 1)

  const [data, setData] = useState<PostsListResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!q) {
      setData(null)
      setError(null)
      return
    }

    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .searchPosts({ q, limit, offset, label })
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
  }, [q, limit, offset, labelParam])

  const pageInfo = useMemo(() => {
    const total = data?.total ?? 0
    const start = total === 0 ? 0 : offset + 1
    const end = Math.min(offset + limit, total)
    const canPrev = offset > 0
    const canNext = offset + limit < total
    return { total, start, end, canPrev, canNext }
  }, [data, offset, limit])

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault()
    const form = new FormData(e.currentTarget)
    const nextQ = String(form.get('q') ?? '').trim()
    const nextLabel = String(form.get('label') ?? '')

    const next = new URLSearchParams()
    nextQ ? next.set('q', nextQ) : next.delete('q')
    nextLabel ? next.set('label', nextLabel) : next.delete('label')
    next.set('offset', '0')
    next.set('limit', String(limit))
    setParams(next)
  }

  function goToOffset(nextOffset: number) {
    const next = new URLSearchParams(params)
    next.set('offset', String(Math.max(0, nextOffset)))
    next.set('limit', String(limit))
    setParams(next)
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Search</h1>

      <form onSubmit={onSubmit} className="rounded-lg border border-slate-200 p-4 grid gap-4 md_grid-cols-3">
        <div className="md_col-span-2">
          <label className="block text-sm text-slate-600">Keyword</label>
          <input
            name="q"
            defaultValue={q}
            placeholder="e.g. anxious, lonely, tips"
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          />
          <div className="mt-1 text-xs text-slate-500">Searches in title + body/selftext (case-insensitive).</div>
        </div>

        <div>
          <label className="block text-sm text-slate-600">Label (optional)</label>
          <select
            name="label"
            defaultValue={labelParam}
            className="mt-1 w-full rounded-md border border-slate-300 px-3 py-2 text-sm"
          >
            <option value="">All</option>
            <option value="0">0 (control)</option>
            <option value="1">1 (distress)</option>
          </select>
        </div>

        <div className="md_col-span-3">
          <button
            type="submit"
            className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover_bg-slate-800"
          >
            Search
          </button>
        </div>
      </form>

      {loading && <div className="text-slate-600">Searching…</div>}
      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-800">{error}</div>}

      {data && (
        <div className="space-y-3">
          <div className="text-sm text-slate-500">
            Showing {pageInfo.start}-{pageInfo.end} of {pageInfo.total.toLocaleString()}
          </div>

          <div className="rounded-lg border border-slate-200 overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500 bg-slate-50">
                  <tr>
                    <th className="py-2 px-3">Post</th>
                    <th className="py-2 px-3">Subreddit</th>
                    <th className="py-2 px-3">Label</th>
                    <th className="py-2 px-3">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((p) => (
                    <tr key={p.post_id} className="border-t border-slate-100">
                      <td className="py-2 px-3">
                        <Link to={`/posts/${p.post_id}`} className="font-medium text-slate-900 hover_underline">
                          {p.title || '(no title)'}
                        </Link>
                        {p.body && <div className="text-slate-500 line-clamp-2">{p.body}</div>}
                      </td>
                      <td className="py-2 px-3">r/{p.subreddit ?? '-'}</td>
                      <td className="py-2 px-3">{p.label ?? '-'}</td>
                      <td className="py-2 px-3">{p.timestamp ?? '-'}</td>
                    </tr>
                  ))}
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
        </div>
      )}
    </div>
  )
}

