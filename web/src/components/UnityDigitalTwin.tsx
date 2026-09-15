import { useEffect, useRef, useState } from 'react'
import type { Prediction } from '../types/prediction'

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
}

export function UnityDigitalTwin({ prediction }: UnityDigitalTwinProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const unityRef = useRef<UnityInstance>(null)
  const [progress, setProgress] = useState(0)
  const [state, setState] = useState<'loading' | 'ready' | 'missing' | 'error'>('loading')
  const [viewport, setViewport] = useState({ width: 0, height: 0 })

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
      'ApplyPredictionJson',
      JSON.stringify(prediction),
    )
  }, [prediction, state])

  return (
    <section className="unity-card" aria-labelledby="unity-title">
      <div className="unity-card__header">
        <div>
          <h2 id="unity-title">3D Process Twin</h2>
          <p>Drag the lower-right corner to resize the live Unity viewport.</p>
        </div>
        <span className="unity-card__size" aria-live="polite">
          {viewport.width} × {viewport.height}
        </span>
      </div>

      <div ref={containerRef} className="unity-viewport">
        <canvas
          ref={canvasRef}
          className="unity-viewport__canvas"
          tabIndex={0}
          aria-label="Interactive Unity digital twin"
          onPointerDown={(event) => event.currentTarget.focus()}
        />

        {state !== 'ready' && (
          <div className="unity-viewport__overlay">
            {state === 'loading' && (
              <>
                <strong>Loading Unity… {Math.round(progress * 100)}%</strong>
                <div className="unity-progress" aria-hidden="true">
                  <span style={{ width: `${progress * 100}%` }} />
                </div>
              </>
            )}
            {state === 'missing' && (
              <>
                <strong>Unity WebGL build required</strong>
                <span>Generate the WebGL build to enable the interactive view.</span>
              </>
            )}
            {state === 'error' && (
              <>
                <strong>Unity could not start</strong>
                <span>Check the browser console and WebGL build files.</span>
              </>
            )}
          </div>
        )}
      </div>

      <p className="unity-controls">WASD move · Q/E height · Shift boost · Right-drag look</p>
    </section>
  )
}
