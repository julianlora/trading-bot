from backtesting import Backtest, Strategy
from backtesting.lib import TrailingStrategy
import pandas as pd
from binance import Client, ThreadedWebsocketManager, ThreadedDepthCacheManager
import binance.enums, pathlib, talib
import plotly.express as px
from backtesting.backtesting import Order, Trade

apikey = 'your key'
secret = 'your secret key'
client = Client(apikey, secret)

# OPCION PARA EXCELS de binance
# print('Reading data file...')
# path = pathlib.Path(r"C:\Users\julia\Desktop\Julian2\Coding\anaconda codes\btc.csv") # Se puede poner una carpeta con archivos en vez del archivo
# dataframe = pd.read_csv(path)

# PARA ADAPTAR
# #Siempre que se agregue nueva informacion hay que chequear que los archivos sean todos iguales.
# #Un excel con títulos ya puestos hace que no funcione nada
# dataframe = pd.concat([pd.read_csv(file_,header=None) for file_ in path.iterdir()],axis=0)
# dataframe.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume','1','2','3','4','5','6']
# dataframe.reset_index(inplace=True)
# dataframe.drop(['index','1','2','3','4','5','6'], axis=1, inplace=True)

# OPCION DATOS HISTÓRICOS ACTUALIZADOS DESDE API
print('Getting historical data...')
dataframe = pd.DataFrame(client.get_historical_klines('BTCUSDT', Client.KLINE_INTERVAL_15MINUTE, '12 Dec 2022', klines_type=binance.enums.HistoricalKlinesType.FUTURES))
dataframe.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume','1','2','3','4','5','6']
dataframe.drop(['1','2','3','4','5','6'], axis=1, inplace=True)
dataframe['Date'] = pd.to_datetime(dataframe['Date']/1000, unit='s')
numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
dataframe[numeric_columns] = dataframe[numeric_columns].apply(pd.to_numeric, axis=1)
dataframe.to_csv(r'C:\Users\julia\Desktop\Julian2\Coding\anaconda codes\btc.csv')

cashinicial = cashreal = cash_peak = highest = 100.0
leverage = 1 #multiplicador ( 1 si no se usa )
canttrades = winners = time_in = 0
entryprice = activation_price = equity = lowest = 0.
searching_long = searching_short = searching_long_hidden = searching_short_hidden = False
Long_regular = Long_hidden = Short_regular = Short_hidden = Trailing = False

def Distribution_Test():# RANDOMNESS TEST (DISTRIBUTION): períodos de a 30 días
    returns = []
    bars_in_day = 24*4
    for x in range(30*bars_in_day, len(dataframe)+1, bars_in_day):
        bt = Backtest(dataframe.iloc[x-30*bars_in_day:x], Div, cash = cashinicial, exclusive_orders=False, margin = 1 / leverage, commission=0.00075)
        stats = bt.run()
        #print(stats["Return [%]"])
        returns.append(stats["Return [%]"])
    fig = px.box(returns, points= "all")
    fig.update_layout(xaxis_title="Strategy", yaxis_title="Returns (%)")
    fig.show()
    media = sum(returns) / len(returns)
    print("Media Retorno Mensual={}".format(media))

def Trades_Por_Semana():# CANTIDAD DE TRADES POR SEMANA
    semanal = []
    bars_in_day = 24*4
    for x in range(7*bars_in_day, len(dataframe)+1, bars_in_day):
        bt = Backtest(dataframe.iloc[x-7*bars_in_day:x], Div, cash = cashinicial, exclusive_orders=False, margin = 1 / leverage, commission=0.00075)
        stats = bt.run()
        #print(stats["# Trades"])
        semanal.append(stats["# Trades"])
    fig = px.box(semanal, points= "all")
    fig.update_layout(xaxis_title="Strategy", yaxis_title="Returns (%)")
    fig.show()
    media = sum(semanal) / len(semanal)
    print("Media trades por semana={}".format(media))

def Print_Stats(stats):
    try:
        winrate = ((stats['_trades'].ReturnPct.gt(0).sum()*100)/len(stats['_trades'])).round(2)
        winratelong = round((((sum((stats['_trades'].Size == 1) & (stats['_trades'].ReturnPct > 0)))*100)/sum(stats['_trades'].Size == 1)),2)
        winrateshort = round((((sum((stats['_trades'].Size == -1) & (stats['_trades'].ReturnPct > 0)))*100)/sum(stats['_trades'].Size == -1)),2)
        wonlong = sum((stats['_trades'].Size == 1) & (stats['_trades'].ReturnPct > 0))
        tradeslong = sum(stats['_trades'].Size == 1)
        wonshort = sum((stats['_trades'].Size == -1) & (stats['_trades'].ReturnPct > 0))
        tradesshort = sum(stats['_trades'].Size == -1)
        cashfinal = round(stats['Equity Final [$]'], 2)
        percentprofit = (cashfinal * 100) / cashinicial
        maxdrawdown = round(stats['Max. Drawdown [%]'], 2)
        avgdrawdown = round(stats['Avg. Drawdown [%]'], 2)
        trades = int(stats['# Trades'])
        avgtrade= round(stats['Avg. Trade [%]'], 2)
        print("\n\n WINRATE TOTAL ------ {0} % ({13} trades)\n WINRATE LONG  ------ {1} % ({2} de {3}) \n WINRATE SHORT ------ {4} % ({5} de {6}) \n CASH INICIAL  ------ $ {7}\n CASH FINAL    ------ $ {8} (+ {9} %)\n AVG TRADE     ------ {14} %\n MAX DRAWDOWN  ------ {11} %\n AVG DRAWDOWN  ------ {12} %\n LEVERAGE      ------ x {10}\n\n".format(winrate, winratelong, wonlong, tradeslong, winrateshort, wonshort, tradesshort, cashinicial, round(cashfinal, 2), round(percentprofit), leverage, maxdrawdown, avgdrawdown, trades, avgtrade))
    except Exception as e:
        return False 
    
    return True

