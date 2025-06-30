#!/usr/bin/env python3
"""
Test authentication flow end-to-end
"""
import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables from the correct path
load_dotenv()

# Add current directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from auth import verify_google_token, create_access_token, get_current_user
from database import get_db, engine
from models import User
from sqlalchemy.orm import Session
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_environment():
    """Test environment variables"""
    logger.info("🔍 Testing environment variables...")
    
    required_vars = ['GOOGLE_CLIENT_ID', 'JWT_SECRET', 'DATABASE_URL']
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if var == 'DATABASE_URL':
                # Show more of database URL for debugging
                logger.info(f"✅ {var}: {value}")
            else:
                logger.info(f"✅ {var}: {'*' * 20}...{value[-10:] if len(value) > 30 else value}")
        else:
            logger.error(f"❌ {var}: Not found")
            return False
    return True

def test_jwt_operations():
    """Test JWT token creation and validation"""
    logger.info("🔍 Testing JWT operations...")
    
    try:
        # Test token creation
        test_data = {"sub": "test@example.com"}
        token = create_access_token(test_data)
        logger.info(f"✅ JWT token created: {token[:50]}...")
        
        # Test token decoding (manual test since we'd need a mock user)
        from jose import jwt
        decoded = jwt.decode(token, os.getenv('JWT_SECRET'), algorithms=['HS256'])
        logger.info(f"✅ JWT token decoded successfully")
        logger.info(f"   Subject: {decoded.get('sub')}")
        logger.info(f"   Type: {decoded.get('type')}")
        logger.info(f"   Issued at: {datetime.fromtimestamp(decoded.get('iat', 0), timezone.utc)}")
        logger.info(f"   Expires at: {datetime.fromtimestamp(decoded.get('exp', 0), timezone.utc)}")
        
        return True
    except Exception as e:
        logger.error(f"❌ JWT operations failed: {e}")
        return False

def test_database_user_operations():
    """Test user database operations"""
    logger.info("🔍 Testing database user operations...")
    
    try:
        # Get database session
        db = next(get_db())
        
        # Test user creation
        test_user = User(
            email="test@example.com",
            name="Test User",
            google_id="test_google_id_123"
        )
        
        # Check if user already exists and clean up
        existing = db.query(User).filter(User.email == "test@example.com").first()
        if existing:
            db.delete(existing)
            db.commit()
            logger.info("🧹 Cleaned up existing test user")
        
        # Create new test user
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        logger.info(f"✅ Test user created with ID: {test_user.id}")
        
        # Test user retrieval
        retrieved_user = db.query(User).filter(User.email == "test@example.com").first()
        if retrieved_user:
            logger.info(f"✅ User retrieved: {retrieved_user.name} ({retrieved_user.email})")
        else:
            logger.error("❌ User retrieval failed")
            return False
        
        # Clean up
        db.delete(test_user)
        db.commit()
        logger.info("🧹 Test user cleaned up")
        
        return True
    except Exception as e:
        logger.error(f"❌ Database operations failed: {e}")
        return False
    finally:
        db.close()

def test_google_client_validation():
    """Test Google OAuth client configuration"""
    logger.info("🔍 Testing Google OAuth configuration...")
    
    client_id = os.getenv('GOOGLE_CLIENT_ID')
    if not client_id:
        logger.error("❌ GOOGLE_CLIENT_ID not found")
        return False
    
    # Validate client ID format
    if '.apps.googleusercontent.com' not in client_id:
        logger.error("❌ Invalid Google Client ID format")
        return False
    
    logger.info(f"✅ Google Client ID format valid")
    logger.info(f"   Client ID: {client_id}")
    
    # Check client secret file
    client_secret_file = "/home/dvir/projects/Bookid/backend/client_secret.json"
    if os.path.exists(client_secret_file):
        try:
            with open(client_secret_file, 'r') as f:
                client_data = json.load(f)
            
            web_config = client_data.get('web', {})
            file_client_id = web_config.get('client_id')
            
            if file_client_id == client_id:
                logger.info("✅ Client secret file matches environment variable")
            else:
                logger.warning("⚠️  Client ID mismatch between .env and client_secret.json")
            
            # Check redirect URIs
            redirect_uris = web_config.get('redirect_uris', [])
            logger.info(f"📋 Configured redirect URIs: {redirect_uris}")
            
            return True
        except Exception as e:
            logger.error(f"❌ Error reading client secret file: {e}")
            return False
    else:
        logger.warning("⚠️  Client secret file not found (not required for ID token verification)")
        return True

def test_auth_endpoints_structure():
    """Test that all auth components are properly structured"""
    logger.info("🔍 Testing authentication components structure...")
    
    try:
        # Test imports
        from routers.auth import router
        logger.info("✅ Auth router imported successfully")
        
        # Check router configuration
        logger.info(f"✅ Router prefix: {router.prefix}")
        logger.info(f"✅ Router tags: {router.tags}")
        
        # List available routes
        routes = []
        for route in router.routes:
            if hasattr(route, 'methods') and hasattr(route, 'path'):
                for method in route.methods:
                    routes.append(f"{method} {router.prefix}{route.path}")
        
        logger.info("📋 Available auth endpoints:")
        for route in routes:
            logger.info(f"   {route}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Auth structure test failed: {e}")
        return False

def main():
    """Run all authentication tests"""
    logger.info("🚀 Starting authentication flow tests...")
    
    tests = [
        ("Environment Variables", test_environment),
        ("JWT Operations", test_jwt_operations),
        ("Database User Operations", test_database_user_operations),
        ("Google OAuth Configuration", test_google_client_validation),
        ("Auth Endpoints Structure", test_auth_endpoints_structure)
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        logger.info(f"🧪 Running: {test_name}")
        if test_func():
            passed += 1
            logger.info(f"✅ {test_name}: PASSED")
        else:
            logger.error(f"❌ {test_name}: FAILED")
    
    logger.info(f"\n{'='*50}")
    logger.info(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All authentication tests passed!")
        logger.info("\n📋 Next steps:")
        logger.info("1. Start your FastAPI server: uvicorn main:app --reload")
        logger.info("2. Test endpoints:")
        logger.info("   - GET  http://localhost:8000/auth/health")
        logger.info("   - POST http://localhost:8000/auth/google (with Google ID token)")
        logger.info("   - GET  http://localhost:8000/auth/me (with Bearer token)")
        return True
    else:
        logger.error("❌ Some tests failed. Please fix the issues above.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)