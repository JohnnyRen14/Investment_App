# User Module - Technical Specification

## 📋 Module Overview
**Purpose**: Handle all user-related functionality including authentication, authorization, user profiles, and session management.

**Core Responsibility**: Secure user management system that provides identity services to all other modules.

## 🎯 Module Scope & Boundaries

### ✅ What This Module Handles:
- User registration and login
- Password management and security
- JWT token generation and validation
- User profile management
- Session handling
- Account settings and preferences
- Password reset functionality
- User activity logging

### ❌ What This Module Does NOT Handle:
- Portfolio data (handled by Portfolio Module)
- DCF calculations (handled by DCF Module)
- Financial data fetching (handled by Data Module)
- Report generation (handled by Report Module)

## 🏗️ Technical Architecture

### Database Schema
```sql
-- Primary user table
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    is_active BOOLEAN DEFAULT true,
    email_verified BOOLEAN DEFAULT false,
    failed_login_attempts INTEGER DEFAULT 0,
    locked_until TIMESTAMP NULL
);

-- User preferences and settings
CREATE TABLE user_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    theme VARCHAR(20) DEFAULT 'light',
    currency VARCHAR(3) DEFAULT 'USD',
    timezone VARCHAR(50) DEFAULT 'UTC',
    email_notifications BOOLEAN DEFAULT true,
    dcf_default_scenario VARCHAR(20) DEFAULT 'base_case',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Password reset tokens
CREATE TABLE password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    used BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User sessions for tracking
CREATE TABLE user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    session_token VARCHAR(255) UNIQUE NOT NULL,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT true
);
```

### Core Classes & Services

#### Authentication Service
```python
from datetime import datetime, timedelta
import bcrypt
import jwt
from typing import Optional

class AuthenticationService:
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.access_token_expire_minutes = 30
        self.refresh_token_expire_days = 7
    
    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(
            plain_password.encode('utf-8'), 
            hashed_password.encode('utf-8')
        )
    
    def create_access_token(self, data: dict) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def create_refresh_token(self, data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=self.refresh_token_expire_days)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[dict]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.JWTError:
            return None
```

#### User Service
```python
from typing import Optional, List
from pydantic import BaseModel, EmailStr

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    created_at: datetime
    last_login: Optional[datetime]
    is_active: bool

class UserService:
    def __init__(self, db_session, auth_service: AuthenticationService):
        self.db = db_session
        self.auth = auth_service
    
    async def create_user(self, user_data: UserCreate) -> UserResponse:
        """Create new user account"""
        # Check if user already exists
        existing_user = await self.get_user_by_email(user_data.email)
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Hash password
        hashed_password = self.auth.hash_password(user_data.password)
        
        # Create user record
        user = User(
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
        
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        
        # Create default preferences
        await self.create_default_preferences(user.id)
        
        return UserResponse.from_orm(user)
    
    async def authenticate_user(self, email: str, password: str) -> Optional[UserResponse]:
        """Authenticate user credentials"""
        user = await self.get_user_by_email(email)
        if not user:
            return None
        
        if not self.auth.verify_password(password, user.password_hash):
            await self.increment_failed_login_attempts(user.id)
            return None
        
        # Reset failed attempts and update last login
        await self.reset_failed_login_attempts(user.id)
        await self.update_last_login(user.id)
        
        return UserResponse.from_orm(user)
    
    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        return await self.db.get(User, user_id)
    
    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()
    
    async def update_user(self, user_id: int, user_data: UserUpdate) -> UserResponse:
        """Update user information"""
        user = await self.get_user_by_id(user_id)
        if not user:
            raise ValueError("User not found")
        
        for field, value in user_data.dict(exclude_unset=True).items():
            setattr(user, field, value)
        
        user.updated_at = datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(user)
        
        return UserResponse.from_orm(user)
```

## 🔌 API Endpoints

### Authentication Endpoints
```python
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
security = HTTPBearer()

@router.post("/register", response_model=UserResponse)
async def register_user(
    user_data: UserCreate,
    user_service: UserService = Depends(get_user_service)
):
    """Register new user account"""
    try:
        user = await user_service.create_user(user_data)
        return user
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.post("/login")
async def login_user(
    credentials: UserLogin,
    user_service: UserService = Depends(get_user_service),
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """Authenticate user and return tokens"""
    user = await user_service.authenticate_user(
        credentials.email, 
        credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = auth_service.create_access_token({"sub": str(user.id)})
    refresh_token = auth_service.create_refresh_token({"sub": str(user.id)})
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "user": user
    }

@router.post("/refresh")
async def refresh_token(
    refresh_token: str,
    auth_service: AuthenticationService = Depends(get_auth_service)
):
    """Refresh access token using refresh token"""
    payload = auth_service.verify_token(refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    new_access_token = auth_service.create_access_token({"sub": payload["sub"]})
    return {"access_token": new_access_token, "token_type": "bearer"}

@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: User = Depends(get_current_user)
):
    """Get current user information"""
    return UserResponse.from_orm(current_user)
```

