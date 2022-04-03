'''
Quantitative Stock App -- Model

# crawler
# GCP database
# quantitative strategy
# machine learning
'''

# database
from audioop import reverse
import sqlite3
# crawler/api
from numpy import array, average, reshape, diff
from pandas import DataFrame
import requests as re
from FinMind.data import DataLoader
from urllib.request import urlopen
from random import randint
from dateutil import rrule # iterate datetime daily/monthly
import json
from time import sleep
# plot
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.pyplot as plt
import mpl_finance as mpf
from talib import abstract
# machine learning
# import sklearn
# from sklearn import preprocessing
# from keras.models import Sequential
# from keras.layers.core import Dense, Dropout, Activation
# from keras.layers.recurrent import  LSTM
# import keras
# others
from os import chdir, path
from datetime import datetime, timedelta
from base64 import b64encode # bytes to base64

chdir(path.dirname(path.abspath(__file__)))

class DownloadData(object): # download data by crawler or finmind_api
    def __init__(self, api_key):
        self.api_key = api_key
        return

    def from_Crawler(self, dtype:str, sid :str='', start :str='', end :str=''):  

        if dtype == 'kbar':
            dt_start = datetime.strptime(start, '%Y%m%d')
            dt_end = datetime.today() if end=='' else datetime.strptime(end, '%Y%m%d')
            
            # download kbar data
            kbar = []
            for dt in rrule.rrule(rrule.MONTHLY, dtstart=dt_start, until=dt_end):
                dt = dt.strftime('%Y%m%d')

                try:
                    # get data from twse json
                    url = f"http://www.twse.com.tw/exchangeReport/STOCK_DAY?response=json&date={dt}&stockNo={sid}"
                    html=urlopen(url)
                    content=html.read().decode('utf-8')
                    jcontent=json.loads(content)
                    data=jcontent['data']
                except:
                    return []

                # delete incomplete info
                l = []
                for x in data:
                    if '--' in x:
                        l+=[data.index(x)] 
                for i in reversed(l):
                    del data[i]

                # get info
                data=[ (str(datetime.strptime(str(int(x[0][:3])+1911)+x[0][3:], '%Y/%m/%d').strftime('%Y%m%d')),
                    x[1].replace(',',''),
                    x[2].replace(',',''),
                    x[3].replace(',',''),
                    x[4].replace(',',''),
                    x[5].replace(',',''),
                    x[6].replace(',',''),
                    x[7].replace(',',''),
                    x[8].replace(',','') ) for x in data ]


                kbar += [x for x in data if x[0] >= start and x[0] <= end ]
                sleep(randint(8, 12))
            
            return kbar

    def from_Finmind(self, dtype:str, sid='', start:str = datetime.today().strftime('%Y%m%d')):
        # if [update=True], [sid='']
        # convert date format in kwargs
        start = datetime.strptime(start, '%Y%m%d').strftime('%Y-%m-%d')

        # func_name = { dtype : function_name }
        func_name = {'stockno':'taiwan_stock_info', 
                'kbar':'taiwan_stock_daily',
                'revenue':'taiwan_stock_month_revenue',
                'institution':'taiwan_stock_institutional_investors',
                'pbr':'taiwan_stock_per_pbr',
                'foreign_inv':'taiwan_stock_shareholding',
                'fin_stat':'taiwan_stock_financial_statement',
                'bs':'taiwan_stock_balance_sheet'
                }

        if dtype not in func_name:
            print('dtype error')
            return [[], []]

        if sid == '': # download data for update if no given sid 
            update = True
        else:
            update = False

        # api login # get data
        api = DataLoader()
        api.login_by_token(self.api_key)
        f =  eval('api.'+ func_name[dtype])
        df = f() if dtype == 'stockno' else f(stock_id = sid, start_date = start)
        if df.empty:
            return [[], []]


        # if (dtype in func_name) and (df is not empty) # clean data
        data = df.values.tolist()

        if dtype == 'stockno':
            # cols = [ industry_category : str,
            #           stock_id : str,
            #           stock_name : str,
            #           type : str]
            temp = [ x[1:3] + ['stock'] for x in data if x[0] not in ['ETF', 'Index', '大盤', '受益證券'] and x[3]=='twse']\
                    + [ x[1:3] + ['etf'] for x in data if x[0]=='ETF' and x[3]=='twse']\
                    + [ x[1:3] + ['indexes'] for x in data if x[0] in ['Index', '大盤'] and x[3]=='twse']

            val = []
            for x in temp: # drop repeated value
                if x not in val:
                    val += [x]
            all_stock = []

        elif dtype == 'kbar':
            # cols = [date:str,
            #       stock_id : str,
            #       Trading_Volume : int,
            #       Trading_money : int,
            #       open : float,
            #       max : float,
            #       min : flost,
            #       close : float,
            #       spread : float,
            #       Trading_turnover : float]

            all_stock = [x[1] for x in data] if update else None
            val = []
            for x in data:
                x.pop(1)
                x[0] = datetime.strptime(x[0], '%Y-%m-%d').strftime('%Y%m%d')
                val.append(x)

        elif dtype == 'revenue':
            # cols = [ date : str,
            #       stock_id : str,
            #       country : str,
            #       revenue : int,
            #       revenue_month : int,
            #       revenue_year : int ]

            all_stock = [x[1] for x in data] if update else None
            val = [[str(x[5])+str(x[4]).zfill(2), x[3]] for x in data] # [ year+month, revenue ]

        elif dtype == 'institution':
            # cols= [ date : str,
            #       stock_id : str,
            #       buy : int,
            #       name : str,
            #       sell : int ]
            indexes = sorted(list(set( [x[int(update)] for x in data] ))) # get and sort all index # index = { 0:date, 1:stock_id }
            val = []
            for name in indexes:
                info = [ x for x in data if x[int(update)]==name ] # int(update) = group index
                foreign_inv = sum([ int(x[2])-int(x[4]) for x in info if x[3]=='Foreign_Investor' or x[3]=='Foreign_Dealer_Self'])
                inv_trust = [int(x[2])-int(x[4]) for x in info if x[3]=='Investment_Trust'][0]
                dealer_self = sum([ int(x[2])-int(x[4]) for x in info if x[3]=='Dealer_self' or x[3]=='Dealer_Hedging'])
                val.append([datetime.strptime(info[0][0], '%Y-%m-%d').strftime('%Y%m%d'), str(foreign_inv), str(inv_trust), str(dealer_self)])
            all_stock = indexes if update else None # if not update, indexes are all_date

        elif dtype == 'pbr':
            # cols = [ date : str,
            #          stock_id : str,
            #          dividend_yield  : float,
            #          PER  : float,
            #          PBR  : float ]
            all_stock = [x[1] for x in data] if update else None
            val = []
            for x in data:
                x.pop(1)
                x[0] = datetime.strptime(x[0], '%Y-%m-%d').strftime('%Y%m%d')
                val.append(x)

        elif dtype == 'foreign_inv':
            # cols = [ date : str,
            #          stock_id : str,
            #          stock_name : str,
            #          InternationalCode : str,
            #          ForeignInvestmentRemainingShares : int,
            #          ForeignInvestmentShares : int,
            #          ForeignInvestmentRemainRatio : float,
            #          ForeignInvestmentSharesRatio : float,  # 外資持股比例
            #          ForeignInvestmentUpperLimitRatio : float,
            #          ChineseInvestmentUpperLimitRatio : float,
            #          NumberOfSharesIssued : int,
            #          RecentlyDeclareDate : str,
            #          note : str ]
            all_stock = [ x[1] for x in data] if update else None
            # val = [date, ForeignInvestmentSharesRatio, NumberOfSharesIssued]
            val = [ [datetime.strptime(x[0], '%Y-%m-%d').strftime('%Y%m%d'), x[7], x[-3]] for x in data]

        elif dtype == 'fin_stat':
            # cols = [ date : str,
            #          stock_id : str,
            #          type : str,
            #          value : float,
            #          origin_name : str ]
            # type = 'EPS' or 'IncomeAfterTaxes' or 'IncomeAfterTax'
            indexes = sorted(list(set( [x[int(update)] for x in data] ))) # get and sort all index # index = { 0:date, 1:stock_id }
            val = []
            for name in indexes:
                info = [ x for x in data if x[int(update)]==name ] # int(update) = group index
                col_type = [x[2] for x in info]
                if 'IncomeAfterTaxes' in col_type or 'IncomeAfterTax' in col_type:
                    income_after_tax = [ x[3] for x in info if x[2]=='IncomeAfterTaxes' or x[2]=='IncomeAfterTax'][0]
                else:
                    income_after_tax = 0
                eps = [ x[3] for x in info if x[2]=='EPS'][0] if 'EPS' in col_type else 0
                
                val.append([datetime.strptime(info[0][0], '%Y-%m-%d').strftime('%Y%m%d'), eps, str(int(income_after_tax))])
            all_stock = indexes if update else None # if not update, indexes are all_date

        elif dtype == 'bs':
            # cols = [ date : str,
            #          stock_id : str,
            #          type : str,
            #          value : float,
            #          origin_name : str ]
            # type = 'Equity'
            indexes = sorted(list(set( [x[int(update)] for x in data] ))) # get and sort all index # index = { 0:date, 1:stock_id }
            val = []
            for name in indexes:
                info = [ x for x in data if x[int(update)]==name ] # int(update) = group index
                col_type = [x[2] for x in info]
                equity = [ x[3] for x in info if x[2]=='Equity'][0] if 'Equity' in col_type else 0
                
                val.append([datetime.strptime(info[0][0], '%Y-%m-%d').strftime('%Y%m%d'), str(int(equity))])
            all_stock = indexes if update else None # if not update, indexes are all_date

        else:
            pass

        return [all_stock, val]

