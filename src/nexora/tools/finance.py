"""
Finance & Stock Price Tool using Alpha Vantage.
"""

import requests
from langchain_core.tools import tool
from nexora.config import ALPHA_VANTAGE_API_KEY


@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA', 'MSFT', 'NVDA')
    using Alpha Vantage.
    """
    try:
        clean_symbol = symbol.strip().upper()
        url = (
            f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE"
            f"&symbol={clean_symbol}&apikey={ALPHA_VANTAGE_API_KEY}"
        )
        r = requests.get(url, timeout=10)
        data = r.json()
        return data
    except Exception as e:
        return {"error": f"Failed to fetch stock price for {symbol}: {str(e)}"}
