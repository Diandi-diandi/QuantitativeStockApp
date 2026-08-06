"""KBar figure widget. Extracted from the old Model."""
from __future__ import annotations

from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
import mpl_finance as mpf
from numpy import array
from talib import abstract


class KBarFigure(FigureCanvas):
    def __init__(self):
        self.fig = Figure()  # Figure() instead of plt.figure() — no pyplot state
        super().__init__(self.fig)

    def plot(self, kbar_rows: list[tuple], days: int = 60) -> None:
        """rows: (date, volume, money, open, high, low, close, spread, turnover),
        latest-first — same shape as KBarRepo.latest returns."""
        rows = kbar_rows[::-1]
        kbar = {
            "date":   [r[0] for r in rows],
            "open":   array([r[3] for r in rows]),
            "high":   array([r[4] for r in rows]),
            "low":    array([r[5] for r in rows]),
            "close":  array([r[6] for r in rows]),
            "volume": [int(r[1]) for r in rows],
        }
        kbar["10MA"] = abstract.SMA(kbar["close"], 10)
        kbar["20MA"] = abstract.SMA(kbar["close"], 20)
        for k in kbar:
            kbar[k] = kbar[k][-days:]

        self.fig.clf()
        ax = self.fig.add_axes([0, .4, 1, .6])
        ax2 = self.fig.add_axes([0, 0, 1, .4])
        ax.set_xticks(range(0, len(kbar["date"]), 10))
        ax.set_xticklabels(kbar["date"][::10])
        mpf.candlestick2_ohlc(ax, kbar["open"], kbar["high"], kbar["low"],
                              kbar["close"], width=.6, colorup="r",
                              colordown="g", alpha=0.75)
        ax.plot(kbar["10MA"], label="10MA")
        ax.plot(kbar["20MA"], label="20MA")

        mpf.volume_overlay(ax2, kbar["open"], kbar["close"], kbar["volume"],
                           colorup="r", colordown="g", width=0.7, alpha=0.8)
        ax2.set_xticks(range(0, len(kbar["date"]), 10))
        ax2.set_xticklabels(kbar["date"][::10])
        ax.legend()
        ax.set_facecolor("black")
        ax2.set_facecolor("black")
        self.draw()
