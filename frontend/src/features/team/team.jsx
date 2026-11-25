import React from 'react'

export function Team({ players }) {
  return <section className="view">
    <h1>Стартовая пятёрка</h1>
    <p className="lead">У каждого игрока своя роль.</p>
    <ul className="team-grid">
      {players.map(({ slot, role, name, description, power }) => <li key={slot} className="player-card">
        <div className="player-role">{role}</div>
        <strong>{name}</strong>
        <p>{description}</p>
        <strong className="player-power">Сила {power}</strong>
      </li>)}
    </ul>
  </section>
}
