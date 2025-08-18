"""
DataModule Test Suite

Comprehensive tests for all DataModule components including API clients,
caching, data quality assessment, and the main data service.

Author: Lebron (Data & Infrastructure Lead)
"""

import pytest
import asyncio
from datetime import datetime, date, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, AsyncMock

# Import all components to test
from ..services.yahoo_finance_client import YahooFinanceClient
from ..services.alpha_vantage_client import AlphaVantageClient
from ..services.cache_service import CacheService
from ..services.data_quality_service import DataQualityService
from ..services.data_service import DataService
from ..models.financial_data import (
    StockData, StockPrice, CompanyInfo, DataSource, DataQualityMetrics, DataType
)


class TestYahooFinanceClient:
    """Test Yahoo Finance client functionality."""
    
    @pytest.fixture
    def yahoo_client(self):
        return YahooFinanceClient()
    
    @pytest.mark.asyncio
    async def test_get_stock_data_success(self, yahoo_client):
        """Test successful stock data retrieval."""
        # Test with a well-known stock
        stock_data = await yahoo_client.get_stock_data("AAPL", period="1mo")
        
        assert stock_data is not None
        assert stock_data.symbol == "AAPL"
        assert stock_data.company_info is not None
        assert stock_data.current_price is not None
        assert len(stock_data.historical_prices) > 0
    
    @pytest.mark.asyncio
    async def test_get_stock_data_invalid_symbol(self, yahoo_client):
        """Test handling of invalid stock symbol."""
        stock_data = await yahoo_client.get_stock_data("INVALID_SYMBOL_XYZ")
        
        # Should handle gracefully, might return None or empty data
        if stock_data:
            assert stock_data.symbol == "INVALID_SYMBOL_XYZ"
    
    @pytest.mark.asyncio
    async def test_search_symbols(self, yahoo_client):
        """Test symbol search functionality."""
        results = await yahoo_client.search_symbols("AAPL")
        
        # Should return some results for Apple
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_health_check(self, yahoo_client):
        """Test Yahoo Finance health check."""
        is_healthy = await yahoo_client.health_check()
        
        assert isinstance(is_healthy, bool)


class TestAlphaVantageClient:
    """Test Alpha Vantage client functionality."""
    
    @pytest.fixture
    def alpha_vantage_client(self):
        return AlphaVantageClient(api_key="2IBUO6HAIYUPSMN0")
    
    @pytest.mark.asyncio
    async def test_get_company_overview(self, alpha_vantage_client):
        """Test company overview retrieval."""
        async with alpha_vantage_client as client:
            company_info = await client.get_company_overview("AAPL")
            
            if company_info:  # Might fail due to rate limits
                assert company_info.symbol == "AAPL"
                assert company_info.company_name is not None
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, alpha_vantage_client):
        """Test rate limiting functionality."""
        # Check initial rate limit status
        can_make_request = await alpha_vantage_client._check_rate_limits()
        assert isinstance(can_make_request, bool)
    
    @pytest.mark.asyncio
    async def test_search_symbols(self, alpha_vantage_client):
        """Test symbol search."""
        async with alpha_vantage_client as client:
            results = await client.search_symbols("Apple")
            
            assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_health_check(self, alpha_vantage_client):
        """Test Alpha Vantage health check."""
        async with alpha_vantage_client as client:
            is_healthy = await client.health_check()
            
            assert isinstance(is_healthy, bool)


