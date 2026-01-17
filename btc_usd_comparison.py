"""
BTC/USD Price Source Comparison (with USDT adjustment)

Chainlink BTC/USD feed aggregates from 16 oracle operators who pull from
multiple exchanges using real USD pairs, NOT USDT.

This script compares:
- Direct BTC/USD sources (Bitstamp, Pyth)
- BTC/USDT sources adjusted for USDT peg deviation
"""

import subprocess
import json
import time
from datetime import datetime

def curl_json(url):
    """Fetch JSON from URL using curl"""
    try:
        cmd = f'curl -s "{url}"'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        return json.loads(result.stdout)
    except:
        return None

def get_pyth_btcusd():
    """Pyth Network BTC/USD oracle"""
    try:
        btc_feed = "0xe62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43"
        data = curl_json(f"https://hermes.pyth.network/api/latest_price_feeds?ids[]={btc_feed}")
        if data and len(data) > 0:
            p = data[0].get('price', {})
            return int(p.get('price', 0)) * (10 ** int(p.get('expo', 0)))
    except:
        pass
    return None

def get_bitstamp_btcusd():
    """Bitstamp BTC/USD - real USD pair"""
    data = curl_json("https://www.bitstamp.net/api/v2/ticker/btcusd/")
    return float(data['last']) if data else None

def get_bitstamp_btcusdt():
    """Bitstamp BTC/USDT"""
    data = curl_json("https://www.bitstamp.net/api/v2/ticker/btcusdt/")
    return float(data['last']) if data else None

def get_bitstamp_usdt_rate():
    """Bitstamp USDT/USD rate - how much 1 USDT is worth in real USD"""
    data = curl_json("https://www.bitstamp.net/api/v2/ticker/usdtusd/")
    return float(data['last']) if data else None

def get_defillama_btcusd():
    """DefiLlama aggregated BTC price"""
    data = curl_json("https://coins.llama.fi/prices/current/coingecko:bitcoin")
    if data:
        return data.get('coins', {}).get('coingecko:bitcoin', {}).get('price')
    return None

def get_defillama_usdt_rate():
    """DefiLlama USDT/USD rate"""
    data = curl_json("https://coins.llama.fi/prices/current/coingecko:tether")
    if data:
        return data.get('coins', {}).get('coingecko:tether', {}).get('price')
    return None

