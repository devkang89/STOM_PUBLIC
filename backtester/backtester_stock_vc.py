import os
import sys
import sqlite3
import datetime
import pandas as pd
from matplotlib import gridspec
from matplotlib import pyplot as plt
from multiprocessing import Process, Queue
sys.path.append(os.path.dirname(os.path.abspath(os.path.dirname(__file__))))
from utility.setting import DB_STOCK_TICK, DB_BACKTEST, GRAPH_PATH, DB_SETTING, ui_num
from utility.static import strf_time, strp_time, timedelta_day, timedelta_sec

BETTING = 20000000     # 종목당 배팅금액
STARTDAY = 0           # 시작날짜(일전)
TESTPERIOD = 14        # 백스팅할 기간 : 시작날짜 기준 이전 기간
START_TIME = 90000
END_TIME = 100000
MULTI_COUNT = 6


class BackTesterStockVc:
    def __init__(self, q_, wq_, code_list_, num_, df1_, df2_, high):
        self.q = q_
        self.wq = wq_
        self.code_list = code_list_
        self.df_name = df1_
        self.df_mt = df2_
        self.high = high

        if type(num_[0]) == list:
            self.gap_ch = num_[0][0]
            self.avgtime = num_[1][0]
            self.gap_sm = num_[2][0]
            self.ch_low = num_[3][0]
            self.dm_low = num_[4][0]
            self.per_low = num_[5][0]
            self.per_high = num_[6][0]
            self.sell_ratio = num_[7][0]
        else:
            self.gap_ch = num_[0]
            self.avgtime = num_[1]
            self.gap_sm = num_[2]
            self.ch_low = num_[3]
            self.dm_low = num_[4]
            self.per_low = num_[5]
            self.per_high = num_[6]
            self.sell_ratio = num_[7]

        self.code = None
        self.df = None

        self.totalcount = 0
        self.totalcount_p = 0
        self.totalcount_m = 0
        self.totalholdday = 0
        self.totaleyun = 0
        self.totalper = 0.

        self.hold = False
        self.buytime = None
        self.buycount = 0
        self.buyprice = 0
        self.sellprice = 0
        self.highper = 0
        self.index = 0
        self.indexb = 0
        self.indexn = 0
        self.ccond = 0

        self.Start()

    def Start(self):
        conn = sqlite3.connect(DB_STOCK_TICK)
        tcount = len(self.code_list)
        end_day_dt = timedelta_day(-STARTDAY)
        end_day = int(strf_time('%Y%m%d', end_day_dt))
        start_day = int(strf_time('%Y%m%d', timedelta_day(-TESTPERIOD, end_day_dt)))
        for k, code in enumerate(self.code_list):
            self.code = code
            self.df = pd.read_sql(f"SELECT * FROM '{code}'", conn).set_index('index')
            self.df['고저평균대비등락율'] = (self.df['현재가'] / ((self.df['고가'] + self.df['저가']) / 2) - 1) * 100
            self.df['고저평균대비등락율'] = self.df['고저평균대비등락율'].round(2)
            self.df['직전체결강도'] = self.df['체결강도'].shift(1)
            self.df['직전당일거래대금'] = self.df['당일거래대금'].shift(1)
            self.df = self.df.fillna(0)
            self.df['초당거래대금'] = self.df['당일거래대금'] - self.df['직전당일거래대금']
            self.df['직전초당거래대금'] = self.df['초당거래대금'].shift(1)
            self.df = self.df.fillna(0)
            self.df['초당거래대금평균'] = self.df['직전초당거래대금'].rolling(window=self.avgtime).mean()
            self.df['체결강도평균'] = self.df['직전체결강도'].rolling(window=self.avgtime).mean()
            self.df['최고체결강도'] = self.df['직전체결강도'].rolling(window=self.avgtime).max()
            self.df = self.df.fillna(0)

            self.totalcount = 0
            self.totalcount_p = 0
            self.totalcount_m = 0
            self.totalholdday = 0
            self.totaleyun = 0
            self.totalper = 0.

            self.hold = False
            self.buytime = None
            self.buycount = 0
            self.buyprice = 0
            self.sellprice = 0
            self.highper = 0
            self.index = 0
            self.indexb = 0
            self.indexn = 0
            self.ccond = 0

            lasth = len(self.df) - 1
            for h, index in enumerate(self.df.index):
                if h != 0 and index[:8] != self.df.index[h - 1][:8]:
                    self.ccond = 0
                if int(index[:8]) <= start_day or int(index[:8]) > end_day or \
                        (not self.hold and (END_TIME <= int(index[8:]) or int(index[8:]) < START_TIME)):
                    continue
                self.index = index
                self.indexn = h
                if not self.hold and START_TIME < int(index[8:]) < END_TIME:
                    self.BuyTerm()
                elif self.hold and START_TIME < int(index[8:]) < END_TIME:
                    self.SellTerm()
                elif self.hold and (h == lasth or int(index[8:]) >= END_TIME > int(self.df.index[h - 1][8:])):
                    self.LastSell()
            self.Report(k + 1, tcount)
        conn.close()

    def BuyTerm(self):
        try:
            if type(self.df['현재가'][self.index]) == pd.Series or type(self.df_mt['거래대금순위'][self.index]) == pd.Series:
                return False
            if self.code not in self.df_mt['거래대금순위'][self.index]:
                self.ccond = 0
            else:
                self.ccond += 1
        except KeyError:
            return False
        if self.ccond < self.avgtime + 1:
            return False

        def now():
            return strp_time('%Y%m%d%H%M%S', self.index)

        매수 = True
        종목명 = self.df_name['종목명'][self.code]
        종목코드 = self.code
        현재가 = self.df['현재가'][self.index]
        시가 = self.df['시가'][self.index]
        고가 = self.df['고가'][self.index]
        저가 = self.df['저가'][self.index]
        등락율 = self.df['등락율'][self.index]
        고저평균대비등락율 = self.df['고저평균대비등락율'][self.index]
        당일거래대금 = self.df['당일거래대금'][self.index]
        VI해제시간 = strp_time('%Y%m%d%H%M%S', self.df['VI해제시간'][self.index])
        VI아래5호가 = self.df['VI아래5호가'][self.index]
        초당거래대금 = self.df['초당거래대금'][self.index]
        초당거래대금평균 = self.df['초당거래대금평균'][self.index]
        체결강도 = self.df['체결강도'][self.index]
        직전체결강도 = self.df['직전체결강도'][self.index]
        체결강도평균 = self.df['체결강도평균'][self.index]
        최고체결강도 = self.df['최고체결강도'][self.index]
        초당매수수량 = self.df['초당매수수량'][self.index]
        초당매도수량 = self.df['초당매도수량'][self.index]
        매도총잔량 = self.df['매도총잔량'][self.index]
        매수총잔량 = self.df['매수총잔량'][self.index]
        매도호가5 = self.df['매도호가5'][self.index]
        매도호가4 = self.df['매도호가4'][self.index]
        매도호가3 = self.df['매도호가3'][self.index]
        매도호가2 = self.df['매도호가2'][self.index]
        매도호가1 = self.df['매도호가1'][self.index]
        매수호가1 = self.df['매수호가1'][self.index]
        매수호가2 = self.df['매수호가2'][self.index]
        매수호가3 = self.df['매수호가3'][self.index]
        매수호가4 = self.df['매수호가4'][self.index]
        매수호가5 = self.df['매수호가5'][self.index]
        매도잔량5 = self.df['매도잔량5'][self.index]
        매도잔량4 = self.df['매도잔량4'][self.index]
        매도잔량3 = self.df['매도잔량3'][self.index]
        매도잔량2 = self.df['매도잔량2'][self.index]
        매도잔량1 = self.df['매도잔량1'][self.index]
        매수잔량1 = self.df['매수잔량1'][self.index]
        매수잔량2 = self.df['매수잔량2'][self.index]
        매수잔량3 = self.df['매수잔량3'][self.index]
        매수잔량4 = self.df['매수잔량4'][self.index]
        매수잔량5 = self.df['매수잔량5'][self.index]

        # 여기에 본인의 전략을 작성하십시오.

    def Buy(self):
        매도호가5 = self.df['매도호가5'][self.index]
        매도호가4 = self.df['매도호가4'][self.index]
        매도호가3 = self.df['매도호가3'][self.index]
        매도호가2 = self.df['매도호가2'][self.index]
        매도호가1 = self.df['매도호가1'][self.index]
        매도잔량5 = self.df['매도잔량5'][self.index]
        매도잔량4 = self.df['매도잔량4'][self.index]
        매도잔량3 = self.df['매도잔량3'][self.index]
        매도잔량2 = self.df['매도잔량2'][self.index]
        매도잔량1 = self.df['매도잔량1'][self.index]
        현재가 = self.df['현재가'][self.index]
        매수수량 = int(BETTING / 현재가)
        if 매수수량 > 0:
            남은수량 = 매수수량
            직전남은수량 = 매수수량
            매수금액 = 0
            호가정보 = {매도호가1: 매도잔량1}
            for 매도호가, 매도잔량 in 호가정보.items():
                남은수량 -= 매도잔량
                if 남은수량 <= 0:
                    매수금액 += 매도호가 * 직전남은수량
                    break
                else:
                    매수금액 += 매도호가 * 매도잔량
                    직전남은수량 = 남은수량
            if 남은수량 <= 0:
                예상체결가 = round(매수금액 / 매수수량, 2)
                self.buyprice = 예상체결가
                self.buycount = 매수수량
                self.hold = True
                self.indexb = self.indexn
                self.buytime = strp_time('%Y%m%d%H%M%S', self.index)
                self.q.put(self.index)

    def SellTerm(self):
        self.q.put(self.index)
        if type(self.df['현재가'][self.index]) == pd.Series:
            return False

        def now():
            return strp_time('%Y%m%d%H%M%S', self.index)

        bg = self.buycount * self.buyprice
        cg = self.buycount * self.df['현재가'][self.index]
        eyun, 수익률 = self.GetEyunPer(bg, cg)
        if 수익률 > self.highper:
            self.highper = 수익률

        매도 = False
        종목명 = self.df_name['종목명'][self.code]
        종목코드 = self.code
        보유수량 = self.buycount
        매수시간 = self.buytime
        최고수익률 = self.highper
        현재가 = self.df['현재가'][self.index]
        시가 = self.df['시가'][self.index]
        고가 = self.df['고가'][self.index]
        저가 = self.df['저가'][self.index]
        등락율 = self.df['등락율'][self.index]
        고저평균대비등락율 = self.df['고저평균대비등락율'][self.index]
        당일거래대금 = self.df['당일거래대금'][self.index]
        VI해제시간 = strp_time('%Y%m%d%H%M%S', self.df['VI해제시간'][self.index])
        VI아래5호가 = self.df['VI아래5호가'][self.index]
        초당거래대금 = self.df['초당거래대금'][self.index]
        초당거래대금평균 = self.df['초당거래대금평균'][self.index]
        체결강도 = self.df['체결강도'][self.index]
        직전체결강도 = self.df['직전체결강도'][self.index]
        체결강도평균 = self.df['체결강도평균'][self.index]
        최고체결강도 = self.df['최고체결강도'][self.index]
        매도총잔량 = self.df['매도총잔량'][self.index]
        매수총잔량 = self.df['매수총잔량'][self.index]
        매도호가5 = self.df['매도호가5'][self.index]
        매도호가4 = self.df['매도호가4'][self.index]
        매도호가3 = self.df['매도호가3'][self.index]
        매도호가2 = self.df['매도호가2'][self.index]
        매도호가1 = self.df['매도호가1'][self.index]
        매수호가1 = self.df['매수호가1'][self.index]
        매수호가2 = self.df['매수호가2'][self.index]
        매수호가3 = self.df['매수호가3'][self.index]
        매수호가4 = self.df['매수호가4'][self.index]
        매수호가5 = self.df['매수호가5'][self.index]
        매도잔량5 = self.df['매도잔량5'][self.index]
        매도잔량4 = self.df['매도잔량4'][self.index]
        매도잔량3 = self.df['매도잔량3'][self.index]
        매도잔량2 = self.df['매도잔량2'][self.index]
        매도잔량1 = self.df['매도잔량1'][self.index]
        매수잔량1 = self.df['매수잔량1'][self.index]
        매수잔량2 = self.df['매수잔량2'][self.index]
        매수잔량3 = self.df['매수잔량3'][self.index]
        매수잔량4 = self.df['매수잔량4'][self.index]
        매수잔량5 = self.df['매수잔량5'][self.index]

        # 여기에 본인의 전략을 작성하십시오.

    def Sell(self):
        매수호가1 = self.df['매수호가1'][self.index]
        매수호가2 = self.df['매수호가2'][self.index]
        매수호가3 = self.df['매수호가3'][self.index]
        매수호가4 = self.df['매수호가4'][self.index]
        매수호가5 = self.df['매수호가5'][self.index]
        매수잔량1 = self.df['매수잔량1'][self.index]
        매수잔량2 = self.df['매수잔량2'][self.index]
        매수잔량3 = self.df['매수잔량3'][self.index]
        매수잔량4 = self.df['매수잔량4'][self.index]
        매수잔량5 = self.df['매수잔량5'][self.index]
        남은수량 = self.buycount
        직전남은수량 = 남은수량
        매도금액 = 0
        호가정보 = {매수호가1: 매수잔량1, 매수호가2: 매수잔량2, 매수호가3: 매수잔량3, 매수호가4: 매수잔량4, 매수호가5: 매수잔량5}
        for 매수호가, 매수잔량 in 호가정보.items():
            남은수량 -= 매수잔량
            if 남은수량 <= 0:
                매도금액 += 매수호가 * 직전남은수량
                break
            else:
                매도금액 += 매수호가 * 매수잔량
                직전남은수량 = 남은수량
        if 남은수량 <= 0:
            예상체결가 = round(매도금액 / self.buycount, 2)
            self.sellprice = 예상체결가
            self.hold = False
            self.CalculationEyun()
            self.highper = 0
            self.indexb = 0

    def LastSell(self):
        self.sellprice = self.df['현재가'][self.index]
        self.hold = False
        self.CalculationEyun()
        self.highper = 0
        self.indexb = 0

    def CalculationEyun(self):
        self.totalcount += 1
        bg = self.buycount * self.buyprice
        cg = self.buycount * self.sellprice
        eyun, per = self.GetEyunPer(bg, cg)
        self.totalper = round(self.totalper + per, 2)
        self.totaleyun = int(self.totaleyun + eyun)
        self.totalholdday += self.indexn - self.indexb
        if per > 0:
            self.totalcount_p += 1
        else:
            self.totalcount_m += 1
        if self.high:
            self.q.put([self.code, self.df.index[self.indexb], self.index, self.buyprice, self.sellprice, per, eyun])

    # noinspection PyMethodMayBeStatic
    def GetEyunPer(self, bg, cg):
        gtexs = cg * 0.0023
        gsfee = cg * 0.00015
        gbfee = bg * 0.00015
        texs = gtexs - (gtexs % 1)
        sfee = gsfee - (gsfee % 10)
        bfee = gbfee - (gbfee % 10)
        pg = int(cg - texs - sfee - bfee)
        eyun = pg - bg
        per = round(eyun / bg * 100, 2)
        return eyun, per

    def Report(self, count, tcount):
        if self.totalcount > 0:
            plus_per = round((self.totalcount_p / self.totalcount) * 100, 2)
            self.q.put([self.code, self.totalcount, self.totalholdday, self.totalcount_p, self.totalcount_m,
                        plus_per, self.totalper, self.totaleyun])
            totalcount, totalholdday, totalcount_p, totalcount_m, plus_per, totalper, totaleyun = \
                self.GetTotal(plus_per, self.totalholdday)
            test = f"종목코드 {self.code} | 보유기간합계  {totalholdday}초 | 거래횟수 {totalcount}회 | " \
                   f"익절 {totalcount_p}회 | 손절 {totalcount_m}회 | 승률   {plus_per}% | " \
                   f"수익률 {totalper}% | 수익금 {totaleyun}원 [{count}/{tcount}]"
            self.wq.put([ui_num['S백테스트'], test])
        else:
            self.q.put([self.code, 0, 0, 0, 0, 0., 0., 0])

    def GetTotal(self, plus_per, totalholdday):
        totalcount = str(self.totalcount)
        totalcount = '    ' + totalcount if len(totalcount) == 1 else totalcount
        totalcount = '   ' + totalcount if len(totalcount) == 2 else totalcount
        totalholdday = str(totalholdday)
        totalholdday = '      ' + totalholdday if len(totalholdday) == 1 else totalholdday
        totalholdday = '    ' + totalholdday if len(totalholdday) == 2 else totalholdday
        totalholdday = '  ' + totalholdday if len(totalholdday) == 3 else totalholdday
        totalholdday = totalholdday + '0' if len(totalholdday) == 1 else totalholdday
        totalcount_p = str(self.totalcount_p)
        totalcount_p = '    ' + totalcount_p if len(totalcount_p) == 1 else totalcount_p
        totalcount_p = '  ' + totalcount_p if len(totalcount_p) == 2 else totalcount_p
        totalcount_m = str(self.totalcount_m)
        totalcount_m = '    ' + totalcount_m if len(totalcount_m) == 1 else totalcount_m
        totalcount_m = '  ' + totalcount_m if len(totalcount_m) == 2 else totalcount_m
        plus_per = str(plus_per)
        plus_per = '    ' + plus_per if len(plus_per.split('.')[0]) == 1 else plus_per
        plus_per = '  ' + plus_per if len(plus_per.split('.')[0]) == 2 else plus_per
        plus_per = plus_per + '0' if len(plus_per.split('.')[1]) == 1 else plus_per
        totalper = str(self.totalper)
        totalper = '      ' + totalper if len(totalper.split('.')[0]) == 1 else totalper
        totalper = '    ' + totalper if len(totalper.split('.')[0]) == 2 else totalper
        totalper = '  ' + totalper if len(totalper.split('.')[0]) == 3 else totalper
        totalper = totalper + '0' if len(totalper.split('.')[1]) == 1 else totalper
        totalper = ' ' + totalper if '-' in totalper else totalper
        totaleyun = format(self.totaleyun, ',')
        if len(totaleyun.split(',')) == 1:
            totaleyun = '                  ' + totaleyun if len(totaleyun.split(',')[0]) == 1 else totaleyun
            totaleyun = '                ' + totaleyun if len(totaleyun.split(',')[0]) == 2 else totaleyun
            totaleyun = '              ' + totaleyun if len(totaleyun.split(',')[0]) == 3 else totaleyun
            totaleyun = '            ' + totaleyun if len(totaleyun.split(',')[0]) == 4 else totaleyun
        elif len(totaleyun.split(',')) == 2:
            totaleyun = '          ' + totaleyun if len(totaleyun.split(',')[0]) == 1 else totaleyun
            totaleyun = '        ' + totaleyun if len(totaleyun.split(',')[0]) == 2 else totaleyun
            totaleyun = '      ' + totaleyun if len(totaleyun.split(',')[0]) == 3 else totaleyun
            totaleyun = '    ' + totaleyun if len(totaleyun.split(',')[0]) == 4 else totaleyun
        elif len(totaleyun.split(',')) == 3:
            totaleyun = '  ' + totaleyun if len(totaleyun.split(',')[0]) == 1 else totaleyun
        totaleyun = ' ' + totaleyun if '-' in totaleyun else totaleyun
        return totalcount, totalholdday, totalcount_p, totalcount_m, plus_per, totalper, totaleyun


