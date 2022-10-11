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

    def __init__(self, period, amount, base_asset, assets, exchanges) -> None:
        self.period = period
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
        return f"strategy-{self.period}-{self.amount}"


class Exchange:
    """
    Generic class to interact with exchanges. Each exchange has its own
    method to build the client, so take that into account when
    building the exchange object.

    All methods from this class will be retried if the operation fails with any exception.
    The logic is to try to retry the operation up to five times waiting
    a fixed amount of time of one second.
    """

    def __init__(self, name, keys={}, test=True) -> None:
        exchange_class = getattr(ccxt, name)
        self.name = name
        self.exchange = exchange_class(keys)
        self.exchange.set_sandbox_mode(test)

    def get_buy_orders(self, pair: str) -> dict:
        """
        Retrieve my buy trades for the given pair.
        """
        for attempt in tenacity.Retrying(
            stop=stop_after_attempt(NUMBER_OF_NETWORK_ATTEMPTS),
            wait=wait_fixed(RETRY_WAIT_TIME_SECONDS),
        ):
            with attempt:
                logging.info(
                    f"#{attempt.retry_state.attempt_number} Trying to retrieve buy trades for {pair}"
                )
                orders = self.exchange.fetch_my_trades(symbol=pair)
                # This is to retrieve only buy orders
                return [order for order in orders if order["info"]["isBuyer"] is True]

    def get_balances(self) -> dict:
        """
        Retrieve account balance.
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
        return self.exchange.name.capitalize()

    def __hash__(self) -> int:
        return hash(self.name)


class StrategyRunner:
    """
    Runner to execute strategies.
    """

    def __init__(
        self,
        on_balance_no_available_callback=None,
        should_execute_buy_callback=None,
        on_order_created_callback=None,
    ) -> None:
        self.on_balance_no_available_callback = on_balance_no_available_callback
        self.should_execute_buy_callback = should_execute_buy_callback
        self.on_order_created_callback = on_order_created_callback

    def run(self, strategy: Strategy, exchange: Exchange):
        # Retrieve balances in order to execute this strategy
        try:
            balances = exchange.get_balances()
        except RetryError:
            logging.error(
                f"Unable to retrieve account balance for exchange {exchange} ('{strategy}')"
            )
            return
        quote_balance = balances[strategy.base_asset]["free"]
        logging.info(
            f"Available balance in {exchange} for '{strategy}' is {quote_balance} {strategy.base_asset}"
        )
        # We are unable to execute the strategy because we don't have available
        # balance.
        if quote_balance < strategy.amount:
            logging.warning(
                f"We can't execute '{strategy}' since available funds are {quote_balance} and required amount is {strategy.amount}"
            )
            # Use our callback to do operations when this happens
            if self.on_balance_no_available_callback is not None:
                self.on_balance_no_available_callback(
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
            # Retrieve last trades to use it to decide if we should buy
            # or not. This operation is completely optional and strategy
            # can continue its execution without it. Just take into account
            # that if you don't define a `should_execute_buy_callback`
            # you have a risk of emptying your account.
            try:
                created_orders = exchange.get_buy_orders(pair)
                logging.info(f"Found {len(created_orders)} buy orders from {exchange}")
            except RetryError:
                pass

            # This is a way to create custom buy logic based on some parameters
            # like past trades or any other type of condition.
            if (
                self.should_execute_buy_callback is not None
                and not self.should_execute_buy_callback(
                    pair, exchange.name, strategy.period, created_orders
                )
            ):
                logging.info(
                    f"Avoid creating buy order for {pair} in exchange {exchange}"
                )
                continue
            # Retrieve ticker price for the current pair in order
            # to calculate the amount of unots to buy.
            try:
                ticker = exchange.get_price(pair)
            except RetryError:
                logging.error(
                    f"Unable to retrieve ticker for symbol {pair} in exchange {exchange} ('{strategy}')"
                )
                # Here we continue in the loop since we need to check each pair
                continue
            logging.info(
                f"Ask price for {pair} is {ticker['ask']} {strategy.base_asset} in {exchange}"
            )
            amount_to_buy = "{:.8f}".format(strategy.amount / ticker["ask"])

            # Try to create the buy order
            try:
                order = order = exchange.buy(pair, amount_to_buy)
                logging.info(
                    f"Order {order['id']}-{exchange} / symbol {pair} / amount {amount_to_buy} / price {order['price']} / status {order['status']}"
                )
                orders.append(order)
                # Notify the created order to callback if available
                if self.on_order_created_callback is not None:
                    self.on_order_created_callback(exchange.name, order)
            except RetryError:
                logging.error(
                    f"Unable to create order for symbol {pair} with amount {amount_to_buy} in exchange {exchange} ('{strategy}')"
                )
                # Continue with the next pair
                continue

        logging.info(f"Created {len(orders)} orders for '{strategy}' in {exchange}")


def on_balance_no_available(exchange: str, current: float, expected: float, asset: str):
    """
    Callback to be notified when no funds are available in the strategy exchange.
    This can be used to send email/telegram notification and top-up the exchange
    account with more funds.
    """
    logging.error(
        f"Exchange {exchange} has {current} {asset} but expected {expected} {asset}"
    )


def should_create_buy_order(
    pair: str, exchange: str, period: str, orders: dict
) -> bool:
    """
    Callback to implement custom logic to know when to buy the given symbol in the
    current exchange.
    """
    logging.info(
        f"Checking if we can create buy order for symbol {pair} in exchange {exchange} ({period})"
    )
    if orders is None or len(orders) == 0:
        return False
    return True


def on_order_created(exchange: str, order: dict):
    """
    Callback to be notified when order is created in exchange.
    """
    pass


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
            period=strategy["period"],
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

    runner = StrategyRunner(
        on_balance_no_available_callback=on_balance_no_available,
        on_order_created_callback=on_order_created,
        should_execute_buy_callback=should_create_buy_order,
    )
    with ThreadPoolExecutor(max_workers=5) as executor:
        for strategy in strategies:
            for exchange in exchanges:
                if exchange.name not in strategy.exchanges:
                    continue
                # Execute strategy in this exchange
                executor.submit(runner.run, strategy, exchange)
