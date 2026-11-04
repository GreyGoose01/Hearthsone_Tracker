"""CI check: the installed package simulates real cards with AutoTavern."""

from hearthwatch.bg.models import BoardSnapshot, CombatSnapshot, Minion
from hearthwatch.sim import autotavern
from hearthwatch.sim.montecarlo import simulate_combat

assert autotavern.available(), "AutoTavern is not bundled"
board = [Minion("BG28_300", 1, 1), Minion("BG26_146", 1, 2)]  # Harmless Bonehead, Lullabot
snap = CombatSnapshot(round=1, player=BoardSnapshot(1, "", "", 1, board),
                      opponent=BoardSnapshot(1, "", "", 1, [Minion("BG31_149", 2, 1)]))
result = simulate_combat(snap, runs=200)
assert result.engine == "autotavern", result
# our patch: the strength of the Beetles is known (a 1/1 vs. its deathrattle Beetles)
vermin = CombatSnapshot(round=5, player=BoardSnapshot(5, "", "", 2, [Minion("BG31_803", 1, 1, taunt=True)]),
                        opponent=BoardSnapshot(5, "", "", 2, [Minion("BG31_149", 9, 9)]))
weak = simulate_combat(vermin, runs=200)
vermin.player.beetle = (40, 40)
strong = simulate_combat(vermin, runs=200)
assert weak.engine == strong.engine == "autotavern" and strong.win > weak.win, (weak, strong)
print("AutoTavern", autotavern.version(), "->", result)
