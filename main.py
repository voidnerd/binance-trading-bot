from xmlrpc.client import Boolean
from binance.client import Client
from binance.enums import *
from binance import ThreadedWebsocketManager
from binance.helpers import round_step_size
import config as Config
import numpy
import talib


class Trade:
    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    def __init__(self, twm: ThreadedWebsocketManager, client: Client) -> None:
        self.twm = twm
        self.client = client
        self.closes = []
        self.close = 0
        self.buy_price = 0
        self.last_rsi = 0
        self.previous_rsi = 0
        self.bail_out_at = 0.2
        self.at_loss = False
        self.BOUGHT = False
        self.SOLD = True
        self.minQty = 0
        self.maxQty = 0
        self.stepSize = 0

    def get_first_set_of_closes(self) -> None:
        for kline in self.client.get_historical_klines(Config.TRADESYMBOL, Client.KLINE_INTERVAL_1MINUTE, "1 hour ago UTC"):
            self.closes.append(float(kline[4]))

    def start(self) -> None:
        self.get_first_set_of_closes()
        self.twm.start()
        self.twm.start_kline_socket(callback=self.handle_socket_message,
                                    symbol=Config.TRADESYMBOL, interval=Client.KLINE_INTERVAL_1MINUTE)

    def get_round_step_quantity(self, qty):
        info = self.client.get_symbol_info(Config.TRADESYMBOL)
        for x in info["filters"]:
            if x["filterType"] == "LOT_SIZE":
                self.minQty = float(x["minQty"])
                self.maxQty = float(x["maxQty"])
                self.stepSize= float(x["stepSize"])
        if qty < self.minQty:
            qty = self.minQty
        return round_step_size(quantity=qty, step_size=self.stepSize)
    
    def get_quantity(self, asset):
        balance = self.get_balance(asset=asset)
        quantity = self.get_round_step_quantity(float(balance))
        return quantity


    def get_balance(self, asset) -> str:
        balance = self.client.get_asset_balance(asset=asset)
        return balance['free']

    def buy(self):
        self.client.order_market_buy(
            symbol=Config.TRADESYMBOL,
            quoteOrderQty=self.get_quantity(Config.QUOTE_ASSET))

    def sell(self):
        self.client.order_market_sell(
            symbol=Config.TRADESYMBOL,
            quantity=self.get_quantity(Config.BASE_ASSET))

    def order(self, side: str) -> bool:
        try:
            if side == SIDE_BUY:
                self.buy()
                self.buy_price = self.close
                self.at_loss = False
                self.BOUGHT = True
                self.SOLD = False
            else:
                self.sell()
                self.SOLD = True
                self.BOUGHT = False
            self.previous_rsi = 0
        except Exception as e:
            print("Error placing order - price: {} - rsi: {}".format(self.close, self.last_rsi))
            return False
        return True

    def should_buy(self) -> bool:
        if self.at_loss and self.last_rsi > Trade.RSI_OVERSOLD:
            return True
        if self.previous_rsi != 0 and self.previous_rsi < self.last_rsi:
            return True
        if(self.last_rsi < Trade.RSI_OVERSOLD and not self.BOUGHT):
            if self.previous_rsi == 0:
                self.previous_rsi = self.last_rsi
                return False
            else:
                self.previous_rsi = self.last_rsi
                return False
        else:
            return False

    def should_sell(self) -> bool:
        if self.shouldStopLoss():
            self.at_loss = True
            return True
        if self.previous_rsi != 0 and self.previous_rsi > self.last_rsi:
            return True
        if(self.last_rsi >= Trade.RSI_OVERBOUGHT and not self.SOLD):
            if self.previous_rsi == 0:
                self.previous_rsi = self.last_rsi
                return False
            else:
                self.previous_rsi = self.last_rsi
                return False
        else:
            return False

    def shouldStopLoss(self) -> bool:
        stop_loss_price = self.buy_price - (self.buy_price * self.bail_out_at)
        if(self.close <= stop_loss_price):
            return True
        else:
            return False

    def buy_or_sell(self) -> None:
        if self.should_buy():
            print("Placing buy order - price: {} - rsi: {}".format(self.close, self.last_rsi))
            self.order(SIDE_BUY)
        if self.should_sell():
            print("Placing sell order - price: {} - rsi: {}".format(self.close, self.last_rsi))
            self.order(SIDE_SELL)

    def handle_socket_message(self, msg) -> None:
        candle = msg['k']
        self.close = float(candle['c'])
        is_candle_closed = candle['x']
        if is_candle_closed:
            self.closes.append(self.close)
            if len(self.closes) > 30:
                # We done't want the arry to get too big for the RAM
                self.closes.pop(0)
                np_closes = numpy.array(self.closes)
                rsi = talib.RSI(np_closes, Trade.RSI_PERIOD)
                self.last_rsi = rsi[-1]
                self.buy_or_sell()
                print("RSI - {}".format(self.last_rsi))


# Start The Trade
twm = ThreadedWebsocketManager(
    api_key=Config.API_KEY, api_secret=Config.API_SECRET)

client = Client(Config.API_KEY, Config.API_SECRET)

trade = Trade(twm, client)

if __name__ == '__main__':
    trade.start()