class StoreData(object): # C(create) # store data to db
    def __init__(self):
        self.__setschema()

    def __setschema(self):
        self.data_db = ['kbar', 'institution', 'revenue', 'pbr', 'foreign_inv', 'fin_stat', 'bs']
        self.table_other = ['stockno', 'strategy']
        self.sql_schema = {} # schema = { col_name : def_list}

        # other info
        self.sql_schema['stockno'] = {'no':['varchar', 'not null unique'], 'name':['varchar'], 'type':['varchar']}

        self.sql_schema['strategy'] = {'name':['varchar', 'not null unique'], 'content':['varchar'], 'type':['varchar']}

        # stock info
        self.sql_schema['kbar'] = {'date':['varchar', 'not null unique'], 'volume':['varchar'], 'money':['varchar'], 'open':['float'],
                                    'high':['float'], 'low':['float'], 'close':['float'], 'spread':['float'], 'turnover':['varchar']}

        self.sql_schema['institution'] = {'date':['varchar', 'not null unique'], 'foreign_inv':['varchar'], 'inv_trust':['varchar'], 'self_dealer':['varchar']}

        self.sql_schema['revenue'] = {'date':['varchar', 'not null unique'], 'revenue':['varchar']}

        self.sql_schema['pbr'] = {'date':['varchar', 'not null unique'], 'dividend_yield':['float'], 'per':['float'], 'pbr':['float']}

        self.sql_schema['foreign_inv'] = {'date':['varchar', 'not null unique'], 'ratio':['float'], 'total':['varchar']}

        self.sql_schema['fin_stat'] = {'date':['varchar', 'not null unique'], 'eps':['float'], 'IncomeAfterTax':['varchar']}

        self.sql_schema['bs'] = {'date':['varchar', 'not null unique'], 'equity':['varchar']}

    def storeData(self, dtype:str, sid:str='', data=[]):
        # select database and table
        if dtype in self.data_db:
            db_name = f'db\\{dtype}.db'
            table_name = 'daily_'+sid
        elif dtype in self.table_other:
            db_name = 'db\\other_info.db'
            table_name = dtype

        # connect to db
        conn = sqlite3.connect(db_name)
        cur = conn.cursor()

        # create table
        schema = self.sql_schema[dtype]
        col_def_cmd = ', '.join( [' '.join([col]+schema[col]) for col in schema] )
        cur.execute('create table if not exists %s(%s)'%(table_name, col_def_cmd))

        # insert data
        for x in data:
            try:
                insert_cmd = 'insert into %s values(%s)'%(table_name, ', '.join(['?']*len(schema)))
                cur.execute(insert_cmd, x)
                conn.commit()
            except:
                pass
        conn.close()

