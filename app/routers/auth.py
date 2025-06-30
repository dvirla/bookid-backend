from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
import models
import schemas
from database import get_db
from auth import verify_google_token, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, get_current_user
import logging
from sqlalchemy.exc import SQLAlchemyError
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["authentication"])

@router.get("/me", response_model=schemas.User)
def get_current_user_info(current_user: models.User = Depends(get_current_user)) -> schemas.User:
    """
    Get current authenticated user information.
    
    Args:
        current_user: Current authenticated user from token
        
    Returns:
        User: Current user information
    """
    logger.info(f"Retrieved user info for: {current_user.email}")
    return schemas.User(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        profile_picture=current_user.profile_picture,
        created_at=current_user.created_at
    )

@router.post("/logout")
def logout() -> Dict[str, str]:
    """
    Logout endpoint (client should discard token).
    
    Returns:
        dict: Success message
    """
    logger.info("User logout requested")
    return {"message": "Successfully logged out"}

@router.get("/health")
def auth_health_check() -> Dict[str, str]:
    """
    Health check endpoint for authentication service.
    
    Returns:
        dict: Health status
    """
    return {"status": "healthy", "service": "authentication"}

@router.post("/google", response_model=schemas.Token)
def google_auth(request: schemas.GoogleAuthRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """
    Authenticate user with Google OAuth2 ID token.
    
    Args:
        request: Google authentication request containing ID token
        db: Database session dependency
        
    Returns:
        dict: Access token and token type
        
    Raises:
        HTTPException: If authentication fails
    """
    try:
        logger.info("Processing Google OAuth authentication request")
        
        # Verify Google token
        google_user = verify_google_token(request.id_token)
        
        # Check if user exists
        user = db.query(models.User).filter(models.User.google_id == google_user['sub']).first()
        
        if not user:
            logger.info(f"Creating new user for Google ID: {google_user['sub']}")
            
            # Check if email already exists with different Google ID
            existing_user = db.query(models.User).filter(models.User.email == google_user['email']).first()
            if existing_user:
                logger.warning(f"Email {google_user['email']} already exists with different Google ID")
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Email already registered with different Google account"
                )
            
            # Create new user
            profile_pic_url = google_user.get('picture')
            logger.info(f"Creating new user with profile picture: {profile_pic_url}")
            user = models.User(
                email=google_user['email'],
                name=google_user['name'],
                google_id=google_user['sub'],
                profile_picture=profile_pic_url
            )
            
            try:
                db.add(user)
                db.commit()
                db.refresh(user)
                logger.info(f"Successfully created user: {user.email}")
            except SQLAlchemyError as e:
                logger.error(f"Database error creating user: {str(e)}")
                db.rollback()
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create user account"
                )
        else:
            logger.info(f"User login: {user.email}")
            
            # Update user info if changed
            updated = False
            if user.name != google_user['name']:
                user.name = google_user['name']
                updated = True
            if user.email != google_user['email']:
                user.email = google_user['email']
                updated = True
            new_profile_pic = google_user.get('picture')
            if user.profile_picture != new_profile_pic:
                logger.info(f"Updating profile picture from {user.profile_picture} to {new_profile_pic}")
                user.profile_picture = new_profile_pic
                updated = True
                
            if updated:
                try:
                    db.commit()
                    logger.info(f"Updated user info for: {user.email}")
                except SQLAlchemyError as e:
                    logger.error(f"Database error updating user: {str(e)}")
                    db.rollback()
        
        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.email}, expires_delta=access_token_expires
        )
        
        logger.info(f"Successfully authenticated user: {user.email}")
        return {"access_token": access_token, "token_type": "bearer"}
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Google authentication: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication service temporarily unavailable"
        )