# Investment App - Complete Architecture Specification v1.0

## ðŸ“Š Project Overview

**Investment Analysis Platform** - A comprehensive web application that provides sophisticated DCF (Discounted Cash Flow) analysis with multi-scenario modeling, professional visualizations, and portfolio management capabilities.

### Core Value Proposition
- **Multi-Scenario DCF Analysis**: Best case, base case, and worst case projections
- **Professional Visualizations**: Interactive charts and sensitivity analysis
- **Portfolio Management**: Save and track investment analyses
- **Collaborative Features**: Share analysis reports with stakeholders
- **Enterprise-Grade Security**: Robust authentication and rate limiting

## ðŸ—ï¸ System Architecture

### Technology Stack

#### Frontend Layer
- **Framework**: Next.js 14+ with TypeScript
- **Styling**: Tailwind CSS for responsive design
- **State Management**: Zustand for application state
- **Charts & Visualization**: Chart.js/Recharts for financial data
- **Forms**: React Hook Form with validation
- **Deployment**: Vercel for optimal performance

#### Backend Layer
- **Framework**: Python FastAPI with Pydantic validation
- **Database**: PostgreSQL 15+ for production data persistence
- **Authentication**: JWT with bcrypt password hashing
- **Rate Limiting**: User-based request throttling
- **Background Tasks**: Async processing for heavy calculations
- **Deployment**: Railway/Render PaaS for scalability

#### External Integrations
- **Primary Data Source**: Yahoo Finance API (free tier)
- **Secondary Data Source**: Alpha Vantage API (free tier, 500 calls/day)
- **Real-time Updates**: WebSocket connections for live data

## ðŸ§® DCF Analysis Engine

### Multi-Scenario Calculation Model

The system implements a sophisticated DCF model with three distinct scenarios to provide comprehensive valuation analysis:

#### Scenario Definitions
```python
SCENARIO_PARAMETERS = {
    'worst_case': {
        'revenue_growth_rate': 0.02,      # 2% conservative growth
        'margin_compression': 0.95,       # 5% margin decline
        'discount_rate': 0.12,            # Higher risk premium
        'terminal_growth_rate': 0.015,    # 1.5% terminal growth
        'confidence_level': 0.8           # 80% confidence
    },
    'base_case': {
        'revenue_growth_rate': 0.05,      # 5% moderate growth
        'margin_stability': 1.0,          # Stable margins
        'discount_rate': 0.10,            # Standard WACC
        'terminal_growth_rate': 0.025,    # 2.5% terminal growth
        'confidence_level': 0.9           # 90% confidence
    },
    'best_case': {
        'revenue_growth_rate': 0.08,      # 8% optimistic growth
        'margin_expansion': 1.05,         # 5% margin improvement
        'discount_rate': 0.08,            # Lower risk premium
        'terminal_growth_rate': 0.035,    # 3.5% terminal growth
        'confidence_level': 0.95          # 95% confidence
    }
}
```