class GetData(object): # R(read) # get data from database

    def __init__(self):
        self.data_db = ['kbar', 'institution', 'revenue', 'pbr', 'foreign_inv', 'fin_stat', 'bs'] # return reverse-order data
        self.table_other = ['stockno', 'strategy'] # return normal-order data

    def getData(self, dtype:str, sid:str='', daylen:int=1, cond:list[str]=[]):

        # select database and table
        if dtype in self.data_db:
            db_name = f'db\\{dtype}.db'
            table_name = f'daily_{sid}'
            get_reverse = True
        elif dtype in self.table_other:
            db_name = 'db\\other_info.db'
            table_name = dtype
            get_reverse = False
        else:
            return [] # wrong type

        # set condition cmd
        # 'where' conition be set before 'order' condition
        cond_cmd = ''
        if cond != []:
            cond_cmd +=  ' where ' + ' and '.join(cond)
        if get_reverse:
            cond_cmd += f' order by date desc limit {daylen} '

        # connect to db
        conn = sqlite3.connect(db_name)
        cur = conn.cursor()

        # try to get data
        try:
            get_cmd = 'select * from %s %s'%(table_name, cond_cmd)
            cur.execute(get_cmd)
            res = [ list(x) for x in cur.fetchall() ]
        except:
            res = []

        return res

    def getTableList(self, db:str):
        conn = sqlite3.connect(f'db\\{db}.db')
        cur = conn.cursor()
        cur.execute('select name from sqlite_schema where type="table"')
        all_table = [x[0][6:] for x in cur.fetchall()]
        return all_table

