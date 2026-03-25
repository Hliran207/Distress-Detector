import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { RedditPost } from '../lib/api'

export function PostDetailsPage() {
  const { postId } = useParams()
  const [data, setData] = useState<RedditPost | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!postId) return
    let cancelled = false
    setLoading(true)
    setError(null)
    api
      .getPost(postId)
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
  }, [postId])

  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold">Post details</h1>
        <Link to="/posts" className="text-sm text-slate-700 hover_underline">
          Back to posts
        </Link>
      </div>

      {loading && <div className="text-slate-600">Loading…</div>}
      {error && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-800">{error}</div>}

      {data && (
        <section className="rounded-lg border border-slate-200 p-4 space-y-3">
          <div>
            <div className="text-sm text-slate-500">Title</div>
            <div className="text-lg font-semibold">{data.title || '(no title)'}</div>
          </div>

          <div className="grid grid-cols-1 md_grid-cols-4 gap-3 text-sm">
            <div>
              <div className="text-slate-500">Post ID</div>
              <div className="font-mono break-all">{data.post_id}</div>
            </div>
            <div>
              <div className="text-slate-500">Subreddit</div>
              <div>r/{data.subreddit ?? '-'}</div>
            </div>
            <div>
              <div className="text-slate-500">Label</div>
              <div>{data.label ?? '-'}</div>
            </div>
            <div>
              <div className="text-slate-500">Timestamp</div>
              <div>{data.timestamp ?? '-'}</div>
            </div>
          </div>

          <div>
            <div className="text-sm text-slate-500">Body</div>
            <pre className="mt-1 whitespace-pre-wrap break-words rounded-md bg-slate-50 border border-slate-200 p-3 text-sm leading-relaxed">
              {data.body || '(no body)'}
            </pre>
          </div>
        </section>
      )}
    </div>
  )
}

