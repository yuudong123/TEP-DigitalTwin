import { useCallback, useEffect, useState } from 'react'
import { predictionSourceConfig } from '../config/predictionSource'
import { predictionSequence } from '../mock/predictionSequence'
import { fetchLatestPrediction } from '../services/predictionApi'
import type { Prediction } from '../types/prediction'

export type PredictionConnectionState = 'mock' | 'connecting' | 'connected' | 'error' | 'paused'

export function usePredictionStream() {
  const { mode, apiUrl, pollIntervalMs, timeoutMs } = predictionSourceConfig
  const [index, setIndex] = useState(0)
  const [isPlaying, setIsPlaying] = useState(true)
  const [prediction, setPrediction] = useState<Prediction | null>(() =>
    mode === 'mock' ? predictionSequence[0] : null,
  )
  const [lastReceivedAt, setLastReceivedAt] = useState<Date | null>(() =>
    mode === 'mock' ? new Date() : null,
  )
  const [connectionState, setConnectionState] = useState<PredictionConnectionState>(
    mode === 'mock' ? 'mock' : 'connecting',
  )
  const [errorMessage, setErrorMessage] = useState<string | null>(null)
  const [retryKey, setRetryKey] = useState(0)

  const advance = useCallback(() => {
    setIndex((current) => {
      const next = (current + 1) % predictionSequence.length
      setPrediction(predictionSequence[next])
      return next
    })
    setLastReceivedAt(new Date())
  }, [])

  useEffect(() => {
    if (mode !== 'mock' || !isPlaying) return
    const timer = window.setInterval(advance, pollIntervalMs)
    return () => window.clearInterval(timer)
  }, [advance, isPlaying, mode, pollIntervalMs])

  useEffect(() => {
    if (mode !== 'api') return
    if (!isPlaying) return

    const controller = new AbortController()
    let requestInFlight = false

    const refresh = async () => {
      if (requestInFlight) return
      requestInFlight = true
      try {
        const next = await fetchLatestPrediction(apiUrl, timeoutMs, controller.signal)
        if (controller.signal.aborted) return
        setPrediction(next)
        setLastReceivedAt(new Date())
        setConnectionState('connected')
        setErrorMessage(null)
      } catch (error) {
        if (controller.signal.aborted) return
        setConnectionState('error')
        setErrorMessage(error instanceof Error ? error.message : 'API 연결에 실패했습니다.')
      } finally {
        requestInFlight = false
      }
    }

    void refresh()
    const timer = window.setInterval(() => void refresh(), pollIntervalMs)
    return () => {
      controller.abort()
      window.clearInterval(timer)
    }
  }, [apiUrl, isPlaying, mode, pollIntervalMs, retryKey, timeoutMs])

  const toggle = useCallback(() => setIsPlaying((playing) => !playing), [])
  const restart = useCallback(() => {
    if (mode === 'mock') {
      setIndex(0)
      setPrediction(predictionSequence[0])
      setLastReceivedAt(new Date())
      setConnectionState('mock')
    } else {
      setConnectionState('connecting')
      setErrorMessage(null)
      setRetryKey((key) => key + 1)
    }
    setIsPlaying(true)
  }, [mode])

  return {
    prediction,
    mode,
    connectionState: isPlaying ? connectionState : 'paused',
    errorMessage,
    currentIndex: index,
    totalSnapshots: mode === 'mock' ? predictionSequence.length : null,
    isPlaying,
    lastReceivedAt,
    toggle,
    restart,
  }
}