class Update(object): # U(update) # download and store data
    def __init__(self, api_key):
        self.getdata = GetData()
        self.download = DownloadData(api_key)
        self.store = StoreData()

    # update the given database from the given date to now
    def updateData(self, dtype:str, date:str):
        start_date = datetime.strptime(date, '%Y%m%d') + timedelta(days=1) # start date
        all_table = self.getdata.getTableList(dtype)
        for d in rrule.rrule(freq=rrule.DAILY, dtstart=start_date, until=datetime.today()): # daily loop
            d = d.strftime('%Y%m%d')
            sid_list, data = self.download.from_Finmind(self.api_key, dtype, update=True, start=d) # no sid # update all table
            for i in range(len(sid_list)):
                sid = sid_list[i]
                if sid in all_table:
                    self.store.storeData(dtype, sid, [data[i]])

class KBar_Fig(FigureCanvas): # draw figure of kbar/tech/base/chips
    def __init__(self):
        self.fig = plt.figure()
        super(KBar_Fig, self).__init__(self.fig)

    def __kbar_to_dict(self, data):
        data = data[::-1]
        kbar = {}
        kbar['date'] = [x[0] for x in data]
        kbar['open'] = array([x[3] for x in data])
        kbar['high'] = array([x[4] for x in data])
        kbar['low'] = array([x[5] for x in data])
        kbar['close'] = array([x[6] for x in data])
        kbar['volume'] = [int(x[1]) for x in data]
        return kbar

    def KBarPlot(self, data, days=60):
        kbar = self.__kbar_to_dict(data)
        kbar['10MA'] = abstract.SMA(kbar['close'], 10)
        kbar['20MA'] = abstract.SMA(kbar['close'], 20)

        for k in kbar.keys():
            kbar[k] = kbar[k][-days:]

        self.ax = self.fig.add_axes([0, .4, 1, .6])
        self.ax2 = self.fig.add_axes([0, 0, 1, .4])
        self.ax.set_xticks(range(0,len(kbar['date']), 10))
        self.ax.set_xticklabels(kbar['date'][::10])
        mpf.candlestick2_ohlc(self.ax, kbar['open'], kbar['high'], kbar['low'],
                        kbar['close'], width=.6, colorup='r', colordown='g', alpha=0.75)
        self.ax.plot(kbar['10MA'], label='10MA')   
        self.ax.plot(kbar['20MA'], label='20MA')

        mpf.volume_overlay(self.ax2, kbar['open'], kbar['close'], kbar['volume'],
                            colorup='r', colordown='g', width=0.7, alpha=0.8)

        self.ax2.set_xticks(range(0,len(kbar['date']), 10))
        self.ax2.set_xticklabels(kbar['date'][::10])

        self.ax.legend()
        self.ax.set_facecolor('black')
        self.ax2.set_facecolor('black')

        plt.close(self.fig) # avoid runtime warning # figure.max_open_warning # consume too much memory

