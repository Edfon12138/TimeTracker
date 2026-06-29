"""Matplotlib chart factory for donut (pie) and horizontal bar charts."""
import matplotlib; matplotlib.use("QtAgg")
from matplotlib.figure import Figure

BG = "#1E2027"; TXT = "#9B958A"; MUTED = "#5E5A54"; BORDER = "#2E3039"

def create_donut_chart(data: list[dict], center_total: str = "", center_label: str = ""):
    fig = Figure(figsize=(2.7, 2.7), facecolor=BG)
    ax = fig.add_subplot(111); ax.set_facecolor(BG)
    vals = [d["value"] for d in data]; colors = [d["color"] for d in data]
    total = sum(vals)
    if total == 0:
        ax.text(0.5, 0.5, "暂无数据", ha="center", va="center", color=TXT, fontsize=12)
        ax.set_xlim(-1,1); ax.set_ylim(-1,1); ax.axis("off"); return fig
    wedges, _ = ax.pie(vals, labels=None, colors=colors, startangle=90,
        counterclock=False, wedgeprops={"width": 0.35, "edgecolor": BG, "linewidth": 2})
    ax.text(0, 0.05, center_total, ha="center", va="center",
        fontsize=18, fontweight="bold", color="#EAE4D9", fontfamily="monospace")
    ax.text(0, -0.22, center_label, ha="center", va="center", fontsize=9, color=MUTED)
    ax.axis("equal"); fig.tight_layout(pad=0.5)
    for i, w in enumerate(wedges):
        w.highlight_key = data[i].get("highlight_key", data[i]["label"])
    return fig

def create_bar_chart(data: list[dict]):
    n = len(data)
    fig = Figure(figsize=(2.8, max(2.5, n*0.45)), facecolor=BG)
    ax = fig.add_subplot(111); ax.set_facecolor(BG)
    labels = [d["label"] for d in data]; vals = [d["value"] for d in data]
    colors = [d["color"] for d in data]; mx = max(vals) if vals else 1
    bars = ax.barh(range(n), vals, height=0.6, color=colors, zorder=2)
    for i, (b, v) in enumerate(zip(bars, vals)):
        b.highlight_key = data[i].get("highlight_key", data[i]["label"])
        pct = v / mx * 100
        txt = f"{v//3600}h {(v%3600)//60}m" if v >= 3600 else f"{v//60}m"
        if pct > 40:
            ax.text(v-mx*0.02, b.get_y()+b.get_height()/2, txt, ha="right", va="center",
                    fontsize=9, color="white", fontweight="bold", fontfamily="monospace")
        else:
            ax.text(v+mx*0.01, b.get_y()+b.get_height()/2, txt, ha="left", va="center",
                    fontsize=9, color=TXT, fontfamily="monospace")
    ax.set_yticks(range(n)); ax.set_yticklabels(labels, fontsize=9, color=TXT)
    ax.set_xlim(0, mx*1.18)
    for s in ["top","right","left"]: ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(BORDER)
    ax.tick_params(axis="x", colors=MUTED, labelsize=8)
    ax.xaxis.grid(True, color=BORDER, alpha=0.3, zorder=1)
    ax.set_axisbelow(True); fig.tight_layout(pad=0.5)
    return fig
