import { useEffect, useMemo, useState } from 'react'
import { api } from '../lib/api'
import type { StatsResponse } from '../lib/api'

export function SummaryPage() {
  const [data, setData] = useState<StatsResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    api
      .getSummary()
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
  }, [])

  const topSubreddits = useMemo(() => {
    if (!data) return []
    return Object.entries(data.posts_per_subreddit)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
  }, [data])

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold">Summary</h1>

      {loading && <div className="text-slate-600">Loading…</div>}
      {error && (
        <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-800">
          {error}
        </div>
      )}

      {data && (
        <>
          <section className="grid grid-cols-1 md_grid-cols-3 gap-4">
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="text-sm text-slate-500">Total records</div>
              <div className="text-3xl font-semibold">{data.total_records.toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="text-sm text-slate-500">Label 0 (control)</div>
              <div className="text-3xl font-semibold">{(data.counts_by_label['0'] ?? 0).toLocaleString()}</div>
            </div>
            <div className="rounded-lg border border-slate-200 p-4">
              <div className="text-sm text-slate-500">Label 1 (distress)</div>
              <div className="text-3xl font-semibold">{(data.counts_by_label['1'] ?? 0).toLocaleString()}</div>
            </div>
          </section>

          <section className="rounded-lg border border-slate-200 p-4">
            <div className="flex items-baseline justify-between">
              <h2 className="text-lg font-semibold">Top subreddits</h2>
              <div className="text-sm text-slate-500">Top 10 by count</div>
            </div>
            <div className="mt-3 overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr>
                    <th className="py-2 pr-4">Subreddit</th>
                    <th className="py-2">Count</th>
                  </tr>
                </thead>
                <tbody>
                  {topSubreddits.map(([subreddit, count]) => (
                    <tr key={subreddit} className="border-t border-slate-100">
                      <td className="py-2 pr-4">r/{subreddit}</td>
                      <td className="py-2">{count.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}
    </div>
  )
}