class Strategy(object):
    def __init__(self):
        self.__get = GetData()
        return
        # self.build = BuildModel()

    def __ConvertDataToDf(self, data):
        data.reverse()
        kbar = DataFrame()
        kbar['date'] = array([x[0] for x in data])
        kbar['volume'] = array([int(x[1]) for x in data])
        kbar['money'] = array([int(x[2]) for x in data])
        kbar['high'] = array([float(x[4]) for x in data])
        kbar['open'] = array([float(x[3]) for x in data])
        kbar['low'] = array([float(x[5]) for x in data])
        kbar['close'] = array([float(x[6]) for x in data])
        kbar['spread'] = array([float(x[7]) for x in data])
        kbar['turnover'] = array([int(x[8]) for x in data])
        return kbar

    def __ConvertDataToDict(self, data): # using for tech analysis
        data.reverse()
        kbar = {}
        kbar['date'] = array([x[0] for x in data])
        kbar['volume'] = array([int(x[1]) for x in data])
        kbar['money'] = array([int(x[2]) for x in data])
        kbar['high'] = array([float(x[4]) for x in data])
        kbar['open'] = array([float(x[3]) for x in data])
        kbar['low'] = array([float(x[5]) for x in data])
        kbar['close'] = array([float(x[6]) for x in data])
        kbar['spread'] = array([float(x[7]) for x in data])
        kbar['turnover'] = array([int(x[8]) for x in data])
        return kbar

### fund
    def pbr_roe(self, sid):
        # ROE > 8%, PBR < 2
        std = {'roe':0.08, 'pbr':2}
        data_finstat = self.__get.getData('fin_stat', sid=sid, daylen=4)
        data_pbr = self.__get.getData('pbr', sid=sid)
        if data_finstat == [] or data_pbr == []:
            return False, '0'

        val_pbr= data_pbr[0][-1] # take the latest pbr
        roe_year = [] # calulate average ROE for one year
        for i in range(len(data_finstat)):
            qt = data_finstat[i][0]
            income = int(data_finstat[i][-1])
            data_bs = self.__get.getData('bs', sid=sid, cond=[f' date = "{qt}" '])
            roe = round(income/int(data_bs[0][-1]), 2) if data_bs != [] and data_bs[0][-1]!='0' else 0
            roe_year.append(roe)
        avg_roe = average(roe_year) if roe_year != [] else 0
            
        if avg_roe > std['roe'] and val_pbr < std['pbr']:
            return True, data_pbr[0][0]
        return False, '0'

    def diviend_per(self, sid):
        # dividend_yield > 8, PER < 15
        std = {'dividend':8, 'per':15}
        data_pbr = self.__get.getData('pbr', sid=sid)
        if data_pbr == []:
            return False, '0'

        dividend = data_pbr[0][1]
        per = data_pbr[0][2]
        if dividend > std['dividend'] and per < std['per']:
            return True, data_pbr[0][0]
        return False, '0'