class Total:
    def __init__(self, q_, wq_, last_, num_, df1_):
        super().__init__()
        self.q = q_
        self.wq = wq_
        self.last = last_
        self.name = df1_

        if type(num_[0]) == list:
            self.gap_ch = num_[0][0]
            self.avg_time = num_[1][0]
            self.gap_sm = num_[2][0]
            self.ch_low = num_[3][0]
            self.dm_low = num_[4][0]
            self.per_low = num_[5][0]
            self.per_high = num_[6][0]
            self.sell_ratio = num_[7][0]
        else:
            self.gap_ch = num_[0]
            self.avg_time = num_[1]
            self.gap_sm = num_[2]
            self.ch_low = num_[3]
            self.dm_low = num_[4]
            self.per_low = num_[5]
            self.per_high = num_[6]
            self.sell_ratio = num_[7]

        self.Start()

    def Start(self):
        columns1 = ['거래횟수', '보유기간합계', '익절', '손절', '승률', '수익률', '수익금']
        columns2 = ['거래횟수', '필요자금', '최대보유종목수', '평균보유기간', '익절', '손절', '승률',
                    '평균수익률', '수익률합계', '수익금합계', '체결강도차이', '평균시간', '거래대금차이',
                    '체결강도하한', '누적거래대금하한', '등락율하한', '등락율상한', '청산수익률']
        df_back = pd.DataFrame(columns=columns1)
        df_bct = pd.DataFrame(columns=['hold_count'])
        df_tsg = pd.DataFrame(columns=['종목명', '매수시간', '매도시간', '매수가', '매도가', '수익률', 'sgm'])
        k = 0
        while True:
            data = self.q.get()
            if type(data) == str:
                if data in df_bct.index:
                    df_bct.at[data] = df_bct['hold_count'][data] + 1
                else:
                    df_bct.at[data] = 1
            elif len(data) == 7:
                name = self.name['종목명'][data[0]]
                if data[2] in df_tsg.index:
                    df_tsg.at[data[2]] = df_tsg['종목명'][data[2]] + ';' + name, \
                                         df_tsg['매수시간'][data[2]] + ';' + data[1], \
                                         df_tsg['매도시간'][data[2]] + ';' + data[2], \
                                         df_tsg['매수가'][data[2]] + ';' + str(data[3]), \
                                         df_tsg['매도가'][data[2]] + ';' + str(data[4]), \
                                         df_tsg['수익률'][data[2]] + ';' + str(data[5]), \
                                         df_tsg['sgm'][data[2]] + data[6]
                else:
                    df_tsg.at[data[2]] = name, data[1], data[2], str(data[3]), str(data[4]), str(data[5]), data[6]
            else:
                df_back.at[data[0]] = data[1], data[2], data[3], data[4], data[5], data[6], data[7]
                k += 1
            if k == self.last:
                break

        tsp = 0
        if len(df_back) > 0:
            text = [self.gap_ch, self.avg_time, self.gap_sm, self.ch_low, self.dm_low,
                    self.per_low, self.per_high, self.sell_ratio]
            self.wq.put([ui_num['S백테스트'], text])
            df_back = df_back[df_back['거래횟수'] > 0]
            tc = df_back['거래횟수'].sum()
            if tc != 0:
                pc = df_back['익절'].sum()
                mc = df_back['손절'].sum()
                pper = round(pc / tc * 100, 2)
                avghold = round(df_back['보유기간합계'].sum() / tc, 2)
                avgsp = round(df_back['수익률'].sum() / tc, 2)
                tsg = int(df_back['수익금'].sum())
                maxholdcount = round(df_bct['hold_count'].max(), 2)
                onegm = int(BETTING * maxholdcount)
                if onegm < BETTING:
                    onegm = BETTING
                tsp = round(tsg / onegm * 100, 4)
                text = f"종목당 배팅금액 {format(BETTING, ',')}원, 필요자금 {format(onegm, ',')}원, "\
                       f"거래횟수 {tc}회, 최대보유종목수 {maxholdcount}개, 평균보유기간 {avghold}초,\n 익절 {pc}회, "\
                       f"손절 {mc}회, 승률 {pper}%, 평균수익률 {avgsp}%, 수익률합계 {tsp}%, 수익금합계 {format(tsg, ',')}원"
                self.wq.put([ui_num['S백테스트'], text])
                df_back = pd.DataFrame(
                    [[tc, onegm, maxholdcount, avghold, pc, mc, pper, avgsp, tsp, tsg, self.gap_ch, self.avg_time,
                      self.gap_sm, self.ch_low, self.dm_low, self.per_low, self.per_high, self.sell_ratio]],
                    columns=columns2, index=[strf_time('%Y%m%d%H%M%S')])
                conn = sqlite3.connect(DB_BACKTEST)
                df_back.to_sql(f"stock_vc_vars_{strf_time('%Y%m%d')}", conn, if_exists='append', chunksize=1000)
                conn.close()
                if len(df_tsg) == 0:
                    df_bct = pd.DataFrame(columns=['hold_count'])

        if len(df_tsg) > 0:
            df_tsg.sort_values(by=['매도시간'], inplace=True)
            df_tsg['sgm_cumsum'] = df_tsg['sgm'].cumsum()
            df_tsg[['sgm', 'sgm_cumsum']] = df_tsg[['sgm', 'sgm_cumsum']].astype(int)
            df_bct['index'] = df_bct.index
            df_bct.sort_values(by=['index'], inplace=True)
            df_bct = df_bct.set_index('index')

            conn = sqlite3.connect(DB_BACKTEST)
            df_bct.to_sql(f"stock_vc_hold_{strf_time('%Y%m%d')}", conn, if_exists='append', chunksize=1000)
            df_tsg.to_sql(f"stock_vc_time_{strf_time('%Y%m%d')}", conn, if_exists='append', chunksize=1000)
            conn.close()

            plt.figure(figsize=(12, 10))
            gs = gridspec.GridSpec(nrows=2, ncols=1, height_ratios=[3, 1])
            plt.subplot(gs[0])
            plt.plot(df_tsg.index, df_tsg['sgm'], label='sgm')
            plt.plot(df_tsg.index, df_tsg['sgm_cumsum'], label='sgm_cumsum')
            plt.xticks([])
            plt.legend(loc='best')
            plt.grid()
            plt.subplot(gs[1])
            plt.plot(df_bct.index, df_bct['hold_count'], color='g', label='hold_count')
            plt.xticks(list(df_tsg.index[::12]), rotation=45)
            plt.legend(loc='best')
            plt.tight_layout()
            plt.savefig(f"{GRAPH_PATH}/stock_vc_{strf_time('%Y%m%d')}.png")
            plt.show()
        else:
            self.q.put(tsp)


