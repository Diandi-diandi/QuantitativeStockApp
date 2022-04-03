'''
Quantitative Stock App -- View

'''
from tkinter.ttk import Style
from PyQt5 import QtCore, QtGui, QtWidgets
from os import path, chdir
import pic
from base64 import b64decode # base64 to bytes
from io import  BytesIO
from PIL import Image, ImageQt
chdir(path.dirname(path.abspath(__file__)))

class Ui_MainWindow(object):

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.setWindowTitle('量化交易看盤程式')
        desktop = QtWidgets.QApplication.desktop()
        MainWindow.setFixedSize(desktop.width(), desktop.height()-30)
        MainWindow.showMaximized()
        MainWindow.setStyleSheet("background-color: rgb(0, 0, 0);")
        self.font_small = QtGui.QFont('新細明體', 9, QtGui.QFont.Bold)
        self.font_general = QtGui.QFont('新細明體', 11, QtGui.QFont.Bold)
        self.font_bigger = QtGui.QFont('新細明體', 14, QtGui.QFont.Bold)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        MainWindow.setCentralWidget(self.centralwidget)

        self. btn_style_str = '''QPushButton{
                                    background-color: rgb(255, 255, 255);
                                    color: rgb(0, 0, 0);
                                    border-radius: 10px;
                                    border: 3px solid rgb(85, 170, 255);
                                }

                                QPushButton::hover{
                                    background-color: rgb(85, 170, 255);
                                    color: rgb(255, 255, 255);
                                }
                                '''

        self.frame_options = QtWidgets.QFrame(self.centralwidget)
        self.frame_options.setGeometry(QtCore.QRect(0, 0, int(desktop.width()*1.5/7), int(desktop.height()*2/3)) )
        self.SetFrameStyle(self.frame_options)
        self.SetFrame_Options()

        self.tabwidget_group = QtWidgets.QTabWidget(self.centralwidget)
        self.tabwidget_group.setGeometry(QtCore.QRect(int(desktop.width()*1.5/7), 0, int(desktop.width()*1.5/7), int(desktop.height()*2/3)))
        self.SetTabStyle(self.tabwidget_group)
        self.SetTab_Group()
        
        self.frame_image = QtWidgets.QFrame(self.centralwidget)
        self.frame_image.setGeometry(QtCore.QRect(int(desktop.width()*3/7), 0, int(desktop.width()*4/7), int(desktop.height()*2/3)) )
        self.SetFrameStyle(self.frame_image)
        self.SetFrame_Image()

        self.tab_fundamental = QtWidgets.QTabWidget(self.centralwidget)
        self.tab_fundamental.setGeometry(QtCore.QRect(0, int(desktop.height()*2/3), int(desktop.width()/2), int(desktop.height()/3) ))
        self.SetTabStyle(self.tab_fundamental)
        self.SetTab_Fundamental()

        self.tab_chip = QtWidgets.QTabWidget(self.centralwidget)
        self.tab_chip.setGeometry(QtCore.QRect(int(desktop.width()/2), int(desktop.height()*2/3), int(desktop.width()/2), int(desktop.height()/3) ))
        self.SetTabStyle(self.tab_chip)
        self.SetTab_Chip()
    
        self.menubar = QtWidgets.QMenuBar(MainWindow)
        self.menubar.setStyleSheet('background-color: rgb(150, 150, 150);\n'
                                    'color: rgb(0, 0, 0);')
        self.SetMenuBar()
        menushow = QtWidgets.QMenu(self.menubar)
        MainWindow.setMenuBar(self.menubar)

        # other dialog window
        self.dialog_manager_login = LoginDialog()
        self.progressbar_update = ProgressBar_Update()
        self.progressbar_loading = ProgressBar_Loading()
        self.progressbar_quanting = ProgreeBar_Quanting()

