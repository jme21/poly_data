"""
Compare BTC prices from multiple sources to find what Polymarket uses for settlement.

Sources:
1. Polymarket RTDS - crypto_prices (Binance feed)
2. Polymarket RTDS - crypto_prices_chainlink (Chainlink feed)
3. Binance direct API (multiple pairs: BTCUSDT, BTCUSDC, BTCFDUSD)
4. CoinGecko API

Settlement: Polymarket 15-minute BTC markets use Chainlink oracles for settlement.
"""

import asyncio
import json
import time
from datetime import datetime
import websockets
import requests
from collections import defaultdict

# Store latest prices from each source
prices = defaultdict(dict)
price_history = []

def get_binance_prices():
    """Get BTC prices from Binance for multiple pairs"""
    pairs = ['BTCUSDT', 'BTCUSDC', 'BTCFDUSD']
    results = {}

    try:
        # Use ticker/price endpoint for multiple symbols
        url = "https://api.binance.com/api/v3/ticker/price"
        response = requests.get(url, timeout=5)
        data = response.json()

        price_map = {item['symbol']: float(item['price']) for item in data}

        for pair in pairs:
            if pair in price_map:
                results[pair] = price_map[pair]
    except Exception as e:
        print(f"Binance error: {e}")

    return results

def get_coingecko_price():
    """Get BTC price from CoinGecko"""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price"
        params = {
            'ids': 'bitcoin',
            'vs_currencies': 'usd',
            'precision': 2
        }
        response = requests.get(url, params=params, timeout=5)
        data = response.json()
        return data.get('bitcoin', {}).get('usd')
    except Exception as e:
        print(f"CoinGecko error: {e}")
        return None

async def polymarket_websocket():
    """Connect to Polymarket RTDS and stream both price feeds"""
    uri = "wss://ws-live-data.polymarket.com"

    try:
        async with websockets.connect(uri) as ws:
            # Subscribe to both Binance and Chainlink feeds
            subscribe_binance = {
                "action": "subscribe",
                "subscriptions": [{
                    "topic": "crypto_prices",
                    "type": "update",
                    "filters": "btcusdt"
                }]
            }

            subscribe_chainlink = {
                "action": "subscribe",
                "subscriptions": [{
                    "topic": "crypto_prices_chainlink",
                    "type": "update",
                    "filters": json.dumps(["btc/usd"])
                }]
            }

            await ws.send(json.dumps(subscribe_binance))
            await ws.send(json.dumps(subscribe_chainlink))

            print("Connected to Polymarket RTDS, subscribed to BTC feeds...")

            # Set up ping task
            async def ping():
                while True:
                    try:
                        await ws.ping()
                        await asyncio.sleep(5)
                    except:
                        break

            ping_task = asyncio.create_task(ping())

            try:
                async for message in ws:
                    try:
                        data = json.loads(message)
                        topic = data.get('topic')
                        payload = data.get('payload', {})

                        if topic == 'crypto_prices':
                            price = payload.get('value')
                            if price:
                                prices['polymarket_binance']['BTCUSDT'] = float(price)
                                print_comparison()

                        elif topic == 'crypto_prices_chainlink':
                            price = payload.get('value')
                            if price:
                                prices['polymarket_chainlink']['BTC/USD'] = float(price)
                                print_comparison()

                    except json.JSONDecodeError:
                        pass
            finally:
                ping_task.cancel()

    except Exception as e:
        print(f"WebSocket error: {e}")

def print_comparison():
    """Print current price comparison"""
    now = datetime.now().strftime('%H:%M:%S')

    # Get fresh Binance and CoinGecko prices
    binance = get_binance_prices()
    coingecko = get_coingecko_price()

    prices['binance_direct'] = binance
    prices['coingecko']['BTC/USD'] = coingecko

    # Get Polymarket prices
    poly_binance = prices.get('polymarket_binance', {}).get('BTCUSDT')
    poly_chainlink = prices.get('polymarket_chainlink', {}).get('BTC/USD')

    print(f"\n{'='*70}")
    print(f"BTC Price Comparison @ {now}")
    print(f"{'='*70}")

    print(f"\n📡 POLYMARKET FEEDS:")
    print(f"   Binance feed (crypto_prices):      ${poly_binance:,.2f}" if poly_binance else "   Binance feed: waiting...")
    print(f"   Chainlink feed (settlement):       ${poly_chainlink:,.2f}" if poly_chainlink else "   Chainlink feed: waiting...")

    print(f"\n📊 DIRECT BINANCE API:")
    for pair, price in binance.items():
        print(f"   {pair}:                          ${price:,.2f}")

    print(f"\n🦎 COINGECKO:")
    print(f"   BTC/USD:                           ${coingecko:,.2f}" if coingecko else "   BTC/USD: error")

    # Calculate differences
    if poly_chainlink and binance.get('BTCUSDT'):
        diff_usdt = poly_chainlink - binance['BTCUSDT']
        print(f"\n📐 DIFFERENCES FROM CHAINLINK (settlement source):")
        print(f"   vs Binance BTCUSDT:               {diff_usdt:+.2f} (${abs(diff_usdt):.2f})")

        if binance.get('BTCUSDC'):
            diff_usdc = poly_chainlink - binance['BTCUSDC']
            print(f"   vs Binance BTCUSDC:               {diff_usdc:+.2f} (${abs(diff_usdc):.2f})")

        if coingecko:
            diff_cg = poly_chainlink - coingecko
            print(f"   vs CoinGecko:                     {diff_cg:+.2f} (${abs(diff_cg):.2f})")

        if poly_binance:
            diff_poly = poly_chainlink - poly_binance
            print(f"   vs Polymarket Binance feed:       {diff_poly:+.2f} (${abs(diff_poly):.2f})")

    # Record for analysis
    price_history.append({
        'time': now,
        'poly_chainlink': poly_chainlink,
        'poly_binance': poly_binance,
        'binance_usdt': binance.get('BTCUSDT'),
        'binance_usdc': binance.get('BTCUSDC'),
        'coingecko': coingecko
    })

async def main():
    print("🔍 BTC Price Source Comparison Tool")
    print("=" * 70)
    print("Comparing Polymarket settlement prices against multiple sources...")
    print("Settlement uses: Chainlink oracles (crypto_prices_chainlink)")
    print("Press Ctrl+C to stop\n")

    # Run WebSocket connection
    try:
        await polymarket_websocket()
    except KeyboardInterrupt:
        print("\n\nStopped by user")

        if price_history:
            print(f"\n📈 Summary: Collected {len(price_history)} price snapshots")

if __name__ == "__main__":
    asyncio.run(main())
