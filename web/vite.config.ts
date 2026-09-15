import react from '@vitejs/plugin-react'
import { defineConfig, type Plugin } from 'vite'

function unityWebGlHeaders(): Plugin {
  const configure = (server: {
    middlewares: {
      use: (handler: (request: { url?: string }, response: { setHeader: (name: string, value: string) => void }, next: () => void) => void) => void
    }
  }) => {
    server.middlewares.use((request, response, next) => {
      const url = request.url ?? ''
      if (url.startsWith('/unity/Build/') && url.endsWith('.br')) {
        response.setHeader('Content-Encoding', 'br')
        response.setHeader(
          'Content-Type',
          url.includes('.wasm.') ? 'application/wasm' : 'application/octet-stream',
        )
      }
      next()
    })
  }

  return {
    name: 'unity-webgl-headers',
    configureServer: configure,
    configurePreviewServer: configure,
  }
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), unityWebGlHeaders()],
})
