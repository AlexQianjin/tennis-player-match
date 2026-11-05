import { useLaunch } from 'virtual:taro/api'
import Taro from 'virtual:taro/api'
import type { PropsWithChildren } from 'react'
import { flushPendingRatings } from './services/offline-queue.ts'
import { openOnboarding } from './services/onboarding.ts'
import { useAuthStore } from './stores/auth.ts'
import './app.css'

function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    void (async () => {
      if (import.meta.env.TARO_APP_TRANSPORT === 'cloud') {
        try {
          await Taro.cloud.init({
            env: import.meta.env.TARO_APP_CLOUD_ENV,
          })
        } catch {
          // The first callContainer reports init failures.
        }
      }
      await useAuthStore.getState().bootstrap()
      openOnboarding()
      await flushPendingRatings()
    })()
  })

  return children
}

export default App
