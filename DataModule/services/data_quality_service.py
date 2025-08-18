"""
Data Quality Service

Handles data quality assessment, validation, and scoring for all financial data
sources with comprehensive quality metrics and reporting.

Author: Lebron (Data & Infrastructure Lead)
"""

import logging
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from statistics import mean, stdev
from ..models.financial_data import (
    DataQualityMetrics, DataSource, DataType, StockData, StockPrice,
    CompanyInfo, FinancialStatement, IncomeStatement, BalanceSheet, CashFlowStatement
)

logger = logging.getLogger(__name__)


class DataQualityService:
    """
    Service for assessing and scoring data quality across all financial data sources.
    """
    
    def __init__(self):
        """Initialize data quality service."""
        self.quality_thresholds = {
            'excellent': 90,
            'good': 75,
            'fair': 60,
            'poor': 40
        }
        
        # Weights for different quality aspects
        self.quality_weights = {
            'completeness': 0.4,  # 40% - How complete is the data
            'freshness': 0.3,     # 30% - How recent is the data
            'accuracy': 0.2,      # 20% - How accurate/consistent is the data
            'consistency': 0.1    # 10% - How consistent across sources
        }
    
    async def assess_stock_data_quality(self, stock_data: StockData, data_source: DataSource) -> DataQualityMetrics:
        """
        Assess overall quality of stock data.
        
        Args:
            stock_data: Stock data to assess
            data_source: Source of the data
            
        Returns:
            DataQualityMetrics object with quality scores
        """
        try:
            logger.info(f"Assessing data quality for {stock_data.symbol} from {data_source}")
            
            issues = []
            
            # Assess different components
            completeness_score = await self._assess_completeness(stock_data, issues)
            freshness_score = await self._assess_freshness(stock_data, issues)
            accuracy_score = await self._assess_accuracy(stock_data, issues)
            consistency_score = await self._assess_consistency(stock_data, issues)
            
            # Calculate overall quality score
            quality_score = (
                completeness_score * self.quality_weights['completeness'] +
                freshness_score * self.quality_weights['freshness'] +
                accuracy_score * self.quality_weights['accuracy'] +
                consistency_score * self.quality_weights['consistency']
            )
            
            quality_metrics = DataQualityMetrics(
                symbol=stock_data.symbol,
                data_source=data_source,
                data_type=DataType.STOCK_PRICE,
                quality_score=Decimal(str(round(quality_score, 2))),
                completeness_score=Decimal(str(round(completeness_score, 2))),
                freshness_score=Decimal(str(round(freshness_score, 2))),
                accuracy_score=Decimal(str(round(accuracy_score, 2))),
                issues=issues
            )
            
            logger.info(f"Quality assessment completed for {stock_data.symbol}: {quality_score:.2f}/100")
            return quality_metrics
            
        except Exception as e:
            logger.error(f"Error assessing data quality for {stock_data.symbol}: {e}")
            # Return default poor quality metrics
            return DataQualityMetrics(
                symbol=stock_data.symbol,
                data_source=data_source,
                data_type=DataType.STOCK_PRICE,
                quality_score=Decimal("0"),
                completeness_score=Decimal("0"),
                freshness_score=Decimal("0"),
                accuracy_score=Decimal("0"),
                issues=[f"Assessment failed: {str(e)}"]
            )
    
    async def _assess_completeness(self, stock_data: StockData, issues: List[str]) -> float:
        """
        Assess data completeness.
        
        Args:
            stock_data: Stock data to assess
            issues: List to append issues to
            
        Returns:
            Completeness score (0-100)
        """
        try:
            total_fields = 0
            completed_fields = 0
            
            # Check company info completeness
            if stock_data.company_info:
                company_fields = [
                    'company_name', 'sector', 'industry', 'market_cap',
                    'trailing_pe', 'beta', 'description'
                ]
                for field in company_fields:
                    total_fields += 1
                    if getattr(stock_data.company_info, field) is not None:
                        completed_fields += 1
                    else:
                        issues.append(f"Missing company info: {field}")
            else:
                issues.append("Company information completely missing")
                total_fields += 7  # Expected company fields
            
            # Check current price completeness
            if stock_data.current_price:
                price_fields = ['open_price', 'high_price', 'low_price', 'close_price', 'volume']
                for field in price_fields:
                    total_fields += 1
                    if getattr(stock_data.current_price, field) is not None:
                        completed_fields += 1
                    else:
                        issues.append(f"Missing current price: {field}")
            else:
                issues.append("Current price data missing")
                total_fields += 5
            
            # Check historical prices completeness
            if stock_data.historical_prices:
                # Check if we have reasonable amount of historical data
                if len(stock_data.historical_prices) >= 30:  # At least 30 days
                    completed_fields += 2
                elif len(stock_data.historical_prices) >= 7:  # At least 1 week
                    completed_fields += 1
                    issues.append("Limited historical price data (less than 30 days)")
                else:
                    issues.append("Insufficient historical price data (less than 7 days)")
                total_fields += 2
            else:
                issues.append("No historical price data")
                total_fields += 2
            
            # Check financial statements completeness
            if stock_data.financial_statements:
                # Check if we have recent financial statements (last 2 years)
                recent_statements = [
                    stmt for stmt in stock_data.financial_statements
                    if stmt.period_ending >= date.today() - timedelta(days=730)
                ]
                
                if len(recent_statements) >= 2:  # At least 2 years
                    completed_fields += 2
                elif len(recent_statements) >= 1:  # At least 1 year
                    completed_fields += 1
                    issues.append("Limited financial statements (less than 2 years)")
                else:
                    issues.append("No recent financial statements")
                total_fields += 2
                
                # Check completeness of financial statement components
                for stmt in recent_statements[:2]:  # Check last 2 statements
                    if stmt.income_statement:
                        completed_fields += 1
                    else:
                        issues.append(f"Missing income statement for {stmt.period_ending}")
                    
                    if stmt.balance_sheet:
                        completed_fields += 1
                    else:
                        issues.append(f"Missing balance sheet for {stmt.period_ending}")
                    
                    if stmt.cash_flow_statement:
                        completed_fields += 1
                    else:
                        issues.append(f"Missing cash flow statement for {stmt.period_ending}")
                    
                    total_fields += 3
            else:
                issues.append("No financial statements available")
                total_fields += 8  # Expected financial statement fields
            
            # Calculate completeness score
            completeness_score = (completed_fields / total_fields * 100) if total_fields > 0 else 0
            
            logger.debug(f"Completeness assessment: {completed_fields}/{total_fields} = {completeness_score:.2f}%")
            return completeness_score
            
        except Exception as e:
            logger.error(f"Error assessing completeness: {e}")
            issues.append(f"Completeness assessment failed: {str(e)}")
            return 0
    
    async def _assess_freshness(self, stock_data: StockData, issues: List[str]) -> float:
        """
        Assess data freshness.
        
        Args:
            stock_data: Stock data to assess
            issues: List to append issues to
            
        Returns:
            Freshness score (0-100)
        """
        try:
            now = datetime.now()
            today = date.today()
            freshness_scores = []
            
            # Check current price freshness
            if stock_data.current_price:
                price_age_days = (today - stock_data.current_price.date).days
                if price_age_days == 0:
                    freshness_scores.append(100)  # Same day
                elif price_age_days <= 1:
                    freshness_scores.append(90)   # 1 day old
                elif price_age_days <= 3:
                    freshness_scores.append(70)   # Up to 3 days
                elif price_age_days <= 7:
                    freshness_scores.append(50)   # Up to 1 week
                else:
                    freshness_scores.append(20)   # Older than 1 week
                    issues.append(f"Current price data is {price_age_days} days old")
            else:
                freshness_scores.append(0)
                issues.append("No current price data available")
            
            # Check historical prices freshness
            if stock_data.historical_prices:
                latest_price = max(stock_data.historical_prices, key=lambda p: p.date)
                hist_age_days = (today - latest_price.date).days
                
                if hist_age_days <= 1:
                    freshness_scores.append(100)
                elif hist_age_days <= 3:
                    freshness_scores.append(80)
                elif hist_age_days <= 7:
                    freshness_scores.append(60)
                else:
                    freshness_scores.append(30)
                    issues.append(f"Historical price data is {hist_age_days} days old")
            else:
                freshness_scores.append(0)
            
            # Check financial statements freshness
            if stock_data.financial_statements:
                latest_statement = max(stock_data.financial_statements, key=lambda s: s.period_ending)
                stmt_age_days = (today - latest_statement.period_ending).days
                
                if stmt_age_days <= 90:    # Within quarter
                    freshness_scores.append(100)
                elif stmt_age_days <= 180: # Within 6 months
                    freshness_scores.append(80)
                elif stmt_age_days <= 365: # Within year
                    freshness_scores.append(60)
                elif stmt_age_days <= 730: # Within 2 years
                    freshness_scores.append(40)
                else:
                    freshness_scores.append(20)
                    issues.append(f"Latest financial statement is {stmt_age_days} days old")
            else:
                freshness_scores.append(0)
            
            # Check overall data freshness
            data_age_hours = (now - stock_data.last_updated).total_seconds() / 3600
            if data_age_hours <= 1:
                freshness_scores.append(100)
            elif data_age_hours <= 6:
                freshness_scores.append(90)
            elif data_age_hours <= 24:
                freshness_scores.append(70)
            elif data_age_hours <= 72:
                freshness_scores.append(50)
            else:
                freshness_scores.append(30)
                issues.append(f"Data was last updated {data_age_hours:.1f} hours ago")
            
            freshness_score = mean(freshness_scores) if freshness_scores else 0
            
            logger.debug(f"Freshness assessment: {freshness_score:.2f}%")
            return freshness_score
            
        except Exception as e:
            logger.error(f"Error assessing freshness: {e}")
            issues.append(f"Freshness assessment failed: {str(e)}")
            return 0
    
    async def _assess_accuracy(self, stock_data: StockData, issues: List[str]) -> float:
        """
        Assess data accuracy through validation and consistency checks.
        
        Args:
            stock_data: Stock data to assess
            issues: List to append issues to
            
        Returns:
            Accuracy score (0-100)
        """
        try:
            accuracy_checks = []
            
            # Price validation checks
            if stock_data.current_price:
                price_valid = await self._validate_price_data(stock_data.current_price, issues)
                accuracy_checks.append(price_valid)
            
            # Historical price validation
            if stock_data.historical_prices:
                valid_prices = 0
                total_prices = len(stock_data.historical_prices)
                
                for price in stock_data.historical_prices[:30]:  # Check last 30 days
                    if await self._validate_price_data(price, issues, silent=True):
                        valid_prices += 1
                
                price_accuracy = (valid_prices / total_prices * 100) if total_prices > 0 else 0
                accuracy_checks.append(price_accuracy)
                
                if price_accuracy < 90:
                    issues.append(f"Historical price validation issues: {valid_prices}/{total_prices} valid")
            
            # Financial statement validation
            if stock_data.financial_statements:
                valid_statements = 0
                total_statements = len(stock_data.financial_statements)
                
                for stmt in stock_data.financial_statements:
                    if await self._validate_financial_statement(stmt, issues, silent=True):
                        valid_statements += 1
                
                stmt_accuracy = (valid_statements / total_statements * 100) if total_statements > 0 else 0
                accuracy_checks.append(stmt_accuracy)
                
                if stmt_accuracy < 90:
                    issues.append(f"Financial statement validation issues: {valid_statements}/{total_statements} valid")
            
            # Company info validation
            if stock_data.company_info:
                company_valid = await self._validate_company_info(stock_data.company_info, issues)
                accuracy_checks.append(company_valid)
            
            accuracy_score = mean(accuracy_checks) if accuracy_checks else 0
            
            logger.debug(f"Accuracy assessment: {accuracy_score:.2f}%")
            return accuracy_score
            
        except Exception as e:
            logger.error(f"Error assessing accuracy: {e}")
            issues.append(f"Accuracy assessment failed: {str(e)}")
            return 0
    
    async def _assess_consistency(self, stock_data: StockData, issues: List[str]) -> float:
        """
        Assess data consistency across different components.
        
        Args:
            stock_data: Stock data to assess
            issues: List to append issues to
            
        Returns:
            Consistency score (0-100)
        """
        try:
            consistency_checks = []
            
            # Check symbol consistency
            symbols = set()
            if stock_data.company_info:
                symbols.add(stock_data.company_info.symbol)
            if stock_data.current_price:
                symbols.add(stock_data.current_price.symbol)
            if stock_data.historical_prices:
                symbols.update(p.symbol for p in stock_data.historical_prices[:5])
            if stock_data.financial_statements:
                symbols.update(s.symbol for s in stock_data.financial_statements[:3])
            
            if len(symbols) == 1:
                consistency_checks.append(100)
            else:
                consistency_checks.append(50)
                issues.append(f"Symbol inconsistency: {symbols}")
            
            # Check date consistency in historical prices
            if len(stock_data.historical_prices) > 1:
                dates = [p.date for p in stock_data.historical_prices]
                dates.sort()
                
                # Check for gaps in trading days (allowing for weekends)
                gaps = 0
                for i in range(1, min(len(dates), 30)):  # Check last 30 days
                    days_diff = (dates[i] - dates[i-1]).days
                    if days_diff > 3:  # More than 3 days gap (accounting for weekends)
                        gaps += 1
                
                if gaps == 0:
                    consistency_checks.append(100)
                elif gaps <= 2:
                    consistency_checks.append(80)
                else:
                    consistency_checks.append(60)
                    issues.append(f"Date gaps in historical prices: {gaps} gaps found")
            
            # Check financial statement date consistency
            if len(stock_data.financial_statements) > 1:
                stmt_dates = [s.period_ending for s in stock_data.financial_statements]
                stmt_dates.sort()
                
                # Check for reasonable intervals (quarterly or annual)
                intervals = []
                for i in range(1, len(stmt_dates)):
                    interval_days = (stmt_dates[i] - stmt_dates[i-1]).days
                    intervals.append(interval_days)
                
                if intervals:
                    avg_interval = mean(intervals)
                    if 80 <= avg_interval <= 100:  # Quarterly
                        consistency_checks.append(100)
                    elif 350 <= avg_interval <= 380:  # Annual
                        consistency_checks.append(100)
                    elif 160 <= avg_interval <= 200:  # Semi-annual
                        consistency_checks.append(90)
                    else:
                        consistency_checks.append(70)
                        issues.append(f"Irregular financial statement intervals: avg {avg_interval:.0f} days")
            
            # Check price consistency (no extreme outliers)
            if len(stock_data.historical_prices) > 10:
                prices = [float(p.close_price) for p in stock_data.historical_prices[:30] if p.close_price]
                
                if len(prices) > 5:
                    price_mean = mean(prices)
                    price_std = stdev(prices) if len(prices) > 1 else 0
                    
                    outliers = 0
                    for price in prices:
                        if abs(price - price_mean) > 3 * price_std:  # 3 sigma rule
                            outliers += 1
                    
                    outlier_ratio = outliers / len(prices)
                    if outlier_ratio <= 0.05:  # Less than 5% outliers
                        consistency_checks.append(100)
                    elif outlier_ratio <= 0.10:  # Less than 10% outliers
                        consistency_checks.append(80)
                    else:
                        consistency_checks.append(60)
                        issues.append(f"Price outliers detected: {outliers}/{len(prices)} ({outlier_ratio:.1%})")
            
            consistency_score = mean(consistency_checks) if consistency_checks else 0
            
            logger.debug(f"Consistency assessment: {consistency_score:.2f}%")
            return consistency_score
            
        except Exception as e:
            logger.error(f"Error assessing consistency: {e}")
            issues.append(f"Consistency assessment failed: {str(e)}")
            return 0
    
    async def _validate_price_data(self, price: StockPrice, issues: List[str], silent: bool = False) -> float:
        """Validate individual price data."""
        try:
            score = 100
            
            # Check for required fields
            if not price.close_price:
                if not silent:
                    issues.append(f"Missing close price for {price.date}")
                score -= 30
            
            # Check price relationships
            if all([price.open_price, price.high_price, price.low_price, price.close_price]):
                if not (price.low_price <= price.open_price <= price.high_price):
                    if not silent:
                        issues.append(f"Invalid price relationship on {price.date}: open not between high/low")
                    score -= 20
                
                if not (price.low_price <= price.close_price <= price.high_price):
                    if not silent:
                        issues.append(f"Invalid price relationship on {price.date}: close not between high/low")
                    score -= 20
            
            # Check for reasonable values
            if price.close_price and (price.close_price <= 0 or price.close_price > 100000):
                if not silent:
                    issues.append(f"Unreasonable close price on {price.date}: {price.close_price}")
                score -= 25
            
            # Check volume
            if price.volume is not None and price.volume < 0:
                if not silent:
                    issues.append(f"Negative volume on {price.date}")
                score -= 15
            
            return max(0, score)
            
        except Exception as e:
            if not silent:
                issues.append(f"Price validation error for {price.date}: {str(e)}")
            return 0
    
    async def _validate_financial_statement(self, stmt: FinancialStatement, issues: List[str], silent: bool = False) -> float:
        """Validate financial statement data."""
        try:
            score = 100
            
            # Check if at least one component exists
            if not any([stmt.income_statement, stmt.balance_sheet, stmt.cash_flow_statement]):
                if not silent:
                    issues.append(f"Empty financial statement for {stmt.period_ending}")
                return 0
            
            # Validate income statement
            if stmt.income_statement:
                if stmt.income_statement.revenue and stmt.income_statement.revenue < 0:
                    if not silent:
                        issues.append(f"Negative revenue in {stmt.period_ending}")
                    score -= 20
            
            # Validate balance sheet
            if stmt.balance_sheet:
                # Assets should equal liabilities + equity (with some tolerance)
                if all([stmt.balance_sheet.total_assets, stmt.balance_sheet.total_liabilities, stmt.balance_sheet.total_equity]):
                    assets = float(stmt.balance_sheet.total_assets)
                    liab_equity = float(stmt.balance_sheet.total_liabilities) + float(stmt.balance_sheet.total_equity)
                    
                    if abs(assets - liab_equity) / assets > 0.05:  # 5% tolerance
                        if not silent:
                            issues.append(f"Balance sheet doesn't balance for {stmt.period_ending}")
                        score -= 30
            
            return max(0, score)
            
        except Exception as e:
            if not silent:
                issues.append(f"Financial statement validation error for {stmt.period_ending}: {str(e)}")
            return 0
    
    async def _validate_company_info(self, company_info: CompanyInfo, issues: List[str]) -> float:
        """Validate company information."""
        try:
            score = 100
            
            # Check for required fields
            if not company_info.company_name:
                issues.append("Missing company name")
                score -= 30
            
            # Check for reasonable values
            if company_info.market_cap and company_info.market_cap <= 0:
                issues.append("Invalid market cap")
                score -= 20
            
            if company_info.trailing_pe and (company_info.trailing_pe <= 0 or company_info.trailing_pe > 1000):
                issues.append(f"Unreasonable P/E ratio: {company_info.trailing_pe}")
                score -= 15
            
            if company_info.beta and abs(company_info.beta) > 5:
                issues.append(f"Extreme beta value: {company_info.beta}")
                score -= 10
            
            return max(0, score)
            
        except Exception as e:
            issues.append(f"Company info validation error: {str(e)}")
            return 0
    
    def get_quality_grade(self, quality_score: float) -> str:
        """
        Get quality grade based on score.
        
        Args:
            quality_score: Quality score (0-100)
            
        Returns:
            Quality grade string
        """
        if quality_score >= self.quality_thresholds['excellent']:
            return 'A'
        elif quality_score >= self.quality_thresholds['good']:
            return 'B'
        elif quality_score >= self.quality_thresholds['fair']:
            return 'C'
        elif quality_score >= self.quality_thresholds['poor']:
            return 'D'
        else:
            return 'F'
    
    async def generate_quality_report(self, quality_metrics: DataQualityMetrics) -> Dict[str, Any]:
        """
        Generate comprehensive quality report.
        
        Args:
            quality_metrics: Quality metrics to report on
            
        Returns:
            Dictionary with quality report
        """
        try:
            grade = self.get_quality_grade(float(quality_metrics.quality_score))
            
            return {
                'symbol': quality_metrics.symbol,
                'data_source': quality_metrics.data_source,
                'overall_score': float(quality_metrics.quality_score),
                'overall_grade': grade,
                'scores': {
                    'completeness': float(quality_metrics.completeness_score),
                    'freshness': float(quality_metrics.freshness_score),
                    'accuracy': float(quality_metrics.accuracy_score)
                },
                'assessment_date': quality_metrics.last_assessed.isoformat(),
                'issues_count': len(quality_metrics.issues),
                'issues': quality_metrics.issues,
                'recommendations': self._generate_recommendations(quality_metrics),
                'quality_level': self._get_quality_level(float(quality_metrics.quality_score))
            }
            
        except Exception as e:
            logger.error(f"Error generating quality report: {e}")
            return {
                'error': str(e),
                'symbol': quality_metrics.symbol,
                'overall_score': 0,
                'overall_grade': 'F'
            }
    
    def _generate_recommendations(self, quality_metrics: DataQualityMetrics) -> List[str]:
        """Generate recommendations based on quality metrics."""
        recommendations = []
        
        if float(quality_metrics.completeness_score) < 80:
            recommendations.append("Improve data completeness by fetching missing fields")
        
        if float(quality_metrics.freshness_score) < 70:
            recommendations.append("Update data more frequently to improve freshness")
        
        if float(quality_metrics.accuracy_score) < 80:
            recommendations.append("Implement additional data validation checks")
        
        if len(quality_metrics.issues) > 5:
            recommendations.append("Address data quality issues systematically")
        
        if float(quality_metrics.quality_score) < 60:
            recommendations.append("Consider using alternative data sources")
        
        return recommendations
    
    def _get_quality_level(self, score: float) -> str:
        """Get quality level description."""
        if score >= 90:
            return "Excellent - Data is highly reliable and complete"
        elif score >= 75:
            return "Good - Data is reliable with minor issues"
        elif score >= 60:
            return "Fair - Data is usable but has some quality concerns"
        elif score >= 40:
            return "Poor - Data has significant quality issues"
        else:
            return "Very Poor - Data quality is unacceptable for analysis"