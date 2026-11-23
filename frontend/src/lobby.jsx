import React, { useEffect, useRef, useState } from 'react'
import { api } from './api'

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

  const closed = ['cancelled', 'expired'].includes(lobby?.status)

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
      setLobby(next)
      enter(next.id)
      setConfirmClose(false)
    } catch (failure) {
      setError(failure.message)
    } finally {
      setPending(false)
    }
  }

  async function copyInvite() {
    try {
      await navigator.clipboard.writeText(lobby.inviteUrl)
      setCopyNote('Ссылка скопирована')
    } catch {
      inviteField.current?.select()
      setCopyNote('Скопируй выделенную ссылку')
    }
  }

  if (!lobbyId) {
    return <section className="view">
      <h1>Играть с другом</h1>
      <p className="lead">Создай лобби для двоих и отправь другу ссылку в Telegram.</p>
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

  const seriesCreated = lobby.series?.phase === 'awaiting_veto'
  const closeLabel = seriesCreated ? 'Закрыть серию' : 'Закрыть лобби'
  const keepLabel = seriesCreated ? 'Оставить серию' : 'Оставить лобби'
  const you = lobby.participants.find((participant) => participant.you)
  const participants = [...lobby.participants].sort((first, second) => Number(second.you) - Number(first.you))

  return <section className="view">
    <h1>{seriesCreated ? 'Серия с другом' : 'Лобби друга'}</h1>
    <p className="lead" role="status">{seriesCreated ? 'Серия создана' : lobbyStatus[lobby.status]}</p>
    <div className="panel">
      <ul className="participants">
        {participants.map((participant) => <li key={participant.you ? 'you' : 'friend'}>
          <span><strong>{participant.name}</strong>{participant.you && <small>Ты</small>}</span>
          <span className={participant.ready ? 'ready' : 'muted'}>{participant.ready ? 'Готов' : 'Не готов'}</span>
        </li>)}
        {participants.length < 2 && <li><span className="muted">Место для друга</span></li>}
      </ul>
      {seriesCreated && <p className="muted">Оба игрока готовы. Следующий этап — вето карт.</p>}
      {closed ? <button type="button" className="primary" onClick={leave}>К игре с другом</button> : <>
        {lobby.inviteUrl && <div className="invite">
          <label className="field">
            Ссылка для друга
            <input ref={inviteField} readOnly value={lobby.inviteUrl} />
          </label>
          <button type="button" onClick={copyInvite}>Копировать</button>
        </div>}
        {lobby.inviteUrl && copyNote && <p role="status">{copyNote}</p>}
        <div className="actions">
          {!seriesCreated && you && <button type="button" className="primary" disabled={pending}
            onClick={() => update(`/lobbies/${lobbyId}/ready`, 'PUT', { ready: !you.ready })}>
            {you.ready ? 'Снять готовность' : 'Я готов'}
          </button>}
          {lobby.canCancel && !confirmClose && <button type="button" disabled={pending}
            onClick={() => setConfirmClose(true)}>{closeLabel}</button>}
        </div>
        {confirmClose && <div className="confirmation">
          <p>{seriesCreated ? 'После закрытия серия завершится до вето.' : 'После закрытия приглашение перестанет действовать.'}</p>
          <div className="actions">
            <button type="button" disabled={pending} onClick={() => update(`/lobbies/${lobbyId}`, 'DELETE')}>Подтвердить закрытие</button>
            <button type="button" disabled={pending} onClick={() => setConfirmClose(false)}>{keepLabel}</button>
          </div>
        </div>}
      </>}
      {(error || connection) && <p role="alert" className="alert">{error || connection}</p>}
    </div>
  </section>
}
