import argparse
import ccxt
import logging
import signal
import time
import yaml

from yaml.loader import SafeLoader


class Strategy:
    """
    Generic class to create DCA strategies.
    """

    def __init__(self, period, amount, quote_asset, assets, exchanges) -> None:
        self.period = period
        self.amount = amount
        self.quote_asset = quote_asset
        self.assets = assets
        self.exchanges = exchanges

    def get_pairs(self):
        """
        Retrieve array of pairs used to run the strategy. All pairs have the same quote
        `quote_asset`, so for example, for a list of assets of `[btc, eth]` and `usdt` as a quote
        asset, this will return the following content `["usdt/btc", "usdt/eth"]`
        """
        return ["{}/{}".format(self.quote_asset, base) for base in self.assets]

    def __str__(self) -> str:
        return f"strategy-{self.period}-{self.amount}"


class StopBot:
    """
    Class used to control the DCA bot lifecycle. All operations occur when
    the `stop` value is set to `False`.
    """

    def __init__(self) -> None:
        self.is_stopped = False
        signal.signal(signal.SIGINT, self.bye)

    def bye(self, *args) -> None:
        self.is_stopped = True


class Exchange:
    """
    Generic class to interact with exchanges. Each exchange has its own
    method to build the client, so take that into account when
    building the exchange object.
    """

    def __init__(self, name, keys={}, test=True) -> None:
        exchange_class = getattr(ccxt, name)
        self.name = name
        self.exchange = exchange_class(keys)
        self.exchange.set_sandbox_mode(test)

    def get_balances(self) -> dict:
        return self.exchange.fetch_balance()

    def get_price(self, pairs: list) -> dict:
        return self.exchange.fetch_tickers(pairs)

    def buy(self, pair: str, amount: float):
        """
        Creates a market buy order for the amount of the specified pair
        """
        return self.exchange.create_order(
            symbol=pair, type="market", side="buy", amount=amount
        )

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Exchange):
            return self.name == other.name
        return False


if __name__ == "__main__":
    ONE_SECOND: int = 1

    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(message)s",
        level=logging.INFO,
        datefmt="%m/%d/%Y %I:%M:%S",
    )
    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, help="The strategy to run")
    parser.add_argument("--keys", required=True, help="Exchange API keys")
    parser.add_argument("--test", default=False, action="store_true")

    args = parser.parse_args()

    # Load the strategy file and the API keys in order to send orders
    # to exchanges.
    with open(args.strategy, "r") as f:
        read_strategies = yaml.load(f, Loader=SafeLoader)
    with open(args.keys, "r") as f:
        read_keys = yaml.load(f, Loader=SafeLoader)

    strategies = [
        Strategy(
            period=strategy["period"],
            amount=strategy["amount"],
            quote_asset=strategy["quote_asset"],
            assets=strategy["assets"],
            exchanges=strategy["exchanges"],
        )
        # Iterate over each strategy to create them
        for strategy in read_strategies["strategy"]
    ]
    for strategy in strategies:
        logging.info(
            f"Running '{strategy}' for pairs {strategy.get_pairs()} into exchanges {strategy.exchanges}"
        )

    exchanges = [
        Exchange(name=exchange, keys=read_keys[exchange], test=args.test)
        for strategy in strategies
        for exchange in strategy.exchanges
    ]

    # Here we start processing our strategies based on the
    # configured period.
    bot = StopBot()
    while not bot.is_stopped:
        time.sleep(ONE_SECOND)
