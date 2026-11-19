export class ApiError extends Error {
  constructor(status, message) {
    super(message)
    this.status = status
  }
}

export async function api(path, { method = 'GET', body, signal } = {}) {
  const options = { method, signal }
  if (body !== undefined) {
    options.headers = { 'Content-Type': 'application/json' }
    options.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(`/api${path}`, options)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(0, 'Нет связи с сервером. Попробуй ещё раз.')
  }

  const payload = await response.json().catch(() => null)
  if (!response.ok || payload === null) {
    const message = typeof payload?.detail === 'string' ? payload.detail : 'Запрос не выполнен. Попробуй ещё раз.'
    throw new ApiError(response.status, message)
  }
  return payload
}

export function getTelegramLaunch() {
  const telegram = window.Telegram?.WebApp
  telegram?.ready()
  return {
    initData: telegram?.initData || '',
    invite: new URLSearchParams(telegram?.initData).get('start_param')
      || new URLSearchParams(window.location.search).get('tgWebAppStartParam'),
  }
}
