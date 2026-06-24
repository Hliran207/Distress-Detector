import { useEffect, useMemo, useRef } from 'react'
import type { CSSProperties } from 'react'
import cloud from 'd3-cloud'
import { select } from 'd3-selection'

export type WordCloudWord = {
  text: string
  value: number
}

type WordCloudProps = {
  words: WordCloudWord[]
  colors?: string[]
  className?: string
  style?: CSSProperties
}

type LayoutWord = WordCloudWord & {
  size?: number
  x?: number
  y?: number
  rotate?: number
}

const DEFAULT_PALETTE = ['#dc2626', '#ea580c', '#f97316', '#ef4444', '#b91c1c', '#c2410c']

export function WordCloud({ words, colors, className, style }: WordCloudProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const palette = useMemo(() => colors ?? DEFAULT_PALETTE, [colors])

  useEffect(() => {
    const container = containerRef.current
    if (!container || words.length === 0) return

    const width = container.clientWidth
    const height = container.clientHeight
    if (width === 0 || height === 0) return

    select(container).selectAll('*').remove()

    const values = words.map((word) => word.value)
    const max = Math.max(...values)
    const min = Math.min(...values)

    const fontSize = (value: number) => {
      if (max === min) return 24
      return 14 + ((value - min) / (max - min)) * 34
    }

    const svg = select(container).append('svg').attr('width', width).attr('height', height)
    const group = svg.append('g').attr('transform', `translate(${width / 2},${height / 2})`)

    const layout = cloud<LayoutWord>()
      .size([width, height])
      .words(words.map((word) => ({ ...word, size: fontSize(word.value) })))
      .padding(2)
      .rotate(() => (Math.random() > 0.5 ? -30 : 30))
      .font('ui-sans-serif, system-ui, sans-serif')
      .fontSize((word) => word.size ?? 16)
      .on('end', (placedWords: LayoutWord[]) => {
        group
          .selectAll('text')
          .data(placedWords)
          .join('text')
          .style('font-size', (word: LayoutWord) => `${word.size ?? 16}px`)
          .style('font-family', 'ui-sans-serif, system-ui, sans-serif')
          .style('fill', (_word: LayoutWord, index: number) => palette[index % palette.length])
          .attr('text-anchor', 'middle')
          .attr('transform', (word: LayoutWord) =>
            `translate(${word.x ?? 0},${word.y ?? 0})rotate(${word.rotate ?? 0})`,
          )
          .text((word: LayoutWord) => word.text)
      })

    layout.start()

    return () => {
      layout.stop()
      select(container).selectAll('*').remove()
    }
  }, [words, palette])

  return <div ref={containerRef} className={className} style={style} />
}
