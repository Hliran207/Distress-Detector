export type RedditPost = {
  post_id: string
  title?: string | null
  body?: string | null
  subreddit?: string | null
  label?: 0 | 1 | null
  created_utc?: number | null
  timestamp?: string | null
}

export type PostsListResponse = {
  total: number
  items: RedditPost[]
}

export type StatsResponse = {
  total_records: number
  counts_by_label: Record<string, number>
  posts_per_subreddit: Record<string, number>
}

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

function buildUrl(path: string, params?: Record<string, string | number | boolean | undefined | null>) {
  const url = new URL(path, API_BASE_URL)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null || v === '') continue
      url.searchParams.set(k, String(v))
    }
  }
  return url.toString()
}

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed ${res.status}: ${text || res.statusText}`)
  }
  return (await res.json()) as T
}

export const api = {
  async getSummary(): Promise<StatsResponse> {
    return fetchJson<StatsResponse>(buildUrl('/stats/summary'))
  },

  async listPosts(args: { limit: number; offset: number; label?: 0 | 1; subreddit?: string }): Promise<PostsListResponse> {
    return fetchJson<PostsListResponse>(
      buildUrl('/posts', {
        limit: args.limit,
        offset: args.offset,
        label: args.label,
        subreddit: args.subreddit,
      }),
    )
  },

  async searchPosts(args: { q: string; limit: number; offset: number; label?: 0 | 1 }): Promise<PostsListResponse> {
    return fetchJson<PostsListResponse>(
      buildUrl('/posts/search', {
        q: args.q,
        limit: args.limit,
        offset: args.offset,
        label: args.label,
      }),
    )
  },

  async getPost(postId: string): Promise<RedditPost> {
    return fetchJson<RedditPost>(buildUrl(`/posts/${encodeURIComponent(postId)}`))
  },
}

