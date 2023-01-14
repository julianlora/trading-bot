import websocket, json, talib, numpy, requests, math, asyncio
from backtesting import Backtest, Strategy
import pandas as pd
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, FUTURE_ORDER_TYPE_STOP_MARKET, FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, HistoricalKlinesType, ORDER_TYPE_MARKET
from datetime import datetime, timedelta
from telebot.async_telebot import AsyncTeleBot

apikey = 'your key'
secret = 'your secret key'
client = Client(apikey, secret)

SOCKET = 'wss://stream.binance.com:9443/ws/btcusdt@kline_15m'

RSI_PERIOD = 14
RSI_OVERBOUGHT = 70
RSI_OVERSOLD = 30
TRADE_SYMBOL = 'BTCUSDT'
INTERVAL = Client.KLINE_INTERVAL_15MINUTE
searching_long = searching_short = False
Long_regular = Short_regular = False

closes = [] # Track the closing prices for analysis
time_out = sl_to_breakeven = sl_to_profit = send_rsi_count = send_result = stop = oposite_obos = False
time_in = contrsi = 0
cash = cash_pretrade = 0.0
position_status = backtest_status = 'none'
leverage = 5
initialize = True

# SET LEVERAGE
#client.futures_change_leverage(symbol='BTCUSDT', leverage=2)

def Truncate(f, n):
    try:
        return math.floor(f * 10 ** n) / 10 ** n
    except Exception as e:
        return 0

def Get_Cash():
    account = client.futures_account_balance()
    for data in account:
        if data['asset'] == 'USDT':
            cash = float(data['balance'])
    return cash

def Send_Notif(text):
    token = "your token"
    url = f"https://api.telegram.org/bot{token}"
    params = {"your params"}
    r = requests.get(url + "/sendMessage", params=params)

def Send_position_status(rsi, breakeven, time_in):
    info = client.futures_position_information(symbol=TRADE_SYMBOL)
    if float(info[-1]['positionAmt']) != 0:
        data = client.futures_get_all_orders(symbol=TRADE_SYMBOL)
        for order in reversed(data):
            if order['type'] == 'MARKET':
                if order['side'] == 'BUY':
                    side = 'LONG'
                    if breakeven:
                        sl = "Si"
                        tiempo_restante = "cumplido"
                    else:
                        sl = "No"
                        tiempo_restante = Div.long_max_time_in - time_in
                        if tiempo_restante / 4 > 1: tiempo_restante = "en " + str(round((tiempo_restante / 4), 2)) + " hs"
                        else: tiempo_restante = "en " + str(tiempo_restante * 15) + " min"
                else:
                    side = 'SHORT'
                    if breakeven:
                        sl = "Si"
                        tiempo_restante = "cumplido"
                    else:
                        sl = "No"
                        tiempo_restante = Div.short_max_time_in - time_in
                        if tiempo_restante / 4 > 1: tiempo_restante = "en " + str(round((tiempo_restante / 4), 2)) + " hs"
                        else: tiempo_restante = "en " + str(tiempo_restante * 15) + " min"
                info = client.futures_position_information(symbol=TRADE_SYMBOL)
                if float(info[-1]['unRealizedProfit']) > 0: profit = "+" + str(round(float(info[-1]['unRealizedProfit']), 2))
                else: profit = str(round(float(info[-1]['unRealizedProfit']), 2))
                
                Send_Notif("Posición actual: {0}\n\nUnrealized Pnl: {1}\n\nObjetivos RSI: {2} de 4\n\nSL al breakeven: {3}\n\nTime out: {4}".format(side, profit, rsi, sl, tiempo_restante))
                break
    else: Send_Notif("No hay posición abierta")