def BacktesterStockVcMain(wq):
    start = datetime.datetime.now()

    con = sqlite3.connect(DB_STOCK_TICK)
    df = pd.read_sql("SELECT name FROM sqlite_master WHERE TYPE = 'table'", con)
    df2 = pd.read_sql('SELECT * FROM moneytop', con).set_index('index')
    con.close()
    con = sqlite3.connect(DB_SETTING)
    df1 = pd.read_sql('SELECT * FROM codename', con).set_index('index')
    con.close()

    table_list = list(df['name'].values)
    table_list.remove('moneytop')
    if 'codename' in table_list:
        table_list.remove('codename')
    if 'dist' in table_list:
        table_list.remove('dist')
    if 'dist_chk' in table_list:
        table_list.remove('dist_chk')
    if 'sqlite_sequence' in table_list:
        table_list.remove('sqlite_sequence')
    if 'temp' in table_list:
        table_list.remove('temp')
    last = len(table_list)

    q = Queue()

    if len(table_list) > 0:
        gap_chs = [3, 4, 5]
        avg_times = [60, 120, 180]
        htsp = -100
        high_var = []

        for gap_ch in gap_chs:
            for avg_time in avg_times:
                num = [gap_ch, avg_time, 50, 50, 0, 0, 25, 0.5]
                w = Process(target=Total, args=(q, wq, last, num, df1))
                w.start()
                procs = []
                workcount = int(last / MULTI_COUNT) + 1
                for j in range(0, last, workcount):
                    code_list = table_list[j:j + workcount]
                    p = Process(target=BackTesterStockVc, args=(q, wq, code_list, num, df1, df2, False))
                    procs.append(p)
                    p.start()
                for p in procs:
                    p.join()
                w.join()
                sp = q.get()
                if sp >= htsp:
                    htsp = sp
                    high_var = num
                    wq.put([ui_num['S백테스트'], f'최고수익률 갱신 {htsp}%'])

        gap_ch = [high_var[0] - 0.5, high_var[0] + 0.5, 0.5, 0.5]
        avg_time = [high_var[1], high_var[1] + 30, 30, 30]
        gap_sm = [50, 500, 50, 10]
        ch_low = [50, 100, 10, 10]
        dm_low = [0, 10000, 1000, 1000]
        per_low = [0, 10, 1, 1]
        per_high = [25, 15, -1, -1]
        sell_ratio = [0.5, 1.0, 0.1, 0.1]
        num = [gap_ch, avg_time, gap_sm, ch_low, dm_low, per_low, per_high, sell_ratio]
        high_var = high_var[0]

        i = 0
        while True:
            w = Process(target=Total, args=(q, wq, last, num, df1))
            w.start()
            procs = []
            workcount = int(last / MULTI_COUNT) + 1
            for j in range(0, last, workcount):
                code_list = table_list[j:j + workcount]
                p = Process(target=BackTesterStockVc, args=(q, wq, code_list, num, df1, df2, False))
                procs.append(p)
                p.start()
            for p in procs:
                p.join()
            w.join()
            sp = q.get()
            if sp >= htsp:
                htsp = sp
                high_var = num[i][0]
                wq.put([ui_num['S백테스트'], f'최고수익률 갱신 {htsp}%'])
            if num[i][0] == num[i][1]:
                num[i][0] = high_var
                if num[i][2] != num[i][3]:
                    num[i][0] -= num[i][2]
                    num[i][1] = round(num[i][0] + num[i][2] * 2 - num[i][3], 1)
                    num[i][2] = num[i][3]
                elif i < len(num) - 1:
                    i += 1
                    high_var = num[i][0]
                    if i == 1:
                        num[i][0] -= num[i][2] * 2
                    elif i == 7:
                        num[i][0] = 0
                else:
                    break
            num[i][0] = round(num[i][0] + num[i][2], 1)

        w = Process(target=Total, args=(q, wq, last, num, df1))
        w.start()
        procs = []
        workcount = int(last / MULTI_COUNT) + 1
        for j in range(0, last, workcount):
            db_list = table_list[j:j + workcount]
            p = Process(target=BackTesterStockVc, args=(q, wq, db_list, num, df1, df2, True))
            procs.append(p)
            p.start()
        for p in procs:
            p.join()
        w.join()

    q.close()
    end = datetime.datetime.now()
    wq.put([ui_num['S백테스트'], f"백테스팅 소요시간 {end - start}"])
