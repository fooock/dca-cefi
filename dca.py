import argparse
import ccxt
import logging
import tenacity
import yaml

from concurrent.futures.thread import ThreadPoolExecutor
from tenacity import RetryError, stop_after_attempt, wait_fixed
from yaml.loader import SafeLoader


NUMBER_OF_NETWORK_ATTEMPTS = 5
RETRY_WAIT_TIME_SECONDS = 1


class Strategy:
    """
    Generic class to create DCA strategies.
    """

    def __init__(self, amount, base_asset, assets, exchanges) -> None:
        self.amount = amount
        self.base_asset = base_asset
        self.assets = assets
        self.exchanges = exchanges

    def get_pairs(self):
        """
        Retrieve array of pairs used to run the strategy. All pairs have the same quote
        `base_asset`, so for example, for a list of assets of `[btc, eth]` and `usdt` as a quote
        asset, this will return the following content `["usdt/btc", "usdt/eth"]`
        """
        return ["{}/{}".format(quote, self.base_asset) for quote in self.assets]

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
        """
        Retrieve account balance.

        This method will be retried if the operation fails with any exception.
        The logic is to try to retry the operation up to five times waiting
        a fixed amount of time of one second.
        """
        for attempt in tenacity.Retrying(
            stop=stop_after_attempt(NUMBER_OF_NETWORK_ATTEMPTS),
            wait=wait_fixed(RETRY_WAIT_TIME_SECONDS),
        ):
            with attempt:
                logging.info(
                    f"#{attempt.retry_state.attempt_number} Trying to retrieve account balance"
                )
                return self.exchange.fetch_balance()

    def get_price(self, pair: str) -> dict:
        """
        Retrieve the ticker price for the given.

        This method will be retried if the operation fails with any exception.
        The logic is to try to retry the operation up to five times waiting
        a fixed amount of time of one second.
        """
        for attempt in tenacity.Retrying(
            stop=stop_after_attempt(NUMBER_OF_NETWORK_ATTEMPTS),
            wait=wait_fixed(RETRY_WAIT_TIME_SECONDS),
        ):
            with attempt:
                logging.info(
                    f"#{attempt.retry_state.attempt_number} Trying to retrieve ticker for symbol {pair}"
                )
                return self.exchange.fetch_ticker(pair)

    def buy(self, pair: str, amount: float) -> dict:
        """
        Creates a market buy order for the amount of the specified pair.

        This method will be retried if the operation fails with any exception.
        The logic is to try to retry the operation up to five times waiting
        a fixed amount of time of one second.
        """
        for attempt in tenacity.Retrying(
            stop=stop_after_attempt(NUMBER_OF_NETWORK_ATTEMPTS),
            wait=wait_fixed(RETRY_WAIT_TIME_SECONDS),
        ):
            with attempt:
                logging.info(
                    f"#{attempt.retry_state.attempt_number} Trying to create order for symbol {pair} and amount {amount}"
                )
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


class StrategyRunner:
    """
    Runner to execute strategies.
    """

    def __init__(self, no_balance_available_callback=None) -> None:
        self.no_balance_available_callback = no_balance_available_callback

    def run(self, strategy: Strategy, exchange: Exchange):
        # Retrieve balances in order to execute this strategy
        try:
            balances = exchange.get_balances()
        except RetryError:
            logging.error(
                f"Unable to retrieve account balance for exchange {exchange.name} ('{strategy}')"
            )
            return
        quote_balance = balances[strategy.base_asset]["free"]
        logging.info(
            f"Available balance in {exchange.name} for '{strategy}' is {quote_balance} {strategy.base_asset}"
        )
        # We are unable to execute the strategy because we don't have available
        # balance.
        if quote_balance < strategy.amount:
            logging.warning(
                f"We can't execute '{strategy}' since available funds are {quote_balance} and required amount is {strategy.amount}"
            )
            # Use our callback to do operations when this happens
            if self.no_balance_available_callback is not None:
                self.no_balance_available_callback(
                    exchange.name, quote_balance, strategy.amount, strategy.base_asset
                )
            return
        # If we have more than one pair, then we need to check if we have the required available
        # balance to fill all pair orders.
        strategy_total_amount = strategy.amount * len(strategy.get_pairs())
        logging.info(
            f"Required amount to execute '{strategy}' is {strategy_total_amount} {strategy.base_asset} for pair {strategy.get_pairs()}"
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
        orders = []
        for pair in order_pairs_to_create:
            # Retrieve ticker price for the current pair in order
            # to calculate the amount of unots to buy.
            try:
                ticker = exchange.get_price(pair)
            except RetryError:
                logging.error(
                    f"Unable to retrieve ticker for symbol {pair} in exchange {exchange.name} ('{strategy}')"
                )
                # Here we continue in the loop since we need to check each pair
                continue
            logging.info(
                f"Ask price for {pair} is {ticker['ask']} {strategy.base_asset}"
            )
            amount_to_buy = "{:.8f}".format(strategy.amount / ticker["ask"])

            # Try to create the buy order
            try:
                order = order = exchange.buy(pair, amount_to_buy)
                logging.info(
                    f"Order {order['id']} / symbol {pair} / amount {amount_to_buy} / price {order['price']} / status {order['status']}"
                )
                orders.append(order)
            except RetryError:
                logging.error(
                    f"Unable to create order for symbol {pair} with amount {amount_to_buy} in exchange {exchange.name} ('{strategy}')"
                )
                return

        logging.info(f"Created {len(orders)} orders for '{strategy}'")


def no_balance_available(exchange: str, current: float, expected: float, asset: str):
    """
    Callback to be notified when no funds are available in the strategy exchange.
    This can be used to send email/telegram notification and top-up the exchange
    account with more funds.
    """
    logging.error(
        f"Exchange {exchange} has {current} {asset} but expected {expected} {asset}"
    )


if __name__ == "__main__":

    # Configure basic logger
    logging.basicConfig(
        format="%(asctime)s [%(threadName)s] [%(levelname)s] - %(message)s",
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
            base_asset=strategy["base_asset"].upper(),
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

    runner = StrategyRunner(no_balance_available_callback=no_balance_available)
    with ThreadPoolExecutor(max_workers=5) as executor:
        for strategy in strategies:
            for exchange in exchanges:
                if exchange.name not in strategy.exchanges:
                    continue
                # Execute strategy in this exchange
                executor.submit(runner.run, strategy, exchange)
