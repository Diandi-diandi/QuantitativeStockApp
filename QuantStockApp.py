''' '
Quantitative Stock App -- Controller

'''
import InfoSet # api_key, pwd
from datetime import datetime, timedelta
from dateutil import rrule
from time import sleep
from calendar import monthrange
import QuantStockApp_Model as model
import QuantStockApp_View as view
from PyQt5 import QtWidgets, QtGui, QtCore
from sys import exit

class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.ui = view.Ui_MainWindow()
        self.ui.setupUi(self)
        self.Desclaimer()

        # set db control model
        self.get_model = model.GetData()
        self.update_model = model.Update(InfoSet.api_key)
        self.strategy_model = model.Strategy()
        self.all_db = {'daily_db' : ['kbar', 'institution', 'pbr', 'foreign_inv'],
        'monthly_db':['revenue'],
        'quarter_db':['fin_stat', 'bs']}
        self.latest_update = '0'

        # set action for check latest data / update data
        self.ui.action_update_data.triggered.connect(self.UpdateData)

        # strategy options control
        self.SetComboboxClassify()
        self.ui.combobox_classify.currentTextChanged[str].connect(self.SetComboboxStrategy) # update strategy by choosen type
        self.ui.combobox_strategy.currentTextChanged[str].connect(self.SetChoosenStrategyContent) # set choosen name showing above and tooltip to show content
        self.ui.btn_execute_quant.clicked[bool].connect(self.SetTableQuant)

        # stock searching results   # searching -> get stock info -> build table
        self.ui.button_search.clicked[bool].connect(self.SetTableSearch)

        # update fundamental/chips tables
        self.ui.tab_fundamental.currentChanged[int].connect(self.SetAllTable)
        self.ui.tab_chip.currentChanged[int].connect(self.SetAllTable)

    def Desclaimer(self):
        QtWidgets.QMessageBox.information(None, '免責聲明',\
            '本軟體內容為台股之客觀數據，本軟體對數據之正確性不負任何責任，'\
            '本軟體所提供之數據不涉及個股操作建議、推薦、行銷，投資人應審慎評估可能之交易風險，並自負盈虧。',\
            QtWidgets.QMessageBox.Ok, QtWidgets.QMessageBox.Ok)