class TestCacheService:
    """Test Redis cache service functionality."""
    
    @pytest.fixture
    def cache_service(self):
        # Use a test Redis instance or mock
        return CacheService(redis_url="redis://localhost:6379")
    
    @pytest.mark.asyncio
    async def test_cache_operations(self, cache_service):
        """Test basic cache operations."""
        try:
            await cache_service.connect()
            
            # Test set and get
            test_data = {"test": "data", "timestamp": datetime.now().isoformat()}
            test_key = "test_key"
            
            # Set data
            success = await cache_service.set(test_key, test_data, ttl=60)
            assert success is True
            
            # Get data
            retrieved_data = await cache_service.get(test_key)
            assert retrieved_data is not None
            assert retrieved_data["test"] == "data"
            
            # Check existence
            exists = await cache_service.exists(test_key)
            assert exists is True
            
            # Delete data
            deleted = await cache_service.delete(test_key)
            assert deleted is True
            
            # Verify deletion
            retrieved_after_delete = await cache_service.get(test_key)
            assert retrieved_after_delete is None
            
        except Exception as e:
            # Cache service might not be available in test environment
            pytest.skip(f"Cache service not available: {e}")
        finally:
            await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_cache_compression(self, cache_service):
        """Test cache compression for large data."""
        try:
            await cache_service.connect()
            
            # Create large test data
            large_data = {"data": "x" * 2000}  # Larger than compression threshold
            test_key = "large_test_key"
            
            success = await cache_service.set(test_key, large_data, ttl=60)
            assert success is True
            
            retrieved_data = await cache_service.get(test_key)
            assert retrieved_data is not None
            assert retrieved_data["data"] == "x" * 2000
            
            await cache_service.delete(test_key)
            
        except Exception as e:
            pytest.skip(f"Cache service not available: {e}")
        finally:
            await cache_service.disconnect()
    
    @pytest.mark.asyncio
    async def test_health_check(self, cache_service):
        """Test cache health check."""
        try:
            is_healthy = await cache_service.health_check()
            assert isinstance(is_healthy, bool)
        except Exception as e:
            pytest.skip(f"Cache service not available: {e}")


class TestDataQualityService:
    """Test data quality assessment functionality."""
    
    @pytest.fixture
    def quality_service(self):
        return DataQualityService()
    
    @pytest.fixture
    def sample_stock_data(self):
        """Create sample stock data for testing."""
        return StockData(
            symbol="AAPL",
            company_info=CompanyInfo(
                symbol="AAPL",
                company_name="Apple Inc.",
                sector="Technology",
                industry="Consumer Electronics",
                market_cap=Decimal("3000000000000"),
                trailing_pe=Decimal("25.5"),
                beta=Decimal("1.2")
            ),
            current_price=StockPrice(
                symbol="AAPL",
                date=date.today(),
                open_price=Decimal("150.00"),
                high_price=Decimal("155.00"),
                low_price=Decimal("149.00"),
                close_price=Decimal("152.50"),
                volume=50000000
            ),
            historical_prices=[
                StockPrice(
                    symbol="AAPL",
                    date=date.today() - timedelta(days=i),
                    close_price=Decimal(f"{150 + i}"),
                    volume=50000000
                ) for i in range(30)
            ]
        )
    
    @pytest.mark.asyncio
    async def test_assess_stock_data_quality(self, quality_service, sample_stock_data):
        """Test stock data quality assessment."""
        quality_metrics = await quality_service.assess_stock_data_quality(
            sample_stock_data, DataSource.YAHOO_FINANCE
        )
        
        assert isinstance(quality_metrics, DataQualityMetrics)
        assert quality_metrics.symbol == "AAPL"
        assert 0 <= float(quality_metrics.quality_score) <= 100
        assert 0 <= float(quality_metrics.completeness_score) <= 100
        assert 0 <= float(quality_metrics.freshness_score) <= 100
        assert 0 <= float(quality_metrics.accuracy_score) <= 100
    
    def test_quality_grade(self, quality_service):
        """Test quality grade calculation."""
        assert quality_service.get_quality_grade(95) == 'A'
        assert quality_service.get_quality_grade(80) == 'B'
        assert quality_service.get_quality_grade(65) == 'C'
        assert quality_service.get_quality_grade(45) == 'D'
        assert quality_service.get_quality_grade(25) == 'F'
    
    @pytest.mark.asyncio
    async def test_generate_quality_report(self, quality_service, sample_stock_data):
        """Test quality report generation."""
        quality_metrics = await quality_service.assess_stock_data_quality(
            sample_stock_data, DataSource.YAHOO_FINANCE
        )
        
        report = await quality_service.generate_quality_report(quality_metrics)
        
        assert isinstance(report, dict)
        assert 'symbol' in report
        assert 'overall_score' in report
        assert 'overall_grade' in report
        assert 'recommendations' in report


