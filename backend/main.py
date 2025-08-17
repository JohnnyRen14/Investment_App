"""
Investment App - Main FastAPI Application
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Create FastAPI app
app = FastAPI(
    title="Investment App API",
    description="DCF Analysis Platform API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "message": "Investment App API is running"}

# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Investment App API",
        "version": "1.0.0",
        "docs": "/docs"
    }

# Module API routers will be added here by each team
# Example:
# from app.api.auth import router as auth_router
# from app.api.dcf import router as dcf_router
# from app.api.portfolio import router as portfolio_router
# from app.api.data import router as data_router
# from app.api.reports import router as reports_router

# app.include_router(auth_router, prefix="/api/v1/auth", tags=["authentication"])
# app.include_router(dcf_router, prefix="/api/v1/dcf", tags=["dcf-analysis"])
# app.include_router(portfolio_router, prefix="/api/v1/portfolios", tags=["portfolios"])
# app.include_router(data_router, prefix="/api/v1/data", tags=["financial-data"])
# app.include_router(reports_router, prefix="/api/v1/reports", tags=["reports"])

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )