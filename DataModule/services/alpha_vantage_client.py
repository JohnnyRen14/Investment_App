"""
Alpha Vantage API Client

Handles all interactions with Alpha Vantage API for fetching fundamental data,
financial statements, and market information with premium data quality.

Author: Lebron (Data & Infrastructure Lead)
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any
import httpx
import json
from ..models.financial_data import (
    StockData, StockPrice, CompanyInfo, FinancialStatement,
    IncomeStatement, BalanceSheet, CashFlowStatement, DataSource, MarketData
)

logger = logging.getLogger(__name__)


class AlphaVantageClient:
    """
    Alpha Vantage API client with comprehensive error handling, rate limiting, and data validation.
    """
    
    def __init__(self, api_key: str = "2IBUO6HAIYUPSMN0", timeout: int = 30, max_retries: int = 3):
        """
        Initialize Alpha Vantage client.
        
        Args:
            api_key: Alpha Vantage API key
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.timeout = timeout
        self.max_retries = max_retries
        self.session = None
        
        # Rate limiting: Alpha Vantage allows 5 API requests per minute and 500 per day
        self.requests_per_minute = 5
        self.requests_per_day = 500
        self.request_timestamps = []
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = httpx.AsyncClient(timeout=self.timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.aclose()
    
    async def _make_request(self, params: Dict[str, str]) -> Optional[Dict[str, Any]]:
        """
        Make API request with rate limiting and error handling.
        
        Args:
            params: Request parameters
            
        Returns:
            API response data or None if failed
        """
        # Add API key to parameters
        params['apikey'] = self.api_key
        
        # Check rate limits
        if not await self._check_rate_limits():
            logger.warning("Rate limit exceeded, waiting...")
            await asyncio.sleep(60)  # Wait 1 minute
            
        for attempt in range(self.max_retries):
            try:
                if not self.session:
                    self.session = httpx.AsyncClient(timeout=self.timeout)
                
                logger.debug(f"Making Alpha Vantage API request: {params}")
                
                response = await self.session.get(self.base_url, params=params)
                response.raise_for_status()
                
                # Track request timestamp for rate limiting
                self.request_timestamps.append(datetime.now())
                
                data = response.json()
                
                # Check for API errors
                if "Error Message" in data:
                    logger.error(f"Alpha Vantage API error: {data['Error Message']}")
                    return None
                    
                if "Note" in data:
                    logger.warning(f"Alpha Vantage API note: {data['Note']}")
                    # This usually means rate limit hit
                    await asyncio.sleep(60)
                    continue
                
                logger.debug("Alpha Vantage API request successful")
                return data
                
            except httpx.HTTPStatusError as e:
                logger.warning(f"HTTP error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
                    
            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error("All retry attempts failed")
        return None
    
    async def _check_rate_limits(self) -> bool:
        """
        Check if we're within rate limits.
        
        Returns:
            True if within limits, False otherwise
        """
        now = datetime.now()
        
        # Clean old timestamps (older than 1 day)
        self.request_timestamps = [
            ts for ts in self.request_timestamps 
            if (now - ts).total_seconds() < 86400
        ]
        
        # Check daily limit
        daily_requests = len(self.request_timestamps)
        if daily_requests >= self.requests_per_day:
            logger.warning(f"Daily rate limit exceeded: {daily_requests}/{self.requests_per_day}")
            return False
        
        # Check per-minute limit
        minute_ago = now - timedelta(minutes=1)
        recent_requests = [
            ts for ts in self.request_timestamps 
            if ts > minute_ago
        ]
        
        if len(recent_requests) >= self.requests_per_minute:
            logger.warning(f"Per-minute rate limit exceeded: {len(recent_requests)}/{self.requests_per_minute}")
            return False
        
        return True
    
    async def get_company_overview(self, symbol: str) -> Optional[CompanyInfo]:
        """
        Get company overview/fundamental data.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            CompanyInfo object or None if failed
        """
        try:
            logger.info(f"Fetching company overview for {symbol}")
            
            params = {
                'function': 'OVERVIEW',
                'symbol': symbol.upper()
            }
            
            data = await self._make_request(params)
            if not data:
                return None
            
            # Alpha Vantage returns empty dict if symbol not found
            if not data or 'Symbol' not in data:
                logger.warning(f"No company data found for {symbol}")
                return None
            
            return CompanyInfo(
                symbol=symbol.upper(),
                company_name=data.get('Name', ''),
                sector=data.get('Sector'),
                industry=data.get('Industry'),
                market_cap=self._safe_decimal(data.get('MarketCapitalization')),
                enterprise_value=self._safe_decimal(data.get('EVToEBITDA')),  # Not direct EV
                trailing_pe=self._safe_decimal(data.get('TrailingPE')),
                forward_pe=self._safe_decimal(data.get('ForwardPE')),
                peg_ratio=self._safe_decimal(data.get('PEGRatio')),
                price_to_book=self._safe_decimal(data.get('PriceToBookRatio')),
                price_to_sales=self._safe_decimal(data.get('PriceToSalesRatioTTM')),
                beta=self._safe_decimal(data.get('Beta')),
                dividend_yield=self._safe_decimal(data.get('DividendYield')),
                description=data.get('Description'),
                employees=self._safe_int(data.get('FullTimeEmployees'))
            )
            
        except Exception as e:
            logger.error(f"Error fetching company overview for {symbol}: {e}")
            return None
    
    async def get_income_statement(self, symbol: str) -> List[IncomeStatement]:
        """
        Get annual income statements.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            List of IncomeStatement objects
        """
        try:
            logger.info(f"Fetching income statements for {symbol}")
            
            params = {
                'function': 'INCOME_STATEMENT',
                'symbol': symbol.upper()
            }
            
            data = await self._make_request(params)
            if not data or 'annualReports' not in data:
                return []
            
            statements = []
            for report in data['annualReports']:
                try:
                    fiscal_date = datetime.strptime(report['fiscalDateEnding'], '%Y-%m-%d').date()
                    
                    income_stmt = IncomeStatement(
                        symbol=symbol.upper(),
                        period_ending=fiscal_date,
                        period_type="Annual",
                        revenue=self._safe_decimal(report.get('totalRevenue')),
                        cost_of_revenue=self._safe_decimal(report.get('costOfRevenue')),
                        gross_profit=self._safe_decimal(report.get('grossProfit')),
                        operating_expenses=self._safe_decimal(report.get('totalOperatingExpense')),
                        operating_income=self._safe_decimal(report.get('operatingIncome')),
                        interest_expense=self._safe_decimal(report.get('interestExpense')),
                        pretax_income=self._safe_decimal(report.get('incomeBeforeTax')),
                        income_tax=self._safe_decimal(report.get('incomeTaxExpense')),
                        net_income=self._safe_decimal(report.get('netIncome')),
                        eps_basic=self._safe_decimal(report.get('reportedEPS')),
                        eps_diluted=self._safe_decimal(report.get('reportedEPS')),  # Alpha Vantage doesn't separate
                        shares_outstanding=self._safe_decimal(report.get('weightedAverageSharesOutstanding'))
                    )
                    
                    statements.append(income_stmt)
                    
                except Exception as e:
                    logger.warning(f"Error processing income statement for {symbol} on {report.get('fiscalDateEnding')}: {e}")
                    continue
            
            return statements
            
        except Exception as e:
            logger.error(f"Error fetching income statements for {symbol}: {e}")
            return []
    
    async def get_balance_sheet(self, symbol: str) -> List[BalanceSheet]:
        """
        Get annual balance sheets.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            List of BalanceSheet objects
        """
        try:
            logger.info(f"Fetching balance sheets for {symbol}")
            
            params = {
                'function': 'BALANCE_SHEET',
                'symbol': symbol.upper()
            }
            
            data = await self._make_request(params)
            if not data or 'annualReports' not in data:
                return []
            
            statements = []
            for report in data['annualReports']:
                try:
                    fiscal_date = datetime.strptime(report['fiscalDateEnding'], '%Y-%m-%d').date()
                    
                    balance_stmt = BalanceSheet(
                        symbol=symbol.upper(),
                        period_ending=fiscal_date,
                        period_type="Annual",
                        total_assets=self._safe_decimal(report.get('totalAssets')),
                        current_assets=self._safe_decimal(report.get('totalCurrentAssets')),
                        cash_and_equivalents=self._safe_decimal(report.get('cashAndCashEquivalentsAtCarryingValue')),
                        inventory=self._safe_decimal(report.get('inventory')),
                        total_liabilities=self._safe_decimal(report.get('totalLiabilities')),
                        current_liabilities=self._safe_decimal(report.get('totalCurrentLiabilities')),
                        long_term_debt=self._safe_decimal(report.get('longTermDebt')),
                        total_equity=self._safe_decimal(report.get('totalShareholderEquity')),
                        retained_earnings=self._safe_decimal(report.get('retainedEarnings'))
                    )
                    
                    statements.append(balance_stmt)
                    
                except Exception as e:
                    logger.warning(f"Error processing balance sheet for {symbol} on {report.get('fiscalDateEnding')}: {e}")
                    continue
            
            return statements
            
        except Exception as e:
            logger.error(f"Error fetching balance sheets for {symbol}: {e}")
            return []
    
    async def get_cash_flow(self, symbol: str) -> List[CashFlowStatement]:
        """
        Get annual cash flow statements.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            List of CashFlowStatement objects
        """
        try:
            logger.info(f"Fetching cash flow statements for {symbol}")
            
            params = {
                'function': 'CASH_FLOW',
                'symbol': symbol.upper()
            }
            
            data = await self._make_request(params)
            if not data or 'annualReports' not in data:
                return []
            
            statements = []
            for report in data['annualReports']:
                try:
                    fiscal_date = datetime.strptime(report['fiscalDateEnding'], '%Y-%m-%d').date()
                    
                    operating_cf = self._safe_decimal(report.get('operatingCashflow'))
                    investing_cf = self._safe_decimal(report.get('cashflowFromInvestment'))
                    financing_cf = self._safe_decimal(report.get('cashflowFromFinancing'))
                    capex = self._safe_decimal(report.get('capitalExpenditures'))
                    
                    # Calculate derived values
                    net_cf = None
                    if all(cf is not None for cf in [operating_cf, investing_cf, financing_cf]):
                        net_cf = operating_cf + investing_cf + financing_cf
                    
                    free_cf = None
                    if operating_cf is not None and capex is not None:
                        free_cf = operating_cf - abs(capex)  # Ensure capex is subtracted
                    
                    cashflow_stmt = CashFlowStatement(
                        symbol=symbol.upper(),
                        period_ending=fiscal_date,
                        period_type="Annual",
                        operating_cash_flow=operating_cf,
                        investing_cash_flow=investing_cf,
                        financing_cash_flow=financing_cf,
                        net_cash_flow=net_cf,
                        free_cash_flow=free_cf,
                        capital_expenditures=capex,
                        depreciation=self._safe_decimal(report.get('depreciationDepletionAndAmortization'))
                    )
                    
                    statements.append(cashflow_stmt)
                    
                except Exception as e:
                    logger.warning(f"Error processing cash flow statement for {symbol} on {report.get('fiscalDateEnding')}: {e}")
                    continue
            
            return statements
            
        except Exception as e:
            logger.error(f"Error fetching cash flow statements for {symbol}: {e}")
            return []
    
    async def get_daily_prices(self, symbol: str, outputsize: str = "compact") -> List[StockPrice]:
        """
        Get daily price data.
        
        Args:
            symbol: Stock symbol
            outputsize: 'compact' (100 days) or 'full' (20+ years)
            
        Returns:
            List of StockPrice objects
        """
        try:
            logger.info(f"Fetching daily prices for {symbol}")
            
            params = {
                'function': 'TIME_SERIES_DAILY_ADJUSTED',
                'symbol': symbol.upper(),
                'outputsize': outputsize
            }
            
            data = await self._make_request(params)
            if not data or 'Time Series (Daily)' not in data:
                return []
            
            prices = []
            time_series = data['Time Series (Daily)']
            
            for date_str, price_data in time_series.items():
                try:
                    price_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    
                    price = StockPrice(
                        symbol=symbol.upper(),
                        date=price_date,
                        open_price=self._safe_decimal(price_data.get('1. open')),
                        high_price=self._safe_decimal(price_data.get('2. high')),
                        low_price=self._safe_decimal(price_data.get('3. low')),
                        close_price=self._safe_decimal(price_data.get('4. close')),
                        adjusted_close=self._safe_decimal(price_data.get('5. adjusted close')),
                        volume=self._safe_int(price_data.get('6. volume'))
                    )
                    
                    prices.append(price)
                    
                except Exception as e:
                    logger.warning(f"Error processing price data for {symbol} on {date_str}: {e}")
                    continue
            
            # Sort by date (newest first)
            prices.sort(key=lambda x: x.date, reverse=True)
            return prices
            
        except Exception as e:
            logger.error(f"Error fetching daily prices for {symbol}: {e}")
            return []
    
    async def get_comprehensive_data(self, symbol: str) -> Optional[StockData]:
        """
        Get comprehensive stock data combining all available information.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            StockData object or None if failed
        """
        try:
            logger.info(f"Fetching comprehensive data for {symbol}")
            
            # Get all data concurrently (with rate limiting consideration)
            company_info = await self.get_company_overview(symbol)
            
            # Add small delays between requests to respect rate limits
            await asyncio.sleep(12)  # 5 requests per minute = 12 seconds between requests
            
            income_statements = await self.get_income_statement(symbol)
            await asyncio.sleep(12)
            
            balance_sheets = await self.get_balance_sheet(symbol)
            await asyncio.sleep(12)
            
            cash_flows = await self.get_cash_flow(symbol)
            await asyncio.sleep(12)
            
            daily_prices = await self.get_daily_prices(symbol, "compact")
            
            # Combine financial statements
            financial_statements = []
            
            # Group statements by period
            periods = set()
            if income_statements:
                periods.update(stmt.period_ending for stmt in income_statements)
            if balance_sheets:
                periods.update(stmt.period_ending for stmt in balance_sheets)
            if cash_flows:
                periods.update(stmt.period_ending for stmt in cash_flows)
            
            for period in periods:
                income_stmt = next((stmt for stmt in income_statements if stmt.period_ending == period), None)
                balance_stmt = next((stmt for stmt in balance_sheets if stmt.period_ending == period), None)
                cashflow_stmt = next((stmt for stmt in cash_flows if stmt.period_ending == period), None)
                
                if any([income_stmt, balance_stmt, cashflow_stmt]):
                    financial_statement = FinancialStatement(
                        symbol=symbol.upper(),
                        period_ending=period,
                        period_type="Annual",
                        income_statement=income_stmt,
                        balance_sheet=balance_stmt,
                        cash_flow_statement=cashflow_stmt,
                        data_source=DataSource.ALPHA_VANTAGE
                    )
                    financial_statements.append(financial_statement)
            
            # Get current price (most recent)
            current_price = daily_prices[0] if daily_prices else None
            
            stock_data = StockData(
                symbol=symbol.upper(),
                company_info=company_info,
                current_price=current_price,
                historical_prices=daily_prices,
                financial_statements=financial_statements,
                last_updated=datetime.now()
            )
            
            logger.info(f"Successfully fetched comprehensive data for {symbol}")
            return stock_data
            
        except Exception as e:
            logger.error(f"Error fetching comprehensive data for {symbol}: {e}")
            return None
    
    async def search_symbols(self, keywords: str) -> List[Dict[str, str]]:
        """
        Search for symbols using keywords.
        
        Args:
            keywords: Search keywords
            
        Returns:
            List of symbol information
        """
        try:
            logger.info(f"Searching symbols for keywords: {keywords}")
            
            params = {
                'function': 'SYMBOL_SEARCH',
                'keywords': keywords
            }
            
            data = await self._make_request(params)
            if not data or 'bestMatches' not in data:
                return []
            
            results = []
            for match in data['bestMatches']:
                results.append({
                    'symbol': match.get('1. symbol', ''),
                    'name': match.get('2. name', ''),
                    'type': match.get('3. type', ''),
                    'region': match.get('4. region', ''),
                    'market_open': match.get('5. marketOpen', ''),
                    'market_close': match.get('6. marketClose', ''),
                    'timezone': match.get('7. timezone', ''),
                    'currency': match.get('8. currency', ''),
                    'match_score': match.get('9. matchScore', '')
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching symbols for '{keywords}': {e}")
            return []
    
    async def get_treasury_rate(self) -> Optional[Decimal]:
        """
        Get 10-year Treasury rate (risk-free rate).
        
        Returns:
            Treasury rate as Decimal or None if failed
        """
        try:
            logger.info("Fetching 10-year Treasury rate")
            
            params = {
                'function': 'TREASURY_YIELD',
                'interval': 'daily',
                'maturity': '10year'
            }
            
            data = await self._make_request(params)
            if not data or 'data' not in data:
                return None
            
            # Get the most recent rate
            if data['data']:
                latest = data['data'][0]
                return self._safe_decimal(latest.get('value'))
            
            return None
            
        except Exception as e:
            logger.error(f"Error fetching Treasury rate: {e}")
            return None
    
    def _safe_decimal(self, value: Any) -> Optional[Decimal]:
        """Safely convert value to Decimal."""
        if value is None or value == 'None' or value == '':
            return None
        try:
            return Decimal(str(value))
        except (ValueError, TypeError):
            return None
    
    def _safe_int(self, value: Any) -> Optional[int]:
        """Safely convert value to int."""
        if value is None or value == 'None' or value == '':
            return None
        try:
            return int(float(str(value)))
        except (ValueError, TypeError):
            return None
    
    async def health_check(self) -> bool:
        """
        Check if Alpha Vantage API is accessible.
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Try to fetch a simple overview (Apple)
            params = {
                'function': 'OVERVIEW',
                'symbol': 'AAPL'
            }
            
            data = await self._make_request(params)
            return bool(data and 'Symbol' in data)
            
        except Exception as e:
            logger.error(f"Alpha Vantage health check failed: {e}")
            return False