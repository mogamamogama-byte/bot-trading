import time
import os
import pandas as pd
from pybit.unified_trading import HTTP
from ta.momentum import RSIIndicator
from datetime import datetime

API_KEY = os.environ.get("H92kWmDZQEFz9g8bF7")
API_SECRET = os.environ.get("xGqbEowAL9eesGyxRjkRarm2IBICDvt6L00Y")
TESTNET = os.environ.get("TESTNET", "true").lower() == "true"

session = HTTP(
    testnet=TESTNET,
    api_key=API_KEY,
    api_secret=API_SECRET
)

CRYPTOS = {
    "BTCUSDT": {
        "capital": 500,
        "stop_loss": 2.0,
        "take_profit": 3.0,
        "qty_decimals": 6
    },
    "SOLUSDT": {
        "capital": 500,
        "stop_loss": 3.0,
        "take_profit": 5.0,
        "qty_decimals": 2
    }
}

RSI_ACHAT = 45
RSI_VENTE = 55
INTERVALLE = 60

stats = {}
for symbol in CRYPTOS:
    stats[symbol] = {
        "trades": 0,
        "gains": 0,
        "pertes": 0,
        "profit_total": 0.0,
        "prix_achat": 0.0,
        "en_position": False
    }

def get_prix_historique(symbol):
    result = session.get_kline(
        category="spot",
        symbol=symbol,
        interval="5",
        limit=100
    )
    df = pd.DataFrame(result['result']['list'])
    df.columns = ['timestamp','open','high','low','close','volume','turnover']
    df['close'] = df['close'].astype(float)
    df = df.iloc[::-1].reset_index(drop=True)
    return df

def calcule_rsi(df):
    rsi = RSIIndicator(close=df['close'], window=14)
    return rsi.rsi().iloc[-1]

def get_solde_usdt():
    result = session.get_wallet_balance(accountType="UNIFIED")
    coins = result['result']['list'][0]['coin']
    for coin in coins:
        if coin['coin'] == 'USDT':
            return float(coin['walletBalance'])
    return 0

def get_solde_coin(coin_name):
    result = session.get_wallet_balance(accountType="UNIFIED")
    coins = result['result']['list'][0]['coin']
    for coin in coins:
        if coin['coin'] == coin_name:
            return float(coin['walletBalance'])
    return 0

def acheter(symbol, prix):
    try:
        capital = CRYPTOS[symbol]['capital']
        session.place_order(
            category="spot",
            symbol=symbol,
            side="Buy",
            orderType="Market",
            qty=str(capital),
            marketUnit="quoteCoin"
        )
        stats[symbol]['prix_achat'] = prix
        stats[symbol]['trades'] += 1
        stats[symbol]['en_position'] = True
        print(f"✅ [{symbol}] ACHAT à {prix:.2f}$")
        return True
    except Exception as e:
        print(f"❌ [{symbol}] Erreur achat : {e}")
        return False

def vendre(symbol, prix, raison="RSI"):
    try:
        coin_name = symbol.replace("USDT", "")
        solde = get_solde_coin(coin_name)
        if solde < 0.0001:
            print(f"⚠️ [{symbol}] Pas assez de {coin_name}")
            return False
        decimals = CRYPTOS[symbol]['qty_decimals']
        qty = round(solde * 0.99, decimals)
        session.place_order(
            category="spot",
            symbol=symbol,
            side="Sell",
            orderType="Market",
            qty=str(qty),
            marketUnit="baseCoin"
        )
        prix_achat = stats[symbol]['prix_achat']
        if prix_achat > 0:
            profit_pct = ((prix - prix_achat) / prix_achat) * 100
            profit_usdt = profit_pct / 100 * CRYPTOS[symbol]['capital']
            stats[symbol]['profit_total'] += profit_usdt
            if profit_pct > 0:
                stats[symbol]['gains'] += 1
            else:
                stats[symbol]['pertes'] += 1
        stats[symbol]['prix_achat'] = 0.0
        stats[symbol]['en_position'] = False
        print(f"✅ [{symbol}] VENTE [{raison}] à {prix:.2f}$")
        return True
    except Exception as e:
        print(f"❌ [{symbol}] Erreur vente : {e}")
        return False

print("🚀 Bot démarré !")
print(f"🌐 Testnet : {TESTNET}")
print(f"📊 Cryptos : {list(CRYPTOS.keys())}")

while True:
    try:
        for symbol in CRYPTOS:
            df = get_prix_historique(symbol)
            rsi = calcule_rsi(df)
            prix = df['close'].iloc[-1]

            en_position = stats[symbol]['en_position']
            prix_achat = stats[symbol]['prix_achat']

            if en_position and prix_achat > 0:
                pnl_pct = ((prix - prix_achat) / prix_achat) * 100
                if pnl_pct <= -CRYPTOS[symbol]['stop_loss']:
                    print(f"🛑 [{symbol}] STOP-LOSS ! {pnl_pct:.2f}%")
                    vendre(symbol, prix, "STOP-LOSS")
                elif pnl_pct >= CRYPTOS[symbol]['take_profit']:
                    print(f"🎯 [{symbol}] TAKE-PROFIT ! {pnl_pct:.2f}%")
                    vendre(symbol, prix, "TAKE-PROFIT")

            solde_usdt = get_solde_usdt()
            if rsi < RSI_ACHAT and not en_position and solde_usdt >= CRYPTOS[symbol]['capital']:
                print(f"📈 [{symbol}] RSI={rsi:.1f} → ACHAT")
                acheter(symbol, prix)
            elif rsi > RSI_VENTE and en_position:
                print(f"📉 [{symbol}] RSI={rsi:.1f} → VENTE")
                vendre(symbol, prix, "RSI")
            else:
                print(f"⏰ {datetime.now().strftime('%H:%M:%S')} [{symbol}] Prix:{prix:.2f}$ RSI:{rsi:.1f} → {'EN POSITION' if en_position else 'EN ATTENTE'}")

        time.sleep(INTERVALLE)

    except Exception as e:
        print(f"❌ Erreur : {e}")
        time.sleep(30)
