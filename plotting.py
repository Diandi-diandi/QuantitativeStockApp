"""KBar figure widget backed by mplfinance (the maintained successor of
the deprecated mpl_finance)."""
from __future__ import annotations

import mplfinance as mpf
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from pandas import DataFrame, to_datetime


# Red-up / green-down matches the Taiwan/Asia convention, opposite of
# mplfinance's default 'yahoo' style.
_MARKET_COLORS = mpf.make_marketcolors(
    up="red", down="green",
    edge="inherit", wick="inherit", volume="inherit",
)
_STYLE = mpf.make_mpf_style(
    marketcolors=_MARKET_COLORS,
    facecolor="black", edgecolor="white",
    figcolor="black", gridcolor="dimgray",
    rc={
        "axes.labelcolor": "white",
        "axes.edgecolor":  "white",
        "xtick.color":     "white",
        "ytick.color":     "white",
        "text.color":      "white",
    },
)


def make_kbar_canvas(kbar_rows: list[tuple], days: int = 60) -> FigureCanvas:
    """Build a Qt-embeddable canvas from KBarRepo.latest output.

    kbar_rows shape (latest-first):
        (date, volume, money, open, high, low, close, spread, turnover)
    """
    rows = list(reversed(kbar_rows))[-days:]
    if not rows:
        # Return an empty canvas rather than crashing on empty input.
        from matplotlib.figure import Figure
        return FigureCanvas(Figure())

    df = DataFrame(
        {
            "Open":   [float(r[3]) for r in rows],
            "High":   [float(r[4]) for r in rows],
            "Low":    [float(r[5]) for r in rows],
            "Close":  [float(r[6]) for r in rows],
            "Volume": [int(r[1])   for r in rows],
        },
        index=to_datetime([r[0] for r in rows], format="%Y%m%d"),
    )

    fig, _ = mpf.plot(
        df,
        type="candle",
        style=_STYLE,
        mav=(10, 20),
        volume=True,
        returnfig=True,
        figsize=(10, 6),
        tight_layout=True,
    )
    return FigureCanvas(fig)
