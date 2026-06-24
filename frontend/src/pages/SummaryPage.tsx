import { EdaCharts } from '../components/EdaCharts'

const POSTS_EDA_ENDPOINTS = {
  distribution: '/stats/posts/distress-distribution',
  overTime: '/stats/posts/messages-over-time',
  topWordsDistress: '/stats/posts/top-words?label=1',
  topWordsNotDistress: '/stats/posts/top-words?label=0',
  subreddits: '/stats/posts/top-subreddits',
}

export function SummaryPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-semibold">Summary</h1>
        <div className="text-sm text-slate-500">Exploratory analysis of Reddit database posts</div>
      </div>

      <EdaCharts
        endpoints={POSTS_EDA_ENDPOINTS}
        loadingLabel="Loading summary…"
        totalLabel="Total posts in database"
        secondaryChart="subreddits"
        subredditsTitle="Top subreddits"
        subredditsSubtitle="Top 10 by post count"
        distressWordcloudSubtitle="Reddit · post body · top 50"
        notDistressWordcloudSubtitle="Reddit · post body · top 50"
        emptySubredditsMessage="No subreddit data yet."
        emptyDistressWordcloudMessage="No distress Reddit posts with body text yet."
        emptyNotDistressWordcloudMessage="No not-distress Reddit posts with body text yet."
        showEscalatedCard={false}
        showTrendChart={false}
        thirdStatCard="not_distress"
      />
    </div>
  )
}
