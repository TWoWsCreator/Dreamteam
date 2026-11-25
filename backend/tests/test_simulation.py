from itertools import chain, repeat

import pytest

from dreamteam.domain.simulation import host_chance, simulate_mirage


@pytest.mark.parametrize(("host", "guest", "chance"), [
    ("balanced", "balanced", 0.50),
    ("balanced", "fast", 0.55),
    ("fast", "hold", 0.55),
    ("hold", "balanced", 0.55),
    ("fast", "balanced", 0.45),
    ("hold", "fast", 0.45),
    ("balanced", "hold", 0.45),
])
def test_chances_for_approved_tactics(host, guest, chance):
    assert host_chance(host, guest) == chance


def test_deciding_round_uses_new_sides_and_ends_at_thirteen():
    host = {"T": "fast", "CT": "hold"}
    guest = {"T": "balanced", "CT": "hold"}
    values = iter([0.52, 0.95] * 12 + [0.52])
    result = simulate_mirage(host, guest, lambda: next(values))
    assert result["score"] == {"host": 13, "guest": 12}
    assert result["winner"] == "host"
    assert [entry["number"] for entry in result["rounds"]] == list(range(1, 26))
    assert result["rounds"][11]["hostSide"] == "T"
    assert result["rounds"][12]["hostSide"] == "CT"
    assert result["rounds"][12]["hostPreset"] == "hold"
    assert result["rounds"][12]["guestPreset"] == "balanced"


def test_probability_boundary_and_no_extra_rounds():
    samples = chain([0.549, 0.55], repeat(0.9))
    result = simulate_mirage(
        {"T": "balanced", "CT": "balanced"},
        {"T": "fast", "CT": "fast"},
        lambda: next(samples),
    )
    assert [entry["winner"] for entry in result["rounds"][:2]] == ["host", "guest"]
    assert result["score"] == {"host": 1, "guest": 13}
    assert len(result["rounds"]) == 14