#### Core DCF Calculation Engine
```python
class DCFAnalysisEngine:
    def __init__(self):
        self.projection_years = 5
        self.scenarios = SCENARIO_PARAMETERS
    
    def calculate_comprehensive_dcf(self, ticker: str) -> DCFAnalysisResult:
        """
        Perform complete DCF analysis across all scenarios
        """
        # 1. Data Collection and Validation
        financial_data = self.collect_financial_data(ticker)
        self.validate_data_quality(financial_data)
        
        # 2. Multi-Scenario Analysis
        scenario_results = {}
        for scenario_name, parameters in self.scenarios.items():
            scenario_results[scenario_name] = self.calculate_scenario_dcf(
                financial_data, parameters
            )
        
        # 3. Sensitivity Analysis
        sensitivity_data = self.generate_sensitivity_matrix(financial_data)
        
        # 4. Comparative Analysis
        comparison_metrics = self.calculate_scenario_comparison(scenario_results)
        
        return DCFAnalysisResult(
            ticker=ticker,
            scenarios=scenario_results,
            sensitivity_analysis=sensitivity_data,
            comparison_metrics=comparison_metrics,
            calculation_timestamp=datetime.utcnow()
        )
    
    def calculate_scenario_dcf(self, data: dict, parameters: dict) -> ScenarioResult:
        """
        Calculate DCF for a specific scenario with given parameters
        """
        # Revenue Projections
        projected_revenues = self.project_revenues(data, parameters)
        
        # Free Cash Flow Calculations
        projected_fcf = self.calculate_free_cash_flows(
            projected_revenues, data, parameters
        )
        
        # Terminal Value Calculation
        terminal_value = self.calculate_terminal_value(
            projected_fcf[-1], parameters['terminal_growth_rate'], 
            parameters['discount_rate']
        )
        
        # Present Value Calculation
        present_values = self.discount_to_present_value(
            projected_fcf, terminal_value, parameters['discount_rate']
        )
        
        # Per-Share Intrinsic Value
        intrinsic_value_per_share = sum(present_values) / data['shares_outstanding']
        
        return ScenarioResult(
            intrinsic_value=intrinsic_value_per_share,
            projected_cash_flows=projected_fcf,
            terminal_value=terminal_value,
            discount_rate=parameters['discount_rate'],
            assumptions=parameters,
            upside_potential=self.calculate_upside_potential(
                intrinsic_value_per_share, data['current_price']
            )
        )
```

### Financial Data Requirements

#### Essential Metrics
- **Income Statement**: Revenue, Operating Income, Net Income (5-year history)
- **Cash Flow Statement**: Operating Cash Flow, Capital Expenditures, Free Cash Flow
- **Balance Sheet**: Total Debt, Cash and Equivalents, Shares Outstanding
- **Market Data**: Current Stock Price, Market Capitalization, Beta
- **Industry Metrics**: Industry Average P/E, Sector Growth Rates

#### Data Validation Framework
```python
class FinancialDataValidator:
    def validate_data_completeness(self, data: dict) -> ValidationResult:
        """Ensure all required financial metrics are present and valid"""
        required_fields = [
            'revenue_history', 'operating_cash_flow', 'capex',
            'current_price', 'shares_outstanding', 'total_debt'
        ]
        
        missing_fields = [field for field in required_fields if not data.get(field)]
        
        if missing_fields:
            return ValidationResult(
                is_valid=False,
                missing_fields=missing_fields,
                confidence_score=0.0
            )
        
        # Data quality scoring
        quality_score = self.calculate_data_quality_score(data)
        
        return ValidationResult(
            is_valid=quality_score > 0.7,
            confidence_score=quality_score,
            data_age=self.calculate_data_freshness(data)
        )
```

## ðŸ“Š Visualization Components

### Interactive DCF Flow Chart
```typescript
interface DCFChartProps {
  scenarioData: ScenarioResult;
  selectedScenario: ScenarioType;
}

const DCFFlowChart: React.FC<DCFChartProps> = ({ scenarioData, selectedScenario }) => {
  const chartConfiguration = {
    type: 'bar' as const,
    data: {
      labels: ['Year 1', 'Year 2', 'Year 3', 'Year 4', 'Year 5', 'Terminal Value'],
      datasets: [{
        label: 'Projected Free Cash Flow ($M)',
        data: scenarioData.projected_cash_flows,
        backgroundColor: [
          'rgba(59, 130, 246, 0.8)',   // Year 1-5
          'rgba(16, 185, 129, 0.8)',   // Terminal
        ],
        borderColor: [
          'rgb(59, 130, 246)',
          'rgb(16, 185, 129)',
        ],
        borderWidth: 2
      }]
    },
    options: {
      responsive: true,
      plugins: {
        title: {
          display: true,
          text: `DCF Analysis - ${selectedScenario.replace('_', ' ').toUpperCase()} Scenario`
        },
        legend: {
          display: true,
          position: 'top' as const
        }
      },
      scales: {
        y: {
          beginAtZero: true,
          title: {
            display: true,
            text: 'Cash Flow ($ Millions)'
          }
        }
      }
    }
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg">
      <Bar data={chartConfiguration.data} options={chartConfiguration.options} />
    </div>
  );
};
```