def Dataframe_Maker():
    
    # CALCULATE STARTING DATE
    rangos = [Div.rango_de_busqueda_long, Div.rango_de_busqueda_hidden_short, Div.rango_de_busqueda_hidden_long, Div.rango_de_busqueda_hidden_short,
                Div.long_max_time_in, Div.short_max_time_in]
    maxrango = max(rangos)
    bars_back = maxrango + RSI_PERIOD + 1
    days_back = int(((bars_back * 15) / 60) / 24) + 3
    today = datetime.now()
    date_start = (today - timedelta(days_back)).strftime('%d %b %Y')
    
    # CREATE DATAFRAME
    print('\nCreating Dataframe since {}'.format(date_start))
    dataframe = pd.DataFrame(client.get_historical_klines(TRADE_SYMBOL, INTERVAL, date_start, klines_type=HistoricalKlinesType.FUTURES))
    dataframe.columns = ['Date', 'Open', 'High', 'Low', 'Close', 'Volume','1','2','3','4','5','6']
    dataframe.drop(['1','2','3','4','5','6'], axis=1, inplace=True)
    dataframe['Date'] = pd.to_datetime(dataframe['Date']/1000, unit='s')
    numeric_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
    dataframe[numeric_columns] = dataframe[numeric_columns].apply(pd.to_numeric, axis=1)
    
    return dataframe
        
def order(side):
    try:
        print('\nSending order...')
        price = client.futures_symbol_ticker(symbol=TRADE_SYMBOL)
        d = Truncate((cash * leverage) / float(price['price']), 3)
        client.futures_create_order(symbol=TRADE_SYMBOL, side=side, quantity=d, type='MARKET') # CREAR ORDER MARKET
    except Exception as e: # Puede fallar si no hay equity suficiente en la cuenta para cubrir la orden
        return False 
    
    return True

def Take_Profit(direction):
    # Chequear que el price pasado no sea una string, y que los decimales sean max 2.
    try:
        info = client.futures_position_information(symbol=TRADE_SYMBOL)
        price = float(info[-1]['entryPrice'])
        if direction == 'LONG':
            tp = Truncate(price + (price * (Div.tplong / 1000)), 1)
            client.futures_create_order(symbol=TRADE_SYMBOL, side=SIDE_SELL, type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, stopPrice=tp, closePosition=True)
        elif direction == 'SHORT':
            tp = Truncate(price - (price * (Div.tpshort / 1000)), 1)
            client.futures_create_order(symbol=TRADE_SYMBOL, side=SIDE_BUY, type=FUTURE_ORDER_TYPE_TAKE_PROFIT_MARKET, stopPrice=tp, closePosition=True)
    except Exception as e:
        return False
    return True

def Stop_Loss(direction):
    # Chequear que el price pasado no sea una string, y que los decimales sean max 2..
    try:
        info = client.futures_position_information(symbol=TRADE_SYMBOL)
        price = float(info[-1]['entryPrice'])
        if direction == 'LONG':
            sl = Truncate(price - (price * (Div.sllong / 1000)), 1)
            client.futures_create_order(symbol=TRADE_SYMBOL, side=SIDE_SELL, type=FUTURE_ORDER_TYPE_STOP_MARKET, stopPrice=sl, closePosition=True)
        elif direction == 'SHORT':
            sl = Truncate(price + (price * (Div.slshort / 1000)), 1)
            client.futures_create_order(symbol=TRADE_SYMBOL, side=SIDE_BUY, type=FUTURE_ORDER_TYPE_STOP_MARKET, stopPrice=sl, closePosition=True)
    except Exception as e:
        return False
    return True

def Close_Position(direction):
    try:
        info = client.futures_symbol_ticker(symbol='BTCUSDT')
        price = round(float(info['price']), 1)
        closed = False
        while not closed:
            if direction == 'LONG':
                price -= 10
                closed = Stop_Loss(price, direction)
            else:
                price += 10
                closed = Stop_Loss(price, direction)
        print("CLOSE ORDER PLACED: waiting for order to complete")
        Send_Notif("Cerrando la posicion...")
        closed = False
        while not closed:
            info = client.futures_position_information(symbol=TRADE_SYMBOL)
            if float(info[-1]['positionAmt']) == 0:
                closed = True 
        global position_status
        position_status = 'none'
        Send_Notif("POSICION CERRADA")
    except Exception as e:
        Send_Notif("Error al cerrar posicion")
        return False
    return True
      
def on_open(ws):
    if initialize:
        Send_Notif("Opened connection")
        print('\nOpened connection: analysing current status')
        Market_Analysis(message=0, run_forever=False)
        Send_position_status(contrsi, sl_to_breakeven, time_in)

def on_close(ws):
    print('\nClosed connection')
    Send_Notif("Conexión interrumpida")

