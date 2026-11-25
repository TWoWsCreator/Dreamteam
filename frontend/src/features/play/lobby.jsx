import React, { useEffect, useRef, useState } from 'react'
import { api } from '../../shared/api'
import { browserInviteBase, getInviteUrl } from '../../shared/telegram'
import { presetName } from '../tactics/tactics'
import { MatchResult } from './result'

const lobbyStatus = {
  waiting: 'Ожидание игроков',
  ready: 'Оба игрока готовы',
  cancelled: 'Лобби закрыто',
  expired: 'Срок приглашения истёк',
}

export function Lobby({ lobbyId, lobby, setLobby, enter, leave }) {
  const [pending, setPending] = useState(false)
  const [error, setError] = useState('')
  const [connection, setConnection] = useState('')
  const [copyNote, setCopyNote] = useState('')
  const [confirmClose, setConfirmClose] = useState(false)
  const inviteField = useRef(null)

  const closed = ['cancelled', 'expired', 'finished'].includes(lobby?.status)
  const inviteUrl = getInviteUrl(lobby?.inviteUrl)

  useEffect(() => {
    if (!lobbyId || pending || closed) return undefined
    const controller = new AbortController()
    let timeout

    async function refresh() {
      try {
        const next = await api(`/lobbies/${lobbyId}`, { signal: controller.signal })
        if (controller.signal.aborted) return
        setLobby(next)
        setConnection('')
      } catch (failure) {
        if (controller.signal.aborted) return
        setConnection(failure.message)
        if (failure.status === 401 || failure.status === 404) {
          setLobby(null)
          return
        }
      }

      if (!controller.signal.aborted) timeout = window.setTimeout(refresh, 2500)
    }

    refresh()
    return () => {
      controller.abort()
      window.clearTimeout(timeout)
    }
  }, [lobbyId, pending, closed, setLobby])

  async function update(path, method, body) {
    setPending(true)
    setError('')
    try {
      const next = await api(path, { method, body })
      setConfirmClose(false)
      if (method === 'DELETE') {
        leave()
      } else {
        setLobby(next)
        enter(next.id)
      }
    } catch (failure) {
      setError(failure.message)
    } finally {
      setPending(false)
    }
  }

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(inviteUrl)
      setCopyNote('Ссылка скопирована')
    } catch {
      inviteField.current?.select()
      setCopyNote('Скопируй выделенную ссылку')
    }
  }

  if (!lobbyId) {
    return <section className="view">
      <h1>Играть с другом</h1>
      <p className="lead">{browserInviteBase
        ? 'Создай лобби и скопируй ссылку для второго игрока.'
        : 'Создай лобби для двоих и отправь другу ссылку в Telegram.'}</p>
      <button type="button" className="primary" disabled={pending}
        onClick={() => update('/lobbies', 'POST')}>{pending ? 'Создаём…' : 'Создать лобби'}</button>
      {error && <p className="alert" role="alert">{error}</p>}
    </section>
  }

  if (!lobby) {
    return <section className="view">
      <h1>Лобби друга</h1>
      {connection
        ? <><p className="alert" role="alert">{connection}</p><button onClick={leave}>К игре с другом</button></>
        : <p role="status">Загружаем лобби…</p>}
    </section>
  }

  if (lobby.status === 'finished' && lobby.series?.result) {
    return <MatchResult result={lobby.series.result} participants={lobby.participants} leave={leave} />
  }

  const legacySeries = lobby.series?.phase === 'awaiting_veto'
  const you = lobby.participants.find((participant) => participant.you)
  const participants = [...lobby.participants].sort((first, second) => Number(second.you) - Number(first.you))

  return <section className="view">
    <h1>Лобби друга</h1>
    <p className="lead" role="status">{lobbyStatus[lobby.status]}</p>
    <div className="panel">
      <ul className="participants">
        {participants.map((participant) => <li key={participant.you ? 'you' : 'friend'}>
          <span><strong>{participant.name}</strong>{participant.you && <small>Ты</small>}</span>
          <span className={participant.ready ? 'ready' : 'muted'}>{participant.ready ? 'Готов' : 'Не готов'}</span>
        </li>)}
        {participants.length < 2 && <li><span className="muted">Место для друга</span></li>}
      </ul>
      {!closed && lobby.preparation && <dl className="preparation">
        <div><dt>Карта</dt><dd>Mirage</dd></div>
        <div><dt>Твоя сторона</dt><dd>{lobby.preparation.side}</dd></div>
        <div><dt>Тактика</dt><dd>{presetName(lobby.preparation.preset)}</dd></div>
      </dl>}
      {closed ? <button type="button" className="primary" onClick={leave}>К игре с другом</button> : <>
        {inviteUrl && <div className="invite">
          <label className="field">
            Ссылка для друга
            <input ref={inviteField} readOnly value={inviteUrl} />
          </label>
          <button type="button" onClick={copyInvite}>Копировать</button>
        </div>}
        {inviteUrl && copyNote && <p role="status">{copyNote}</p>}
        <div className="actions">
          {you && <button type="button" className="primary" disabled={pending}
            onClick={() => update(`/lobbies/${lobbyId}/ready`, 'PUT', { ready: legacySeries || !you.ready })}>
            {legacySeries ? 'Продолжить' : you.ready ? 'Снять готовность' : 'Я готов'}
          </button>}
          {lobby.canCancel && !confirmClose && <button type="button" disabled={pending}
            onClick={() => setConfirmClose(true)}>Закрыть лобби</button>}
        </div>
        {confirmClose && <div className="confirmation">
          <p>Лобби закроется для обоих игроков.</p>
          <div className="actions">
            <button type="button" disabled={pending} onClick={() => update(`/lobbies/${lobbyId}`, 'DELETE')}>Подтвердить закрытие</button>
            <button type="button" disabled={pending} onClick={() => setConfirmClose(false)}>Оставить лобби</button>
          </div>
        </div>}
      </>}
      {(error || connection) && <p role="alert" className="alert">{error || connection}</p>}
    </div>
  </section>
}
