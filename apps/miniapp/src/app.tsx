import { useLaunch } from 'virtual:taro/api'
import Taro from 'virtual:taro/api'
import type { PropsWithChildren } from 'react'
import './app.css'

function App({ children }: PropsWithChildren) {
  useLaunch(() => {
    if (import.meta.env.TARO_APP_TRANSPORT === 'cloud') {
      void Taro.cloud.init({
        env: import.meta.env.TARO_APP_CLOUD_ENV,
      })
    }
  })

  return children
}

export default App
