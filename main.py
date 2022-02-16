from ast import Try
from binance.client import Client
from binance.enums import *
from binance import ThreadedWebsocketManager
import config as Config
import numpy
import talib



RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
BOUGHT = False
SOLD = False

client = Client(Config.API_KEY, Config.API_SECRET)

def main():
    closes = []
    
    twm = ThreadedWebsocketManager(api_key=Config.API_KEY, api_secret=Config.API_SECRET)
    # start is required to initialise its internal loop
    twm.start()

    for kline in client.get_historical_klines_generator(Config.TRADESYMBOL, Client.KLINE_INTERVAL_1MINUTE, "1 day ago UTC"):
        closes.append(float(kline[4]))
    def order(side, type):
        try:
            print("placing order for {}".format(side))
            global BOUGHT
            global SOLD
            client.create_order(symbol=Config.TRADESYMBOL, side=side, type=type, quantity=Config.TRADEQUANTITY)
            if side == SIDE_BUY:
                BOUGHT = True
                SOLD = False
            else:
                SOLD = True
                BOUGHT = False
        except Exception as e:
            print("error placing order for {}".format(side))
            return False
        return True

    def handle_socket_message(msg):
        # print("candle: {}".format(msg['k']))
        candle = msg['k']
        close = candle['c']
        is_candle_closed = candle['x']
        if is_candle_closed:
            closes.append(float(close))
            print("close: {}".format(close))
            if len(closes) > RSI_PERIOD:
                np_closes = numpy.array(closes)
                rsi = talib.RSI(np_closes, RSI_PERIOD)
                last_rsi = rsi[-1]
                if last_rsi > RSI_OVERBOUGHT:
                    if not SOLD:
                        print("SELL SELL")
                        order(SIDE_SELL, ORDER_TYPE_MARKET)
                if last_rsi < RSI_OVERSOLD:
                    if not BOUGHT:
                        print("BUY BUY BUY")
                        order(SIDE_BUY, ORDER_TYPE_MARKET)
                print(last_rsi)
                # baseAsset = client.get_asset_balance(asset=ASSETS[1])
                # print("{} Balance: {}".format(ASSETS[1],baseAsset))
                # tradedAsset = client.get_asset_balance(asset=ASSETS[0])
                # print("{} Balance: {}".format(ASSETS[0], tradedAsset))
        # print("closes: {}".format(closes))

    twm.start_kline_socket(callback=handle_socket_message, symbol=Config.TRADESYMBOL, interval=Client.KLINE_INTERVAL_1MINUTE)

if __name__ == "__main__":
    main()
