import unittest
from unittest.mock import MagicMock
from main import Trade
from binance.client import Client
from binance.enums import *
from binance import ThreadedWebsocketManager
import config as Config

twm = ThreadedWebsocketManager(
    api_key=Config.TESTNET_API_KEY, api_secret=Config.TESTNET_API_SECRET, testnet=True)

client = Client(Config.TESTNET_API_KEY,
                Config.TESTNET_API_SECRET, testnet=True)


class TestUser(unittest.TestCase):

    def test_buys_when_rsi_is_oversold(self):
        trade = Trade(twm, client)

        trade.last_rsi = 24

        self.assertTrue(trade.should_buy())

    def test_sells_when_rsi_is_overbought(self):
        trade = Trade(twm, client)
        trade.SOLD = False

        trade.buy_price = 30
        trade.close = 35

        trade.last_rsi = 71

        self.assertTrue(trade.should_sell())

    def test_it_should_stop_buy_when_at_loss(self):
        trade = Trade(twm, client)

        trade.at_loss = True

        trade.last_rsi = 29

        self.assertFalse(trade.should_buy())

    def test_it_should_sell_you_hit_stop_loss(self):
        trade = Trade(twm, client)

        trade.buy_price = 30
        trade.close = 27

        self.assertTrue(trade.should_sell())
        self.assertTrue(trade.at_loss)

    def test_should_simulate_buy_or_sell_properly(self):
        trade = Trade(twm, client)
        trade.buy = MagicMock(return_value=None)
        trade.sell = MagicMock(return_value=None)
        trade.close = 24

        trade.last_rsi = 29.8
        trade.buy_or_sell()

        trade.buy.assert_called_once()
        self.assertTrue(trade.BOUGHT)
        self.assertFalse(trade.SOLD)

        trade.last_rsi = 71
        trade.buy_or_sell()

        trade.sell.assert_called_once()
        self.assertFalse(trade.BOUGHT)
        self.assertTrue(trade.SOLD)

    def test_should_simulate_buy_or_sell_when_at_loss_properly(self):
        trade = Trade(twm, client)
        trade.buy = MagicMock(return_value=None)
        trade.sell = MagicMock(return_value=None)
        trade.close = 30
        # Assert that we don't try to sell asset that we don't have
        # we we first enter the market.
        trade.last_rsi = 79
        trade.buy_or_sell()

        trade.sell.assert_not_called()

        # Assert buy is first order

        trade.last_rsi = 29.5
        trade.buy_or_sell()

        trade.buy.assert_called_once()

        # Assert can bail out when it hits stop loss
        trade.close = 28.5
        trade.buy_or_sell()

        trade.buy.assert_called_once()
        trade.sell.assert_called_once()
        self.assertTrue(trade.SOLD)
        self.assertFalse(trade.BOUGHT)
        self.assertTrue(trade.at_loss)

        # should do nothing
        trade.last_rsi = 26
        trade.buy_or_sell()
        trade.buy.assert_called_once()
        trade.sell.assert_called_once()
        self.assertTrue(trade.at_loss)

        # it should buy again when market is promising
        trade.last_rsi = 79
        trade.buy_or_sell()

        # trade.buy.assert_called()
        self.assertFalse(trade.at_loss)
        self.assertEqual(trade.buy.call_count, 1)

        # it should start buying again
        trade.last_rsi = 29
        trade.buy_or_sell()

        trade.sell.assert_called_once()
        self.assertEqual(trade.buy.call_count, 2)

        # it should sell
        trade.last_rsi = 72
        trade.buy_or_sell()

        self.assertEqual(trade.sell.call_count, 2)


if __name__ == '__main__':
    unittest.main()