### tech
    def MAcross(self, sid):
        # 5ma > 10ma # ratio > 0.05
        day_term = {'s':5, 'l':10}

        data = self.__get.getData('kbar', sid, day_term['l'])
        if len(data) < day_term['l']:
            return False, '0'

        kbar = self.__ConvertDataToDict(data)
        # SMA
        for term in day_term:
            day_term[term] = abstract.SMA(kbar['close'], day_term[term])

        # ratio
        if kbar['close'][-2] != 0:
            ratio = round(kbar['spread'][-1]/kbar['close'][-2], 2)
        else:
            ratio = 0

        # condition
        if day_term['s'][-1] > day_term['l'][-1] and ratio > 0.05:
            return True, kbar['date'][-1]
        else:
            return False, '0'

    def KD(self, sid):
        # K>D # any D>20 for 3 days # ratio > 0.03
        day_len = 15 # 9+3+3

        data = self.__get.getData('kbar', sid, day_len)
        if data == []:
            return False, '0'

        kbar = self.__ConvertDataToDict(data)
        # KD
        K, D = abstract.STOCH(kbar['high'], kbar['low'], kbar['close'], fastk_period = 9)
        k = K[-1]
        d = D[-1]
        # ratio
        if kbar['close'][-2] != 0:
            ratio = round(kbar['spread'][-1]/kbar['close'][-2], 2)
        else:
            ratio = 0

        # condition
        if d > 20 and k > d and any(_ >20 for _ in D[-3:]) and ratio > 0.03:
            return True, kbar['date'][-1]
        else:
            return False, '0'

    def BBands(self, sid, mode):
        # mode = 'l' is close price < lower bound
        # mode = 'u' is close price > upper bound
        times = 2 # up/down stddv times
        day_len = 20

        data = self.__get.getData('kbar', sid, day_len)
        if len(data) < day_len:
            return False, '0'

        kbar = self.__ConvertDataToDict(data)
        ub, mb, lb = abstract.BBANDS(kbar['close'], timeperiod=day_len)
        close = kbar['close'][-1]
        upper = ub[-1]
        lower = lb[-1]

        if (mode == 'l' and close < lower) or (mode == 'u' and close > upper):
            return True, kbar['date'][-1]
        else:
            return False, '0'
    def BB_Lower(self, sid):
        return self.BBands(sid, 'l')
    def BB_Upper(self, sid):
        return self.BBands(sid, 'u')

### chips
    def foreign_overbuy(self, sid):
        # overbuy days > upperBB for n days
        # stock holding ratio of foreign_inv > 20%
        day_len = 30
        data_ins = self.__get.getData('institution', sid=sid, daylen=day_len)
        data_ratio = self.__get.getData('foreign_inv', sid=sid) # latest # holding ratio
        if len(data_ins) < day_len or data_ratio == []:
            return False, '0'

        data_ins = data_ins[::-1] # reverse
        foreign_overbuy = array([ float(x[1]) for x in data_ins])
        ub, mb, lb = abstract.BBANDS(foreign_overbuy, timeperiod=day_len) # 2 times stddev
        # overbuy_days = len([ x for x in foreign_overbuy if x > 0])
        ratio = data_ratio[0][1]
        if foreign_overbuy[-1] > ub[-1] and ratio > 20:
            return True, data_ratio[0][0]
        return False, '0'
        pass

