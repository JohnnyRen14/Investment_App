# User Module - Development Setup Guide

## 📋 Module Overview
**Responsibility**: User authentication, authorization, profile management, and session handling.

## 🎯 What's Already Set Up
- ✅ Project structure with backend/frontend folders
- ✅ FastAPI main application (`backend/main.py`)
- ✅ Next.js configuration (`frontend/next.config.js`, `frontend/tailwind.config.js`)
- ✅ Docker configuration
- ✅ Database structure defined
- ✅ Module specification (`USER_MODULE_CLAUDE.md`)

## 🚀 Your Development Tasks

### 1. Backend Implementation
**Location**: `backend/app/api/auth/`

**Files to Create**:
```
backend/app/api/auth/
├── __init__.py
├── routes.py          # Authentication endpoints
├── dependencies.py    # Auth dependencies (get_current_user, etc.)
├── schemas.py         # Pydantic models
└── services.py        # Authentication business logic
```

**Key Components to Implement**:
- `AuthenticationService` class (from specification)
- `UserService` class (from specification)
- JWT token generation and validation
- Password hashing with bcrypt
- User registration and login endpoints

### 2. Database Models
**Location**: `backend/app/models/`

**Files to Create**:
```
backend/app/models/
├── __init__.py
├── user.py           # User SQLAlchemy models
└── base.py           # Base model class
```

**Models to Implement**:
- `User` model
- `UserPreferences` model
- `PasswordResetToken` model
- `UserSession` model

### 3. Frontend Components
**Location**: `frontend/src/components/auth/`

**Components to Create**:
```
frontend/src/components/auth/
├── LoginForm.tsx
├── RegisterForm.tsx
├── PasswordReset.tsx
├── UserProfile.tsx
└── AuthProvider.tsx
```

## 🔧 Development Environment Setup

### Backend Setup
1. **Install Dependencies**:
```bash
cd backend
pip install fastapi uvicorn sqlalchemy asyncpg python-jose[cryptography] passlib[bcrypt]
```

2. **Create Database Models**:
```python
# backend/app/models/user.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.sql import func
from .base import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    first_name = Column(String(100))
    last_name = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True))
    is_active = Column(Boolean, default=True)
    email_verified = Column(Boolean, default=False)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True))
```

3. **Create Authentication Service**:
```python
# backend/app/api/auth/services.py
from datetime import datetime, timedelta
import bcrypt
import jwt
from typing import Optional

class AuthenticationService:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = 30
    
    def hash_password(self, password: str) -> str:
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    def create_access_token(self, data: dict) -> str:
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
```

### Frontend Setup
1. **Install Dependencies**:
```bash
cd frontend
npm install @hookform/resolvers react-hook-form zod axios js-cookie @types/js-cookie
```

2. **Create Auth Context**:
```typescript
// frontend/src/components/auth/AuthProvider.tsx
import React, { createContext, useContext, useState, useEffect } from 'react';

interface User {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
}

interface AuthContextType {
  user: User | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  isLoading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
```

## 🧪 Testing Setup

### Backend Tests
**Location**: `backend/tests/test_auth.py`

```python
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_register_user():
    response = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe"
    })
    assert response.status_code == 200
    assert "id" in response.json()

def test_login_user():
    # First register
    client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "password123",
        "first_name": "John",
        "last_name": "Doe"
    })
    
    # Then login
    response = client.post("/api/v1/auth/login", json={
        "email": "test@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    assert "access_token" in response.json()
```

### Frontend Tests
**Location**: `frontend/src/components/auth/__tests__/LoginForm.test.tsx`

```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import LoginForm from '../LoginForm';

test('renders login form', () => {
  render(<LoginForm />);
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
  expect(screen.getByRole('button', { name: /login/i })).toBeInTheDocument();
});
```

## 📚 Integration Points

### With Other Modules
- **Portfolio Module**: Provides `get_current_user` dependency
- **DCF Module**: Provides user context for calculations
- **Data Module**: No direct integration
- **Report Module**: Provides user authentication for reports

### API Endpoints to Implement
```
POST /api/v1/auth/register     # User registration
POST /api/v1/auth/login        # User login
POST /api/v1/auth/refresh      # Token refresh
GET  /api/v1/auth/me           # Get current user
PUT  /api/v1/auth/profile      # Update profile
POST /api/v1/auth/change-password  # Change password
POST /api/v1/auth/forgot-password  # Password reset
```

## 🔗 Dependencies for Other Modules
```python
# This will be used by other modules
async def get_current_user(
    token: str = Depends(security),
    auth_service: AuthenticationService = Depends(get_auth_service)
) -> User:
    # Implementation here
    pass

def get_user_id(current_user: User = Depends(get_current_user)) -> int:
    return current_user.id
```

## 📋 Checklist
- [ ] Create database models
- [ ] Implement authentication service
- [ ] Create API endpoints
- [ ] Build frontend components
- [ ] Write unit tests
- [ ] Write integration tests
- [ ] Test with other modules
- [ ] Update main.py to include auth router
- [ ] Document API endpoints

## 🚨 Important Notes
- Use environment variables for JWT secrets
- Implement proper password validation
- Add rate limiting for login attempts
- Ensure CORS is properly configured
- Test token expiration handling
- Implement proper error messages

## 📞 Need Help?
- Check `USER_MODULE_CLAUDE.md` for detailed specifications
- Review the main project `README.md` for overall setup
- Test your endpoints using `/docs` (FastAPI auto-docs)