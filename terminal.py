#!/usr/bin/env python
import requests
import sys
import datetime
import xml.etree.ElementTree as ET
import subprocess

def get_stock_data(symbol):
    """Fetches and displays a stock's current price, trend chart, and news for a given symbol."""
    try:
        # --- 1. Fetch Price Data from Yahoo Finance API ---
        # The symbol is now dynamically inserted into the URL.
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}"
        headers = {'User-Agent': 'Mozilla/5.0'}  # Yahoo Finance requires a User-Agent header
        response = requests.get(url, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        data = response.json()

        # --- 2. Parse JSON Response ---
        # Check if the API returned a valid result for the symbol.
        if not data.get('chart') or not data['chart'].get('result'):
            print(f"\nError: Could not find data for the symbol '{symbol}'. Please check the ticker.")
            return

        result = data['chart']['result'][0]
        meta = result['meta']
        
        # Safely get data points, providing 'N/A' as a default.
        current_price = meta.get('regularMarketPrice')
        previous_close = meta.get('chartPreviousClose')
        
        # If essential data is missing, we can't proceed.
        if current_price is None or previous_close is None:
            print(f"\nError: Could not retrieve current price for '{symbol}'. The ticker may be delisted or invalid.")
            return

        currency = meta.get('currency', '')
        day_high = meta.get('regularMarketDayHigh')
        day_low = meta.get('regularMarketDayLow')
        regular_market_volume = meta.get('regularMarketVolume')
        market_cap = meta.get('marketCap')
        pe_ratio = meta.get('trailingPE')
        data_timestamp = meta.get('regularMarketTime')
        
        # Get the last 20 data points for the trend, filtering out potential None values.
        prices = [p for p in result['indicators']['quote'][0]['close'][-20:] if p is not None]
        volumes = [v for v in result['indicators']['quote'][0]['volume'][-20:] if v is not None]

        # --- 3. Determine Color and Trend Symbol ---
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100

        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        color = GREEN if change >= 0 else RED
        direction_symbol = "▲" if change >= 0 else "▼"

        # --- 4. Create Price and Volume Sparklines ---
        def create_sparkline(data_points, ticks, colorize=False):
            if not data_points:
                return ""
            min_val, max_val = min(data_points), max(data_points)
            val_range = max_val - min_val
            sparkline = ""
            for i, point in enumerate(data_points):
                tick_color = ''
                if colorize and i > 0:
                    if point > data_points[i-1]: tick_color = GREEN
                    elif point < data_points[i-1]: tick_color = RED
                
                if val_range > 0:
                    tick_index = int(((point - min_val) / val_range) * (len(ticks) - 1))
                    sparkline += tick_color + ticks[tick_index]
                else:
                    sparkline += ticks[0] # All data points are the same
            return sparkline + RESET

        price_ticks = [' ', '▂', '▃', '▄', '▅', '▆', '▇', '█']
        price_sparkline = create_sparkline(prices, price_ticks, colorize=True)
        volume_sparkline = create_sparkline(volumes, price_ticks)
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        # --- 5. Print the Output (Bloomberg-like) ---
        print("\n" + "="*50)
        # The stock symbol is now a variable in the output string.
        print(f"{symbol.upper()}: {current_price:.2f} {currency} {color}{direction_symbol} {change:+.2f} ({change_percent:+.2f}%){RESET}")
        print("="*50)
        print(f"High: {day_high:.2f}" if day_high is not None else "High: N/A")
        print(f"Low:  {day_low:.2f}" if day_low is not None else "Low:  N/A")
        print(f"Volume: {regular_market_volume:,}" if regular_market_volume is not None else "Volume: N/A")
        if market_cap: print(f"Mkt Cap: {market_cap:,}")
        if pe_ratio: print(f"P/E Ratio (TTM): {pe_ratio:.2f}")
        print("-"*50)
        if prices: print(f"Price ({len(prices)} days): {price_sparkline}  [{min(prices):.2f} - {max(prices):.2f}]")
        if volumes: print(f"Volume ({len(volumes)} days): {volume_sparkline}  (Avg: {avg_volume:,.0f})")
        print("-"*50)
        if data_timestamp:
            dt_object = datetime.datetime.fromtimestamp(data_timestamp)
            print(f"Data as of: {dt_object.strftime('%Y-%m-%d %H:%M:%S')}")

        # --- 6. Fetch and Print News ---
        try:
            # The symbol is now dynamically inserted into the news URL.
            news_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol.upper()}&region=US&lang=en-US"
            news_response = requests.get(news_url, headers=headers, timeout=5)
            news_response.raise_for_status()
            
            root = ET.fromstring(news_response.content)
            news_items = root.findall('.//item')
            
            if news_items:
                print("\n--- Latest News ---")
                news_links = []
                for i, item in enumerate(news_items[:3]):  # Limit to 3 news items
                    title = item.find('title').text
                    link = item.find('link').text
                    news_links.append(link)
                    print(f"{i+1}. {title}\n   {link}")
                
                if news_links:
                    while True:
                        try:
                            choice = input("\nEnter the number of the news item to open in browser (or 0 to skip): ").strip()
                            if choice == '0':
                                break
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(news_links):
                                print(f"Opening {news_links[choice_idx]}...")
                                subprocess.run(["termux-open-url", news_links[choice_idx]])
                                break
                            else:
                                print("Invalid number. Please try again.")
                        except ValueError:
                            print("Invalid input. Please enter a number.")
            else:
                print("\n--- No news found for this symbol ---")

        except Exception as e:
            print(f"\nCould not fetch news: {e}")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: A network error occurred.\nDetails: {e}")
    except (KeyError, IndexError):
        print("Error: Could not parse the API response. The data format may have changed.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # --- Main execution block ---
    # Prompt the user for a stock symbol.
    symbol_input = input("Enter a stock ticker symbol (e.g., AAPL, GOOG, MSFT): ").strip()

    if not symbol_input:
        print("No symbol entered. Exiting.")
    else:
        # Call the main function with the user's input.
        get_stock_data(symbol_input)
    
    # Keep the console window open until the user presses Enter.
    if sys.stdin.isatty():
        input("\nPress Enter to exit...")
