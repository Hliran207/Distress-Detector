declare module 'd3-cloud' {
  export interface CloudWord {
    text?: string
    size?: number
    x?: number
    y?: number
    rotate?: number
    value?: number
    font?: string
    style?: string
    weight?: string
    padding?: number
  }

  export interface Cloud<
    T extends CloudWord = CloudWord,
  > {
    size(size: [number, number]): this
    words(words: T[]): this
    padding(padding: number): this
    rotate(rotate: number | ((word: T, index: number) => number)): this
    font(font: string | ((word: T, index: number) => string)): this
    fontSize(fontSize: number | ((word: T, index: number) => number)): this
    on(
      type: 'end',
      listener: (words: T[], bounds?: [{ x: number; y: number }, { x: number; y: number }]) => void,
    ): this
    start(): this
    stop(): this
  }

  export default function cloud<T extends CloudWord = CloudWord>(): Cloud<T>
}
