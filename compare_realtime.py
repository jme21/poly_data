"""
Compare Polymarket BTC settlement price vs Binance BTCUSDT (converted to USD)
at 1-second frequency for 10 minutes.

Sources:
- Pyth BTC/USD: Proxy for Chainlink/Polymarket settlement price
- Bitstamp BTC/USDT × USDT/USD: Simulates Binance BTCUSDT converted to real USD
"""

import subprocess
import json
import time
import csv
from datetime import datetime
from statistics import mean, stdev, median

def curl_json(url):
    """Fetch JSON using curl"""
    try:
        result = subprocess.run(
            f'curl -s "{url}"',
            shell=True, capture_output=True, text=True, timeout=5
        )
        return json.loads(result.stdout)
    except:
        return None

def get_pyth_btcusd():
    """Pyth BTC/USD - similar to Chainlink (Polymarket settlement)"""
    try:
        feed = "e62df6c8b4a85fe1a67db44dc12de5db330f7ac66b72dc658afedf0f4a415b43"
        data = curl_json(f"https://hermes.pyth.network/api/latest_price_feeds?ids[]={feed}")
        if data and len(data) > 0:
            p = data[0]['price']
            return int(p['price']) * (10 ** int(p['expo']))
    except:
        pass
    return None

def get_bitstamp_btcusdt():
    """Bitstamp BTC/USDT"""
    data = curl_json("https://www.bitstamp.net/api/v2/ticker/btcusdt/")
    return float(data['last']) if data else None

def get_bitstamp_usdt_rate():
    """Bitstamp USDT/USD rate"""
    data = curl_json("https://www.bitstamp.net/api/v2/ticker/usdtusd/")
    return float(data['last']) if data else None

def get_bitstamp_btcusd():
    """Bitstamp BTC/USD (real USD for reference)"""
    data = curl_json("https://www.bitstamp.net/api/v2/ticker/btcusd/")
    return float(data['last']) if data else None

def collect_data(duration_seconds=600, interval=1):
    """Collect price data for specified duration"""

    print("=" * 80)
    print("POLYMARKET vs BINANCE BTC PRICE COMPARISON")
    print("=" * 80)
    print(f"""
Data Sources:
  - Pyth BTC/USD: Oracle price (proxy for Chainlink/Polymarket settlement)
  - Bitstamp BTC/USDT: Simulating Binance spot
  - USDT/USD rate: To convert USDT to real USD
  - Bitstamp BTC/USD: Reference (real USD fiat pair)

Duration: {duration_seconds} seconds ({duration_seconds//60} minutes)
Interval: {interval} second(s)
Expected samples: {duration_seconds // interval}
""")
    print("-" * 80)

    samples = []
    start_time = time.time()
    sample_count = 0
    errors = 0

    print(f"{'Time':^12} | {'Pyth BTC/USD':^14} | {'USDT Adjusted':^14} | {'Diff':^10} | {'USDT Raw':^14}")
    print("-" * 80)

    while time.time() - start_time < duration_seconds:
        loop_start = time.time()

        # Fetch all prices
        pyth = get_pyth_btcusd()
        btcusdt = get_bitstamp_btcusdt()
        usdt_rate = get_bitstamp_usdt_rate()
        btcusd_ref = get_bitstamp_btcusd()

        if pyth and btcusdt and usdt_rate:
            now = datetime.now().strftime('%H:%M:%S')

            # Convert USDT to USD
            btcusdt_adjusted = btcusdt * usdt_rate

            # Calculate difference
            diff = pyth - btcusdt_adjusted
            diff_pct = (diff / pyth) * 100

            sample = {
                'timestamp': datetime.now().isoformat(),
                'pyth_btcusd': pyth,
                'btcusdt_raw': btcusdt,
                'usdt_rate': usdt_rate,
                'btcusdt_adjusted': btcusdt_adjusted,
                'btcusd_reference': btcusd_ref,
                'diff_pyth_vs_adjusted': diff,
                'diff_pct': diff_pct
            }
            samples.append(sample)
            sample_count += 1

            # Print every 10 samples
            if sample_count % 10 == 1 or sample_count <= 5:
                print(f"{now:^12} | ${pyth:>12,.2f} | ${btcusdt_adjusted:>12,.2f} | {diff:>+9.2f} | ${btcusdt:>12,.2f}")
        else:
            errors += 1

        # Sleep to maintain interval
        elapsed = time.time() - loop_start
        sleep_time = max(0, interval - elapsed)
        time.sleep(sleep_time)

    print("-" * 80)
    print(f"Collection complete. Samples: {len(samples)}, Errors: {errors}")

    return samples

