"""
Quantitative Stock App — Controller.

Thin coordinator between view, workers, and repositories. Business logic
lives in strategies.py; SQL lives in repositories.py; download lives in
downloader.py; long-running tasks in workers.py.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

# --- Qt bootstrap ---------------------------------------------------------
# Some Windows setups (Anaconda, other Qt-based apps) leave
# QT_QPA_PLATFORM_PLUGIN_PATH stuck at an empty string. Qt then treats it
# as "no valid location" and refuses to load the platform plugin
# ("Could not find the Qt platform plugin \"windows\" in \"\""). Repair it
# by pointing at PyQt5's bundled plugins before importing any Qt module.
if sys.platform == "win32" and not os.environ.get("QT_QPA_PLATFORM_PLUGIN_PATH"):
    import importlib.util as _il
    _spec = _il.find_spec("PyQt5")
    if _spec and _spec.submodule_search_locations:
        _plugins = (Path(_spec.submodule_search_locations[0])
                    / "Qt5" / "plugins" / "platforms")
        if _plugins.exists():
            os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = str(_plugins)
# --------------------------------------------------------------------------

from PyQt5 import QtWidgets

import QuantStockApp_View as view
from config import SYS_PWD
from downloader import check_connection
from plotting import make_kbar_canvas
from repositories import (
    BSRepo, FinStatRepo, ForeignInvRepo, InstitutionRepo, KBarRepo,
    PBRRepo, RevenueRepo, StockRepo, StrategyRepo,
)
from strategies import CATEGORIES, sync_db as sync_strategies
from workers import (
    QuantWorker, UpdateDataWorker,
    batch_stock_summary, check_latest, fetch_stock_bundle,
)


CLASSIFY_ORDER = [("策略分類", ""), ("所有", ""), ("基本面", "fund"),
                  ("技術面", "tech"), ("籌碼面", "chip"), ("其他", "others")]


def _fmt_int(n) -> str:
    try:
        return format(int(n), ",d")
    except (TypeError, ValueError):
        return "--"


def _fmt_date(yyyymmdd: str, sep: str = "-") -> str:
    try:
        d = datetime.strptime(yyyymmdd, "%Y%m%d")
    except ValueError:
        return yyyymmdd
    return d.strftime(f"%Y{sep}%m{sep}%d")


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.ui = view.Ui_MainWindow()
        self.ui.setupUi(self)
        sync_strategies()          # push registry -> strategies table
        self._show_disclaimer()
        self._wire_widgets()
        self._populate_classify_combo()
        self._update_worker: UpdateDataWorker | None = None
        self._quant_worker: QuantWorker | None = None
        self._latest_update: dict[str, str] | None = None
        self._plot_canvas = None

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------
    def _show_disclaimer(self):
        QtWidgets.QMessageBox.information(
            None, "免責聲明",
            "本軟體內容為台股之客觀數據，本軟體對數據之正確性不負任何責任，"
            "本軟體所提供之數據不涉及個股操作建議、推薦、行銷，投資人應審慎評估"
            "可能之交易風險，並自負盈虧。",
            QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok,
        )

    def _wire_widgets(self):
        self.ui.action_update_data.triggered.connect(self.on_update_triggered)
        self.ui.combobox_classify.currentTextChanged.connect(self.on_classify_changed)
        self.ui.combobox_strategy.currentTextChanged.connect(self.on_strategy_changed)
        self.ui.btn_execute_quant.clicked.connect(self.on_execute_quant)
        self.ui.button_search.clicked.connect(self.on_search_clicked)
        self.ui.tab_fundamental.currentChanged.connect(self._refresh_detail_tables)
        self.ui.tab_chip.currentChanged.connect(self._refresh_detail_tables)

    def _populate_classify_combo(self):
        for i, (label, _) in enumerate(CLASSIFY_ORDER):
            self.ui.combobox_classify.addItem(label)
        model = self.ui.combobox_classify.model()
        model.item(0).setEnabled(False)   # placeholder row

    # ------------------------------------------------------------------
    # Update flow
    # ------------------------------------------------------------------
    def on_update_triggered(self):
        latest = check_latest()
        self._latest_update = latest
        summary = "\n".join(
            f"{k}: {_fmt_date(v, '/') if v != '0' else '(尚無資料)'}"
            for k, v in latest.items()
        )
        proceed = QtWidgets.QMessageBox.information(
            None, "資料現況",
            f"最新資料\n{summary}\n\n是否登入並繼續進行更新？\n"
            "*更新資料可能花費數分鐘，更新過程中請勿任意關閉視窗",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.Yes,
        )
        if proceed != QtWidgets.QMessageBox.Yes:
            return

        if not self._manager_login():
            QtWidgets.QMessageBox.warning(None, "登入失敗", "已取消更新")
            return
        if not check_connection():
            QtWidgets.QMessageBox.warning(None, "連線失敗", "未偵測到網路連線，請重新嘗試!")
            return

        self.ui.progressbar_update.show()
        self._update_worker = UpdateDataWorker(latest)
        self._update_worker.progress.connect(self.ui.progressbar_update.setValue)
        self._update_worker.finished_with_result.connect(self._on_update_finished)
        self._update_worker.start()

    def _manager_login(self) -> bool:
        while True:
            res = self.ui.dialog_manager_login.exec_()
            if res != QtWidgets.QDialog.Accepted:
                return False
            if self.ui.dialog_manager_login.lineedit_pwd.text() == SYS_PWD:
                return True

    def _on_update_finished(self, ok: bool, latest: dict):
        self.ui.progressbar_update.close()
        self.ui.clear_all_tables()
        self._latest_update = latest
        if ok:
            summary = "\n".join(f"{k}: {_fmt_date(v, '/')}" for k, v in latest.items())
            QtWidgets.QMessageBox.information(
                None, "更新完成", f"資料庫更新完成\n最新資料\n{summary}"
            )
        else:
            QtWidgets.QMessageBox.warning(None, "更新失敗", "未知錯誤，請重新嘗試")

    # ------------------------------------------------------------------
    # Strategy combos
    # ------------------------------------------------------------------
    def on_classify_changed(self, text: str):
        code = dict(CLASSIFY_ORDER).get(text, "")
        # '所有' returns everything (empty type filter)
        names = StrategyRepo.by_type(code)
        self.ui.combobox_strategy.blockSignals(True)
        self.ui.combobox_strategy.clear()
        self.ui.combobox_strategy.addItem("未選擇")
        for n in names:
            self.ui.combobox_strategy.addItem(n)
        self.ui.combobox_strategy.model().item(0).setEnabled(False)
        self.ui.combobox_strategy.blockSignals(False)

    def on_strategy_changed(self, text: str):
        self.ui.label_choosen_strategy.setText(f"選股策略：  {text}")
        row = StrategyRepo.by_name(text)
        self.ui.label_question_mark.setToolTip(row[1] if row else "請選擇策略")

    # ------------------------------------------------------------------
    # Quant
    # ------------------------------------------------------------------
    def on_execute_quant(self):
        strat_name = self.ui.combobox_strategy.currentText()
        if not StrategyRepo.by_name(strat_name):
            QtWidgets.QMessageBox.warning(None, "執行錯誤", "請重新選擇量化交易策略")
            return
        self.ui.progressbar_quanting.show()
        self._quant_worker = QuantWorker(strat_name)
        self._quant_worker.progress.connect(self.ui.progressbar_quanting.setValue)
        self._quant_worker.finished_with_result.connect(
            lambda date, sids: self._on_quant_finished(strat_name, date, sids)
        )
        self._quant_worker.start()

    def _on_quant_finished(self, strat_name: str, trading_date: str, sids: list):
        self.ui.progressbar_quanting.close()
        QtWidgets.QMessageBox.information(
            None, "策略執行結果",
            f"執行日期： {_fmt_date(trading_date, '/')}\n"
            f"[{strat_name}] 共篩選到 [{len(sids)}] 檔股票\n"
            "按下確認鍵稍待幾秒將為您顯示符合條件之個股\n\n"
            "注意：若非預期的執行日期，請將資料更新後再重新執行策略"
        )
        rows = batch_stock_summary(sids)
        self.ui.populate_table(
            self.ui.table_quant, rows,
            color_cols=range(5), color_ref_col=3,
            on_item_clicked=self.on_summary_row_clicked,
        )
        self.ui.tabwidget_group.setCurrentIndex(0)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def on_search_clicked(self):
        keyword = self.ui.lineedit_search.text().strip()
        if not keyword:
            return
        hits = StockRepo.search(keyword)
        rows = batch_stock_summary([h[0] for h in hits])
        self.ui.populate_table(
            self.ui.table_search, rows,
            color_cols=range(5), color_ref_col=3,
            on_item_clicked=self.on_summary_row_clicked,
        )
        self.ui.tabwidget_group.setCurrentIndex(1)

    # ------------------------------------------------------------------
    # Per-stock detail
    # ------------------------------------------------------------------
    def on_summary_row_clicked(self, item):
        table = item.tableWidget()
        row = table.currentRow()
        first_cell = table.item(row, 0)
        if first_cell is None:
            return
        sid_name = first_cell.text()
        try:
            sid, name = sid_name.split(" ", 1)
        except ValueError:
            return
        self._current_sid = sid
        self._current_name = name
        self.ui.set_stock_label(sid, name)
        self._plot_kbar_and_price(sid)
        self._refresh_detail_tables()

    def _refresh_detail_tables(self):
        sid = getattr(self, "_current_sid", None)
        if not sid:
            return
        self.ui.clear_stock_detail_tables()
        bundle = fetch_stock_bundle(sid)
        self._fill_revenue_table(sid, bundle["revenue"])
        self._fill_pbr_table(sid, bundle["pbr"])
        self._fill_eps_table(sid, bundle["fin_stat"])
        self._fill_institution_table(bundle["institution"])
        self._fill_foreign_inv_table(bundle["foreign_inv"])

    def _plot_kbar_and_price(self, sid: str):
        latest = KBarRepo.latest(sid, 60)
        if not latest:
            return
        if sid.isdigit():
            self._plot_canvas = make_kbar_canvas(latest)
            self.ui.add_kbar_plot(self._plot_canvas)
        latest_row = latest[0]  # (date, volume, money, open, high, low, close, spread, turnover)
        price_row = (
            _fmt_date(latest_row[0], "/"),
            latest_row[3], latest_row[4], latest_row[5], latest_row[6],
            _fmt_int(latest_row[1]),
            latest_row[7],   # spread (drives color)
        )
        self.ui.set_price_display(price_row)

    # -------- detail table fillers --------------------------------------

    def _fill_revenue_table(self, sid: str, rev_rows: list):
        # rev_rows: latest-first list of (yyyymm, revenue)
        if not rev_rows:
            return
        rev_asc = list(reversed(rev_rows))
        display = []
        for i, (ym, revenue) in enumerate(rev_asc):
            if i == 0:
                ratio = "--"
            else:
                prev = float(rev_asc[i - 1][1] or 0)
                ratio = f"{round((float(revenue) - prev) * 100 / prev, 2)}%" if prev else "--"
            close_row = KBarRepo.by_month(sid, ym)  # descending -> most recent close of that month
            close = close_row[0][5] if close_row else "--"  # close column index in tuple minus stock_no
            display.append((
                datetime.strptime(ym, "%Y%m").strftime("%Y-%m"),
                _fmt_int(revenue), ratio, close,
            ))
        display.reverse()  # newest first for display
        self.ui.populate_table(self.ui.table_revenue, display,
                               color_cols=(1, 2), color_ref_col=2, draw_by_row=True)

    def _fill_pbr_table(self, sid: str, pbr_rows: list):
        if not pbr_rows:
            return
        display = []
        for date, div, per, pbr in pbr_rows:
            close_row = KBarRepo.by_date(sid, date)
            close = close_row[5] if close_row else "--"
            display.append((date, div, per, pbr, close))
        self.ui.populate_table(self.ui.table_pbr, display)

    def _fill_eps_table(self, sid: str, fin_rows: list):
        if not fin_rows:
            return
        # Pull BS records once, map by date, avoid N+1
        bs_rows = BSRepo.latest(sid, len(fin_rows) * 2)
        bs_by_date = {r[0]: r[1] for r in bs_rows}
        display = []
        for date, eps, income in fin_rows:
            equity = bs_by_date.get(date)
            if equity and int(equity) != 0:
                roe = round(int(income) / int(equity), 2)
            else:
                roe = 0
            display.append((_fmt_date(date), eps, roe))
        self.ui.populate_table(self.ui.table_eps, display)

    def _fill_institution_table(self, ins_rows: list):
        if not ins_rows:
            return
        display = []
        for date, foreign_inv, inv_trust, dealer in ins_rows:
            vols = [int(x) for x in (foreign_inv, inv_trust, dealer)]
            total = _fmt_int(sum(vols))
            display.append((_fmt_date(date), *[_fmt_int(v) for v in vols], total))
        self.ui.populate_table(self.ui.table_institution, display,
                               color_cols=range(1, 5), draw_by_row=False)

    def _fill_foreign_inv_table(self, fi_rows: list):
        if not fi_rows:
            return
        asc = list(reversed(fi_rows))
        display = []
        for i, (date, ratio, total) in enumerate(asc):
            if i == 0:
                dif = "--"
            else:
                prev = asc[i - 1][1]
                dif = f"{round(ratio - prev, 2)}%"
            display.append((_fmt_date(date), f"{ratio}%", dif, _fmt_int(total)))
        display.reverse()
        self.ui.populate_table(self.ui.table_foreign_inv, display,
                               color_cols=(2,), draw_by_row=False)


def main():
    app = QtWidgets.QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
