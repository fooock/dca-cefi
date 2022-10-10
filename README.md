# Cryptocurrency `DCA` bot

>Dollar cost averaging bot for centralized exchanges.

This is a simple script to buy fixed amounts of some cryptocurrency assets in your preferred
exchanges. It supports any exchange available in [`CCXT`](https://github.com/ccxt/ccxt) (more than 100). 
You can run multiple strategies using the same bot.

A strategy is a file where we define the list of buy actions our bot is going to execute. See for example
the file [`strategy.yaml`](strategy.yaml) for more information. As a summary, each strategy will 
contain the following info:

| Field        	| Description                                                        	|
|--------------	|--------------------------------------------------------------------	|
| `amount`     	| This is the maximum amount our bot will buy per asset and exchange 	|
| `base_asset` 	| The asset we are going to use as a base currency                   	|
| `assets`     	| List of cryptocurrencies to buy                                       |
| `exchanges`  	| List of exchanges used to buy assets                               	|

### Features

* Supports more than 100 exchanges.
* Buy multiple cryptocurrencies at once.
* You can be notified when no funds are available in the exchange by implementing the [`no_balance_available_callback`](https://github.com/fooock/dca-cefi/blob/main/dca.py#L243) method.
* You can implement your own logic to know when to create buy orders by implementing the [`should_create_buy_order_callback`](https://github.com/fooock/dca-cefi/blob/main/dca.py#L254) method.
* The script is flexible enough to be run by hand, Docker, cronjob, or whatever you want.

## Install

The best way to run this script is by using Docker. Just pull the image and run it with 
your own strategy and exchange keys:

```sh
docker pull fooock/dca-cefi:latest
docker run -v $(pwd):/app:ro fooock/dca-cefi --strategy strategy.yaml --keys keys.yaml --test
```

>It is super important to mount the directory where your strategy and keys are located.
>The `--test` flag is only used in sandbox environments when the exchange supports it.

## How it works?

See the following strategy file as an example to undestand better the bot functionality:

>You can use the [Binance Sandbox](https://testnet.binance.vision/) to test this script.

```yaml
strategy:
  # Strategy 1
  - amount: 50
    base_asset: usdt
    assets:
      - btc
      - eth
    exchanges:
      - binance
  # Strategy 2
  - amount: 20
    base_asset: busd
    assets:
      - btc
    exchanges:
      - bitso
```

Our bot will execute two strategies in paralell.

>Note that our strategy will interact with two exchanges, so we need to create the required API keys and
>secrets to be able to recover information from our account.

#### Strategy one:

| Field        	| Value                                                        	|
|--------------	|--------------------------------------------------------------------	|
| `amount`     	| `50` 	|
| `base_asset` 	| `USDT`                   	|
| `assets`     	| `BTC`, `ETH`                                       |
| `exchanges`  	| `binance`                              	|

This first strategy will use a total of `100 USDT` to buy `BTC` and `ETH` from Binance (`50` each one).

#### Strategy two:

| Field        	| Value                                                        	|
|--------------	|--------------------------------------------------------------------	|
| `amount`     	| `20` 	|
| `base_asset` 	| `BUSD`                   	|
| `assets`     	| `BTC`                                       |
| `exchanges`  	| `bitso`                              	|

This second strategy will use a total of `20 BUSD` to buy `BTC` from Bitso. 

## Exchange keys

To be able to create orders in the selected exchanges you need to create your API keys and secrets. This
is something that needs to be kept private, that's why you need to define it in a separate file from the strategy.
Based on the exchange, the method can be different, so check your Exchange documentation.

In order to define the keys used by the exchanges we need to define it using a predefined format, the
exchange name as a key and `apiKey` and `secret` with the values provided by the exchange. For example:

```yaml
binance:
  apiKey: dead
  secret: beef
```

## Donate

If you want to be a supporter, you can use this address in any EVM network to send me donations `0x63335aA5efbfB9D591B047354DBb012ce1CAfc0A`.
