import { useEffect, useRef, useState } from 'react'
import type { Prediction } from '../types/prediction'
import type { PredictionConnectionState } from '../hooks/usePredictionStream'
import type { PredictionSourceMode } from '../config/predictionSource'
import { unityEnvelope } from '../services/unityEnvelope'

type UnityInstance = {
  Quit: () => Promise<void>
  SetFullscreen: (fullscreen: number) => void
  SendMessage: (gameObject: string, method: string, value: string) => void
}

type UnityConfig = {
  arguments: string[]
  dataUrl: string
  frameworkUrl: string
  codeUrl: string
  streamingAssetsUrl: string
  companyName: string
  productName: string
  productVersion: string
  matchWebGLToCanvasSize: boolean
  devicePixelRatio: number
}

type CreateUnityInstance = (
  canvas: HTMLCanvasElement,
  config: UnityConfig,
  onProgress: (progress: number) => void,
) => Promise<UnityInstance>

declare global {
  interface Window {
    createUnityInstance?: CreateUnityInstance
  }
}

const loaderUrl = '/unity/Build/unity.loader.js'
let loaderPromise: Promise<void> | undefined

function loadUnityLoader() {
  if (window.createUnityInstance) return Promise.resolve()
  if (loaderPromise) return loaderPromise

  loaderPromise = new Promise<void>((resolve, reject) => {
    const script = document.createElement('script')
    script.src = loaderUrl
    script.async = true
    script.onload = () => resolve()
    script.onerror = () => reject(new Error('Unity WebGL build not found'))
    document.body.append(script)
  })

  return loaderPromise
}

interface UnityDigitalTwinProps {
  prediction: Prediction
  receivedAt: Date
  sourceMode: PredictionSourceMode
  connectionState: PredictionConnectionState
}

export function UnityDigitalTwin({ prediction, receivedAt, sourceMode, connectionState }: UnityDigitalTwinProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const unityRef = useRef<UnityInstance>(null)
  const [progress, setProgress] = useState(0)
  const [state, setState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading')
  const [viewport, setViewport] = useState({ width: 0, height: 0 })
  const [applied, setApplied] = useState<{ trajectory: string; timestamp: number; receivedAt: number; connection: string; count: number } | null>(null)

  useEffect(() => {
    const acknowledge = (event: Event) => {
      const envelope = (event as CustomEvent).detail
      if (typeof envelope?.prediction?.trajectory_key !== 'string' || !Number.isFinite(envelope?.prediction?.timestamp_hours)
        || !Number.isFinite(envelope?.received_at_unix_ms) || typeof envelope?.connection_state !== 'string') return
      setApplied((prior) => ({ trajectory: envelope.prediction.trajectory_key, timestamp: envelope.prediction.timestamp_hours,
        receivedAt: envelope.received_at_unix_ms, connection: envelope.connection_state, count: (prior?.count ?? 0) + 1 }))
    }
    window.addEventListener('tep-unity-prediction', acknowledge)
    return () => window.removeEventListener('tep-unity-prediction', acknowledge)
  }, [])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    const observer = new ResizeObserver(([entry]) => {
      if (!entry) return
      const width = Math.round(entry.contentRect.width)
      const height = Math.round(entry.contentRect.height)
      setViewport({ width, height })

      // Unity's loader synchronizes the WebGL render buffer to this CSS size.
      // The resize event makes that synchronization immediate after a drag.
      window.dispatchEvent(new Event('resize'))
    })
    observer.observe(container)
    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return
    let cancelled = false

    async function startUnity() {
      try {
        await loadUnityLoader()
        if (cancelled || !canvas || !window.createUnityInstance) return

        const instance = await window.createUnityInstance(
          canvas,
          {
            arguments: [],
            dataUrl: '/unity/Build/unity.data',
            frameworkUrl: '/unity/Build/unity.framework.js',
            codeUrl: '/unity/Build/unity.wasm',
            streamingAssetsUrl: '/unity/StreamingAssets',
            companyName: 'TEP Digital Twin',
            productName: 'TEP Digital Twin',
            productVersion: '1.0.0',
            matchWebGLToCanvasSize: true,
            devicePixelRatio: Math.min(window.devicePixelRatio || 1, 2),
          },
          (value) => {
            if (!cancelled) setProgress(value)
          },
        )

        if (cancelled) {
          await instance.Quit()
          return
        }
        unityRef.current = instance
        setState('ready')
      } catch (error) {
        if (cancelled) return
        setState(error instanceof Error && error.message.includes('not found') ? 'missing' : 'error')
      }
    }

    void startUnity()
    return () => {
      cancelled = true
      const instance = unityRef.current
      unityRef.current = null
      if (instance) void instance.Quit()
    }
  }, [])

  useEffect(() => {
    if (state !== 'ready' || !unityRef.current) return
    unityRef.current.SendMessage(
      'DigitalTwinRuntime',
      'ApplyPredictionEnvelope',
      unityEnvelope(prediction, receivedAt, sourceMode, connectionState),
    )
  }, [prediction, receivedAt, sourceMode, connectionState, state])

  return (
    <section className="unity-card" aria-labelledby="unity-title" data-unity-state={state}
      data-unity-trajectory={applied?.trajectory} data-unity-timestamp={applied?.timestamp}
      data-unity-received-at={applied?.receivedAt} data-unity-connection={applied?.connection} data-unity-ack-count={applied?.count ?? 0}>
      <div className="unity-card__header">
        <div>
          <h2 id="unity-title">3D 공정 디지털트윈</h2>
          <p>{applied ? '실제 3D 화면의 예측 동기화가 확인됐어.' : '오른쪽 아래 모서리를 드래그하면 화면 크기를 조절할 수 있어.'}</p>
        </div>
        <span className="unity-card__size" aria-live="polite">
          {viewport.width} × {viewport.height}
        </span>
      </div>

      <div ref={containerRef} className="unity-viewport">
        <canvas
          id="unity-canvas"
          ref={canvasRef}
          className="unity-viewport__canvas"
          tabIndex={0}
          aria-label="상호작용 가능한 3D 공정 디지털트윈"
          onPointerDown={(event) => event.currentTarget.focus()}
        />

        {state !== 'ready' && (
          <div className="unity-viewport__overlay">
            {state === 'loading' && (
              <>
                <strong>3D 화면 불러오는 중… {Math.round(progress * 100)}%</strong>
                <div className="unity-progress" aria-hidden="true">
                  <span style={{ width: `${progress * 100}%` }} />
                </div>
              </>
            )}
            {state === 'missing' && (
              <>
                <strong>3D 화면 빌드가 필요해</strong>
                <span>Unity에서 웹용 빌드를 생성하면 공정 화면이 표시돼.</span>
              </>
            )}
            {state === 'error' && (
              <>
                <strong>3D 화면을 실행할 수 없어</strong>
                <span>브라우저 오류와 웹용 빌드 파일을 확인해줘.</span>
              </>
            )}
          </div>
        )}
      </div>

      <p className="unity-controls">공정 흐름과 전체 예측 상태를 함께 보여주는 3D 개요 화면</p>
    </section>
  )
}
