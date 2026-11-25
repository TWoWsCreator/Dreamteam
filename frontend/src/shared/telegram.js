export const browserInviteBase = import.meta.env.VITE_BROWSER_INVITE_BASE

export function getLaunchInvite(initData = window.Telegram?.WebApp?.initData) {
  const query = new URLSearchParams(window.location.search)
  return new URLSearchParams(initData).get('start_param')
    || query.get('tgWebAppStartParam')
    || (browserInviteBase ? query.get('startapp') : null)
}

export function getInviteUrl(telegramUrl) {
  if (!browserInviteBase || !telegramUrl) return telegramUrl
  const code = new URL(telegramUrl).searchParams.get('startapp')
  if (!code) return telegramUrl
  const url = new URL(browserInviteBase)
  url.searchParams.set('startapp', code)
  return url.href
}

export function getTelegramLaunch() {
  const telegram = window.Telegram?.WebApp
  telegram?.ready()
  return {
    initData: telegram?.initData || '',
    invite: getLaunchInvite(telegram?.initData),
  }
}