class Div(TrailingStrategy):
    
    """CONDICIONES DE ESTRATEGIA
    1. DIVERGENCIAS.
    2. Solo generadas en over o underbought RSI (OBOS).
    3. Cuando se encuentra una divergencia, se espera a que
    el RSI se mueva al menos una vez hacia la direccion del trade
    4. TIME OUT: Si despues de X cantidad de barras, el trade esta ganando, mover el sl a breakeven. Si esta perdiendo, cerrar el trade.
    5. RSI COUNTER: Si el trade todavía no salio por ningun TP/SL y se alcanzo el OBOS contrario X cantidad de veces, cerrar trade."""
    
    # Probado sin exito:

    # 2. Restringir la direccion segun el resultado del trade anterior.
    # 3. Esperar X cantidad de barras luego de haber sido confirmada la divergencia para entrar al trade.
    # 4. Quitar la restriccion de solo buscar divergencias en OBOS.
    # 5. Hacer una jerarquia de prioridad no cambió nada
    # 6. HEDGE no dio resultado de ninguna manera, con o sin trailing. Es incierto si se debe a errores en calculo y codigo o a la estrategia
    # 7. Si el movimiento de rsi o de precio es X %, ignorar la restriccion de rango ignorado.
    # 8. Prohibir entrada si sucedio entre ambos puntos de la divergencia un RSI OBOS del lado opuesto
    # 9. Establecer una restriccion para entrar de minimo o maximo de diferencia de precio o RSI entre los dos puntos de la divergencia
    # 10. HIDDENS se encuentran muy pocos como para confiar en sus resultados
    # 11. Bajar el TP el mismo % que baja el precio por debajo del entry price
    # 12. No entrar cuando ambos puntos de rsi son menores a 71 o mayores a 29

    upper_bound = 70
    lower_bound = 30
    tplong = 35.5 # 30 = (0.03) (3%)
    sllong = 25 # 5 = (0.005) (0.5%)
    tpshort = 42.5
    slshort = 25
    tphidden = 50
    slhidden = 40
    rango_de_busqueda_long = 75
    rango_de_busqueda_short = 89
    rango_ignorado_long = 36 #(en positivo)
    rango_ignorado_short = 49
    rango_de_busqueda_hidden_long = 360
    rango_de_busqueda_hidden_short = 360
    rango_ignorado_hidden_long = 175
    rango_ignorado_hidden_short = 175
    long_max_time_in = 175
    short_max_time_in = 180
    trailing = 37 #(1 = 0.001 %)
    cont = 0
    atr_4h = 0.
    profit = 180
    dif = 150

    def init(self):
        super().init()
        self.set_trailing_sl(1000)
        self.rsi = self.I (talib.RSI, self.data.Close, 14)
        
    def next (self):
        super().next()
        
        price = bottom_price_hidden = top_price_hidden = self.data.Close[-1]
        top = bottom = self.rsi[-1]
        top_price = bottom_price = top_rsi_hidden = 0.0
        top_bar = bottom_bar = bottom_bar_hidden = top_bar_hidden = 0
        bottom_rsi_hidden = 100.
        
        global tp, sl, entryprice, activation_price, Long_regular, Long_hidden, Short_regular, Short_hidden, Trailing
        global searching_long, searching_short, searching_long_hidden, searching_short_hidden
        global equity, canttrades, cashreal, leverage, winners, cash_peak, time_in, lowest, highest
        
        Long_regular = Long_hidden = Short_regular = Short_hidden = False 
        
        if self.rsi > 70:
            if self.rsi[-1] > highest:
                highest = self.rsi
        else: highest = 0
        if self.rsi < 30:
            if self.rsi[-1] < lowest:
                lowest = self.rsi
        else: lowest = 100
        
        #DIVERGENCIAS
        if len(self.trades) < 1:# and self.data.index[-1] >= 1344:
            
            if self.rsi < self.lower_bound: # DIVERGENCIAS LONG
                if len(self.data.Close) >= self.rango_de_busqueda_long:
                    # REGULAR
                    for i in range(self.rango_de_busqueda_long):
                        if self.rsi[-i] < bottom:
                            bottom = self.rsi[-i]
                            bottom_price = self.data.Close[-i]
                            bottom_bar = -i
                    if bottom_bar < -self.rango_ignorado_long and bottom_price > price and abs(bottom_price - price) > self.dif:
                        searching_long = True
                    else: searching_long = False
            
                        
            if self.rsi > self.upper_bound: # DIVERGENCIAS SHORT
                if len(self.data.Close) >= self.rango_de_busqueda_short:
                    # REGULAR
                    for i in range(self.rango_de_busqueda_short):
                        if self.rsi[-i] > top:
                            top = self.rsi[-i]
                            top_price = self.data.Close[-i]
                            top_bar = -i
                    if top_bar < -self.rango_ignorado_short and top_price < price and abs(top_price - price) > self.dif:
                        searching_short = True
                    else: searching_short = False

        if not self.position: #and self.tplong > self.sllong:
            self.cont = 0
            # CONTADOR DE TRADES
            if len(self.closed_trades) > 0:
                if equity != self.equity:
                    if equity < self.equity:
                        winners += 1
                    else:
                        print('yes')
                    #canttrades += 1
                    equity = self.equity
                    
            else: equity = self.equity 

            
            # ENTRY SIGNAL
            if searching_long and self.rsi[-2] < self.rsi:
                Long_regular = True
            elif searching_long_hidden and self.rsi[-2] < self.rsi:
                Long_hidden = True
            elif searching_short and self.rsi[-2] > self.rsi:
                Short_regular = True
            elif searching_short_hidden and self.rsi[-2] > self.rsi:
                Short_hidden = True
            
            # ENTRY
            if Long_regular:
                activation_price = price + (price * (self.tplong / 1000))
                tp= price + (price * (self.tplong / 1000))
                sl= price - (price * (self.sllong / 1000))
                self.buy(size=1, tp=tp, sl= sl)
                searching_long = False
            elif Long_hidden:
                activation_price = price + (price * (self.tplong / 1000))
                tp= price + (price * (self.tphidden / 1000))
                sl= price - (price * (self.slhidden / 1000))
                self.buy(size=1, tp=tp, sl= sl)
                searching_long_hidden = False
            elif Short_regular:
                activation_price = price - (price * (self.tpshort / 1000))
                tp = price - (price * (self.tpshort / 1000))
                sl = price + (price * (self.slshort / 1000))
                self.buy(size=-1, tp=tp, sl= sl)
                searching_short = False
            elif Short_hidden:
                activation_price = price - (price * (self.tpshort / 1000))
                tp= price - (price * (self.tphidden / 1000))
                sl= price + (price * (self.slhidden / 1000))
                self.buy(size=-1, tp=tp, sl= sl)
                searching_short_hidden = False
        else:
            time_in = self.data.index[-1] - self.trades[-1].entry_bar
        
        if self.position: # Contador de tiempo en trade
            
            if self.position.is_long:
                # RSI OBJECTIVES
                if self.rsi[-2] < 70 and self.rsi > 70:
                    self.cont += 1
                if self.cont == 4:
                    self.position.close()
                # TIME OUT
                elif (self.data.index[-2] - self.trades[-1].entry_bar) >= self.long_max_time_in and Trailing == False:
                    if self.trades[-1].pl > 0:
                        if price > (self.trades[-1].entry_price + self.profit):
                            self.trades[-1].sl = self.trades[-1].entry_price + self.profit
                        else:
                            self.trades[-1].sl = self.trades[-1].entry_price
                    else:
                        self.position.close()
                # RSI OPOSITE OBOS
                if self.rsi < 30 and ((self.cont >= 2) or ((self.data.index[-1] - self.trades[-1].entry_bar) >= self.long_max_time_in)):
                    self.position.close()
            else:
                # RSI OBJECTIVES
                if self.rsi[-2] > 30 and self.rsi < 30:
                    self.cont += 1
                if self.cont == 4:
                    self.position.close()
                # TIME OUT
                elif (self.data.index[-2] - self.trades[-1].entry_bar) >= self.short_max_time_in and Trailing == False:
                    if self.trades[-1].pl > 0:
                        if price < self.trades[-1].entry_price - self.profit:
                            self.trades[-1].sl = self.trades[-1].entry_price - self.profit
                        else:
                            self.trades[-1].sl = self.trades[-1].entry_price
                    else:
                        self.position.close()
                # RSI OPOSITE OBOS
                if self.rsi > 70 and ((self.cont >= 2) or ((self.data.index[-1] - self.trades[-1].entry_bar) >= self.short_max_time_in)):
                    self.position.close()
                    


print('Backtesting...')
bt = Backtest(dataframe, Div, cash = cashinicial, exclusive_orders=False, margin = 1 / leverage, commission=0.00075, hedging=False) # margin = 1/leverage
stats = bt.run()
# stats = bt.optimize(dif = range(50, 500, 50),
#                     #maximize='Win Rate [%]')
#                     maximize='Equity Final [$]')
if Print_Stats(stats) == False: # Dado que los datos intratrade no parecen computar de forma correcta, las stats que pertenecen a trades individuales no son confiables, pero si los totales finales
    print(stats)
bt.plot()
