import { createHmac, randomInt } from 'node:crypto'
import { expect, test } from '@playwright/test'

const botToken = process.env.DREAMTEAM_E2E_BOT_TOKEN

function initData(user, invitation) {
  const fields = {
    auth_date: Math.floor(Date.now() / 1000).toString(),
    user: JSON.stringify(user),
  }
  if (invitation) fields.start_param = invitation
  const check = Object.keys(fields).sort().map((key) => `${key}=${fields[key]}`).join('\n')
  const key = createHmac('sha256', 'WebAppData').update(botToken).digest()
  return new URLSearchParams({
    ...fields,
    hash: createHmac('sha256', key).update(check).digest('hex'),
  }).toString()
}

async function prepareTelegram(page, data = '') {
  await page.route('https://telegram.org/js/telegram-web-app.js', (route) => route.fulfill({
    contentType: 'application/javascript',
    body: 'window.Telegram = { WebApp: { initData: window.testInitData, ready() {} } };',
  }))
  await page.addInitScript((init) => { window.testInitData = init }, data)
}

test('вне Telegram показывается подсказка о входе', async ({ page }) => {
  await prepareTelegram(page)
  await page.route('**/api/me', (route) => route.fulfill({ status: 401, json: { detail: 'Unauthorized' } }))
  await page.goto('/')
  await expect(page.getByRole('alert')).toHaveText('Чтобы войти, открой Dreamteam из Telegram.')
  await expect(page.getByRole('button', { name: 'Попробовать снова' })).toBeVisible()
})

test('недействительное приглашение оставляет возможность создать своё лобби', async ({ page }) => {
  await prepareTelegram(page, 'start_param=invalid')
  await page.route('**/api/session', (route) => route.fulfill({
    json: { displayName: 'Таисия', team: [], activeLobby: null },
  }))
  await page.route('**/api/lobbies/join', (route) => route.fulfill({
    status: 410,
    json: { detail: 'Срок приглашения истёк' },
  }))
  await page.goto('/')
  await expect(page.getByRole('alert')).toHaveText('Срок приглашения истёк')
  await expect(page.getByRole('button', { name: 'Создать лобби' })).toBeVisible()
})

test('пять карточек из API и одинаковый итог Mirage у двух игроков после обновления', async ({ page, browser }, info) => {
  test.skip(!botToken, 'Для сквозной проверки запусти API и укажи DREAMTEAM_E2E_BOT_TOKEN')
  const guest = await browser.newPage({ viewport: page.viewportSize() })
  const hostId = randomInt(1_000_000, 1_000_000_000)
  try {
    await prepareTelegram(page, initData({ id: hostId, first_name: 'Игрок 1' }))
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'Играй с другом' })).toBeVisible()
    if (process.env.DREAMTEAM_PREVIEW_DIR) {
      await page.screenshot({ path: `${process.env.DREAMTEAM_PREVIEW_DIR}/dreamteam-${info.project.name}.png`, fullPage: true })
    }

    await page.getByRole('button', { name: 'Команда', exact: true }).click()
    await expect(page.locator('.player-card')).toHaveCount(5)
    await expect(page.locator('.player-card')).toContainText(['IGL', 'AWP', 'Entry', 'Support', 'Lurker'])
    await expect(page.getByText('Сила 50', { exact: true })).toHaveCount(5)
    const navigation = page.getByRole('navigation')
    await navigation.getByRole('button', { name: 'Тактики' }).click()
    await page.getByLabel('Быстрый темп').check()
    await page.getByRole('button', { name: 'Сохранить тактику' }).click()
    await expect(page.getByRole('status')).toHaveText('Тактика сохранена')

    await navigation.getByRole('button', { name: 'Играть' }).click()
    await page.getByRole('button', { name: 'Создать лобби' }).click()
    const link = await page.getByLabel('Ссылка для друга').inputValue()
    const invitation = new URL(link).searchParams.get('startapp')
    expect(invitation).toBeTruthy()

    await prepareTelegram(guest, initData({ id: hostId + 1_000_000_000, first_name: 'Игрок 2' }, invitation))
    await guest.goto(info.project.use.baseURL)
    await expect(guest.getByText('Игрок 1', { exact: true })).toBeVisible()
    await expect(page.getByText('Игрок 2', { exact: true })).toBeVisible()

    await page.getByRole('button', { name: 'Я готов' }).click()
    await expect(page.getByRole('status')).toHaveText('Ожидание игроков')
    const lobbyRequest = '**/api/lobbies/*'
    await page.route(lobbyRequest, (route) => route.abort())
    await expect(page.getByRole('alert')).toHaveText('Нет связи с сервером. Попробуй ещё раз.')
    await expect(page.getByRole('status')).toHaveText('Ожидание игроков')
    await page.unroute(lobbyRequest)
    await expect(page.getByRole('alert')).toHaveCount(0)

    await expect(page.locator('.preparation')).toContainText('Mirage')
    await expect(page.locator('.preparation')).toContainText('Быстрый темп')
    await guest.getByRole('button', { name: 'Я готов' }).click()
    await expect(page.getByRole('heading', { name: 'Итог карты' })).toBeVisible()
    await expect(guest.getByRole('heading', { name: 'Итог карты' })).toBeVisible()
    const score = await page.locator('.scoreboard dd').allTextContents()
    await expect(guest.locator('.scoreboard dd')).toHaveText(score)
    await page.getByText('Раунды', { exact: true }).click()
    expect(await page.locator('.round-log li').count()).toBeGreaterThanOrEqual(13)

    await page.reload()
    await expect(page.locator('.scoreboard dd')).toHaveText(score)
    await guest.reload()
    await expect(guest.locator('.scoreboard dd')).toHaveText(score)
    if (process.env.DREAMTEAM_PREVIEW_DIR) {
      await page.screenshot({ path: `${process.env.DREAMTEAM_PREVIEW_DIR}/result-${info.project.name}.png`, fullPage: true })
    }

    await page.getByRole('button', { name: 'На главную' }).click()
    await page.getByRole('button', { name: 'Последний итог' }).click()
    await expect(page.locator('.scoreboard dd')).toHaveText(score)
  } finally {
    await guest.close()
  }
})


test('гость закрывает лобби и возвращается на главную', async ({ page, browser }, info) => {
  test.skip(!botToken, 'Для сквозной проверки запусти API и укажи DREAMTEAM_E2E_BOT_TOKEN')
  const guest = await browser.newPage({ viewport: page.viewportSize() })
  const hostId = randomInt(1_000_000, 1_000_000_000)
  try {
    await prepareTelegram(page, initData({ id: hostId, first_name: 'Организатор' }))
    await page.goto('/')
    await page.getByRole('button', { name: 'Играть с другом', exact: true }).click()
    await page.getByRole('button', { name: 'Создать лобби' }).click()
    const link = await page.getByLabel('Ссылка для друга').inputValue()
    const invitation = new URL(link).searchParams.get('startapp')
    await prepareTelegram(guest, initData({ id: hostId + 1_000_000_000, first_name: 'Гость' }, invitation))
    await guest.goto(info.project.use.baseURL)
    await guest.getByRole('button', { name: 'Закрыть лобби' }).click()
    await guest.getByRole('button', { name: 'Подтвердить закрытие' }).click()
    await expect(guest.getByRole('heading', { name: 'Играй с другом' })).toBeVisible()
    await expect(page.getByRole('status')).toHaveText('Лобби закрыто')
  } finally {
    await guest.close()
  }
})