### style of Qtwidgets
    def SetFrameStyle(self, frame):
        frame.setFrameShape(QtWidgets.QFrame.Box)
        frame.setFrameShadow(QtWidgets.QFrame.Raised)
        frame.setLineWidth(0)
        frame.setMidLineWidth(5)

    def SetTabStyle(self, tab):
        tab.setTabShape(QtWidgets.QTabWidget.Triangular) # QTabWidget::Rounded(default)
        tab.setFont(self.font_general)
        tab.setStyleSheet('color: rgb(255, 255, 255);')

    def SetObjectStyle(self, obj, geo:list, **kwargs):
        # type(obj) in [QLabel, QPushButton, QComboBox]
        font_size = kwargs.pop('font_size') if 'font_size' in kwargs else None
        text = kwargs.pop('text') if 'text' in kwargs else None
        style = kwargs.pop('style') if 'style' in kwargs else None

        # setting
        obj.setGeometry(QtCore.QRect(*geo))
        if font_size:
            obj.setFont(QtGui.QFont('新細明體', font_size, QtGui.QFont.Bold))
        if text:
            obj.setText(text)
        if style:
            obj.setStyleSheet(style)

    def SetTableStyle(self, table:QtWidgets.QTableWidget, geo:list, font_size:int, colnums:int):
        table.setGeometry(QtCore.QRect(*geo))
        table.setColumnCount(colnums)
        table.setFont(QtGui.QFont('新細明體', font_size, QtGui.QFont.Bold))
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setStyleSheet('color: rgb(255, 255, 255);')
        table.horizontalHeader().setStyleSheet('QHeaderView::section { background-color: rgb(12, 12, 255); }')

    def SetTableItemStyle(self, table:QtWidgets.QTableWidget, index:int, text:str, width:int):
        temp = QtWidgets.QTableWidgetItem(text)
        table.setHorizontalHeaderItem(index, temp)
        table.setColumnWidth(index, width)