#=== update =======================================================================

    def __Manager_Login(self):
        while True:
            res = self.ui.dialog_manager_login.exec_()
            if res == QtWidgets.QDialog.Accepted and self.ui.dialog_manager_login.lineedit_pwd.text() != InfoSet.sys_pwd:
                continue
            elif self.ui.dialog_manager_login.lineedit_pwd.text() == InfoSet.sys_pwd:
                return True
            else: return False

    def UpdateData(self):
        ### check latest ##############################################################
        res = QtWidgets.QMessageBox.information(None, '準備檢測更新',
                '檢查資料可能花費數分鐘，檢查過程中請勿任意關閉程式',\
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
        if res == QtWidgets.QMessageBox.Yes: # start checking latest
            self.ui.progressbar_update.show() # execute progress # updating
            thread = Thread_Check_Latest() # open update thread
            thread.signal_check.connect(self.ui.progressbar_update.setValue) # connect signal to progressbar
            self.latest_update = thread.run(self.all_db) # return a date dict for 3 freq
            sleep(0.5)
            self.ui.progressbar_update.close() # close progress

            # show result and ask for updating
            date_res = [ x+': '+datetime.strptime(self.latest_update[x], '%Y%m%d').strftime('%Y/%m/%d') for x in self.latest_update]
            result_text = '\n'.join(date_res)
            res = QtWidgets.QMessageBox.information(None, '檢查完成', '最新資料\n' + result_text + '\n\n是否登入並繼續進行更新?\n'
                    '*更新資料可能花費數分鐘，更新過程中請勿任意關閉視窗',
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.Yes)
            if res == QtWidgets.QMessageBox.No:
                QtWidgets.QMessageBox.warning(None, '更新結果', '已取消更新')
                return
        else: # res == QtWidgets.QMessageBox.No
            QtWidgets.QMessageBox.warning(None, '檢查結果', '已取消檢查')
            return


        ### update data ##############################################################
        login_ok = self.__Manager_Login()
        conn_ok = model.CheckConnection() # check internet connection
        if res == QtWidgets.QMessageBox.Yes and login_ok and conn_ok: # start updating
            self.ui.progressbar_update.show()
            thread_update = Thread_Update_Data()
            thread_update.signal_update.connect(self.ui.progressbar_update.setValue)
            finished, self.latest_update = thread_update.run(self.latest_update, self.all_db)
            sleep(0.5)
            self.ui.progressbar_update.close()

            self.AllClear() # clear all table
            
            if finished:
                date_res = [ x+': '+datetime.strptime(self.latest_update[x], '%Y%m%d').strftime('%Y/%m/%d') for x in self.latest_update]
                result_text ='\n'.join(date_res)
                QtWidgets.QMessageBox.information(None, '更新完成', '資料庫更新完成\n' + '最新資料\n' + result_text)

            else:
                QtWidgets.QMessageBox.warning(None, '更新失敗', '未知錯誤，請重新嘗試')
        elif not conn_ok:
            QtWidgets.QMessageBox.warning(None, '連線失敗', '未偵測到網路連線，請重新嘗試!')
        elif not login_ok:
            QtWidgets.QMessageBox.warning(None, '登入失敗', '已取消更新')

#=== combobox =======================================================================

    def BuildCombobox(self, box:QtWidgets.QComboBox, data:list, disabled:list=[]):
        '''
        add [data] in the given [box]
        [disabled] is a list to record which item is disabled to click
        '''
        for i in range(len(data)):
            item = QtGui.QStandardItem()
            item.setBackground(QtGui.QColor('white'))
            item.setFont(self.ui.font_general)
            item.setText(str(data[i]))
            if i in disabled:
                item.setEnabled(False)
            box.model().appendRow(item)

    def SetComboboxClassify(self):
        #set combobox_classify
        classify_type = ['策略分類', '所有', '基本面', '技術面', '籌碼面', '其他']
        self.BuildCombobox(self.ui.combobox_classify, classify_type, disabled=[0])

    def SetComboboxStrategy(self):
        class_in_ch = [ self.ui.combobox_classify.itemText(i) for i in range(1, self.ui.combobox_classify.count())] # class in Chinese # 1 to len(rows)
        class_in_en = ['', 'fund', 'tech', 'chip', 'others'] # class in English # corresponding to col--'type' in database
        choosen_type = self.ui.combobox_classify.currentText() # get choosen text
        choosen_type = class_in_en[ class_in_ch.index(choosen_type) ]

        # query strategies of choosen type
        StrategyList = self.get_model.getData('strategy', cond=[ f'type like "%{choosen_type}%"' ] )
        StrategyList = ['未選擇'] + [ x[0] for x in StrategyList] # get strategy names

        self.ui.combobox_strategy.clear() # remove all items
        self.BuildCombobox(self.ui.combobox_strategy, StrategyList, disabled=[0])

#=== table ===================================================================

    def BuildTable(self, table:QtWidgets.QTableWidget, data:list, col_draw:list=[], draw_by_row:bool=True,color_index:int=None, connect:bool=False):
        '''
        add [data:list] in the given [table:QTable]
        column indexes in [col_draw:list] will be drawn color
        if [draw_by_row:bool] is True, [color_index:int] must be set as an integer
        [color_index:int] is a column index be referenced to draw color
        if [connect:bool] is True, all rows will have signal-connect
        '''
        if data == []: # del all items on the table
            self.ui.table_search.setRowCount(0)
            return
        row_num = len(data)
        col_num = len(data[0])
        for i in range(row_num):
            table.insertRow(i)
            table.setRowCount(i+1)
            for j in range(col_num):
                item = QtWidgets.QTableWidgetItem(str(data[i][j]))
                item.setFont(self.ui.font_bigger)
                # draw color
                if j in col_draw:
                    color_ele = data[i][color_index] if draw_by_row else data[i][j]
                    if color_ele == '--':
                        item.setForeground(QtGui.QColor('gray'))
                    elif color_ele[0]=='-':
                        item.setForeground(QtGui.QColor('green'))
                    elif color_ele in ['0.0%', '0']:
                        item.setForeground(QtGui.QColor('orange'))
                    else:
                        item.setForeground(QtGui.QColor('red'))
                else:
                    item.setForeground(QtGui.QColor('white'))
                table.setItem(i, j, item)
        if connect:
            table.itemClicked.connect(self.SetAllTable)

    def SetTableQuant(self):
        choosen_strat = self.ui.combobox_strategy.currentText()
        self.ui.progressbar_quanting.show()
        res = self.get_model.getData('strategy', cond=[f'name="{choosen_strat}"'])
        if res == []:
            self.ui.progressbar_quanting.close()
            QtWidgets.QMessageBox.warning(None, '執行錯誤', '請重新選擇量化交易策略')
        else:
            thread_quant = Thread_Quanting()
            thread_quant.signal_quanting.connect(self.ui.progressbar_quanting.setValue)
            trade_date, sidlist = thread_quant.run(choosen_strat)
            self.ui.progressbar_quanting.close()
            QtWidgets.QMessageBox.information(None, '策略執行結果',\
                                            '執行日期： %s\n'%(datetime.strptime(trade_date, '%Y%m%d').strftime('%Y/%m/%d')) +
                                            '[%s] 共篩選到 [%s] 檔股票\n'%(choosen_strat, str(len(sidlist))) +
                                            '按下確認鍵稍待幾秒將為您顯示符合條件之個股\n\n' +
                                            '注意：若非預期的執行日期，請將資料更新後再重新執行策略')
            data = self.GetStockInfo(sidlist)
            self.BuildTable(self.ui.table_quant, data, list(range(5)), color_index=3, connect=True)
            self.ui.tabwidget_group.setCurrentIndex(0)

    def SetTableSearch(self):
        text = self.ui.lineedit_search.text()
        res_no = self.get_model.getData('stockno', cond=[ f'no like "%{text}%"' ] )
        res_name = self.get_model.getData('stockno', cond=[ f'name like "%{text}%"' ])
        res = res_no + res_name # union of two querying results
        res = [x[0] for x in res]
        data = self.GetStockInfo(res)
        self.BuildTable(self.ui.table_search, data, list(range(5)), color_index=3, connect=True)
        self.ui.tabwidget_group.setCurrentIndex(1)

    def SetTableRevenue(self, sid):
        data_len = 36  # for latest 36 months
        res = self.get_model.getData('revenue', sid = sid, daylen=data_len)
        if res == []:
            return

        # calculate ratio
        revenue = [round(int(x[1])/1000000, 2) for x in res] #  in normal order
        revenue.reverse()
        dif = model.diff(revenue) # diff[0] = revenue[1]-revenue[0]
        ratio = ['--']
        for i in range(len(dif)):
            rev = float(revenue[i])
            ratio += [ str(round(float(dif[i])*100/rev, 2))+'%'] if rev != 0 else ['--']
        ratio.reverse()

        # clean data
        data = []
        for i in range(len(res)):
            month = datetime.strptime(res[i][0], '%Y%m').strftime('%Y-%m')
            close = self.get_model.getData('kbar', sid=sid, cond=[f'date like "%{res[i][0]}%"'])
            close = close[0][6] if close!=[] else '--'
            data.append([month, format(int(res[i][1]), ',d'), ratio[i], close])
        self.BuildTable(self.ui.table_revenue, data, [1,2], color_index=2)

    def SetTablePBR(self, sid):
        data_len = 20  # for latest 20 days
        res = self.get_model.getData('pbr', sid=sid, daylen=data_len)
        if res == []:
            return

        data = []
        for row in res:
            kbar = self.get_model.getData('kbar', sid=sid, cond=[f'date="{row[0]}"'])
            close = kbar[0][6] if kbar != [] else '--'
            row.append(close)
            data.append(row)
        self.BuildTable(self.ui.table_pbr, data)

    def SetTableEPS(self, sid):
        data_len = 12  # for latest 12 quarter
        res_finstat = self.get_model.getData('fin_stat', sid=sid, daylen=data_len)
        if res_finstat == [] and res_bs == []:
            return
        data = []
        for i in range( len(res_finstat) ):
            qt = res_finstat[i][0]
            income =int(res_finstat[i][-1])
            res_bs = self.get_model.getData('bs', sid=sid, cond=[f' date = "{qt}" '])
            roe = round(income/int(res_bs[0][-1]), 2) if res_bs != [] and res_bs[0][-1]!='0' else 0
            data.append([datetime.strptime(res_finstat[i][0], '%Y%m%d').strftime('%Y-%m-%d'), res_finstat[i][1], roe])

        self.BuildTable(self.ui.table_eps, data)

    def SetTableInstitution(self, sid):
        data_len = 30
        res = self.get_model.getData('institution', sid=sid, daylen=data_len)
        if res == []:
            return

        data = []
        for row in res:
            volume = [int(x) for x in row[1:]]
            total = format(sum(volume), ',d')
            data.append([datetime.strptime(row[0], '%Y%m%d').strftime('%Y-%m-%d'), *[format(x, ',d') for x in volume], total])
            # [date, foreign_inv, inv_trust, self_dealer, total]

        self.BuildTable(self.ui.table_institution, data, list(range(1,5)), draw_by_row=False)

    def SetTableForeignInv(self, sid):
        data_len=30
        res = self.get_model.getData('foreign_inv', sid=sid, daylen=data_len)
        if res == []:
            return

        # calculate diff
        inv = [ x[1] for x in res ] # in normal order
        inv.reverse()
        dif = model.diff(inv)
        dif = ['--'] + [ str(round(x, 2)) for x in dif]   
        dif.reverse()

        data = []
        for i in range(len(res)):
            date = datetime.strptime(res[i][0], '%Y%m%d').strftime('%Y-%m-%d')
            data.append([date, str(res[i][1])+'%', str(dif[i])+'%', format(int(res[i][-1]), ',d')])

        self.BuildTable(self.ui.table_foreign_inv, data, [2], draw_by_row=False)

    def SetAllTable(self):
        if self.ui.table_quant.currentItem() == None and self.ui.table_search.currentItem() == None:
            return
        else:
            self.ui.progressbar_loading.show()
            loading = Thread_Loading(self)
            loading.signal_loading.connect(self.ui.progressbar_loading.setValue)
            loading.run()
            self.ui.progressbar_loading.close()

#=== ploting ==========================================================================

    def SetKbarPlot(self, sid):
        sid, name = sid.split(' ')
        self.ui.label_current_stock.setText('〔' + sid + '〕' + name)
        if sid.isdigit():
            kbar = self.get_model.getData('kbar', sid=sid, daylen=60)
            if kbar != []:
                self.img = model.KBar_Fig()
                self.img.fig.clf()
                self.img.KBarPlot(kbar)
                self.ui.layout_tech_plot.addWidget(self.img, 0, 0)
        price = self.get_model.getData('kbar', sid=sid)[0]
        spread = price[7]
        price = [datetime.strptime(price[0], '%Y%m%d').strftime('%Y/%m/%d'), *price[3:7], format(int(price[1]), ',d')]
        title=['時', '開', '高', '低', '收', '量']
        text_price = ''
        for i in range(6):
            text_price += title[i] + ' ' + str(price[i]) + '  '

        self.ui.label_price.setText(text_price)
        if spread > 0:
            self.ui.label_price.setStyleSheet('color: rgb(255, 0, 0);')
        elif spread == 0:
            self.ui.label_price.setStyleSheet('color: orange;')
        else:
            self.ui.label_price.setStyleSheet('color: rgb(0, 255, 0);')

#=== others ==========================================================================

    def GetStockInfo(self, sidlist):
        data = []
        for sid in sidlist:
            info = self.get_model.getData('stockno', cond=[f'no = "{sid}"'])
            kbar = self.get_model.getData('kbar', sid=sid, daylen=2) # row[0]=sid # get 2 days kbar
            if kbar == []:
                continue
            try: 
                ratio = str(round(kbar[0][7]*100/kbar[-1][6], 2)) + '%' # spread_0/close_1
            except ZeroDivisionError: # close_1 == 0
                ratio = '--'
            temp = [' '.join(info[0][:2]), *kbar[0][6:8], ratio, format(int(kbar[0][1]), ',d')]
            data.append(temp)
        return data

    def SetChoosenStrategyContent(self):
        strategy_name = self.ui.combobox_strategy.currentText()
        content = self.get_model.getData('strategy', cond=[ f'name = "{strategy_name}"' ])
        
        self.ui.label_choosen_strategy.setText('選股策略：  %s'%(strategy_name,) )
        if content!= []:
            self.ui.label_question_mark.setToolTip(content[0][1]) # content = [['name', 'content']]
        else :
            self.ui.label_question_mark.setToolTip('請選擇策略')

    def AllClear(self):
        self.ui.table_quant.setRowCount(0)
        self.ui.table_search.setRowCount(0)
        # self.ui.layout_tech_plot.removeWidget(self.img)
        self.ui.table_revenue.setRowCount(0)
        self.ui.table_pbr.setRowCount(0)
        self.ui.table_institution.setRowCount(0)
        self.ui.table_foreign_inv.setRowCount(0)


class Thread_Check_Latest(QtCore.QThread):
    signal_check = QtCore.pyqtSignal([str, int, int, int, int])
    def __init__(self):
        super(Thread_Check_Latest, self).__init__()
        self.get_model = model.GetData()

    def run(self, all_db:dict):
        freq_text = {'daily_db':'日資料', 'monthly_db':'月資料', 'quarter_db':'季資料'} # convert freq text in chinese
        latest_date = {} # check and record the latest date of each freq
        for freq in all_db: # loop for db frequency
            time_temp = '0'
            text_temp = freq_text[freq]
            db_temp = all_db[freq]
            for db in db_temp: # loop for databases
                i = db_temp.index(db)
                all_table = self.get_model.getTableList(db)
                for sid in all_table: # loop for all table
                    j = all_table.index(sid)
                    data = self.get_model.getData(db, sid=sid) # daylen = 1
                    new_t = data[0][0] if data != [] else '0'
                    time_temp = new_t if new_t > time_temp else time_temp
                    self.signal_check.emit(text_temp + ' 更新檢查中', i+1, len(db_temp), j+1, len(all_table))

            if len(time_temp) == 6: # convert to the last day of the respective month
                time_temp = datetime.strptime(time_temp, '%Y%m')
                time_temp = datetime(time_temp.year, time_temp.month, monthrange(time_temp.year, time_temp.month)[-1])
                time_temp = time_temp.strftime('%Y%m%d')
            latest_date[text_temp] = time_temp
        return latest_date

class Thread_Update_Data(QtCore.QThread):
    signal_update = QtCore.pyqtSignal([str, int, int, int, int])

    def __init__(self):
        super(Thread_Update_Data, self).__init__()
        self.get_model = model.GetData()
        self.download_model = model.DownloadData(InfoSet.api_key)
        self.store_model = model.StoreData()

    def run(self, latest_date:dict, all_db:dict):
        freq_text = {'daily_db':'日資料', 'monthly_db':'月資料', 'quarter_db':'季資料'}
        all_stockno = self.get_model.getData('stockno') # get all stockno from other_info.db
        all_stockno = [x[0] for x in all_stockno]

        for freq in all_db: # loop for freq
            rrule_freq = rrule.DAILY if freq=='daily_db' else rrule.MONTHLY
            db_temp = all_db[freq]
            date_temp = latest_date[freq]
            start_date = datetime.strptime(date_temp, '%Y%m%d') + timedelta(days=1) # start date
            freq_temp = freq_text[freq]
            for d in rrule.rrule(freq=rrule_freq, dtstart=start_date, until=datetime.today()): # daily loop # datetime format
                if d.month % 3 != 0 and freq == 'quarter_db': # update quarter db only in month = 3/6/9/12
                    continue
                for db in db_temp: # loop for all databases
                    sid_list, data = self.download_model.from_Finmind(db, start=d.strftime('%Y%m%d')) # no given sid # dowload for update
                    if data == []:
                        continue

                    for sid in all_stockno: # loop for all stockno in other_info
                        if sid in sid_list:
                            self.store_model.storeData(db, sid, [ data[sid_list.index(sid)] ])
                            self.signal_update.emit(d.strftime('%Y/%m/%d')+' 資料更新中',\
                                                    db_temp.index(db)+1, len(db_temp),\
                                                    all_stockno.index(sid)+1, len(all_stockno))
                latest_date[freq_temp] = d.strftime('%Y%m%d')
        return True, latest_date

class Thread_Loading(QtCore.QThread):
    signal_loading = QtCore.pyqtSignal([str, bool])

    def __init__(self, win):
        super(Thread_Loading, self).__init__()
        self.table_fund = ['營收收入成長', '殖利率 / pbr / per', 'EPS / ROE']
        self.table_chip = ['三大法人買賣超', '外資持股比例']

        self.win = win

    def run(self):
        index_tab_find = self.win.ui.tabwidget_group.currentIndex()
        if index_tab_find == 0 :
            sid_name = self.win.ui.table_quant.currentItem().text()
        elif index_tab_find == 1:
            sid_name = self.win.ui.table_search.currentItem().text()
        self.signal_loading.emit('K線圖', False)
        self.win.SetKbarPlot(sid_name)
        sid, name = sid_name.split(' ')
        fund_index = self.win.ui.tab_fundamental.currentIndex()
        chip_index = self.win.ui.tab_chip.currentIndex()
        self.signal_loading.emit('其他數據', False)

        if fund_index == 0:
            self.win.SetTableRevenue(sid)
            self.signal_loading.emit('營收收入成長', False)
        elif fund_index == 1:
            self.win.SetTablePBR(sid)
            self.signal_loading.emit('殖利率 / pbr / per', False)
        elif fund_index == 2:
            self.win.SetTableEPS(sid)
            self.signal_loading.emit('EPS / ROE', False)
        
        if chip_index == 0:
            self.win.SetTableInstitution(sid)
            self.signal_loading.emit('三大法人買賣超', False)
        elif chip_index == 1:
            self.win.SetTableForeignInv(sid)
            self.signal_loading.emit('外資持股比例', False)

        self.signal_loading.emit('', True)

class Thread_Quanting(QtCore.QThread):
    signal_quanting = QtCore.pyqtSignal([str, int, int])

    def __init__(self):
        super(Thread_Quanting, self).__init__()
        # store function as str # using eval()
        self.strategy_dict = {'均線策略':'MAcross',
                            'KD指標':'KD',
                            '布林通道策略--上界':'BB_Upper',
                            '布林通道策略--下界':'BB_Lower',
                            'PBR/ROE':'pbr_roe',
                            '殖利率/PER':'diviend_per',
                            '外資買超':'foreign_overbuy'}
        self.get_model = model.GetData()
        self.strategy_model = model.Strategy()

    def run(self, choosen_strat):
        f = self.strategy_dict[choosen_strat]
        f = eval("self.strategy_model." + f) # function evaluate
        all_stockno = self.get_model.getData('stockno') # test all stockno
        sidlist = [] # collect sid which pass the strategy
        trading_date = '0' # record the latest date as trading date
        for i in range(len(all_stockno)):
            sid = all_stockno[i][0]
            good, latest_date = f(sid)
            sidlist += [sid] if good else []
            trading_date = latest_date if latest_date > trading_date else trading_date
            self.signal_quanting.emit(choosen_strat, i, len(all_stockno))
        if trading_date == '0':
            trading_date = datetime.today().strftime('%Y%m%d')

        return trading_date, sidlist


if __name__ == '__main__':
    app = QtWidgets.QApplication([])
    mainwindow = MainWindow()
    mainwindow.show()
    exit(app.exec_())
