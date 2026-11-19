import React, { useEffect, useState } from 'react'
import { api } from './api'

const maps = [
  ['ancient', 'Ancient'], ['anubis', 'Anubis'], ['dust2', 'Dust II'],
  ['inferno', 'Inferno'], ['mirage', 'Mirage'], ['nuke', 'Nuke'], ['train', 'Train'],
]
const presets = [
  ['balanced', 'Баланс', 'Подходит, когда у команды нет особых предпочтений.'],
  ['fast', 'Быстрый темп', 'Команда действует активнее с начала раунда.'],
  ['hold', 'Выжидание', 'Команда удерживает позиции и ждёт действия соперника.'],
]

export function Tactics() {
  const [map, setMap] = useState('mirage')
  const [side, setSide] = useState('T')
  const [saved, setSaved] = useState(null)
  const [drafts, setDrafts] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [retry, setRetry] = useState(0)

  useEffect(() => {
    const controller = new AbortController()
    setError('')
    api('/tactics', { signal: controller.signal }).then((values) => {
      setSaved(Object.fromEntries(values.map(({ map, side, preset }) => [`${map}:${side}`, preset])))
    }).catch((failure) => {
      if (!controller.signal.aborted) setError(failure.message)
    })
    return () => controller.abort()
  }, [retry])

  const key = `${map}:${side}`
  const preset = drafts[key] ?? saved?.[key] ?? 'balanced'

  async function save(event) {
    event.preventDefault()
    setSaving(true)
    setError('')
    setNotice('')
    try {
      await api('/tactics', { method: 'PUT', body: { map, side, preset } })
      setSaved((previous) => ({ ...previous, [key]: preset }))
      setNotice('Тактика сохранена')
    } catch (failure) {
      setError(failure.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <section className="view">
      <h1>Тактики</h1>
      <p className="lead">У каждой карты свои настройки для T и CT.</p>
      {!saved && error && <button type="button" onClick={() => setRetry(retry + 1)}>Повторить загрузку</button>}
      {!saved && !error && <p role="status">Загружаем тактики…</p>}
      {saved && <form className="panel form" onSubmit={save}>
        <label className="field">
          Карта
          <select value={map} disabled={saving} onChange={(event) => { setMap(event.target.value); setNotice('') }}>
            {maps.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <fieldset className="side-picker" disabled={saving}>
          <legend>Сторона</legend>
          {['T', 'CT'].map((value) => <label key={value}>
            <input type="radio" name="side" value={value} checked={side === value}
              onChange={() => { setSide(value); setNotice('') }} />
            <span>{value}</span>
          </label>)}
        </fieldset>
        <fieldset disabled={saving}>
          <legend>Пресет</legend>
          <div className="preset-list">
            {presets.map(([value, title, description]) => <label className="preset" key={value}>
              <input type="radio" name="preset" value={value} checked={preset === value}
                onChange={() => { setDrafts((previous) => ({ ...previous, [key]: value })); setNotice('') }} />
              <span><strong>{title}</strong><small>{description}</small></span>
            </label>)}
          </div>
        </fieldset>
        <div className="actions">
          <button className="primary" type="submit" disabled={saving}>{saving ? 'Сохраняем…' : 'Сохранить тактику'}</button>
          {notice && <span role="status">{notice}</span>}
        </div>
      </form>}
      {error && <p role="alert" className="alert">{error}</p>}
    </section>
  )
}
