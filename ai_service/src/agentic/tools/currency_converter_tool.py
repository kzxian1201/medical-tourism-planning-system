# ai_service/src/agentic/tools/currency_converter_tool.py
import asyncio
import requests
from langchain_core.tools import tool
from ..logger import logging
from ..config import AppConfig
from ..models import CurrencyConverterInput

def create_currency_converter_tool(config: AppConfig):
    """[Factory] Creates the Currency Converter Tool."""
    
    @tool("currency_converter", args_schema=CurrencyConverterInput)
    async def currency_converter(amount: float, base_currency: str, target_currency: str) -> str:
        """Fetch live currency exchange rates to convert between ANY two currencies."""
        url = f"https://api.exchangerate-api.com/v4/latest/{base_currency.upper()}"
        timeout = 10 if config.environment == "development" else 5
        
        try:
            logging.info(f"💱 Fetching live exchange rate: {base_currency.upper()} -> {target_currency.upper()}")
            response = await asyncio.to_thread(requests.get, url, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            
            rate = data.get("rates", {}).get(target_currency.upper())
            if not rate:
                return f"Error: Currency {target_currency} not supported or invalid base {base_currency}."
                
            converted_amount = amount * rate
            return f"LIVE RATE: 1 {base_currency.upper()} = {rate} {target_currency.upper()}. Total: {converted_amount:,.2f} {target_currency.upper()}."
            
        except Exception as e:
            logging.error(f"Currency API Error: {e}")
            return f"Error: Currency API Offline. Unable to fetch live rates for {target_currency.upper()}."

    return currency_converter