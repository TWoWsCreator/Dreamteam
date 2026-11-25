import React from 'react'
import { presetName } from '../tactics/tactics'

export function MatchResult({ result, participants, leave }) {
  const names = Object.fromEntries(participants.map(({ seat, name }) => [seat, name]))

  return <section className="view">
    <h1>Итог карты</h1>
    <p className="lead" role="status">Победитель: {names[result.winner]}</p>
    <div className="panel">
      <dl className="scoreboard" aria-label="Счёт Mirage">
        <div><dt>{names.host}</dt><dd>{result.score.host}</dd></div>
        <div><dt>{names.guest}</dt><dd>{result.score.guest}</dd></div>
      </dl>
      <p>Mirage · {result.rounds.length} раундов</p>
      <details className="round-log">
        <summary>Раунды</summary>
        <ol>
          {result.rounds.map((round) => <li key={round.number}>
            <strong>{names[round.winner]}</strong>
            <small>{round.hostSide} · {presetName(round.hostPreset)} / {round.guestSide} · {presetName(round.guestPreset)}</small>
          </li>)}
        </ol>
      </details>
      <button className="primary" type="button" onClick={leave}>На главную</button>
    </div>
  </section>
}