class Div(Strategy):
    
    """CONDICIONES DE ESTRATEGIA
    1. DIVERGENCIAS.
    2. Solo generadas en over o underbought RSI (OBOS).
    3. Cuando se encuentra una divergencia, se espera a que
    el RSI se mueva al menos una vez hacia la direccion del trade
    4. TIME OUT: Si despues de X cantidad de barras, el trade esta ganando, mover el sl a breakeven. Si esta perdiendo, cerrar el trade.
    5. RSI COUNTER: Si el trade todavía no salio por ningun TP/SL y se alcanzo el OBOS contrario X cantidad de veces, cerrar trade."""
    
    upper_bound = 70
    lower_bound = 30
    tplong = 35.5 # 30 = (0.03) (3%)
    sllong = 25 # 5 = (0.005) (0.5%)
    tpshort = 42.5
    slshort = 25
    rango_de_busqueda_long = 75
    rango_de_busqueda_short = 89
    rango_ignorado_long = 36 #(en positivo)
    rango_ignorado_short = 49
    rango_de_busqueda_hidden_long = 114
    rango_de_busqueda_hidden_short = 114
    rango_ignorado_hidden_long = 110
    rango_ignorado_hidden_short = 115
    long_max_time_in = 175
    short_max_time_in = 180
    cont = 0
    profit = 180
    dif = 150

    def init(self):
        self.rsi = self.I (talib.RSI, self.data.Close, 14)
        
    def next (self):

        price = self.data.Close[-1]
        top = bottom = self.rsi
        top_price = bottom_price = 0.0
        top_bar = bottom_bar = 0    
        
        global Long_regular, Short_regular
        global searching_long, searching_short
        global position_status, time_out, sl_to_breakeven, sl_to_profit, send_rsi_count, time_in, contrsi, oposite_obos, backtest_status
        contrsi = self.cont
        
        Long_regular = Short_regular = send_rsi_count = oposite_obos = False
        
        #DIVERGENCIAS
        if len(self.trades) < 1:
            
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

        if not self.position: #and self.tp > self.sl:
            
            backtest_status = 'none'
            self.cont = 0
            time_out = False
            sl_to_breakeven = False
            sl_to_profit = False
            time_in = 0
            
            if searching_long and self.rsi[-2] < self.rsi:
                Long_regular = True
            elif searching_short and self.rsi[-2] > self.rsi:
                Short_regular = True

            if Long_regular:
                self.buy(size=1,
                         tp= price + (price * (self.tplong / 1000)),
                         sl= price - (price * (self.sllong / 1000)))
                searching_long = False
            
            if Short_regular:
                self.buy(size=-1,
                         tp= price - (price * (self.tpshort / 1000)),
                         sl= price + (price * (self.slshort / 1000)))
                searching_short = False
                
        else:
            time_in = int(self.data.index[-1]) - self.trades[-1].entry_bar

            if self.position.is_long:
                backtest_status = 'LONG'
                # RSI OBJECTIVES
                if self.rsi[-2] < 70 and self.rsi > 70:
                    self.cont += 1
                    send_rsi_count = True
                if self.cont == 4:
                    self.position.close()
                    send_rsi_count = True
                # TIME OUT
                elif (self.data.index[-2] - self.trades[-1].entry_bar) >= self.long_max_time_in: # LONG
                    if self.trades[-1].pl > 0:
                        if price > (self.trades[-1].entry_price + self.profit):
                            self.trades[-1].sl = self.trades[-1].entry_price + self.profit
                            sl_to_profit = True
                        else:
                            self.trades[-1].sl = self.trades[-1].entry_price + 5
                        sl_to_breakeven = True
                    else:
                        self.position.close()
                        time_out = True
                # OPOSITE RSI OBOS
                if self.position and self.rsi < 30 and ((self.cont >= 2) or ((self.data.index[-1] - self.trades[-1].entry_bar) >= self.long_max_time_in)):
                    self.position.close()
                    oposite_obos = True
            else:
                backtest_status = 'SHORT'
                # RSI OBJECTIVES
                if self.rsi[-2] > 30 and self.rsi < 30:
                    self.cont += 1
                    send_rsi_count = True
                if self.cont == 4:
                    self.position.close()
                    send_rsi_count = True
                # TIME OUT
                elif (self.data.index[-2] - self.trades[-1].entry_bar) >= self.short_max_time_in: # SHORT
                    if self.trades[-1].pl > 0:
                        if price < self.trades[-1].entry_price - self.profit:
                            self.trades[-1].sl = self.trades[-1].entry_price - self.profit
                            sl_to_profit = True
                        else:
                            self.trades[-1].sl = self.trades[-1].entry_price - 5
                        sl_to_breakeven = True
                    else:
                        self.position.close()
                        time_out = True
                # OPOSITE RSI OBOS
                if self.position and self.rsi > 70 and ((self.cont >= 2) or ((self.data.index[-1] - self.trades[-1].entry_bar) >= self.short_max_time_in)):
                    self.position.close()
                    oposite_obos = True

