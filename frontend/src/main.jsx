import React, { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { api, getTelegramLaunch } from './api'
import { Lobby } from './lobby'
import { Tactics } from './tactics'
import './style.css'

const menu = [
  ['home', 'Главная', 'home'],
  ['team', 'Команда', 'team'],
  ['play', 'Играть', 'play'],
  ['tactics', 'Тактики', 'tactics'],
  ['profile', 'Профиль', 'profile'],
]

const iconPaths = {
  home: 'm3 11 9-8 9 8v9H3z M9 20v-6h6v6',
  team: 'M16 20v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2 M22 20v-2a4 4 0 0 0-3-4 M13 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0 M17 3a4 4 0 0 1 0 8',
  play: 'M8 5v14l12-7z',
  tactics: 'M4 7h16 M4 12h16 M4 17h16 M8 4v6 M15 9v6 M11 14v6',
  profile: 'M20 21v-2a5 5 0 0 0-5-5H9a5 5 0 0 0-5 5v2 M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0',
}

function Icon({ name }) {
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.65"
    strokeLinecap="round" strokeLinejoin="round"><path d={iconPaths[name]} /></svg>
}

function Navigation({ current, navigate }) {
  return <nav className="navigation" aria-label="Разделы приложения">
    {menu.map(([value, label, icon]) => <button key={value} type="button"
      aria-current={current === value ? 'page' : undefined} onClick={() => navigate(value)}>
      <Icon name={icon} />
      <span>{label}</span>
    </button>)}
  </nav>
}

function Home({ profile, lobbyId, navigate }) {
  return <>
    <section className="hero">
      <p className="eyebrow">{profile.displayName}</p>
      <h1>Играй с другом</h1>
      <p>Выбери тактику для своей пятёрки и позови друга в лобби.</p>
      <button className="primary" type="button" onClick={() => navigate('play')}>
        {lobbyId ? 'Вернуться в лобби' : 'Играть с другом'}
      </button>
    </section>
    <section className="home-links" aria-label="Команда и тактики">
      <button type="button" onClick={() => navigate('team')}>
        <Icon name="team" /><span><strong>Стартовая пятёрка</strong><small>Роли игроков</small></span>
      </button>
      <button type="button" onClick={() => navigate('tactics')}>
        <Icon name="tactics" /><span><strong>Тактики</strong><small>Пресеты для T и CT</small></span>
      </button>
    </section>
  </>
}

function Team({ players }) {
  return <section className="view">
    <h1>Стартовая пятёрка</h1>
    <p className="lead">У каждого игрока своя роль.</p>
    <ul className="team-grid">
      {players.map(({ role, name, description }) => <li key={role} className="player-card">
        <div className="player-role">{role}</div>
        <strong>{name}</strong>
        <p>{description}</p>
      </li>)}
    </ul>
  </section>
}

function App() {
  const [profile, setProfile] = useState(null)
  const [screen, setScreen] = useState('home')
  const [tacticsOpened, setTacticsOpened] = useState(false)
  const [lobby, setLobby] = useState(null)
  const [lobbyId, setLobbyId] = useState(null)
  const [error, setError] = useState('')
  const [inviteError, setInviteError] = useState('')
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    const { signal } = controller
    const { initData, invite } = getTelegramLaunch()
    setError('')
    setInviteError('')

    async function boot() {
      let account
      try {
        account = initData
          ? await api('/session', { method: 'POST', body: { initData }, signal })
          : await api('/me', { signal })
      } catch (failure) {
        if (signal.aborted) return
        setError(failure.status === 401 && !initData
          ? 'Чтобы войти, открой Dreamteam из Telegram.'
          : failure.message)
        return
      }

      let room = null
      if (invite) {
        try {
          room = await api('/lobbies/join', { method: 'POST', body: { code: invite }, signal })
        } catch (failure) {
          if (!signal.aborted) setInviteError(failure.message)
        }
      }
      if (signal.aborted) return

      setProfile(account)
      setLobby(room)
      setLobbyId(room?.id ?? account.activeLobby)
      if (account.activeLobby || invite) setScreen('play')
    }
    boot()
    return () => controller.abort()
  }, [attempt])

  useEffect(() => {
    const back = window.Telegram?.WebApp?.BackButton
    if (!back) return undefined
    const home = () => setScreen('home')
    if (screen !== 'home') back.show()
    else back.hide()
    back.onClick(home)
    return () => back.offClick(home)
  }, [screen])

  function navigate(next) {
    setInviteError('')
    if (next === 'tactics') setTacticsOpened(true)
    setScreen(next)
  }

  function leaveLobby() {
    setLobby(null)
    setLobbyId(null)
    setInviteError('')
  }

  return <>
    <header><div className="brand"><span aria-hidden="true">D</span>Dreamteam</div></header>
    <main>
      {!profile && <section className="view welcome">
        <h1>Dreamteam</h1>
        {error
          ? <><p className="lead" role="alert">{error}</p><button type="button" onClick={() => setAttempt(attempt + 1)}>Попробовать снова</button></>
          : <p className="lead" role="status">Входим в игру…</p>}
      </section>}
      {profile && <>
        {error && <p className="alert" role="alert">{error}</p>}
        {screen === 'home' && <Home profile={profile} lobbyId={lobbyId} navigate={navigate} />}
        {screen === 'team' && <Team players={profile.team} />}
        {screen === 'play' && <>
          {inviteError && <p className="alert" role="alert">{inviteError}</p>}
          <Lobby lobbyId={lobbyId} lobby={lobby} setLobby={setLobby} enter={setLobbyId} leave={leaveLobby} />
        </>}
        {tacticsOpened && <div hidden={screen !== 'tactics'}><Tactics /></div>}
        {screen === 'profile' && <section className="view">
          <h1>Профиль</h1>
          <div className="panel profile"><div className="avatar" aria-hidden="true">{profile.displayName.slice(0, 1)}</div>
            <div><strong>{profile.displayName}</strong><p className="muted">Аккаунт Telegram</p></div>
          </div>
        </section>}
      </>}
    </main>
    {profile && <Navigation current={screen} navigate={navigate} />}
  </>
}

createRoot(document.getElementById('root')).render(<App />)
