#!/usr/bin/env python
import requests
import sys
import datetime
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

def webscrape_article(url):
    try:
        print(f"Fetching content from {url}...")
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Try to find the main article content using common selectors
        selectors = [
            'article',
            '.article-body',
            '#article-body',
            '.main-content',
            '#main-content',
            '.post-content',
        ]
        
        article_content = None
        for selector in selectors:
            article_content = soup.select_one(selector)
            if article_content:
                break
        
        # If a specific container is found, get paragraphs from it.
        # Otherwise, fall back to the whole page.
        if article_content:
            paragraphs = article_content.find_all('p')
        else:
            paragraphs = soup.find_all('p')

        article_text = '\n'.join(p.get_text() for p in paragraphs)

        print("\n--- Article Content ---")
        print(article_text)
        print("\n--- End of Article Content ---")

    except requests.exceptions.RequestException as e:
        print(f"Error fetching article: {e}")
    except Exception as e:
        print(f"An unexpected error occurred during web scraping: {e}")

def format_market_cap(cap):
    """Format market cap with suffixes (e.g., 123.45B for billions)."""
    if cap is None:
        return "N/A"
    if cap >= 1e12:
        return f"{cap / 1e12:.2f}T"
    elif cap >= 1e9:
        return f"{cap / 1e9:.2f}B"
    elif cap >= 1e6:
        return f"{cap / 1e6:.2f}M"
    else:
        return f"{cap:,.0f}"

