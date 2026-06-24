import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { WordCloud } from './WordCloud'

const API_BASE_URL =
  (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? 'http://localhost:8000'

export type DistressDistribution = {
  distress: number
  not_distress: number
  average_distress_score: number
  escalated_count: number
}

export type MessagesOverTimeItem = {
  date: string
  total: number
  distress: number
  avg_score: number
}

export type TopWordItem = {
  text: string
  value: number
}

export type SubredditCountItem = {
  subreddit: string
  total: number
  distress: number
}

export type EdaEndpoints = {
  distribution: string
  overTime: string
  topWordsDistress: string
  topWordsNotDistress: string
  subreddits?: string
}

export type EdaChartsProps = {
  endpoints: EdaEndpoints
  loadingLabel?: string
  totalLabel?: string
  secondaryChart?: 'volume' | 'subreddits'
  volumeTitle?: string
  volumeSubtitle?: string
  subredditsTitle?: string
  subredditsSubtitle?: string
  distressWordcloudSubtitle?: string
  notDistressWordcloudSubtitle?: string
  emptyVolumeMessage?: string
  emptySubredditsMessage?: string
  emptyDistressWordcloudMessage?: string
  emptyNotDistressWordcloudMessage?: string
  showEscalatedCard?: boolean
  showTrendChart?: boolean
  thirdStatCard?: 'average' | 'not_distress'
}

function buildUrl(path: string) {
  return new URL(path, API_BASE_URL).toString()
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(buildUrl(path))
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Request failed ${res.status}: ${text || res.statusText}`)
  }
  return (await res.json()) as T
}

function formatPercent(score: number): string {
  return `${Math.round(score * 1000) / 10}%`
}

function formatShortDate(dateStr: string): string {
  const [, month, day] = dateStr.split('-')
  return `${month}/${day}`
}

function LoadingSpinner({ label }: { label: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-12 text-slate-600">
      <span
        className="inline-block rounded-full border-2 border-slate-200 border-t-slate-600"
        style={{ width: 20, height: 20, animation: 'eda-spin 0.8s linear infinite' }}
        aria-hidden
      />
      <span>{label}</span>
      <style>{`@keyframes eda-spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  )
}

const PIE_COLORS = {
  distress: '#dc2626',
  safe: '#16a34a',
}

const WORDCLOUD_COLORS_DISTRESS = ['#dc2626', '#ea580c', '#f97316', '#ef4444', '#b91c1c', '#c2410c']
const WORDCLOUD_COLORS_SAFE = ['#16a34a', '#22c55e', '#15803d', '#4ade80', '#166534', '#86efac']

function WordCloudPanel({
  title,
  subtitle,
  words,
  colors,
  emptyMessage,
}: {
  title: string
  subtitle: string
  words: { text: string; value: number }[]
  colors: string[]
  emptyMessage: string
}) {
  return (
    <div className="md_col-span-2 rounded-lg border border-slate-200 p-4">
      <div className="flex items-baseline justify-between">
        <h2 className="text-lg font-semibold">{title}</h2>
        <div className="text-sm text-slate-500">{subtitle}</div>
      </div>
      <div
        className="mt-3 rounded-md border border-slate-100 bg-slate-50"
        style={{ width: '100%', height: 320 }}
      >
        {words.length === 0 ? (
          <div className="flex items-center justify-center h-full text-slate-500 text-sm">
            {emptyMessage}
          </div>
        ) : (
          <WordCloud words={words} colors={colors} style={{ width: '100%', height: '100%' }} />
        )}
      </div>
    </div>
  )
}

