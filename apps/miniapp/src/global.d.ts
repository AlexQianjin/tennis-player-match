interface ImportMetaEnv {
  readonly TARO_APP_TRANSPORT: 'http' | 'cloud'
  readonly TARO_APP_API_BASE_URL: string
  readonly TARO_APP_CLOUD_ENV: string
  readonly TARO_APP_CLOUD_SERVICE: string
  readonly TARO_APP_ENV: 'dev' | 'test' | 'prod'
  readonly VITE_VPT_WECHAT_APP_ID?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
