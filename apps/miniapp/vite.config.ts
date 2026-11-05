import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig, loadEnv } from 'vite'
import vpt from 'vite-plugin-taro'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

const pages = [
  { path: 'pages/index/index', title: '首页' },
  { path: 'pages/publish/index', title: '发布' },
  { path: 'pages/my-matches/index', title: '我的约球' },
  { path: 'pages/me/index', title: '个人中心' },
  { path: 'subpackages/match/detail/index', title: '约球详情' },
  { path: 'subpackages/match/applications/index', title: '申请列表' },
  { path: 'subpackages/match/rate/index', title: '评分' },
  { path: 'subpackages/user/profile-edit/index', title: '编辑资料' },
  { path: 'subpackages/user/my-list/index', title: '我的列表' },
  { path: 'subpackages/user/settings/index', title: '设置' },
] as const

const tabs = [
  { path: 'pages/index/index', text: '首页', icon: 'home' },
  { path: 'pages/publish/index', text: '发布', icon: 'publish' },
  { path: 'pages/my-matches/index', text: '我的约球', icon: 'matches' },
  { path: 'pages/me/index', text: '个人中心', icon: 'me' },
] as const

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, projectRoot, ['VITE_', 'TARO_APP_'])
  const appId = env.VITE_VPT_WECHAT_APP_ID || 'touristappid'

  return {
    envPrefix: ['VITE_', 'TARO_APP_'],
    resolve: {
      alias: {
        '@': path.resolve(projectRoot, 'src'),
      },
    },
    build: {
      outDir: path.resolve(projectRoot, 'dist/wx'),
    },
    plugins: [
      vpt({
        target: 'wx',
        renderer: 'template',
        app: 'src/app.tsx',
        pages: pages.map((page) => ({
          path: page.path,
          config: {
            navigationBarTitleText: page.title,
            navigationBarBackgroundColor: '#166534',
            navigationBarTextStyle: 'white',
          },
        })),
        appJson: {
          lazyCodeLoading: 'requiredComponents',
          window: {
            navigationBarTitleText: '网球约球',
            navigationBarBackgroundColor: '#166534',
            navigationBarTextStyle: 'white',
            backgroundColor: '#f8fafc',
          },
          tabBar: {
            color: '#64748b',
            selectedColor: '#166534',
            backgroundColor: '#ffffff',
            borderStyle: 'black',
            list: tabs.map((tab) => ({
              pagePath: tab.path,
              text: tab.text,
              iconPath: `assets/tabbar/${tab.icon}.png`,
              selectedIconPath: `assets/tabbar/${tab.icon}-active.png`,
            })),
          },
        },
        projectConfigJson: {
          appid: appId,
          projectname: 'tennis-miniapp',
          compileType: 'miniprogram',
          setting: {
            urlCheck: false,
            es6: false,
            enhance: false,
            postcss: false,
            minified: false,
            compileHotReLoad: true,
            skylineRenderEnable: false,
          },
        },
        projectPrivateConfigJson: {
          setting: {
            urlCheck: false,
          },
        },
        sitemapJson: {
          rules: [{ action: 'allow', page: '*' }],
        },
      }),
    ],
  }
})