### Sensitivity Analysis Heatmap
```typescript
interface SensitivityHeatmapProps {
  sensitivityData: SensitivityMatrix;
  currentWACC: number;
  currentGrowthRate: number;
}

const SensitivityHeatmap: React.FC<SensitivityHeatmapProps> = ({ 
  sensitivityData, 
  currentWACC, 
  currentGrowthRate 
}) => {
  const getHeatmapColor = (value: number, currentPrice: number): string => {
    const ratio = value / currentPrice;
    if (ratio > 1.2) return 'bg-green-500 text-white';
    if (ratio > 1.1) return 'bg-green-300 text-gray-800';
    if (ratio > 0.9) return 'bg-yellow-300 text-gray-800';
    if (ratio > 0.8) return 'bg-orange-300 text-gray-800';
    return 'bg-red-500 text-white';
  };

  return (
    <div className="bg-white p-6 rounded-lg shadow-lg">
      <h3 className="text-lg font-semibold mb-4">
        Sensitivity Analysis: WACC vs Terminal Growth Rate
      </h3>
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr>
              <th className="px-3 py-2 text-xs font-medium text-gray-500">WACC \ Growth</th>
              {sensitivityData.growth_rates.map(rate => (
                <th key={rate} className="px-3 py-2 text-xs font-medium text-gray-500">
                  {(rate * 100).toFixed(1)}%
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sensitivityData.wacc_rates.map((wacc, i) => (
              <tr key={wacc}>
                <td className="px-3 py-2 text-xs font-medium text-gray-500">
                  {(wacc * 100).toFixed(1)}%
                </td>
                {sensitivityData.value_matrix[i].map((value, j) => (
                  <td
                    key={j}
                    className={`px-3 py-2 text-xs text-center ${getHeatmapColor(value, sensitivityData.current_price)}`}
                  >
                    ${value.toFixed(0)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
```
## ??? Database Architecture

### PostgreSQL Schema Design
```sql
-- Users and Authentication
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true
);

-- Portfolio Management
CREATE TABLE portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- DCF Analysis Storage
CREATE TABLE dcf_analyses (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id),
    ticker VARCHAR(10) NOT NULL,
    scenario_type VARCHAR(20) NOT NULL,
    intrinsic_value DECIMAL(10,2),
    current_price DECIMAL(10,2),
    upside_percentage DECIMAL(5,2),
    assumptions JSONB,
    calculation_data JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Shared Reports System
CREATE TABLE shared_reports (
    id SERIAL PRIMARY KEY,
    share_token VARCHAR(64) UNIQUE NOT NULL,
    user_id INTEGER REFERENCES users(id),
    dcf_analysis_id INTEGER REFERENCES dcf_analyses(id),
    ticker VARCHAR(10) NOT NULL,
    title VARCHAR(255),
    expires_at TIMESTAMP,
    view_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## ?? Security Implementation

### Authentication System
```python
class AuthenticationService:
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.algorithm = "HS256"
    
    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=30)
        to_encode.update({"exp": expire})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
```

## ?? API Endpoints

### Core DCF Analysis
```python
@app.get("/api/v1/stocks/{ticker}/dcf/scenarios")
async def get_dcf_scenarios(ticker: str, user: User = Depends(get_current_user)):
    dcf_engine = DCFAnalysisEngine()
    analysis_result = await dcf_engine.calculate_comprehensive_dcf(ticker)
    return analysis_result

@app.post("/api/v1/portfolios")
async def create_portfolio(portfolio_data: PortfolioCreate, user: User = Depends(get_current_user)):
    portfolio_service = PortfolioService()
    return await portfolio_service.create_portfolio(user.id, portfolio_data)

@app.post("/api/v1/reports/share")
async def create_shared_report(share_request: ShareReportRequest, user: User = Depends(get_current_user)):
    sharing_service = ReportSharingService()
    return await sharing_service.create_shareable_report(user.id, share_request.dcf_analysis_id)
