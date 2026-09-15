import { useCallback, useEffect, useState } from 'react'
import { predictionSequence } from '../mock/predictionSequence'

const DEFAULT_INTERVAL_MS = 2_000

export function usePredictionStream(intervalMs = DEFAULT_INTERVAL_MS) {
  const [index, setIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(true)
  const [lastReceivedAt, setLastReceivedAt] = useState(() => new Date())

  const advance = useCallback(() => {
    setIndex((current) => (current + 1) % predictionSequence.length)
    setLastReceivedAt(new Date())
  }, [])

  useEffect(() => {
    if (!isPlaying) return
    const timer = window.setInterval(advance, intervalMs)
    return () => window.clearInterval(timer)
  }, [advance, intervalMs, isPlaying])

  const toggle = useCallback(() => setIsPlaying((playing) => !playing), [])
  const restart = useCallback(() => {
    setIndex(0)
    setLastReceivedAt(new Date())
    setIsPlaying(true)
  }, [])

  return {
    prediction: predictionSequence[index],
    currentIndex: index,
    totalSnapshots: predictionSequence.length,
    isPlaying,
    lastReceivedAt,
    toggle,
    restart,
  }
}