def analyze_data(samples):
    """Analyze collected data"""

    if len(samples) < 10:
        print("Not enough samples for analysis")
        return

    print("\n" + "=" * 80)
    print("ANALYSIS RESULTS")
    print("=" * 80)

    # Extract differences
    diffs = [s['diff_pyth_vs_adjusted'] for s in samples]
    diffs_pct = [s['diff_pct'] for s in samples]
    usdt_rates = [s['usdt_rate'] for s in samples]

    # Raw USDT vs Pyth differences
    raw_diffs = [s['pyth_btcusd'] - s['btcusdt_raw'] for s in samples]

    # Calculate statistics
    avg_diff = mean(diffs)
    std_diff = stdev(diffs) if len(diffs) > 1 else 0
    min_diff = min(diffs)
    max_diff = max(diffs)
    med_diff = median(diffs)

    avg_raw_diff = mean(raw_diffs)

    avg_usdt = mean(usdt_rates)
    avg_pyth = mean([s['pyth_btcusd'] for s in samples])

    print(f"""
SAMPLE STATISTICS:
  Total samples:     {len(samples)}
  Duration:          {len(samples)} seconds
  Average BTC price: ${avg_pyth:,.2f}
  Average USDT rate: ${avg_usdt:.6f} (deviation: {(1-avg_usdt)*100:+.4f}%)

PYTH (Polymarket) vs BINANCE USDT-ADJUSTED:
┌────────────────────────────────────────────────────────────────┐
│ Metric                              │ Value                    │
├─────────────────────────────────────┼──────────────────────────┤
│ Average difference                  │ {avg_diff:>+10.2f} ({mean(diffs_pct):>+.4f}%)     │
│ Standard deviation                  │ {std_diff:>10.2f}              │
│ Minimum difference                  │ {min_diff:>+10.2f}              │
│ Maximum difference                  │ {max_diff:>+10.2f}              │
│ Median difference                   │ {med_diff:>+10.2f}              │
└─────────────────────────────────────┴──────────────────────────┘

PYTH vs RAW BINANCE USDT (NOT adjusted):
  Average difference: {avg_raw_diff:>+.2f}
  (This is the error if you DON'T adjust for USDT peg)

IMPROVEMENT FROM USDT ADJUSTMENT:
  Error reduced by: ${abs(avg_raw_diff) - abs(avg_diff):.2f}
""")

    # Time series analysis
    if len(samples) >= 60:
        # Check for drift over time
        first_30 = mean([s['diff_pyth_vs_adjusted'] for s in samples[:30]])
        last_30 = mean([s['diff_pyth_vs_adjusted'] for s in samples[-30:]])
        drift = last_30 - first_30

        print(f"""TEMPORAL ANALYSIS:
  First 30s avg diff: {first_30:>+.2f}
  Last 30s avg diff:  {last_30:>+.2f}
  Drift over period:  {drift:>+.2f}
""")

    # Conclusion
    print("=" * 80)
    print("CONCLUSIONS")
    print("=" * 80)
    print(f"""
1. PRICE TRACKING:
   - Pyth/Chainlink and Binance USDT (adjusted) track within ${abs(avg_diff):.2f} on average
   - This is {abs(mean(diffs_pct)):.4f}% of the BTC price

2. USDT ADJUSTMENT IMPACT:
   - Without adjustment: ${abs(avg_raw_diff):.2f} average error
   - With adjustment:    ${abs(avg_diff):.2f} average error
   - Adjustment reduces error by ~${abs(avg_raw_diff) - abs(avg_diff):.2f}

3. FOR POLYMARKET BACKTESTING:
   - If using Binance BTCUSDT data, MUST multiply by USDT/USD rate
   - Formula: True_USD = BTCUSDT × USDT_rate
   - Expected accuracy after adjustment: ±${std_diff:.2f}

4. SETTLEMENT PRECISION:
   - At settlement time, expect ~${abs(avg_diff):.0f}-${abs(avg_diff)+std_diff:.0f} difference
   - For a $100 bet at 0.5 probability, this is ~${abs(avg_diff)/avg_pyth*100*100:.2f}% impact
""")

    return {
        'avg_diff': avg_diff,
        'std_diff': std_diff,
        'avg_raw_diff': avg_raw_diff,
        'samples': len(samples)
    }

def main():
    # Collect 10 minutes of data (but can be shortened for testing)
    duration = 600  # 10 minutes

    print(f"\nStarting {duration//60}-minute data collection...")
    print("Press Ctrl+C to stop early and analyze collected data\n")

    try:
        samples = collect_data(duration_seconds=duration, interval=1)
    except KeyboardInterrupt:
        print("\n\nStopped early by user")
        samples = []

    if samples:
        # Save raw data
        with open('btc_comparison_data.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=samples[0].keys())
            writer.writeheader()
            writer.writerows(samples)
        print(f"\nRaw data saved to: btc_comparison_data.csv")

        # Analyze
        analyze_data(samples)

if __name__ == "__main__":
    main()
