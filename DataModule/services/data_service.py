"""
Data Service - Main Orchestrator

Main service that orchestrates all data operations, API integrations, caching,
rate limiting, and data quality assessment.

Author: Lebron (Data & Infrastructure Lead)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Union
from decimal import Decimal

from .yahoo_finance_client import YahooFinanceClient
from .alpha_vantage_client import AlphaVantageClient
from .cache_service import CacheService
from .data_quality_service import DataQualityService
from ..models.financial_data import (
    StockData, DataSource, DataQualityMetrics, APIRateLimit, MarketData
)

logger = logging.getLogger(__name__)


class DataService:
    """
    Main data service that orchestrates all financial data operations.
    """
    
    def __init__(
        self,
        alpha_vantage_api_key: str = "2IBUO6HAIYUPSMN0",
        redis_url: str = "redis://localhost:6379",
        enable_caching: bool = True,
        enable_quality_assessment: bool = True
    ):
        """
        Initialize data service.
        
        Args:
            alpha_vantage_api_key: Alpha Vantage API key
            redis_url: Redis connection URL
            enable_caching: Whether to enable caching
            enable_quality_assessment: Whether to enable quality assessment
        """
        self.enable_caching = enable_caching
        self.enable_quality_assessment = enable_quality_assessment
        
        # Initialize clients and services
        self.yahoo_client = YahooFinanceClient()
        self.alpha_vantage_client = AlphaVantageClient(api_key=alpha_vantage_api_key)
        
        if enable_caching:
            self.cache_service = CacheService(redis_url=redis_url)
        else:
            self.cache_service = None
            
        if enable_quality_assessment:
            self.quality_service = DataQualityService()
        else:
            self.quality_service = None
        
        # Rate limiting tracking
        self.rate_limits = {
            DataSource.YAHOO_FINANCE: APIRateLimit(
                api_name="yahoo_finance",
                endpoint="general",
                requests_limit=2000,  # Conservative estimate
                reset_time=datetime.now() + timedelta(hours=1)
            ),
            DataSource.ALPHA_VANTAGE: APIRateLimit(
                api_name="alpha_vantage",
                endpoint="general", 
                requests_limit=500,   # 500 per day
                reset_time=datetime.now() + timedelta(days=1)
            )
        }
        
        # Data source priority (primary -> fallback)
        self.data_source_priority = [DataSource.YAHOO_FINANCE, DataSource.ALPHA_VANTAGE]
        
        # Performance metrics
        self.metrics = {
            'requests_made': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'api_errors': 0,
            'quality_assessments': 0
        }
    
    async def get_stock_data(
        self, 
        symbol: str, 
        force_refresh: bool = False,
        preferred_source: Optional[DataSource] = None
    ) -> Optional[StockData]:
        """
        Get comprehensive stock data with caching and fallback mechanisms.
        
        Args:
            symbol: Stock symbol
            force_refresh: Whether to bypass cache
            preferred_source: Preferred data source
            
        Returns:
            StockData object or None if failed
        """
        try:
            symbol = symbol.upper()
            logger.info(f"Getting stock data for {symbol}")
            
            # Check cache first (unless force refresh)
            if not force_refresh and self.cache_service:
                cached_data = await self.cache_service.get(symbol, 'stock_data')
                if cached_data:
                    self.metrics['cache_hits'] += 1
                    logger.info(f"Retrieved {symbol} from cache")
                    
                    # Convert dict back to StockData if needed
                    if isinstance(cached_data, dict):
                        # This would need proper deserialization logic
                        pass
                    
                    return cached_data
                else:
                    self.metrics['cache_misses'] += 1
            
            # Determine data sources to try
            sources_to_try = [preferred_source] if preferred_source else self.data_source_priority
            
            stock_data = None
            for source in sources_to_try:
                if not await self._check_rate_limit(source):
                    logger.warning(f"Rate limit exceeded for {source}, skipping")
                    continue
                
                try:
                    if source == DataSource.YAHOO_FINANCE:
                        stock_data = await self._get_data_from_yahoo(symbol)
                    elif source == DataSource.ALPHA_VANTAGE:
                        stock_data = await self._get_data_from_alpha_vantage(symbol)
                    
                    if stock_data:
                        logger.info(f"Successfully retrieved {symbol} from {source}")
                        break
                        
                except Exception as e:
                    logger.error(f"Error getting data from {source} for {symbol}: {e}")
                    self.metrics['api_errors'] += 1
                    continue
            
            if not stock_data:
                logger.error(f"Failed to retrieve data for {symbol} from all sources")
                return None
            
            # Assess data quality
            if self.enable_quality_assessment and self.quality_service:
                try:
                    quality_metrics = await self.quality_service.assess_stock_data_quality(
                        stock_data, source
                    )
                    stock_data.data_quality = quality_metrics
                    self.metrics['quality_assessments'] += 1
                    
                    logger.info(f"Quality score for {symbol}: {quality_metrics.quality_score}/100")
                    
                except Exception as e:
                    logger.warning(f"Quality assessment failed for {symbol}: {e}")
            
            # Cache the result
            if self.cache_service:
                try:
                    # Determine cache TTL based on data quality
                    cache_ttl = self._determine_cache_ttl(stock_data)
                    await self.cache_service.set(symbol, stock_data, ttl=cache_ttl, data_type='stock_data')
                    logger.debug(f"Cached {symbol} with TTL {cache_ttl}s")
                    
                except Exception as e:
                    logger.warning(f"Failed to cache data for {symbol}: {e}")
            
            self.metrics['requests_made'] += 1
            return stock_data
            
        except Exception as e:
            logger.error(f"Error in get_stock_data for {symbol}: {e}")
            return None
    
    async def _get_data_from_yahoo(self, symbol: str) -> Optional[StockData]:
        """Get data from Yahoo Finance."""
        try:
            await self._update_rate_limit(DataSource.YAHOO_FINANCE)
            return await self.yahoo_client.get_stock_data(symbol)
        except Exception as e:
            logger.error(f"Yahoo Finance error for {symbol}: {e}")
            return None
    
    async def _get_data_from_alpha_vantage(self, symbol: str) -> Optional[StockData]:
        """Get data from Alpha Vantage."""
        try:
            await self._update_rate_limit(DataSource.ALPHA_VANTAGE)
            async with self.alpha_vantage_client as client:
                return await client.get_comprehensive_data(symbol)
        except Exception as e:
            logger.error(f"Alpha Vantage error for {symbol}: {e}")
            return None
    
    async def search_symbols(self, query: str) -> List[Dict[str, str]]:
        """
        Search for stock symbols across data sources.
        
        Args:
            query: Search query
            
        Returns:
            List of symbol information
        """
        try:
            logger.info(f"Searching symbols for query: {query}")
            
            # Check cache first
            cache_key = f"search:{query.lower()}"
            if self.cache_service:
                cached_results = await self.cache_service.get(cache_key, 'search_results')
                if cached_results:
                    return cached_results
            
            results = []
            
            # Try Yahoo Finance first
            if await self._check_rate_limit(DataSource.YAHOO_FINANCE):
                try:
                    yahoo_results = await self.yahoo_client.search_symbols(query)
                    results.extend(yahoo_results)
                    await self._update_rate_limit(DataSource.YAHOO_FINANCE)
                except Exception as e:
                    logger.warning(f"Yahoo Finance search error: {e}")
            
            # Try Alpha Vantage if we need more results
            if len(results) < 5 and await self._check_rate_limit(DataSource.ALPHA_VANTAGE):
                try:
                    async with self.alpha_vantage_client as client:
                        av_results = await client.search_symbols(query)
                        # Convert Alpha Vantage format to standard format
                        for result in av_results:
                            if result not in results:  # Avoid duplicates
                                results.append({
                                    'symbol': result.get('symbol', ''),
                                    'name': result.get('name', ''),
                                    'type': result.get('type', ''),
                                    'region': result.get('region', '')
                                })
                    await self._update_rate_limit(DataSource.ALPHA_VANTAGE)
                except Exception as e:
                    logger.warning(f"Alpha Vantage search error: {e}")
            
            # Cache results
            if self.cache_service and results:
                await self.cache_service.set(cache_key, results, ttl=3600, data_type='search_results')
            
            logger.info(f"Found {len(results)} results for query: {query}")
            return results
            
        except Exception as e:
            logger.error(f"Error searching symbols for {query}: {e}")
            return []
    
    async def get_market_data(self) -> Optional[MarketData]:
        """
        Get market-wide data (indices, rates, etc.).
        
        Returns:
            MarketData object or None if failed
        """
        try:
            logger.info("Getting market data")
            
            # Check cache first
            cache_key = "market_data"
            if self.cache_service:
                cached_data = await self.cache_service.get(cache_key, 'market_data')
                if cached_data:
                    return cached_data
            
            market_data = None
            
            # Try Yahoo Finance first
            if await self._check_rate_limit(DataSource.YAHOO_FINANCE):
                try:
                    yahoo_market_data = await self.yahoo_client.get_market_data()
                    await self._update_rate_limit(DataSource.YAHOO_FINANCE)
                    
                    if yahoo_market_data:
                        # Convert to MarketData object
                        market_data = MarketData(
                            date=datetime.now().date(),
                            sp500_return=Decimal(str(yahoo_market_data.get('^GSPC', {}).get('change_percent', 0))),
                            vix=Decimal(str(yahoo_market_data.get('^VIX', {}).get('close', 0))),
                            data_source=DataSource.YAHOO_FINANCE
                        )
                        
                except Exception as e:
                    logger.warning(f"Yahoo Finance market data error: {e}")
            
            # Try Alpha Vantage for Treasury rate
            if await self._check_rate_limit(DataSource.ALPHA_VANTAGE):
                try:
                    async with self.alpha_vantage_client as client:
                        treasury_rate = await client.get_treasury_rate()
                        await self._update_rate_limit(DataSource.ALPHA_VANTAGE)
                        
                        if treasury_rate and market_data:
                            market_data.risk_free_rate = treasury_rate
                        elif treasury_rate and not market_data:
                            market_data = MarketData(
                                date=datetime.now().date(),
                                risk_free_rate=treasury_rate,
                                data_source=DataSource.ALPHA_VANTAGE
                            )
                            
                except Exception as e:
                    logger.warning(f"Alpha Vantage treasury rate error: {e}")
            
            # Cache market data
            if market_data and self.cache_service:
                await self.cache_service.set(cache_key, market_data, ttl=1800, data_type='market_data')  # 30 min cache
            
            return market_data
            
        except Exception as e:
            logger.error(f"Error getting market data: {e}")
            return None
    
    async def batch_get_stock_data(self, symbols: List[str], max_concurrent: int = 5) -> Dict[str, Optional[StockData]]:
        """
        Get stock data for multiple symbols concurrently.
        
        Args:
            symbols: List of stock symbols
            max_concurrent: Maximum concurrent requests
            
        Returns:
            Dictionary mapping symbols to StockData
        """
        try:
            logger.info(f"Getting batch stock data for {len(symbols)} symbols")
            
            # Create semaphore to limit concurrent requests
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def get_single_stock(symbol: str) -> tuple[str, Optional[StockData]]:
                async with semaphore:
                    data = await self.get_stock_data(symbol)
                    return symbol, data
            
            # Execute requests concurrently
            tasks = [get_single_stock(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            stock_data_map = {}
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Batch request error: {result}")
                    continue
                    
                symbol, data = result
                stock_data_map[symbol] = data
            
            successful = sum(1 for data in stock_data_map.values() if data is not None)
            logger.info(f"Batch request completed: {successful}/{len(symbols)} successful")
            
            return stock_data_map
            
        except Exception as e:
            logger.error(f"Error in batch stock data request: {e}")
            return {}
    
    async def _check_rate_limit(self, source: DataSource) -> bool:
        """Check if we can make a request to the given source."""
        try:
            rate_limit = self.rate_limits.get(source)
            if not rate_limit:
                return True
            
            # Check if rate limit has reset
            if datetime.now() > rate_limit.reset_time:
                rate_limit.requests_made = 0
                if source == DataSource.ALPHA_VANTAGE:
                    rate_limit.reset_time = datetime.now() + timedelta(days=1)
                else:
                    rate_limit.reset_time = datetime.now() + timedelta(hours=1)
            
            return not rate_limit.is_limit_exceeded
            
        except Exception as e:
            logger.error(f"Error checking rate limit for {source}: {e}")
            return True  # Allow request if check fails
    
    async def _update_rate_limit(self, source: DataSource):
        """Update rate limit counter after making a request."""
        try:
            rate_limit = self.rate_limits.get(source)
            if rate_limit:
                rate_limit.requests_made += 1
                
        except Exception as e:
            logger.error(f"Error updating rate limit for {source}: {e}")
    
    def _determine_cache_ttl(self, stock_data: StockData) -> int:
        """Determine cache TTL based on data quality and type."""
        try:
            base_ttl = 900  # 15 minutes default
            
            # Adjust based on data quality
            if stock_data.data_quality:
                quality_score = float(stock_data.data_quality.quality_score)
                if quality_score >= 90:
                    return base_ttl * 2  # Cache longer for high quality data
                elif quality_score >= 75:
                    return base_ttl
                elif quality_score >= 60:
                    return base_ttl // 2  # Cache shorter for lower quality
                else:
                    return base_ttl // 4  # Very short cache for poor quality
            
            return base_ttl
            
        except Exception as e:
            logger.error(f"Error determining cache TTL: {e}")
            return 900  # Default fallback
    
    async def get_service_health(self) -> Dict[str, Any]:
        """
        Get health status of all services.
        
        Returns:
            Dictionary with health status
        """
        try:
            health_status = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'healthy',
                'services': {},
                'metrics': self.metrics
            }
            
            # Check Yahoo Finance
            try:
                yahoo_healthy = await self.yahoo_client.health_check()
                health_status['services']['yahoo_finance'] = {
                    'status': 'healthy' if yahoo_healthy else 'unhealthy',
                    'rate_limit': {
                        'requests_made': self.rate_limits[DataSource.YAHOO_FINANCE].requests_made,
                        'requests_remaining': self.rate_limits[DataSource.YAHOO_FINANCE].requests_remaining
                    }
                }
            except Exception as e:
                health_status['services']['yahoo_finance'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check Alpha Vantage
            try:
                async with self.alpha_vantage_client as client:
                    av_healthy = await client.health_check()
                health_status['services']['alpha_vantage'] = {
                    'status': 'healthy' if av_healthy else 'unhealthy',
                    'rate_limit': {
                        'requests_made': self.rate_limits[DataSource.ALPHA_VANTAGE].requests_made,
                        'requests_remaining': self.rate_limits[DataSource.ALPHA_VANTAGE].requests_remaining
                    }
                }
            except Exception as e:
                health_status['services']['alpha_vantage'] = {
                    'status': 'error',
                    'error': str(e)
                }
            
            # Check Cache
            if self.cache_service:
                try:
                    cache_healthy = await self.cache_service.health_check()
                    cache_stats = await self.cache_service.get_cache_stats()
                    health_status['services']['cache'] = {
                        'status': 'healthy' if cache_healthy else 'unhealthy',
                        'stats': cache_stats
                    }
                except Exception as e:
                    health_status['services']['cache'] = {
                        'status': 'error',
                        'error': str(e)
                    }
            
            # Determine overall status
            service_statuses = [service.get('status') for service in health_status['services'].values()]
            if 'error' in service_statuses:
                health_status['overall_status'] = 'degraded'
            elif 'unhealthy' in service_statuses:
                health_status['overall_status'] = 'degraded'
            
            return health_status
            
        except Exception as e:
            logger.error(f"Error getting service health: {e}")
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e)
            }
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.cache_service:
                await self.cache_service.disconnect()
            
            # Close other clients if needed
            logger.info("DataService cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")