# trading-bot
This is a personal project to build a pyhton crypto trading bot with the capabilities of backtesting a strategy and selecting the most optimal configurations to work as signals for buying and selling the desired currency

# Packages
We use the backtesting.py package that allows us to backtest and plot a given dataframe.

# Dataframe
The dataframe is obtained from the Binance API, which grants us historical data from the selected dates. A csv file is created for further backtesting, to avoid the download of huge chunks of data in every backtest.

# Strategy
Inside the strategy class we code the logic of the strategy we want to trade, in this case is regular divergences in the 15 min timeframe, adjusted to look for the most historically profitable ratios of take profit to stop loss, along with other specifications tested for increased profitability.

# Live trading
Once the strategy is selected and optimized, we run the bot with the use of the websocket package, which recieves a message with every price change in real time. Only when that  message marks the ending of a candle of the selected trading timeframe, we create a dataframe with the market data selecting the date at whichever point in time is the minimum necesary for the strategy to detect an entry or out. With such dataframe we run a backtest that tells us if the current candle close fired any action such as buy, sell, move take profit or stoploss, etc, and we use the exchange´s API functions to operate in the market.

# Notifications
We use the Telebot package to send a telegram message with actualizations on the bot activity, and we can also give instructions sending commands to the telegram bot.