### set blocks
    def SetMenuBar(self):
        self.menu_set =  self.menubar.addMenu('設定資料')
    
        self.action_update_data = QtWidgets.QAction('檢查更新/更新資料')
        self.menu_set.addAction(self.action_update_data)

        self.menu_set.addSeparator()

        self.action_quit = QtWidgets.QAction('結束程式')
        self.action_quit.setShortcut('Ctrl+Q')
        self.action_quit.triggered.connect(QtWidgets.qApp.quit)
        self.menu_set.addAction(self.action_quit)

    def SetFrame_Options(self):

        self.label_title_template = QtWidgets.QLabel(self.frame_options)
        self.SetObjectStyle(self.label_title_template, [ (self.frame_options.width()-230)//2, 20, 230, 30], font_size = 16,\
                            text = '>>量化交易選股<<', style = 'color: rgb(255, 255, 255);\n' + 'background-color: rgb(0, 0, 255);')

        self.label_title_strategy = QtWidgets.QLabel(self.frame_options)
        self.SetObjectStyle(self.label_title_strategy, [20, 80, 200, 30], font_size = 11, text = '▼ 選擇量化策略', style = 'color: rgb(255, 255, 255);\n')

        self.combobox_classify = QtWidgets.QComboBox(self.frame_options)
        self.SetObjectStyle(self.combobox_classify, [30, 130, 150, 30], font_size = 11, style = "background-color: rgb(255, 255, 255);")

        self.combobox_strategy = QtWidgets.QComboBox(self.frame_options)
        self.SetObjectStyle(self.combobox_strategy, [30, 190, 250, 30], font_size = 11, style = "background-color: rgb(255, 255, 255);")

        self.label_question_mark = QtWidgets.QLabel(self.frame_options)
        self.SetObjectStyle(self.label_question_mark, [320, 300, 30, 30], font_size = 9, style = 'QLabel:hover{color: rgb(0, 0, 0);}')
        self.label_question_mark.setMouseTracking(True)
        # convert str to pixmap
        byte = b64decode(pic.question_mark)
        img = BytesIO(byte)
        qimg = ImageQt.ImageQt(Image.open(img))
        pixmap_question_mark = QtGui.QPixmap.fromImage(qimg)
        self.label_question_mark.setScaledContents(True)
        self.label_question_mark.setPixmap(pixmap_question_mark)

        self.label_choosen_strategy = QtWidgets.QLabel(self.frame_options)
        self.SetObjectStyle(self.label_choosen_strategy, [20, 300, 300, 30], font_size = 11, text = '選股策略：  No selection', style = 'color: rgb(255, 255, 255);')

        self.btn_execute_quant = QtWidgets.QPushButton(self.frame_options)
        self.SetObjectStyle(self.btn_execute_quant, [ (self.frame_options.width()-80)//2, 350, 80, 30], font_size = 9,\
                            text = '執行策略', style = self.btn_style_str)

    def SetTab_Group(self):

        self.table_quant = QtWidgets.QTableWidget(self.tabwidget_group)
        self.SetTableStyle(self.table_quant, [0, 0, self.tabwidget_group.size().width(), self.tabwidget_group.size().height() ], 14, 5)

        self.widget_search = QtWidgets.QWidget(self.tabwidget_group)
        self.widget_search.setGeometry(QtCore.QRect(0, 0, self.tabwidget_group.size().width(), self.tabwidget_group.size().height()))

        self.lineedit_search = QtWidgets.QLineEdit(self.widget_search)
        self.SetObjectStyle(self.lineedit_search, [10, 5, self.widget_search.size().width()-120, 30], font_size = 11,\
                            style = 'background-color: rgb(255, 255, 255);\n' + 'color: rgb(0, 0, 0);\n' + 'border-radius: 15px;')
        self.lineedit_search.setPlaceholderText('請輸入股票代號或名稱')

        self.button_search = QtWidgets.QPushButton(self.widget_search)
        self.SetObjectStyle(self.button_search, [ self.widget_search.size().width()-90, 5, 70, 30], font_size = 11,\
                            text = '搜尋', style = self.btn_style_str)

        self.table_search = QtWidgets.QTableWidget(self.widget_search)
        self.SetTableStyle(self.table_search, [0, 40, self.widget_search.size().width(), self.widget_search.size().height()-40 ], 14, 5)

        # set table item
        title_list = ['商品', '收盤價', '漲跌', '幅度', '交易量(股)']
        width_ratio = [2.5, 4, 5, 4, 3]
        for i in range(5):
            self.SetTableItemStyle(self.table_quant, i, title_list[i], self.table_quant.size().width()//width_ratio[i])
            self.SetTableItemStyle(self.table_search, i, title_list[i], self.table_search.size().width()//width_ratio[i])
        
        self.tabwidget_group.addTab(self.table_quant, '策略群組')
        self.tabwidget_group.addTab(self.widget_search, '個股報價')

    def SetFrame_Image(self):

        self.label_current_stock = QtWidgets.QLabel(self.frame_image)
        self.SetObjectStyle(self.label_current_stock, [5, 10, 500, 30], font_size = 16, text = '〔      〕', style = 'color: rgb(255, 255, 255);')

        self.label_price = QtWidgets.QLabel(self.frame_image)
        self.SetObjectStyle(self.label_price, [20, 50, 700, 30], font_size = 14, style = 'color: rgb(255, 255, 255);')

        self.button_add_stock = QtWidgets.QPushButton(self.frame_image)
        self.SetObjectStyle(self.button_add_stock, [ self.frame_image.width()-140, 20, 80, 30],font_size = 11, text = '加入群組',\
                            style = self.btn_style_str)

        self.widget_plot = QtWidgets.QWidget(self.frame_image)
        self.widget_plot.setGeometry(QtCore.QRect(5, 90, self.frame_image.width()-10, self.frame_image.height()-90))
        self.tabwidget_plot = QtWidgets.QTabWidget(self.widget_plot)
        self.tabwidget_plot.setGeometry(QtCore.QRect(0, 0, self.widget_plot.size().width(), self.widget_plot.size().height()))
        self.SetTabStyle(self.tabwidget_plot)
        widget_tech_plot = QtWidgets.QWidget(self.tabwidget_plot)
        self.layout_tech_plot = QtWidgets.QGridLayout(widget_tech_plot)
        self.tabwidget_plot.addTab(widget_tech_plot, '技術分析')

    def SetTab_Fundamental(self):

        self.table_revenue = QtWidgets.QTableWidget(self.tab_fundamental)
        self.SetTableStyle(self.table_revenue, [0, 0, self.tab_fundamental.size().width(), self.tab_fundamental.size().height()], 14, 4)
        col_revenue = ['月份', '營業收入(元)', '月成長率', '月收盤價']
        for i in range(len(col_revenue)):
            self.SetTableItemStyle(self.table_revenue, i, col_revenue[i], self.table_revenue.size().width()//len(col_revenue))
        self.tab_fundamental.addTab(self.table_revenue, '月收益表')

        self.table_pbr = QtWidgets.QTableWidget(self.tab_fundamental)
        self.SetTableStyle(self.table_pbr, [0 ,0, self.tab_fundamental.size().width(), self.tab_fundamental.size().height()], 14, 5)
        col_pbr = ['日期', '殖利率', '本益比(PER)', '股價淨值比(PBR)', '收盤價']
        for i in range(len(col_pbr)):
            self.SetTableItemStyle(self.table_pbr, i, col_pbr[i], self.table_pbr.size().width()//len(col_pbr))
        self.tab_fundamental.addTab(self.table_pbr, '殖利率 / PER / PBR')
        
        self.table_eps = QtWidgets.QTableWidget(self.tab_fundamental)
        self.SetTableStyle(self.table_eps, [0 ,0, self.tab_fundamental.size().width(), self.tab_fundamental.size().height()], 14, 3)
        col_eps = ['季度', '每股盈餘(EPS)', '股東權益報酬率(ROE)']
        for i in range(len(col_eps)):
            self.SetTableItemStyle(self.table_eps, i, col_eps[i], self.table_eps.size().width()//len(col_eps))
        self.tab_fundamental.addTab(self.table_eps, 'EPS / ROE')

    def SetTab_Chip(self):

        col_institution = ['日期', '外資(股)', '投信(股)', '自營商(股)', '總計(股)']
        col_num = len(col_institution)
        self.table_institution = QtWidgets.QTableWidget(self.tab_chip)
        self.SetTableStyle(self.table_institution, [0, 0, self.tab_chip.size().width(), self.tab_chip.size().height()], 14, 5)
        for i in range(col_num):
            self.SetTableItemStyle(self.table_institution, i, col_institution[i], self.table_institution.size().width()//col_num)
        self.tab_chip.addTab(self.table_institution, '三大法人')

        col_foreign_inv = ['日期', '外資持股比例', '外資持股比例增減', '已發行股數(股)']
        col_num = len(col_foreign_inv)
        self.table_foreign_inv = QtWidgets.QTableWidget(self.tab_chip)
        self.SetTableStyle(self.table_foreign_inv, [0, 0, self.tab_chip.size().width(), self.tab_chip.size().height()], 14, 4)
        for i in range(col_num):
            self.SetTableItemStyle(self.table_foreign_inv, i, col_foreign_inv[i], self.table_foreign_inv.size().width()//col_num)
        self.tab_chip.addTab(self.table_foreign_inv, '外資持股比例')


class LoginDialog(QtWidgets.QInputDialog):
    def __init__(self, parent=None):
        super(LoginDialog, self).__init__(parent)
        self.setFixedSize(300, 200)
        self.setInputMode(0)
        self.setWindowTitle('管理者登入')
        self.setLabelText('')
        self.setStyleSheet('background-color: black;\
                            color: white;')
        self.frame_pwd = QtWidgets.QFrame(self)
        self.frame_pwd.setGeometry(QtCore.QRect(0, 0, 300, 200))

        self.lineedit_pwd = QtWidgets.QLineEdit(self.frame_pwd)
        self.lineedit_pwd.setPlaceholderText('請輸入密碼')
        self.lineedit_pwd.setGeometry(QtCore.QRect(50, 20, 200, 30))
        self.lineedit_pwd.setEchoMode(QtWidgets.QLineEdit.Password)

class ProgressBar(QtWidgets.QProgressBar): ## overwrite text format
    def text(self):
        return self.format()%(self.value, self.maximum())

class ProgressBar_Update(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(ProgressBar_Update, self).__init__(parent)
        font = QtGui.QFont('新細明體', 11)
        self.setFixedSize(300, 50)
        self.setWindowTitle('Update')
        self.setFont(font)

        self.label_title = QtWidgets.QLabel(self)
        self.label_title.setGeometry(QtCore.QRect(5, 5, 290, 20))
        self.label_title.setFont(font)
        self.label_title.setText('正在準備中...')

        self.setProgressBar()

    def setProgressBar(self):
        self.progressbar = QtWidgets.QProgressBar(self)
        self.progressbar.setGeometry(QtCore.QRect(5, 30, 290, 15))
        self.progressbar.setRange(0, 100)
        self.progressbar.setValue(0)
        self.progressbar.setAlignment(QtCore.Qt.AlignCenter)
        self.progressbar.setFormat('%v/%m')

    def setValue(self, state:str, cur_task:int=0, total_task:int=0, cur_sub_task:int=0, total_sub_task:int=0):
        self.label_title.setText('%s......%d/%d'%(state, cur_task, total_task))
        self.progressbar.setRange(0, total_sub_task)
        self.progressbar.setValue(cur_sub_task)
        QtWidgets.QApplication.processEvents() # refresh progressbar

class ProgressBar_Loading(QtWidgets.QDialog):
    def __init__(self):
        super(ProgressBar_Loading, self).__init__()
        font = QtGui.QFont('新細明體', 11)
        self.setFixedSize(300, 50)
        self.setWindowTitle('Data Loading')
        self.setFont(font)

        self.label_title = QtWidgets.QLabel(self)
        self.label_title.setGeometry(QtCore.QRect(5, 5, 180, 20))
        self.label_title.setFont(font)
        self.label_title.setText('資料載入中...')

        self.setProgressBar()

    def setProgressBar(self):
        self.progressbar = QtWidgets.QProgressBar(self)
        self.progressbar.setGeometry(QtCore.QRect(5, 30, 310, 15))
        self.progressbar.setRange(0, 0)

    def setValue(self, state:str='', finished:bool=False):
        if not finished:
            self.label_title.setText('%s 載入中...'%(state))
        else:
            self.label_title.setText('完成資料載入')
        QtWidgets.QApplication.processEvents() # refresh progressbar

class ProgreeBar_Quanting(QtWidgets.QDialog):
    def __init__(self):
        super(ProgreeBar_Quanting, self).__init__()
        font = QtGui.QFont('新細明體', 11)
        self.setFixedSize(300, 50)
        self.setWindowTitle('策略篩選中')
        self.setFont(font)

        self.label_title = QtWidgets.QLabel(self)
        self.label_title.setGeometry(QtCore.QRect(20, 5, 180, 20))
        self.label_title.setFont(font)
        self.label_title.setText('資料準備中...')

        self.setProgressBar()

    def setProgressBar(self):
        self.progressbar = QtWidgets.QProgressBar(self)
        self.progressbar.setGeometry(QtCore.QRect(5, 30, 290, 15))
        self.progressbar.setRange(0, 100)
        self.progressbar.setValue(0)
        self.progressbar.setAlignment(QtCore.Qt.AlignCenter)
        self.progressbar.setFormat('%v/%m')

    def setValue(self, strategy:str, cur_task:int=0, total_task:int=0):
        self.label_title.setText(strategy)
        self.progressbar.setRange(0, total_task)
        self.progressbar.setValue(cur_task)
        QtWidgets.QApplication.processEvents() # refresh progressbar


if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())

    