def run_comparison(samples=12, interval=2):
    """Compare BTC/USD sources with USDT adjustment"""

    print("=" * 85)
    print("BTC/USD vs BTC/USDT COMPARISON (with USDT peg adjustment)")
    print("=" * 85)
    print("""
KEY INSIGHT:
- Chainlink uses BTC/USD (real USD), aggregated from fiat pairs
- Binance primarily has BTC/USDT, not BTC/USD
- To use Binance data: Adjusted_USD = BTCUSDT × USDT_rate

SOURCES:
- Pyth Network: BTC/USD oracle (similar to Chainlink)
- Bitstamp BTC/USD: Real USD fiat pair
- Bitstamp BTC/USDT: Tether pair (raw)
- Bitstamp BTC/USDT adjusted: USDT × USDT/USD rate = estimated USD
- DefiLlama: Aggregated price
""")
    print("-" * 85)

    all_samples = []

    for i in range(samples):
        now = datetime.now().strftime('%H:%M:%S')

        # Fetch all prices
        pyth = get_pyth_btcusd()
        bitstamp_usd = get_bitstamp_btcusd()
        bitstamp_usdt = get_bitstamp_btcusdt()
        usdt_rate = get_bitstamp_usdt_rate()
        defillama = get_defillama_btcusd()
        defillama_usdt_rate = get_defillama_usdt_rate()

        if pyth and bitstamp_usd and bitstamp_usdt and usdt_rate:
            # Calculate USDT-adjusted price
            btcusdt_adjusted = bitstamp_usdt * usdt_rate

            # Differences from Bitstamp BTC/USD (our reference)
            raw_usdt_diff = bitstamp_usdt - bitstamp_usd
            adjusted_diff = btcusdt_adjusted - bitstamp_usd
            pyth_diff = pyth - bitstamp_usd

            sample = {
                'time': now,
                'pyth': pyth,
                'bitstamp_usd': bitstamp_usd,
                'bitstamp_usdt': bitstamp_usdt,
                'usdt_rate': usdt_rate,
                'btcusdt_adjusted': btcusdt_adjusted,
                'defillama': defillama,
                'raw_usdt_diff': raw_usdt_diff,
                'adjusted_diff': adjusted_diff,
                'pyth_diff': pyth_diff
            }
            all_samples.append(sample)

            usdt_deviation = (1 - usdt_rate) * 100

            print(f"[{now}] USDT rate: ${usdt_rate:.6f} (deviation: {usdt_deviation:+.4f}%)")
            print(f"         Bitstamp BTC/USD:      ${bitstamp_usd:>10,.2f}  ← Reference (real USD)")
            print(f"         Bitstamp BTC/USDT:     ${bitstamp_usdt:>10,.2f}  (raw, diff: {raw_usdt_diff:+.2f})")
            print(f"         BTC/USDT × USDT rate:  ${btcusdt_adjusted:>10,.2f}  (adjusted, diff: {adjusted_diff:+.2f})")
            print(f"         Pyth BTC/USD:          ${pyth:>10,.2f}  (oracle, diff: {pyth_diff:+.2f})")
            if defillama:
                defillama_diff = defillama - bitstamp_usd
                print(f"         DefiLlama:             ${defillama:>10,.2f}  (aggregated, diff: {defillama_diff:+.2f})")
            print()
        else:
            print(f"[{now}] Error fetching some prices")

        if i < samples - 1:
            time.sleep(interval)

    # Analysis
    if len(all_samples) >= 3:
        print("=" * 85)
        print("ANALYSIS RESULTS")
        print("=" * 85)

        avg_usd = sum(s['bitstamp_usd'] for s in all_samples) / len(all_samples)
        avg_usdt_rate = sum(s['usdt_rate'] for s in all_samples) / len(all_samples)

        avg_raw_diff = sum(s['raw_usdt_diff'] for s in all_samples) / len(all_samples)
        avg_adj_diff = sum(s['adjusted_diff'] for s in all_samples) / len(all_samples)
        avg_pyth_diff = sum(s['pyth_diff'] for s in all_samples) / len(all_samples)

        max_raw = max(abs(s['raw_usdt_diff']) for s in all_samples)
        max_adj = max(abs(s['adjusted_diff']) for s in all_samples)
        max_pyth = max(abs(s['pyth_diff']) for s in all_samples)

        print(f"""
SAMPLES: {len(all_samples)}
REFERENCE: Bitstamp BTC/USD (real fiat pair)
AVG BTC PRICE: ${avg_usd:,.2f}
AVG USDT RATE: ${avg_usdt_rate:.6f} (deviation: {(1-avg_usdt_rate)*100:+.4f}%)

COMPARISON TO BITSTAMP BTC/USD:
┌─────────────────────────────────┬────────────────┬────────────────┬────────────────┐
│ Source                          │ Avg Diff ($)   │ Avg Diff (%)   │ Max Diff ($)   │
├─────────────────────────────────┼────────────────┼────────────────┼────────────────┤
│ Pyth BTC/USD (oracle)           │ {avg_pyth_diff:>+12.2f}   │ {(avg_pyth_diff/avg_usd)*100:>+12.4f}%  │ {max_pyth:>12.2f}   │
│ BTC/USDT adjusted (×USDT rate)  │ {avg_adj_diff:>+12.2f}   │ {(avg_adj_diff/avg_usd)*100:>+12.4f}%  │ {max_adj:>12.2f}   │
│ BTC/USDT raw (NOT adjusted)     │ {avg_raw_diff:>+12.2f}   │ {(avg_raw_diff/avg_usd)*100:>+12.4f}%  │ {max_raw:>12.2f}   │
└─────────────────────────────────┴────────────────┴────────────────┴────────────────┘
""")

        improvement = abs(avg_raw_diff) - abs(avg_adj_diff)
        print(f"USDT ADJUSTMENT IMPROVEMENT: ${improvement:.2f} closer to true USD price")

        print("=" * 85)
        print("CONCLUSIONS")
        print("=" * 85)
        print(f"""
1. USDT PEG STATUS:
   - Current USDT rate: ${avg_usdt_rate:.6f}
   - Deviation from $1.00: {(1-avg_usdt_rate)*100:+.4f}%
   - Impact on $95k BTC: ~${avg_usd * (1-avg_usdt_rate):.2f} difference

2. RAW BTC/USDT ERROR:
   - Using Binance BTCUSDT directly would give ${avg_raw_diff:+.2f} error
   - This is {(avg_raw_diff/avg_usd)*100:+.4f}% of the price

3. ADJUSTED BTC/USDT ACCURACY:
   - After adjusting for USDT rate: ${avg_adj_diff:+.2f} error
   - This is {(avg_adj_diff/avg_usd)*100:+.4f}% of the price
   - MUCH closer to real USD price!

4. BEST APPROACH FOR POLYMARKET BACKTESTING:

   OPTION A (Best): Use BTC/USD directly
   - Bitstamp BTC/USD historical
   - Coinbase BTC-USD historical
   - Kraken XBT/USD historical

   OPTION B (If Binance needed): Adjust for USDT peg
   - Get historical BTC/USDT from Binance
   - Get historical USDT/USD rate
   - Calculate: True_USD = BTCUSDT × USDT_rate

5. FORMULA FOR BINANCE ADJUSTMENT:
   True_BTC_USD = Binance_BTCUSDT × (USDT/USD rate)

   Example with current rates:
   ${bitstamp_usdt:,.2f} × {usdt_rate:.6f} = ${bitstamp_usdt * usdt_rate:,.2f}
   (vs actual BTC/USD: ${bitstamp_usd:,.2f})
""")

if __name__ == "__main__":
    run_comparison(samples=10, interval=2)
