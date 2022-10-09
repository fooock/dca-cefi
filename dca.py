import argparse
import ccxt
import logging
import yaml

from yaml.loader import SafeLoader


class Strategy:
    """
    Generic class to create DCA strategies.
    """

    def __init__(self, amount, quote_asset, assets, exchanges) -> None:
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
        return f"strategy-{self.amount}"


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

    def __repr__(self) -> str:
        return self.exchange.name

    def __hash__(self) -> int:
        return hash(self.name)


class Runner:
    """
    Runner to execute strategies.
    """

    def run(self, strategy: Strategy, exchange: Exchange):
        # Retrieve balances in order to execute this strategy
        balances = exchange.get_balances()
        quote_balance = balances[strategy.quote_asset]["free"]
        logging.info(
            f"Available balance in {exchange.name} for '{strategy}' is {quote_balance} {strategy.quote_asset}"
        )
        # We are unable to execute the strategy because we don't have available
        # balance.
        if quote_balance < strategy.amount:
            logging.warning(
                f"We can't execute '{strategy}' since available funds are {quote_balance} and required amount is {strategy.amount}"
            )
            return
        # If we have more than one pair, then we need to check if we have the required available
        # balance to fill all pair orders.
        strategy_total_amount = strategy.amount * len(strategy.get_pairs())
        logging.info(
            f"Required amount to execute '{strategy}' is {strategy_total_amount} {strategy.quote_asset} for pair {strategy.get_pairs()}"
        )
        order_pairs_to_create = []
        aux_balance = 0
        for pair in strategy.get_pairs():
            if (aux_balance + strategy.amount) <= quote_balance:
                aux_balance += strategy.amount
                order_pairs_to_create.append(pair)
        logging.info(
            f"Prepared to create orders for '{strategy}' in pairs {order_pairs_to_create} for a total amount of {aux_balance}"
        )
        if len(order_pairs_to_create) != len(strategy.get_pairs()):
            logging.info(
                f"Partialy execute '{strategy}' for pairs {order_pairs_to_create} (originaly {strategy.get_pairs()})"
            )
        # Lets go to create orders


if __name__ == "__main__":

    # Configure basic logger
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
            amount=int(strategy["amount"]),
            quote_asset=strategy["quote_asset"].upper(),
            assets=[asset.upper() for asset in strategy["assets"]],
            exchanges=strategy["exchanges"],
        )
        # Iterate over each strategy to create them
        for strategy in read_strategies["strategy"]
    ]
    for strategy in strategies:
        logging.info(
            f"Detected '{strategy}' for pairs {strategy.get_pairs()} into exchanges {strategy.exchanges}"
        )
    # Build exchange objects based on the ones found in strategies.
    # These ones are being used inside the strategy runner.
    exchanges = [
        Exchange(name=exchange, keys=read_keys[exchange], test=args.test)
        for strategy in strategies
        for exchange in strategy.exchanges
    ]
    exchanges = list(set(exchanges))
    logging.info(f"Created {len(exchanges)} exchanges: {exchanges}")

    runner = Runner()
    for strategy in strategies:
        for exchange in exchanges:
            if exchange.name not in strategy.exchanges:
                continue
            # Execute strategy in this exchange
            runner.run(strategy, exchange)