### User Management Endpoints
```python
@router.put("/profile", response_model=UserResponse)
async def update_profile(
    user_data: UserUpdate,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Update user profile"""
    return await user_service.update_user(current_user.id, user_data)

@router.post("/change-password")
async def change_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    user_service: UserService = Depends(get_user_service)
):
    """Change user password"""
    if not user_service.auth.verify_password(
        password_data.current_password, 
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    await user_service.update_password(current_user.id, password_data.new_password)
    return {"message": "Password updated successfully"}
```

## 🔗 Module Interfaces

### Outgoing Dependencies (What this module needs from others)
```python
# No direct dependencies on other modules
# This module is foundational and provides services to others
```

### Incoming Dependencies (What other modules need from this module)
```python
# Authentication dependency for all protected endpoints
async def get_current_user(
    token: str = Depends(security),
    auth_service: AuthenticationService = Depends(get_auth_service),
    user_service: UserService = Depends(get_user_service)
) -> User:
    """Dependency to get current authenticated user"""
    payload = auth_service.verify_token(token.credentials)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = await user_service.get_user_by_id(int(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive"
        )
    
    return user

# User ID provider for other modules
def get_user_id(current_user: User = Depends(get_current_user)) -> int:
    """Get current user ID for other modules"""
    return current_user.id
```

## 🧪 Testing Strategy

### Unit Tests
```python
import pytest
from unittest.mock import Mock, patch

class TestAuthenticationService:
    def test_hash_password(self):
        auth_service = AuthenticationService("test_secret")
        password = "test_password"
        hashed = auth_service.hash_password(password)
        
        assert hashed != password
        assert auth_service.verify_password(password, hashed)
    
    def test_create_access_token(self):
        auth_service = AuthenticationService("test_secret")
        data = {"sub": "123"}
        token = auth_service.create_access_token(data)
        
        assert isinstance(token, str)
        payload = auth_service.verify_token(token)
        assert payload["sub"] == "123"
        assert payload["type"] == "access"

class TestUserService:
    @pytest.mark.asyncio
    async def test_create_user(self):
        mock_db = Mock()
        auth_service = AuthenticationService("test_secret")
        user_service = UserService(mock_db, auth_service)
        
        user_data = UserCreate(
            email="test@example.com",
            password="password123",
            first_name="John",
            last_name="Doe"
        )
        
        with patch.object(user_service, 'get_user_by_email', return_value=None):
            user = await user_service.create_user(user_data)
            assert user.email == "test@example.com"
            assert user.first_name == "John"
```

### Integration Tests
```python
import pytest
from fastapi.testclient import TestClient

class TestAuthEndpoints:
    def test_register_user(self, client: TestClient):
        response = client.post("/api/v1/auth/register", json={
            "email": "test@example.com",
            "password": "password123",
            "first_name": "John",
            "last_name": "Doe"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert "id" in data
    
    def test_login_user(self, client: TestClient):
        # First register a user
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
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
```

## 🔒 Security Considerations

### Password Security
- Minimum 8 characters with complexity requirements
- bcrypt hashing with salt
- Failed login attempt tracking
- Account lockout after 5 failed attempts

### Token Security
- JWT with short expiration (30 minutes for access tokens)
- Refresh tokens with longer expiration (7 days)
- Token blacklisting capability
- Secure token storage recommendations

### Session Management
- Session tracking with IP and user agent
- Concurrent session limits
- Session invalidation on password change
- Automatic cleanup of expired sessions

## 📊 Performance Requirements

### Response Times
- Authentication: < 200ms
- User profile operations: < 100ms
- Token validation: < 50ms

### Scalability
- Support 1000+ concurrent users
- Database connection pooling
- Efficient query optimization
- Caching for frequently accessed user data

## 🚀 Deployment Considerations

### Environment Variables
```bash
# Required environment variables
JWT_SECRET_KEY=your_super_secret_key_here
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
PASSWORD_MIN_LENGTH=8
MAX_FAILED_LOGIN_ATTEMPTS=5
ACCOUNT_LOCKOUT_MINUTES=15
```

### Database Migrations
- Use Alembic for database migrations
- Version control all schema changes
- Backup strategy for user data
- Data retention policies

## 📝 Development Guidelines

### Code Standards
- Follow PEP 8 for Python code
- Use type hints throughout
- Comprehensive docstrings
- Error handling with custom exceptions

### Logging
- Log all authentication attempts
- Track user actions for audit
- Monitor failed login patterns
- Performance metrics logging

---

## 🤝 Team Coordination

### Communication with Other Modules
- **Portfolio Module**: Provides user authentication for portfolio operations
- **DCF Module**: Provides user context for calculations and history
- **Data Module**: No direct interaction (Data Module is stateless)
- **Report Module**: Provides user authentication for report generation and sharing

### Shared Dependencies
- Database session management
- Error handling patterns
- Logging configuration
- Environment variable management

This module serves as the foundation for all user-related functionality and security across the entire Investment App platform.