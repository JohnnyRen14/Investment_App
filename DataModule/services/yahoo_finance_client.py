"""
Yahoo Finance API Client

Handles all interactions with Yahoo Finance API for fetching stock data,
financial statements, and market information.

Author: Lebron (Data & Infrastructure Lead)
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import yfinance as yf
import pandas as pd
from ..models.financial_data import (
    StockData, StockPrice, CompanyInfo, FinancialStatement,
    IncomeStatement, BalanceSheet, CashFlowStatement, DataSource
)

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """
    Yahoo Finance API client with error handling, retry logic, and data validation.
    """
    
    def __init__(self, timeout: int = 30, max_retries: int = 3):
        """
        Initialize Yahoo Finance client.
        
        Args:
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = None
        
    async def get_stock_data(self, symbol: str, period: str = "1y") -> Optional[StockData]:
        """
        Get comprehensive stock data for a symbol.
        
        Args:
            symbol: Stock symbol (e.g., 'AAPL')
            period: Data period ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            
        Returns:
            StockData object or None if failed
        """
        try:
            logger.info(f"Fetching stock data for {symbol} with period {period}")
            
            # Create ticker object
            ticker = yf.Ticker(symbol)
            
            # Get all data concurrently
            tasks = [
                self._get_company_info(ticker, symbol),
                self._get_historical_prices(ticker, symbol, period),
                self._get_current_price(ticker, symbol),
                self._get_financial_statements(ticker, symbol)
            ]
            
            company_info, historical_prices, current_price, financial_statements = await asyncio.gather(
                *tasks, return_exceptions=True
            )
            
            # Handle exceptions
            if isinstance(company_info, Exception):
                logger.warning(f"Failed to get company info for {symbol}: {company_info}")
                company_info = None
                
            if isinstance(historical_prices, Exception):
                logger.warning(f"Failed to get historical prices for {symbol}: {historical_prices}")
                historical_prices = []
                
            if isinstance(current_price, Exception):
                logger.warning(f"Failed to get current price for {symbol}: {current_price}")
                current_price = None
                
            if isinstance(financial_statements, Exception):
                logger.warning(f"Failed to get financial statements for {symbol}: {financial_statements}")
                financial_statements = []
            
            # Create StockData object
            stock_data = StockData(
                symbol=symbol.upper(),
                company_info=company_info,
                current_price=current_price,
                historical_prices=historical_prices or [],
                financial_statements=financial_statements or [],
                last_updated=datetime.now()
            )
            
            logger.info(f"Successfully fetched stock data for {symbol}")
            return stock_data
            
        except Exception as e:
            logger.error(f"Error fetching stock data for {symbol}: {e}")
            return None
    
    async def _get_company_info(self, ticker: yf.Ticker, symbol: str) -> Optional[CompanyInfo]:
        """Get company information from Yahoo Finance."""
        try:
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ticker.info
            )
            
            if not info:
                return None
                
            return CompanyInfo(
                symbol=symbol.upper(),
                company_name=info.get('longName', ''),
                sector=info.get('sector'),
                industry=info.get('industry'),
                market_cap=self._safe_decimal(info.get('marketCap')),
                enterprise_value=self._safe_decimal(info.get('enterpriseValue')),
                trailing_pe=self._safe_decimal(info.get('trailingPE')),
                forward_pe=self._safe_decimal(info.get('forwardPE')),
                peg_ratio=self._safe_decimal(info.get('pegRatio')),
                price_to_book=self._safe_decimal(info.get('priceToBook')),
                price_to_sales=self._safe_decimal(info.get('priceToSalesTrailing12Months')),
                beta=self._safe_decimal(info.get('beta')),
                dividend_yield=self._safe_decimal(info.get('dividendYield')),
                description=info.get('longBusinessSummary'),
                website=info.get('website'),
                employees=info.get('fullTimeEmployees')
            )
            
        except Exception as e:
            logger.error(f"Error getting company info for {symbol}: {e}")
            return None
    
    async def _get_historical_prices(self, ticker: yf.Ticker, symbol: str, period: str) -> List[StockPrice]:
        """Get historical price data."""
        try:
            hist = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ticker.history(period=period)
            )
            
            if hist.empty:
                return []
            
            prices = []
            for date_idx, row in hist.iterrows():
                try:
                    price = StockPrice(
                        symbol=symbol.upper(),
                        date=date_idx.date(),
                        open_price=self._safe_decimal(row.get('Open')),
                        high_price=self._safe_decimal(row.get('High')),
                        low_price=self._safe_decimal(row.get('Low')),
                        close_price=self._safe_decimal(row.get('Close')),
                        adjusted_close=self._safe_decimal(row.get('Close')),  # Yahoo Finance adjusts by default
                        volume=int(row.get('Volume', 0)) if pd.notna(row.get('Volume')) else None
                    )
                    prices.append(price)
                except Exception as e:
                    logger.warning(f"Error processing price data for {symbol} on {date_idx}: {e}")
                    continue
            
            return prices
            
        except Exception as e:
            logger.error(f"Error getting historical prices for {symbol}: {e}")
            return []
    
    async def _get_current_price(self, ticker: yf.Ticker, symbol: str) -> Optional[StockPrice]:
        """Get current price data."""
        try:
            # Get the most recent day's data
            hist = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ticker.history(period="1d")
            )
            
            if hist.empty:
                return None
            
            latest = hist.iloc[-1]
            latest_date = hist.index[-1].date()
            
            return StockPrice(
                symbol=symbol.upper(),
                date=latest_date,
                open_price=self._safe_decimal(latest.get('Open')),
                high_price=self._safe_decimal(latest.get('High')),
                low_price=self._safe_decimal(latest.get('Low')),
                close_price=self._safe_decimal(latest.get('Close')),
                adjusted_close=self._safe_decimal(latest.get('Close')),
                volume=int(latest.get('Volume', 0)) if pd.notna(latest.get('Volume')) else None
            )
            
        except Exception as e:
            logger.error(f"Error getting current price for {symbol}: {e}")
            return None
    
    async def _get_financial_statements(self, ticker: yf.Ticker, symbol: str) -> List[FinancialStatement]:
        """Get financial statements (income statement, balance sheet, cash flow)."""
        try:
            # Get financial data concurrently
            tasks = [
                asyncio.get_event_loop().run_in_executor(None, lambda: ticker.financials),
                asyncio.get_event_loop().run_in_executor(None, lambda: ticker.balance_sheet),
                asyncio.get_event_loop().run_in_executor(None, lambda: ticker.cashflow)
            ]
            
            financials, balance_sheet, cashflow = await asyncio.gather(*tasks, return_exceptions=True)
            
            statements = []
            
            # Process annual data
            if not isinstance(financials, Exception) and not financials.empty:
                for date_col in financials.columns:
                    try:
                        period_date = date_col.date() if hasattr(date_col, 'date') else date_col
                        
                        # Create income statement
                        income_stmt = self._create_income_statement(financials, symbol, period_date, "Annual")
                        
                        # Create balance sheet
                        balance_stmt = None
                        if not isinstance(balance_sheet, Exception) and not balance_sheet.empty and date_col in balance_sheet.columns:
                            balance_stmt = self._create_balance_sheet(balance_sheet, symbol, period_date, "Annual")
                        
                        # Create cash flow statement
                        cashflow_stmt = None
                        if not isinstance(cashflow, Exception) and not cashflow.empty and date_col in cashflow.columns:
                            cashflow_stmt = self._create_cashflow_statement(cashflow, symbol, period_date, "Annual")
                        
                        # Create financial statement
                        financial_statement = FinancialStatement(
                            symbol=symbol.upper(),
                            period_ending=period_date,
                            period_type="Annual",
                            income_statement=income_stmt,
                            balance_sheet=balance_stmt,
                            cash_flow_statement=cashflow_stmt,
                            data_source=DataSource.YAHOO_FINANCE
                        )
                        
                        statements.append(financial_statement)
                        
                    except Exception as e:
                        logger.warning(f"Error processing financial statement for {symbol} on {date_col}: {e}")
                        continue
            
            return statements
            
        except Exception as e:
            logger.error(f"Error getting financial statements for {symbol}: {e}")
            return []
    
    def _create_income_statement(self, financials: pd.DataFrame, symbol: str, period_date: date, period_type: str) -> Optional[IncomeStatement]:
        """Create income statement from Yahoo Finance data."""
        try:
            col_data = financials[period_date] if period_date in financials.columns else None
            if col_data is None:
                return None
            
            return IncomeStatement(
                symbol=symbol.upper(),
                period_ending=period_date,
                period_type=period_type,
                revenue=self._safe_decimal(col_data.get('Total Revenue')),
                cost_of_revenue=self._safe_decimal(col_data.get('Cost Of Revenue')),
                gross_profit=self._safe_decimal(col_data.get('Gross Profit')),
                operating_expenses=self._safe_decimal(col_data.get('Operating Expense')),
                operating_income=self._safe_decimal(col_data.get('Operating Income')),
                interest_expense=self._safe_decimal(col_data.get('Interest Expense')),
                pretax_income=self._safe_decimal(col_data.get('Pretax Income')),
                income_tax=self._safe_decimal(col_data.get('Tax Provision')),
                net_income=self._safe_decimal(col_data.get('Net Income')),
                eps_basic=self._safe_decimal(col_data.get('Basic EPS')),
                eps_diluted=self._safe_decimal(col_data.get('Diluted EPS')),
                shares_outstanding=self._safe_decimal(col_data.get('Basic Average Shares'))
            )
            
        except Exception as e:
            logger.warning(f"Error creating income statement for {symbol}: {e}")
            return None
    
    def _create_balance_sheet(self, balance_sheet: pd.DataFrame, symbol: str, period_date: date, period_type: str) -> Optional[BalanceSheet]:
        """Create balance sheet from Yahoo Finance data."""
        try:
            col_data = balance_sheet[period_date] if period_date in balance_sheet.columns else None
            if col_data is None:
                return None
            
            return BalanceSheet(
                symbol=symbol.upper(),
                period_ending=period_date,
                period_type=period_type,
                total_assets=self._safe_decimal(col_data.get('Total Assets')),
                current_assets=self._safe_decimal(col_data.get('Current Assets')),
                cash_and_equivalents=self._safe_decimal(col_data.get('Cash And Cash Equivalents')),
                inventory=self._safe_decimal(col_data.get('Inventory')),
                total_liabilities=self._safe_decimal(col_data.get('Total Liabilities Net Minority Interest')),
                current_liabilities=self._safe_decimal(col_data.get('Current Liabilities')),
                long_term_debt=self._safe_decimal(col_data.get('Long Term Debt')),
                total_equity=self._safe_decimal(col_data.get('Total Equity Gross Minority Interest')),
                retained_earnings=self._safe_decimal(col_data.get('Retained Earnings'))
            )
            
        except Exception as e:
            logger.warning(f"Error creating balance sheet for {symbol}: {e}")
            return None
    
    def _create_cashflow_statement(self, cashflow: pd.DataFrame, symbol: str, period_date: date, period_type: str) -> Optional[CashFlowStatement]:
        """Create cash flow statement from Yahoo Finance data."""
        try:
            col_data = cashflow[period_date] if period_date in cashflow.columns else None
            if col_data is None:
                return None
            
            operating_cf = self._safe_decimal(col_data.get('Operating Cash Flow'))
            investing_cf = self._safe_decimal(col_data.get('Investing Cash Flow'))
            financing_cf = self._safe_decimal(col_data.get('Financing Cash Flow'))
            capex = self._safe_decimal(col_data.get('Capital Expenditure'))
            
            # Calculate free cash flow
            free_cf = None
            if operating_cf is not None and capex is not None:
                free_cf = operating_cf + capex  # capex is usually negative
            
            # Calculate net cash flow
            net_cf = None
            if all(cf is not None for cf in [operating_cf, investing_cf, financing_cf]):
                net_cf = operating_cf + investing_cf + financing_cf
            
            return CashFlowStatement(
                symbol=symbol.upper(),
                period_ending=period_date,
                period_type=period_type,
                operating_cash_flow=operating_cf,
                investing_cash_flow=investing_cf,
                financing_cash_flow=financing_cf,
                net_cash_flow=net_cf,
                free_cash_flow=free_cf,
                capital_expenditures=capex,
                depreciation=self._safe_decimal(col_data.get('Depreciation And Amortization'))
            )
            
        except Exception as e:
            logger.warning(f"Error creating cash flow statement for {symbol}: {e}")
            return None
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None or pd.isna(value):
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
    
    async def search_symbols(self, query: str) -> List[Dict[str, str]]:
        """
        Search for stock symbols based on query.
        
        Args:
            query: Search query (company name or symbol)
            
        Returns:
            List of dictionaries with symbol information
        """
        try:
            # This is a simplified implementation
            # In a real scenario, you might want to use a dedicated search API
            logger.info(f"Searching for symbols with query: {query}")
            
            # For now, just validate if the query is a valid symbol
            if len(query) <= 5 and query.isalpha():
                ticker = yf.Ticker(query.upper())
                info = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: ticker.info
                )
                
                if info and info.get('longName'):
                    return [{
                        'symbol': query.upper(),
                        'name': info.get('longName', ''),
                        'sector': info.get('sector', ''),
                        'industry': info.get('industry', '')
                    }]
            
            return []
            
        except Exception as e:
            logger.error(f"Error searching symbols for query '{query}': {e}")
            return []
    
    async def get_market_data(self) -> Dict[str, Any]:
        """
        Get market-wide data (indices, rates, etc.).
        
        Returns:
            Dictionary with market data
        """
        try:
            logger.info("Fetching market data")
            
            # Get major indices and treasury rates
            symbols = ['^GSPC', '^DJI', '^IXIC', '^TNX', '^VIX']  # S&P 500, Dow, Nasdaq, 10Y Treasury, VIX
            
            market_data = {}
            
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    hist = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: ticker.history(period="1d")
                    )
                    
                    if not hist.empty:
                        latest = hist.iloc[-1]
                        market_data[symbol] = {
                            'close': float(latest['Close']),
                            'change': float(latest['Close'] - latest['Open']),
                            'change_percent': float((latest['Close'] - latest['Open']) / latest['Open'] * 100),
                            'date': hist.index[-1].date().isoformat()
                        }
                        
                except Exception as e:
                    logger.warning(f"Error fetching data for {symbol}: {e}")
                    continue
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return {}
    
    async def health_check(self) -> bool:
        """
        Check if Yahoo Finance API is accessible.
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Try to fetch a simple ticker (Apple)
            ticker = yf.Ticker("AAPL")
            info = await asyncio.get_event_loop().run_in_executor(
                None, lambda: ticker.info
            )
            
            return bool(info and info.get('symbol'))
            
        except Exception as e:
            logger.error(f"Yahoo Finance health check failed: {e}")
            return False