### others

    def skyrocket(self, sid): # at least 10 days
        day_len = 10
        data = self.__get.getData('kbar', sid, day_len)
        kbar = self.__ConvertDataToDict(data)
        kbar['10ma'] = abstract.SMA(kbar['close'], 10)
        
        
        Close = kbar['close'][-1]
        Close_1 = kbar['close'][-2]
        MA10 = kbar['10ma'][-1]
        Vol = kbar['volume'][-1]
        Vol_1 = kbar['volume'][-2]
        Spread = kbar['spread'][-1]
        Ratio = round(Spread/Close_1, 2)

        if Close > MA10 and Vol > 1.5*Vol_1 and Ratio > 0.05:
            return True, kbar['date'][-1]
        return False, '0'

'''
    def LSTM(self, daylen, data): # predict by LSTM
        kbar = self.__ConvertDataToDf(data)
        kbar = kbar.drop(['date', 'money', 'spread', 'turnover'], axis=1)
        kbar = kbar[['open', 'high', 'low', 'volume', 'close']]
        # reserve ['volume', 'open', 'high', 'low', 'close']

        ### preprocessing # normalize
        range_scalar = preprocessing.MinMaxScaler()
        for x in kbar:
            kbar[x] = range_scalar.fit_transform(kbar[x].values.reshape(-1, 1))

        cols_len = len(kbar.columns)
        data = kbar.values

        ### each data have len = daylen
        result = []
        for index in range( len(data)-(daylen+1)):
            result.append(data[index : index+daylen+1])
        result = array(result)
        num_train_data = round(0.9*result.shape[0]) # take 90% data as train data

        ### set train data and test data
        x_train = result[:int(num_train_data), :-1]
        x_train = reshape(x_train, (*x_train.shape[:2], cols_len))
        y_train = result[:int(num_train_data)+1,-1][:-1]

        x_test = result[int(num_train_data):, :-1]
        x_test = reshape(x_test, (*x_test.shape[:2], cols_len))
        y_test = result[int(num_train_data):, -1][-1]

        LSTM_model = self.build.LSTM_model([daylen, cols_len]) # build LSTM model
        LSTM_model.fit(x_train, y_train, batch_size=128, epochs=50, validation_split=0.1, verbose=1) # train model
        pred = LSTM_model.predict(x_test) # prediction

        original_val = kbar['close'].values.reshape(-1, 1)
        vals = [y_test, pred]
        inv_norm_vals = []
        for v in vals:
            v = v.reshape(-1, 1)
            range_scalar.fit_transform(original_val)
            inv_norm_vals.append(range_scalar.inverse_transform(v))

        return inv_norm_vals
'''

'''
class BuildModel(object):

    def LSTM_model(self, shape):        
        ### set each layers of LSTM model
        r = 0.3 # dropout freq # avoid overfitting
        model = Sequential()
        model.add(LSTM(256, input_shape=(*shape,), return_sequences=True))
        model.add(Dropout(r))
        model.add(LSTM(256, input_shape=(*shape,), return_sequences=False))
        model.add(Dropout(r))
        model.add(Dense(16, kernel_initializer='uniform', activation='relu'))
        model.add(Dense(1, kernel_initializer='uniform', activation='linear'))
        model.compile(loss='mse', optimizer='adam', metrics=['accuracy'])

        return model
'''


def pic2str(fname, strname): # convert pic to str
    pic = open(fname, 'rb')
    content = f'{strname} = {b64encode(pic.read())}\n'
    pic.close()
    f = open('pic.py', 'a', newline='')
    f.write(content)

def CheckConnection(): # check internet connection
    try:
        res = re.get('https://github.com/Diandi-diandi/QuantitativeStockApp')
        if res.status_code == re.codes.ok:
            return True
        else:
            return False
    except re.exceptions.ConnectionError:
        return False