def Market_Analysis(message, run_forever = True):
    global closes
    global position_status, send_result, stop, cash, cash_pretrade, time_out, sl_to_breakeven, sl_to_profit, send_rsi_count, time_in, initialize
    global Long_regular, Short_regular
    
    if run_forever:
        json_message = json.loads(message) #convierte strings to python data
        candle = json_message['k'] #ohlc etc
        is_candle_closed = candle['x'] # Verdadero cuando el tick recibido es el ultimo de la barra
        close = candle['c'] # (es string)
        #print(close)
    else:
        #close = client.get_symbol_ticker(symbol=TRADE_SYMBOL)
        is_candle_closed = True
    
    if is_candle_closed and not stop:
        if run_forever:
            print('\nCandle closed at {} USDT'.format(round(float(close), 2)))
            #closes.append(float(close)) # Agrega nuevo close al array (innecesario por ahora)
        
        # Seguimiento REAL de la posicion, no tiene que ser afectado por la simulacion, cambia solo con movimientos reales
        info = client.futures_position_information(symbol=TRADE_SYMBOL)
        if float(info[-1]['positionAmt']) != 0:
            data = client.futures_get_all_orders(symbol=TRADE_SYMBOL)
            for dat in reversed(data):
                if dat['type'] == 'MARKET':
                    if dat['side'] == 'BUY':
                        position_status = 'LONG'
                    else: position_status = 'SHORT'
                    break
        else: position_status = 'none'
        
        # GET DATAFRAME
        df = Dataframe_Maker()
        cash = Get_Cash()
        
        # EJECUTAR ANALISIS
        print('\nAnalysing...')
        bt = Backtest(df, Div, cash = cash, margin=1, commission=0.00075)
        bt.run()
        bt.plot()
        
        if position_status == 'none':
            if send_result == True:
                send_result = False
                if cash_pretrade < cash: Send_Notif("GANADO\nProfit: +{0} USD\nCapital actual: {1}".format(round((cash - cash_pretrade), 2), round(cash, 2)))
                else: Send_Notif("PERDIDO\nLoss: -{0} USD\nCapital actual: {1}".format(round((cash_pretrade - cash), 2), round(cash, 2)))
                #bt.plot()
            cash_pretrade = cash
            
            if backtest_status == 'LONG':
                print('\nLong signal')
                intentos = 0
                order_succeeded = False
                while not order_succeeded and intentos < 5:
                    intentos += 1
                    order_succeeded = order(SIDE_BUY)
                if order_succeeded:
                    position_status = 'LONG'
                    Send_Notif("------ LONG successfully placed ------")
                    print('\n----- Order success. Creating TP/SL -----')
                    info = client.futures_get_open_orders(symbol=TRADE_SYMBOL)
                    for i in range(5):
                        if len(info) != 2:
                            Take_Profit(position_status)
                            Stop_Loss(position_status)
                            info = client.futures_get_open_orders(symbol=TRADE_SYMBOL)
                    if len(info) != 2:
                        Send_Notif("Error al crear TP/SL")
                        Close_Position(position_status)
                    else: Send_Notif("TP/SL creado")
                else:
                    print('\nORDER FAILED')
                    Send_Notif("Long order failed")
                    stop = True                
            elif backtest_status == 'SHORT':
                print('\nShort signal')
                intentos = 0
                order_succeeded = False
                while not order_succeeded and intentos < 5:
                    intentos += 1
                    order_succeeded = order(SIDE_SELL)
                if order_succeeded:
                    position_status = 'SHORT'
                    Send_Notif("------ SHORT successfully placed ------")
                    print('\n----- Order success. Creating TP/SL -----')
                    info = client.futures_get_open_orders(symbol=TRADE_SYMBOL)
                    for i in range(5):
                        if len(info) != 2:
                            Take_Profit(position_status)
                            Stop_Loss(position_status)
                            info = client.futures_get_open_orders(symbol=TRADE_SYMBOL)
                    if len(info) != 2:
                        Send_Notif("Error al crear TP/SL")
                        Close_Position(position_status)
                    else: Send_Notif("TP/SL creado")
                else:
                    print('\nORDER FAILED')
                    Send_Notif("Short order failed")
                    stop = True
            else: print('\nNo signal')
            
        elif run_forever:        
            if time_out:
                print('\nClosing position due to time out...')
                Send_Notif("CLOSE: Time out")
                Close_Position(position_status)
                time_out = False
            elif oposite_obos:
                Send_Notif("CLOSE: Oposite RSI OBOS")
                Close_Position(position_status)
            elif send_rsi_count:
                if contrsi == 4:
                    Send_Notif("CLOSE: Objetivos RSI completados (4/4)")
                    Close_Position(position_status)
                elif contrsi != 0: Send_Notif("Rsi objetives: {} of 4".format(contrsi))
                send_rsi_count = False
            if position_status != 'none': # corroborar que no se haya cerrado la posicion en los pasos anteriores
                if sl_to_breakeven:
                    info = client.futures_position_information(symbol=TRADE_SYMBOL)
                    price = Truncate(float(info['entryPrice']), 1)
                    if position_status == 'LONG':
                        if sl_to_profit:
                            price += float(Div.profit)
                        else:
                            price += 5
                        if Stop_Loss(price, 'LONG'): Send_Notif('Stop loss movido al breakeven + 180')
                        else: Send_Notif('Error al mover stop loss')
                    else:
                        if sl_to_profit:
                            price -= float(Div.profit)
                        else:
                            price -= 5
                        if Stop_Loss(price, 'SHORT'): Send_Notif('Stop loss movido al breakeven - 180')
                        else: Send_Notif('Error al mover stop loss')
                    sl_to_breakeven = False
                    print("Stop loss movido al breakeven")
            else:
                print('Posicion cerrada')
            send_result = True
        
        if run_forever or initialize:            
            initialize = False
            if position_status != "none":
                print('\nIn position since {} candles'.format(time_in))
            ws.close()
            
