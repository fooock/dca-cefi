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

## Install

The best way to run this script is by using Docker. Just pull the image and run it with 
your own strategy and exchange keys:

```sh
docker pull fooock/dca-cefi:latest
docker run -v $(pwd):/app:ro fooock/dca-cefi --strategy strategy.yaml --keys keys.yaml --test
```

>It is super important to mount the directory where your strategy and keys are located.

## How it works?

See the following strategy file as an example to undestand better the bot functionality:

>You can use the [Binance Sandbox](https://testnet.binance.vision/) to test this script.

```yaml
strategy:
  - amount: 50
    base_asset: usdt
    assets:
      - btc
      - eth
    exchanges:
      - binance
  - amount: 20
    base_asset: busd
    assets:
      - btc
    exchanges:
      - bitso
```

Our bot will execute two strategies in paralell. The first one:

| Field        	| Value                                                        	|
|--------------	|--------------------------------------------------------------------	|
| `amount`     	| `50` 	|
| `base_asset` 	| `USDT`                   	|
| `assets`     	| `BTC`, `ETH`                                       |
| `exchanges`  	| `binance`                              	|

This first strategy will use a total of `100 USDT` to buy `BTC` and `ETH` from Binance (`50` each one).

The second strategy:

| Field        	| Value                                                        	|
|--------------	|--------------------------------------------------------------------	|
| `amount`     	| `20` 	|
| `base_asset` 	| `BUSD`                   	|
| `assets`     	| `BTC`                                       |
| `exchanges`  	| `bitso`                              	|

This second strategy will use a total of `20 BUSD` to buy `BTC` from Bitso. 

>Note that our strategy will interact with two exchanges, so we need to create the required API keys and
>secrets to be able to recover information from our account.

In order to define the keys used by the exchanges we need to define it using a predefined format, the
exchange name as a key and `apiKey` and `secret` with the values provided by the exchange. For example:

```yaml
binance:
  apiKey: dead
  secret: beef
```

When you have all things defined just execute it:

```
(dca-cefi-env) $ python dca.py --strategy strategy.yaml --keys keys.yaml --test
```

>Note the flag `--test` is only used in sandbox environments.
