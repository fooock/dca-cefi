import argparse
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

    def bye(self, *args):
        self.is_stopped = True


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

    # Here we start processing our strategies based on the
    # configured period.
    bot = StopBot()
    while not bot.is_stopped:
        time.sleep(ONE_SECOND)
