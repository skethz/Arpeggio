"""Draw Fig. 1 from the recorded mechanism traces, BER ratios and matched ASIC runs."""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


WORK = Path(__file__).resolve().parent
DATA = WORK.parents[1] / "data"
OUT = WORK / "out"


def read(path):
    return json.loads(path.read_text())


mechanism = DATA / "ber/mechanism"
return_stats = read(mechanism / "mech_traces_summary.json")


def return_percentage(policy, decimals):
    rates = [100 * return_stats[k][policy]["mean_period2_rate"] for k in ("K1", "K2")]
    low = f"{min(rates):.{decimals}f}"
    high = f"{max(rates):.{decimals}f}"
    return (low if low == high else f"{low}–{high}") + "%"


with (mechanism / "mech_traces_examples.csv").open(newline="") as handle:
    examples = {"no_alternation": [], "alternation": []}
    for row in csv.DictReader(handle):
        if row["K"] == "2" and row["example"] == "0" and row["variant"] in examples:
            if int(row["half_step"]) <= 10:
                examples[row["variant"]].append(row)
    for rows in examples.values():
        rows.sort(key=lambda row: int(row["half_step"]))

with (mechanism / "mech_traces_population.csv").open(newline="") as handle:
    population = {}
    for row in csv.DictReader(handle):
        step = int(row["half_step"])
        if row["K"] == "1" and step > 0:
            rounds, gaps = population.setdefault(row["variant"], ([], []))
            rounds.append(step)
            gaps.append(float(row["mean_energy_gap_to_truth"]))

sa = read(DATA / "results/a521/analysis.json")["points"]
arp16 = read(DATA / "results/a519/analysis.json")["P1"]["A16_C0"]
arp32 = read(DATA / "results/a514/analysis_a515_a516_20261110.json")["A515"]["A32_C0"]
assert arp16["hi"] < 1 and arp32["lo"] < 1 < arp32["hi"]

hardware = read(DATA / "asic/a518/d32_d64.json")
matched = [hardware["P1"]["like_for_like"], hardware["P2"]["like_for_like"],
           read(DATA / "asic/a518/d128_pair_1200.json")["like_for_like"]]

WIDTH, HEIGHT = 252, 204
INK, MUTED, GRAY = "#17191D", "#44474C", "#9C9EA1"
CHORD, ARPEGGIO = "#8C1515", "#195FE2"
RULE, GRID = "#C9CBD0", "#E1E3E6"
plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Times", "STIXGeneral"],
    "mathtext.fontset": "stix", "font.size": 8, "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.linewidth": .45, "axes.spines.top": False, "axes.spines.right": False,
    "xtick.labelsize": 8, "ytick.labelsize": 8, "xtick.major.size": 2,
    "ytick.major.size": 2, "xtick.major.width": .45, "ytick.major.width": .45,
    "xtick.major.pad": 1, "ytick.major.pad": 1,
})
fig = plt.figure(figsize=(WIDTH / 72, HEIGHT / 72))
canvas = fig.add_axes([0, 0, 1, 1])
canvas.set(xlim=(0, WIDTH), ylim=(HEIGHT, 0))
canvas.axis("off")


def label(x, y, value, *, align="left", weight="normal", color=INK, size=8):
    return canvas.text(x, y, value, ha=align, va="center",
                       fontweight=weight, color=color, fontsize=size)


def rule(y):
    canvas.plot([0, WIDTH], [y, y], color=RULE, lw=.45, clip_on=False)


def axes(left, right, top=53, bottom=81):
    return fig.add_axes([left/WIDTH, 1-bottom/HEIGHT,
                         (right-left)/WIDTH, (bottom-top)/HEIGHT])


label(126, 5.5, "Parallel tests, one flip per cycle", align="center", weight="bold", size=9)
label(0, 18, "Chord", weight="bold", color=CHORD)
label(25, 18, "Commit all accepted flips")
label(126, 18, "Arpeggio", weight="bold", color=ARPEGGIO)
label(162, 18, "Commit first, then re-test")
rule(26)
uncolored = return_percentage("no_alternation", 0)
colored = return_percentage("alternation", 1)
label(0, 34, f"(a) Returns: {uncolored} → {colored}", weight="bold")
label(131, 34, "(b) Energy gap", weight="bold")
for x, color, name in [(8, GRAY, "Synchronous"), (82, CHORD, "Chord")]:
    canvas.plot([x, x+8], [45, 45], color=color, lw=1.1)
    label(x+11, 45, name)