export function EdaCharts({
  endpoints,
  loadingLabel = 'Loading charts…',
  totalLabel = 'Total records analyzed',
  secondaryChart = 'volume',
  volumeTitle = 'Records per day',
  volumeSubtitle = 'Last 30 days',
  subredditsTitle = 'Top subreddits',
  subredditsSubtitle = 'Top 10 by post count',
  distressWordcloudSubtitle = 'Top 50 words',
  notDistressWordcloudSubtitle = 'Top 50 words',
  emptyVolumeMessage = 'No records to display yet.',
  emptySubredditsMessage = 'No subreddit data yet.',
  emptyDistressWordcloudMessage = 'No distress records with text yet.',
  emptyNotDistressWordcloudMessage = 'No not-distress records with text yet.',
  showEscalatedCard = true,
  showTrendChart = true,
  thirdStatCard = 'average',
}: EdaChartsProps) {
  const [distribution, setDistribution] = useState<DistressDistribution | null>(null)
  const [overTime, setOverTime] = useState<MessagesOverTimeItem[] | null>(null)
  const [topWordsDistress, setTopWordsDistress] = useState<TopWordItem[] | null>(null)
  const [topWordsNotDistress, setTopWordsNotDistress] = useState<TopWordItem[] | null>(null)
  const [subreddits, setSubreddits] = useState<SubredditCountItem[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      setError(null)
      try {
        const needTimeline = showTrendChart || secondaryChart === 'volume'
        const [dist, distressWords, notDistressWords, timeline, subs] = await Promise.all([
          fetchJson<DistressDistribution>(endpoints.distribution),
          fetchJson<TopWordItem[]>(endpoints.topWordsDistress),
          fetchJson<TopWordItem[]>(endpoints.topWordsNotDistress),
          needTimeline
            ? fetchJson<MessagesOverTimeItem[]>(endpoints.overTime)
            : Promise.resolve([] as MessagesOverTimeItem[]),
          secondaryChart === 'subreddits' && endpoints.subreddits
            ? fetchJson<SubredditCountItem[]>(endpoints.subreddits)
            : Promise.resolve([] as SubredditCountItem[]),
        ])
        if (cancelled) return
        setDistribution(dist)
        setTopWordsDistress(distressWords)
        setTopWordsNotDistress(notDistressWords)
        setOverTime(timeline)
        setSubreddits(subs)
      } catch (e: unknown) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : String(e))
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()
    return () => {
      cancelled = true
    }
  }, [
    endpoints.distribution,
    endpoints.overTime,
    endpoints.topWordsDistress,
    endpoints.topWordsNotDistress,
    endpoints.subreddits,
    secondaryChart,
    showTrendChart,
  ])

  const pieData = useMemo(() => {
    if (!distribution) return []
    return [
      { name: 'Distress', value: distribution.distress },
      { name: 'Not distress', value: distribution.not_distress },
    ]
  }, [distribution])

  const barData = useMemo(() => {
    if (!overTime) return []
    return overTime.map((row) => ({
      ...row,
      label: formatShortDate(row.date),
    }))
  }, [overTime])

  const subredditBarData = useMemo(() => {
    if (!subreddits) return []
    return subreddits.map((row) => ({
      ...row,
      label: `r/${row.subreddit}`,
    }))
  }, [subreddits])

  const lineData = useMemo(() => {
    if (!overTime) return []
    return overTime.map((row) => ({
      date: row.date,
      label: formatShortDate(row.date),
      avg_score: row.avg_score,
    }))
  }, [overTime])

  const distressWordcloudWords = useMemo(
    () => (topWordsDistress ?? []).map((w) => ({ text: w.text, value: w.value })),
    [topWordsDistress],
  )

  const notDistressWordcloudWords = useMemo(
    () => (topWordsNotDistress ?? []).map((w) => ({ text: w.text, value: w.value })),
    [topWordsNotDistress],
  )

  const totalRecords = distribution ? distribution.distress + distribution.not_distress : 0

  if (loading) {
    return <LoadingSpinner label={loadingLabel} />
  }

  if (error) {
    return (
      <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-red-800">{error}</div>
    )
  }

  if (!distribution || !topWordsDistress || !topWordsNotDistress || overTime === null || subreddits === null) {
    return null
  }

  return (
    <>
      <section
        className={`grid grid-cols-1 gap-4 ${showEscalatedCard ? 'md_grid-cols-4' : 'md_grid-cols-3'}`}
      >
        <div className="rounded-lg border border-slate-200 p-4">
          <div className="text-sm text-slate-500">{totalLabel}</div>
          <div className="text-3xl font-semibold">{totalRecords.toLocaleString()}</div>
        </div>
        <div className="rounded-lg border border-slate-200 p-4">
          <div className="text-sm text-slate-500">Total distress detected</div>
          <div className="text-3xl font-semibold text-red-700">
            {distribution.distress.toLocaleString()}
          </div>
        </div>
        <div className="rounded-lg border border-slate-200 p-4">
          {thirdStatCard === 'not_distress' ? (
            <>
              <div className="text-sm text-slate-500">Total not distress</div>
              <div className="text-3xl font-semibold" style={{ color: PIE_COLORS.safe }}>
                {distribution.not_distress.toLocaleString()}
              </div>
            </>
          ) : (
            <>
              <div className="text-sm text-slate-500">Average distress score</div>
              <div className="text-3xl font-semibold">
                {formatPercent(distribution.average_distress_score)}
              </div>
            </>
          )}
        </div>
        {showEscalatedCard && (
          <div className="rounded-lg border border-slate-200 p-4">
            <div className="text-sm text-slate-500">Escalated to transformer</div>
            <div className="text-3xl font-semibold">
              {distribution.escalated_count.toLocaleString()}
            </div>
          </div>
        )}
      </section>

      <section className="grid grid-cols-1 md_grid-cols-4 gap-4">
        <div className="md_col-span-2 rounded-lg border border-slate-200 p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">Distress distribution</h2>
            <div className="text-sm text-slate-500">All records</div>
          </div>
          <div style={{ width: '100%', height: 300, marginTop: 12 }}>
            {pieData.every((d) => d.value === 0) ? (
              <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                {emptyVolumeMessage}
              </div>
            ) : (
              <ResponsiveContainer>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    outerRadius={100}
                    label={(entry) => {
                      const pct = typeof entry.percent === 'number' ? entry.percent : 0
                      return `${entry.name}: ${(pct * 100).toFixed(0)}%`
                    }}
                  >
                    <Cell fill={PIE_COLORS.distress} />
                    <Cell fill={PIE_COLORS.safe} />
                  </Pie>
                  <Tooltip />
                  <Legend />
                </PieChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="md_col-span-2 rounded-lg border border-slate-200 p-4">
          <div className="flex items-baseline justify-between">
            <h2 className="text-lg font-semibold">
              {secondaryChart === 'subreddits' ? subredditsTitle : volumeTitle}
            </h2>
            <div className="text-sm text-slate-500">
              {secondaryChart === 'subreddits' ? subredditsSubtitle : volumeSubtitle}
            </div>
          </div>
          <div style={{ width: '100%', height: 300, marginTop: 12 }}>
            {secondaryChart === 'subreddits' ? (
              subredditBarData.length === 0 ? (
                <div className="flex items-center justify-center h-full text-slate-500 text-sm">
                  {emptySubredditsMessage}
                </div>
              ) : (
                <ResponsiveContainer>
                  <BarChart
                    layout="vertical"
                    data={subredditBarData}
                    margin={{ top: 8, right: 8, left: 8, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                    <XAxis type="number" tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                    <YAxis
                      type="category"
                      dataKey="label"
                      width={110}
                      tick={{ fontSize: 11, fill: '#64748b' }}
                    />
                    <Tooltip />
                    <Legend />
                    <Bar dataKey="total" name="Total" fill="#64748b" radius={[0, 4, 4, 0]} />
                    <Bar dataKey="distress" name="Distress" fill={PIE_COLORS.distress} radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              )
            ) : (
              <ResponsiveContainer>
                <BarChart data={barData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                  <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} interval="preserveStartEnd" />
                  <YAxis tick={{ fontSize: 11, fill: '#64748b' }} allowDecimals={false} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="total" name="Total" fill="#64748b" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="distress" name="Distress" fill={PIE_COLORS.distress} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </section>

      {showTrendChart && (
      <section className="rounded-lg border border-slate-200 p-4">
        <div className="flex items-baseline justify-between">
          <h2 className="text-lg font-semibold">Distress score trend</h2>
          <div className="text-sm text-slate-500">Daily average · last 30 days</div>
        </div>
        <div style={{ width: '100%', height: 300, marginTop: 12 }}>
          <ResponsiveContainer>
            <LineChart data={lineData} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis dataKey="label" tick={{ fontSize: 11, fill: '#64748b' }} interval="preserveStartEnd" />
              <YAxis
                tick={{ fontSize: 11, fill: '#64748b' }}
                domain={[0, 1]}
                tickFormatter={(v: number) => `${Math.round(v * 100)}%`}
              />
              <Tooltip
                formatter={(value) => [
                  formatPercent(typeof value === 'number' ? value : 0),
                  'Avg score',
                ]}
              />
              <Legend />
              <Line
                type="monotone"
                dataKey="avg_score"
                name="Avg distress score"
                stroke={PIE_COLORS.distress}
                strokeWidth={2}
                dot={{ r: 2, fill: PIE_COLORS.distress }}
                activeDot={{ r: 4 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>
      )}

      <section className="grid grid-cols-1 md_grid-cols-4 gap-4">
        <WordCloudPanel
          title="Top words in distress posts"
          subtitle={distressWordcloudSubtitle}
          words={distressWordcloudWords}
          colors={WORDCLOUD_COLORS_DISTRESS}
          emptyMessage={emptyDistressWordcloudMessage}
        />
        <WordCloudPanel
          title="Top words in not distress posts"
          subtitle={notDistressWordcloudSubtitle}
          words={notDistressWordcloudWords}
          colors={WORDCLOUD_COLORS_SAFE}
          emptyMessage={emptyNotDistressWordcloudMessage}
        />
      </section>
    </>
  )
}
