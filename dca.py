import argparse
import ccxt
import signal
import time
import yaml

from yaml.loader import SafeLoader


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
    Base class to interact with exchanges. Each exchange has its own
    method to build the client, so take that into account when
    building the exchange object.
    """

    def __init__(self, name, args) -> None:
        exchange_keys = {"apiKey": args["apiKey"], "secret": args["secret"]}
        exchange_class = getattr(ccxt, name)
        self.exchange = exchange_class(exchange_keys)
        self.exchange.set_sandbox_mode(True)

    def get_balance(self) -> dict:
        return self.exchange.fetch_balance()

    def get_price(self, pairs: list) -> dict:
        return self.exchange.fetch_tickers(pairs)

    def buy(self, pair: str, position: float):
        pass


if __name__ == "__main__":
    ONE_SECOND: int = 1

    parser = argparse.ArgumentParser()
    parser.add_argument("--strategy", required=True, help="The strategy to run")
    parser.add_argument("--keys", required=True, help="Exchange API keys")

    args = parser.parse_args()

    # Load the strategy file and the API keys in order to send orders
    # to exchanges.
    with open(args.strategy, "r") as f:
        strategy = yaml.load(f, Loader=SafeLoader)
    with open(args.keys, "r") as f:
        keys = yaml.load(f, Loader=SafeLoader)

    exchanges = [
        Exchange(name=exchange, args=keys[exchange])
        for exchange in strategy["strategy"][0]["exchanges"]
    ]
    # Here we start processing our strategies based on the
    # configured period.
    bot = StopBot()
    while not bot.is_stopped:
        usd = exchanges[0].get_balance()
        time.sleep(ONE_SECOND)
