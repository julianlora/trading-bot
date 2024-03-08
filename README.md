# Screens
![trading bot 2](https://github.com/julianlora/trading-bot/assets/120677363/a6375a94-c177-4434-a87a-38167d2c52ce)

![stats](https://github.com/julianlora/trading-bot/assets/120677363/dbd1e27d-0d1c-4e4b-a68f-3ef70d95acee)

![WhatsApp Image 2024-03-08 at 12 21 13](https://github.com/julianlora/trading-bot/assets/120677363/d2e7efed-1fb6-4c3b-b090-42d7e7dfb2bf)

# Trading-bot
This is a personal project to build a python crypto trading bot capable of backtesting a strategy and selecting the most optimal configurations to work as signals for buying and selling the desired currency

# Packages
We use the backtesting.py package that allows us to backtest and plot a given dataframe. Its source code has been modified to allow certain features that crypto trading requires but forex doesn't, such as trading with less than a unit of the currency, and leverage calculations.

# Dataframe
The dataframe is obtained from the Binance API, which provides historical data from the selected dates. A csv file is created for further backtesting, to avoid the download of huge chunks of data in every backtest.

# Strategy
Inside the strategy class we code the logic of the strategy we want to trade, in this case is trend continuation in the 15 min timeframe using a regression channel, adjusted to look for the most historically profitable ratios of take profit to stop loss, along with other specifications tested for increased profitability.

# Live trading
Once the strategy is selected and optimized, we run the bot with the use of the websocket package, which recieves a message with every price change in real time. Only when that message marks the ending of a candle of the selected trading timeframe, we create a dataframe with the market data selecting the date at whichever point in time is the minimum necesary for the strategy to detect an entry or out. With such dataframe we run a backtest that tells us if the current candle close fired any action such as buy, sell, move take profit or stoploss, etc, and we use the exchange´s API functions to operate in the market.

# Notifications
We use the Telebot package to send a telegram message with actualizations on the bot activity, and we can also give instructions sending commands to the telegram bot.
