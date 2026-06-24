import { EdaCharts } from '../components/EdaCharts'

const TELEGRAM_EDA_ENDPOINTS = {
  distribution: '/stats/distress-distribution',
  overTime: '/stats/messages-over-time',
  topWordsDistress: '/stats/top-words?label=1',
  topWordsNotDistress: '/stats/top-words?label=0',
}

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-baseline justify-between gap-4 flex-wrap">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <div className="text-sm text-slate-500">Exploratory analysis of Telegram distress detection data</div>
      </div>

      <EdaCharts
        endpoints={TELEGRAM_EDA_ENDPOINTS}
        loadingLabel="Loading dashboard…"
        totalLabel="Total messages analyzed"
        volumeTitle="Messages per day"
        distressWordcloudSubtitle="Telegram · clean_text · top 50"
        notDistressWordcloudSubtitle="Telegram · clean_text · top 50"
        emptyVolumeMessage="No messages to display yet."
        emptyDistressWordcloudMessage="No distress Telegram messages with text yet."
        emptyNotDistressWordcloudMessage="No not-distress Telegram messages with text yet."
      />
    </div>
  )
}
