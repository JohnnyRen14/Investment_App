# Investment App - DCF Analysis Platform

A comprehensive web application for sophisticated DCF (Discounted Cash Flow) analysis with multi-scenario modeling, professional visualizations, and portfolio management capabilities.

## 🎯 Project Overview

**Core Features:**
- Multi-scenario DCF analysis (worst/base/best case)
- Interactive financial visualizations and charts
- Portfolio management and watchlists
- Professional PDF report generation
- Shareable analysis reports
- Real-time financial data integration

## 🏗️ Architecture

### Technology Stack
- **Frontend**: Next.js 14+ with TypeScript, Tailwind CSS
- **Backend**: Python FastAPI with Pydantic validation
- **Database**: PostgreSQL 15+ with Redis caching
- **Charts**: Plotly.js for interactive visualizations
- **Reports**: ReportLab for PDF generation

### Module Structure
```
Investment_App/
├── frontend/           # Next.js application
├── backend/           # FastAPI application
├── UserModule/        # Authentication & user management
├── PortfolioModule/   # Portfolio & watchlist management
├── DcfModule/         # DCF calculation engine
├── DataModule/        # Data fetching & validation
├── ReportModule/      # Charts & report generation
├── database/          # Database scripts & migrations
├── tests/            # Test suites
├── docker/           # Docker configuration
└── docs/             # Documentation
```

## 🚀 Quick Start

### Prerequisites
- Node.js 18+
- Python 3.9+
- PostgreSQL 14+
- Redis 6+

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd Investment_App
```

2. **Backend Setup**
```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
# Configure your environment variables
```

3. **Frontend Setup**
```bash
cd frontend
npm install
cp .env.local.example .env.local
# Configure your environment variables
```

4. **Database Setup**
```bash
# Run database migrations
cd database
python run_migrations.py
```

5. **Start Development Servers**
```bash
# Backend (Terminal 1)
cd backend
uvicorn app.main:app --reload --port 8000

# Frontend (Terminal 2)
cd frontend
npm run dev
```

## 📚 Documentation

- [Project Architecture](./CLAUDE.md)
- [User Module](./UserModule/USER_MODULE_CLAUDE.md)
- [Portfolio Module](./PortfolioModule/PORTFOLIO_MODULE_CLAUDE.md)
- [DCF Module](./DcfModule/DCF_MODULE_CLAUDE.md)
- [Data Module](./DataModule/DATA_MODULE_CLAUDE.md)
- [Report Module](./ReportModule/REPORT_MODULE_CLAUDE.md)

## 🧪 Testing

```bash
# Backend tests
cd backend
pytest

# Frontend tests
cd frontend
npm test

# E2E tests
cd tests/e2e
npm run test:e2e
```

## 🐳 Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up --build
```

## 📊 Features

### DCF Analysis
- Multi-scenario modeling (conservative, base, optimistic)
- Sensitivity analysis with interactive heatmaps
- WACC calculation with industry benchmarks
- Terminal value modeling
- Data quality assessment

### Portfolio Management
- Multiple portfolio support
- Watchlist functionality
- Performance tracking
- Asset allocation analysis

### Reporting
- Interactive charts and visualizations
- Professional PDF reports
- Shareable report links
- Export capabilities (PNG, PDF, Excel)

## 🔧 Development

### Module Development
Each module is designed for independent development:
- Clear API interfaces between modules
- Comprehensive testing strategies
- Detailed technical specifications
- Independent deployment capability

### Code Standards
- TypeScript for frontend type safety
- Python type hints for backend
- Comprehensive test coverage (>80%)
- ESLint + Prettier for code formatting
- Pre-commit hooks for quality assurance

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This application is for educational and informational purposes only. It should not be considered as investment advice. Please consult with qualified financial advisors before making investment decisions.