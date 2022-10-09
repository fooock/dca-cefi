# Crypto `DCA` bot

>Dollar cost averaging bot.

This is a simple script to buy fixed amounts of some cryptocurrency assets in your preferred
exchanges. You can run multiple strategies using the same bot.

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

In order to run the script, first you need to install the required dependencies that can be found in
the [`requirements.txt`](requirements.txt) file. It is recommended to do this process in a virtual
environment.

```sh
$ python3 -m venv dca-cefi-env
```

When done, activate it and install:

```sh
$ source dca-cefi-env/bin/activate
(dca-cefi-env) $ pip install -r requirements.txt
```

You can see the bot functionality by executing the following command `python dca.py -h`:

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