def get_stock_data(symbol):
    """Fetches and displays a stock's data in a Bloomberg Terminal-like format."""
    try:
        # --- 1. Fetch Price Data from Yahoo Finance API ---
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol.upper()}?interval=1d&range=1mo"  # Adjusted for ~30 days
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        data = response.json()

        # --- 2. Parse JSON Response ---
        if not data.get('chart') or not data['chart'].get('result'):
            print(f"\nError: Could not find data for the symbol '{symbol}'. Please check the ticker.")
            return

        result = data['chart']['result'][0]
        meta = result['meta']
        
        current_price = meta.get('regularMarketPrice')
        previous_close = meta.get('chartPreviousClose')
        
        if current_price is None or previous_close is None:
            print(f"\nError: Could not retrieve current price for '{symbol}'. The ticker may be delisted or invalid.")
            return

        currency = meta.get('currency', '')
        day_high = meta.get('regularMarketDayHigh')
        day_low = meta.get('regularMarketDayLow')
        regular_market_volume = meta.get('regularMarketVolume')
        market_cap = meta.get('marketCap')
        pe_ratio = meta.get('trailingPE')
        dividend_yield = meta.get('dividendYield')  # Corrected key
        eps = meta.get('epsTrailingTwelveMonths')
        fifty_two_week_high = meta.get('fiftyTwoWeekHigh')
        fifty_two_week_low = meta.get('fiftyTwoWeekLow')
        data_timestamp = meta.get('regularMarketTime')
        
        # Get the last 30 data points for the trend, filtering out None
        prices = [p for p in result['indicators']['quote'][0]['close'][-30:] if p is not None]
        volumes = [v for v in result['indicators']['quote'][0]['volume'][-30:] if v is not None]

        # --- 3. Determine Color and Trend Symbol ---
        change = current_price - previous_close
        change_percent = (change / previous_close) * 100

        GREEN = '\033[92m'
        RED = '\033[91m'
        RESET = '\033[0m'
        color = GREEN if change >= 0 else RED
        direction_symbol = "▲" if change >= 0 else "▼"

        # --- 4. Create Price and Volume Sparklines (Enhanced AAA Version) ---
        def create_sparkline(data_points, ticks, colorize=False):
            if not data_points:
                return ""
            min_val, max_val = min(data_points), max(data_points)
            val_range = max_val - min_val if max_val > min_val else 1
            sparkline = ""
            for i, point in enumerate(data_points):
                tick_color = ''
                if colorize and i > 0:
                    if point > data_points[i-1]: tick_color = GREEN
                    elif point < data_points[i-1]: tick_color = RED
                
                tick_index = int(((point - min_val) / val_range) * (len(ticks) - 1))
                sparkline += tick_color + ticks[tick_index]
            return sparkline + RESET

        price_ticks = ['▁', '▂', '▃', '▄', '▅', '▆', '▇', '█']  # Smooth, professional gradient
        price_sparkline = create_sparkline(prices, price_ticks, colorize=True)
        volume_sparkline = create_sparkline(volumes, price_ticks, colorize=True)  # Now colorized for AAA feel
        avg_volume = sum(volumes) / len(volumes) if volumes else 0

        # Add trend indicators
        price_trend = f"{GREEN}↑{RESET}" if prices and prices[-1] > prices[0] else f"{RED}↓{RESET}"
        volume_trend = f"{GREEN}↑{RESET}" if volumes and volumes[-1] > volumes[0] else f"{RED}↓{RESET}"

        # --- 5. Print the Output (Enhanced Bloomberg-like) ---
        dt_object = datetime.datetime.fromtimestamp(data_timestamp) if data_timestamp else datetime.datetime.now()
        print("\n" + "=" * 70)
        print(f" BLOOMBERG-LIKE TERMINAL | {symbol.upper()} | {dt_object.strftime('%Y-%m-%d %H:%M:%S')} ")
        print("=" * 70)
        print(f"Price:      {current_price:.2f} {currency} {color}{direction_symbol} {change:+.2f} ({change_percent:+.2f}%){RESET}")
        print(f"Mkt Cap:    {format_market_cap(market_cap)}")
        print("-" * 70)
        print(f"High/Low:   {day_high:.2f} / {day_low:.2f}" if day_high and day_low else "High/Low: N/A")
        print(f"52-Wk:      {fifty_two_week_high:.2f} / {fifty_two_week_low:.2f}" if fifty_two_week_high and fifty_two_week_low else "52-Wk: N/A")
        print(f"Volume:     {regular_market_volume:,}" if regular_market_volume else "Volume: N/A")
        print(f"Avg Vol:    {avg_volume:,.0f}")
        print(f"P/E (TTM):  {pe_ratio:.2f}" if pe_ratio else "P/E (TTM): N/A")
        print(f"EPS (TTM):  {eps:.2f}" if eps else "EPS (TTM): N/A")
        print(f"Div Yield:  {dividend_yield:.2%}" if dividend_yield else "Div Yield: N/A")
        print("-" * 70)
        if prices: print(f"Price Graph (30 days): {price_sparkline} {price_trend}  [Low: {min(prices):.2f} | High: {max(prices):.2f}]  Scale: ▁ Low ─ █ High")
        if volumes: print(f"Volume Graph (30 days): {volume_sparkline} {volume_trend}  [Low: {min(volumes):,.0f} | High: {max(volumes):,.0f}]  Scale: ▁ Low ─ █ High")
        print("=" * 70)

        # --- 6. Fetch and Print News ---
        try:
            news_url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol.upper()}&region=US&lang=en-US"
            news_response = requests.get(news_url, headers=headers, timeout=5)
            news_response.raise_for_status()
            
            root = ET.fromstring(news_response.content)
            news_items = root.findall('.//item')
            
            if news_items:
                print("\n--- Latest News (Top 5) ---")
                news_links = []
                for i, item in enumerate(news_items[:5]):
                    title = item.find('title').text
                    link = item.find('link').text
                    news_links.append(link)
                    print(f"{i+1}. {title}\n   {link}")
                
                if news_links:
                    while True:
                        try:
                            choice = input("\nEnter the number of the news item to webscrape (or 0 to skip): ").strip()
                            if choice == '0':
                                break
                            choice_idx = int(choice) - 1
                            if 0 <= choice_idx < len(news_links):
                                webscrape_article(news_links[choice_idx])
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
    if len(sys.argv) > 1:
        if sys.argv[1].startswith('http'):
            webscrape_article(sys.argv[1])
        else:
            get_stock_data(sys.argv[1])
    else:
        print("Usage:")
        print("  To get stock data: python buh.py <STOCK_SYMBOL>")
        print("  To scrape an article: python buh.py <URL>")
