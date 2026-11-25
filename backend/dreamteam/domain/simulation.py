MIRAGE = "mirage"
WINNING_SCORE = 13
SWITCH_AFTER = 12
BEATS = {"balanced": "fast", "fast": "hold", "hold": "balanced"}


def host_chance(host_preset, guest_preset):
    if host_preset == guest_preset:
        return 0.5
    return 0.55 if BEATS[host_preset] == guest_preset else 0.45


def simulate_mirage(host_tactics, guest_tactics, sample):
    rounds = []
    score = {"host": 0, "guest": 0}
    while max(score.values()) < WINNING_SCORE:
        host_side, guest_side = ("T", "CT") if len(rounds) < SWITCH_AFTER else ("CT", "T")
        host_preset = host_tactics[host_side]
        guest_preset = guest_tactics[guest_side]
        winner = "host" if sample() < host_chance(host_preset, guest_preset) else "guest"
        score[winner] += 1
        rounds.append({
            "number": len(rounds) + 1,
            "hostSide": host_side,
            "guestSide": guest_side,
            "hostPreset": host_preset,
            "guestPreset": guest_preset,
            "winner": winner,
        })
    return {"map": MIRAGE, "score": score, "winner": rounds[-1]["winner"], "rounds": rounds}