canvas.plot([158, 171], [45, 45], color=MUTED, ls="--", lw=.7)
label(175, 45, "No pinning")

ax_a = axes(22, 120)
for variant, color, lw in [("no_alternation", GRAY, .75), ("alternation", CHORD, 1.05)]:
    rows = examples[variant]
    rounds = [int(row["half_step"]) for row in rows]
    for coordinate, offset in zip((2, 3, 7), (-0.07, 0, 0.07)):
        levels = [float(row[f"d{coordinate}"]) / 2 + offset for row in rows]
        ax_a.plot(rounds, levels, color=color, lw=lw)
ax_a.set(xlim=(0, 10), ylim=(-2.4, 2.4), xticks=[0, 5, 10], yticks=[-2, 0, 2],
         ylabel="Levels")
ax_a.yaxis.labelpad = .4
ax_b = axes(147, 245)
for key, color, style, lw in [
    ("no_alternation", GRAY, "-", .85), ("no_alternation_q0", GRAY, "--", .85),
    ("alternation_q0", CHORD, "--", .85), ("alternation", CHORD, "-", 1.05),
]:
    rounds, gaps = population[key]
    ax_b.plot(rounds, gaps, color=color, ls=style, lw=lw)
ax_b.set(xscale="log", yscale="log", xlim=(1, 256), ylim=(.12, 600),
         xticks=[1, 100], yticks=[1, 100])
ax_b.minorticks_off()
for ax in (ax_a, ax_b):
    ax.set_xlabel("Round", ha="center", va="center", fontsize=8)
    # Use each plot frame, independent of its tick-label widths or log scale.
    ax.xaxis.set_label_coords(.5, (81-100)/28)
rule(107)

label(0, 116, "(c) BER relative to Chord", weight="bold")
ber_columns = (153, 217)
for x, users in zip(ber_columns, (16, 32)):
    label(x, 116, f"{users} users", align="center")
for y, name, results, precision, color in [
    (129, "1-comparator SA", (sa["P1"], sa["P2"]), 1, INK),
    (141, "Arpeggio", (arp16, arp32), 2, ARPEGGIO),
]:
    label(0, y, name)
    for x, result in zip(ber_columns, results):
        unresolved = result["lo"] <= 1 <= result["hi"]
        value = f"{result['ratio']:.{precision}f}×"
        label(x, y, value + ("*" if unresolved else ""), align="center",
              color=MUTED if unresolved else color,
              weight="normal" if unresolved else "bold")
label(0, 153, "* The paired 95% confidence interval includes 1 (equal BER).", color=MUTED)
rule(160)

label(0, 168, "(d) Arpeggio / Chord (lower is better)", weight="bold")
for x, users in zip([44, 115, 186], (16, 32, 64)):
    label(x+18, 178, f"{users} users", align="center")
for y, name, key in [(188, "Time", "rho_t"), (198, "Energy", "rho_E")]:
    label(0, y, name)
    for x, m in zip([44, 115, 186], matched):
        val = m[key]
        canvas.barh(y, 36, left=x, height=4.5, color=GRID, edgecolor="none")
        canvas.barh(y, 36*val, left=x, height=4.5, color=ARPEGGIO,
                    edgecolor=ARPEGGIO, lw=.65)
        label(x+40, y, f"{val:.2f}")

fig.canvas.draw()
renderer = fig.canvas.get_renderer()
for ax in (ax_a, ax_b):
    box = ax.xaxis.label.get_window_extent(renderer)
    assert abs((box.x0+box.x1)/2 - (ax.bbox.x0+ax.bbox.x1)/2) < .01
OUT.mkdir(exist_ok=True)
fig.savefig(OUT / "teaser.pdf", metadata={"Author": None, "Title": None, "Creator": None,
                           "Producer": None, "CreationDate": None, "ModDate": None})
fig.savefig(OUT / "teaser.png", dpi=220)
plt.close(fig)