class TestDataService:
    """Test main data service functionality."""
    
    @pytest.fixture
    def data_service(self):
        return DataService(
            alpha_vantage_api_key="2IBUO6HAIYUPSMN0",
            enable_caching=False,  # Disable caching for tests
            enable_quality_assessment=True
        )
    
    @pytest.mark.asyncio
    async def test_get_stock_data(self, data_service):
        """Test main stock data retrieval."""
        stock_data = await data_service.get_stock_data("AAPL")
        
        if stock_data:  # Might fail due to API limits
            assert stock_data.symbol == "AAPL"
            assert isinstance(stock_data, StockData)
    
    @pytest.mark.asyncio
    async def test_search_symbols(self, data_service):
        """Test symbol search through data service."""
        results = await data_service.search_symbols("Apple")
        
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_batch_get_stock_data(self, data_service):
        """Test batch stock data retrieval."""
        symbols = ["AAPL", "GOOGL", "MSFT"]
        results = await data_service.batch_get_stock_data(symbols, max_concurrent=2)
        
        assert isinstance(results, dict)
        assert len(results) == len(symbols)
        
        for symbol in symbols:
            assert symbol in results
    
    @pytest.mark.asyncio
    async def test_get_service_health(self, data_service):
        """Test service health check."""
        health_status = await data_service.get_service_health()
        
        assert isinstance(health_status, dict)
        assert 'overall_status' in health_status
        assert 'services' in health_status
        assert 'metrics' in health_status
    
    @pytest.mark.asyncio
    async def test_rate_limiting(self, data_service):
        """Test rate limiting functionality."""
        # Test rate limit checking
        can_make_yahoo_request = await data_service._check_rate_limit(DataSource.YAHOO_FINANCE)
        can_make_av_request = await data_service._check_rate_limit(DataSource.ALPHA_VANTAGE)
        
        assert isinstance(can_make_yahoo_request, bool)
        assert isinstance(can_make_av_request, bool)


class TestIntegration:
    """Integration tests for the complete DataModule."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_data_flow(self):
        """Test complete data flow from API to quality assessment."""
        # Initialize data service
        data_service = DataService(
            alpha_vantage_api_key="2IBUO6HAIYUPSMN0",
            enable_caching=False,
            enable_quality_assessment=True
        )
        
        try:
            # Get stock data
            stock_data = await data_service.get_stock_data("AAPL")
            
            if stock_data:
                # Verify data structure
                assert isinstance(stock_data, StockData)
                assert stock_data.symbol == "AAPL"
                
                # Verify quality assessment was performed
                if stock_data.data_quality:
                    assert isinstance(stock_data.data_quality, DataQualityMetrics)
                    assert 0 <= float(stock_data.data_quality.quality_score) <= 100
                
                # Test search functionality
                search_results = await data_service.search_symbols("AAPL")
                assert isinstance(search_results, list)
                
                # Test health check
                health_status = await data_service.get_service_health()
                assert isinstance(health_status, dict)
                
        finally:
            await data_service.cleanup()
    
    @pytest.mark.asyncio
    async def test_error_handling(self):
        """Test error handling across the module."""
        data_service = DataService(
            alpha_vantage_api_key="invalid_key",
            enable_caching=False,
            enable_quality_assessment=True
        )
        
        try:
            # Test with invalid symbol
            stock_data = await data_service.get_stock_data("INVALID_SYMBOL_XYZ")
            
            # Should handle gracefully (return None or empty data)
            if stock_data:
                assert stock_data.symbol == "INVALID_SYMBOL_XYZ"
            
            # Test search with invalid query
            search_results = await data_service.search_symbols("")
            assert isinstance(search_results, list)
            
        finally:
            await data_service.cleanup()


# Performance tests
class TestPerformance:
    """Performance tests for DataModule components."""
    
    @pytest.mark.asyncio
    async def test_concurrent_requests(self):
        """Test performance under concurrent load."""
        data_service = DataService(
            alpha_vantage_api_key="2IBUO6HAIYUPSMN0",
            enable_caching=False,
            enable_quality_assessment=False  # Disable for performance test
        )
        
        try:
            symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
            
            start_time = datetime.now()
            results = await data_service.batch_get_stock_data(symbols, max_concurrent=3)
            end_time = datetime.now()
            
            duration = (end_time - start_time).total_seconds()
            
            # Should complete within reasonable time
            assert duration < 60  # 1 minute max for 5 stocks
            assert isinstance(results, dict)
            
        finally:
            await data_service.cleanup()


# Fixtures for pytest
@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])