```

## ?? Project Structure

```
Investment_App/
+-- frontend/                    # Next.js Application
¦   +-- src/
¦   ¦   +-- components/         # React Components
¦   ¦   ¦   +-- dcf/           # DCF Analysis Components
¦   ¦   ¦   +-- portfolio/     # Portfolio Management
¦   ¦   ¦   +-- charts/        # Visualization Components
¦   ¦   ¦   +-- shared/        # Shared UI Components
¦   ¦   +-- pages/             # Next.js Pages
¦   ¦   +-- hooks/             # Custom React Hooks
¦   ¦   +-- utils/             # Utility Functions
¦   ¦   +-- types/             # TypeScript Definitions
¦   ¦   +-- store/             # State Management
¦   +-- public/                # Static Assets
¦   +-- package.json
¦
+-- backend/                    # FastAPI Application
¦   +-- app/
¦   ¦   +-- api/               # API Routes
¦   ¦   +-- core/              # Core Business Logic
¦   ¦   +-- models/            # Database Models
¦   ¦   +-- services/          # Business Services
¦   ¦   +-- utils/             # Utility Functions
¦   +-- tests/                 # Test Suite
¦   +-- requirements.txt
¦
+-- database/                   # Database Scripts
¦   +-- migrations/            # Database Migrations
¦   +-- seeds/                 # Sample Data
¦
+-- docs/                      # Documentation
    +-- api/                   # API Documentation
    +-- deployment/            # Deployment Guides
```

## ?? Deployment Strategy

### Development Environment
- **Frontend**: Next.js development server with hot reload
- **Backend**: FastAPI with auto-reload enabled
- **Database**: PostgreSQL local instance
- **Environment**: Docker Compose for service orchestration

### Production Environment
- **Frontend**: Vercel deployment with automatic CI/CD
- **Backend**: Railway/Render PaaS deployment
- **Database**: Managed PostgreSQL service
- **Monitoring**: Application performance monitoring and logging

## ?? Performance Metrics

### Target Performance
- **DCF Calculation**: <2 seconds per analysis
- **API Response Time**: <500ms for cached data
- **Page Load Time**: <1 second initial load
- **Database Queries**: <100ms average response time

### Scalability Targets
- **Concurrent Users**: 1,000+ simultaneous users
- **Daily Analyses**: 10,000+ DCF calculations
- **Data Storage**: 100GB+ financial data cache
- **Uptime**: 99.9% availability SLA

## ?? Success Metrics

### User Engagement
- **Monthly Active Users**: 70%+ retention rate
- **Feature Adoption**: 80%+ users utilize scenario analysis
- **Report Sharing**: 25%+ users share analysis reports
- **Portfolio Usage**: 60%+ users maintain active portfolios

### Technical Performance
- **System Reliability**: 99.9% uptime
- **Data Accuracy**: 95%+ user satisfaction with analysis quality
- **Response Times**: 95th percentile <1 second
- **Error Rate**: <0.1% application errors

### Business Metrics
- **User Growth**: 20%+ month-over-month growth
- **Engagement**: 15+ minutes average session duration
- **Conversion**: 10%+ free-to-premium conversion rate
- **Support**: <24 hour response time for issues

---

## ?? Implementation Roadmap

### Phase 1: Core Foundation (Weeks 1-6)
- ? Basic DCF calculation engine
- ? User authentication system
- ? PostgreSQL database setup
- ? Essential API endpoints
- ? Basic frontend interface

### Phase 2: Enhanced Features (Weeks 7-12)
- ? Multi-scenario DCF analysis
- ? Interactive visualizations
- ? Portfolio management system
- ? Report sharing functionality
- ? Security hardening

### Phase 3: Scale & Optimize (Weeks 13-18)
- ? Performance optimization
- ? Advanced analytics
- ? Mobile responsiveness
- ? Comprehensive monitoring
- ? Production deployment

This architecture provides a comprehensive foundation for building a professional-grade investment analysis platform with robust DCF modeling, portfolio management, and collaborative features.