def on_message(ws, message): #'message' es la informacion que recibe del broker
    Market_Analysis(message=message)

ws = websocket.WebSocketApp(SOCKET, on_open=on_open, on_close=on_close, on_message=on_message)

async def Run_Bot():
    try:
        print("\nBot running")
        await ws.run_forever()
    except Exception as e:
        return False
    return True

async def Trading_bot():
    await Run_Bot()
    print('sleeping')
    now = str(datetime.now())[14:16]
    while now != '14' and now != '29' and now != '44' and now != '59':
        await asyncio.sleep(30)
        now = str(datetime.now())[14:16]

bot = AsyncTeleBot('your token')

# Handle all other messages with content_type 'text' (content_types defaults to ['text'])
@bot.message_handler(func=lambda message: True)
async def reply(message):
    if message.text == 'hola' or message.text == 'Hola':
        await bot.reply_to(message, 'chau')
    elif message.text == 'cash' or message.text == 'Cash':
        await bot.reply_to(message, str(Truncate(Get_Cash(), 2)) + ' USDT')
    elif message.text == 'status' or message.text == 'Status':
        Send_position_status(contrsi, sl_to_breakeven, time_in)
    elif message.text == 'price' or message.text == 'Price':
        price = client.futures_symbol_ticker(symbol=TRADE_SYMBOL)
        await bot.reply_to(message, str(price['price']) + ' USDT')
    elif message.text == 'plot' or message.text == 'Plot':
        df = Dataframe_Maker()
        bt = Backtest(df, Div, cash = cash, exclusive_orders=False, margin=1, commission=0.00075)
        bt.run()
        bt.plot()
    elif message.text == 'stop' or message.text == 'Stop':
        await bot.reply_to(message, 'Bot apagado')
        exit()
    elif message.text == 'menu' or message.text == 'Menu':
        await bot.reply_to(message, 'cash / status / price / plot / stop / alive')
    else: await bot.reply_to(message, 'alive')

async def main():
    run = True
    
    telegram_connection = asyncio.create_task(bot.infinity_polling())
    
    while run:
        task = asyncio.create_task(Trading_bot())
        await task
        
asyncio.run(main())
