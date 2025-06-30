from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import models
import schemas
from database import get_db
from auth import get_current_user
from services.story_generator import StoryGeneratorService
from services.content_moderator import ContentModeratorService
from utils.logger import story_logger
import uuid
import os
import time

router = APIRouter(prefix="/stories", tags=["stories"])

@router.post("/create", response_model=schemas.Story)
async def create_story(
    story_data: schemas.StoryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    request_id = str(uuid.uuid4())
    start_time = time.time()
    
    # Log story creation request
    story_logger.log_story_request(
        user_id=current_user.id,
        story_data=story_data.model_dump(),
        request_id=request_id
    )
    
    try:
        # Validate content
        moderator = ContentModeratorService()
        story_data_dict = story_data.model_dump()
        story_data_dict['user_id'] = current_user.id  # Add user_id for logging
        
        if not await moderator.is_safe_request(story_data_dict, current_user.id, request_id):
            story_logger.log_user_action(
                user_id=current_user.id,
                action="story_creation_rejected",
                details={"reason": "content_moderation_failed"},
                request_id=request_id
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Content request contains inappropriate elements"
            )
        
        # Create story record
        story = models.Story(
            user_id=current_user.id,
            title=f"{story_data.hero_name}'s {story_data.theme.capitalize()} Adventure",
            theme=story_data.theme,
            hero_name=story_data.hero_name,
            hero_age=story_data.hero_age,
            reading_time=story_data.reading_time,
            special_request=story_data.special_request,
            is_interactive=1 if story_data.is_interactive else 0
        )
        db.add(story)
        db.commit()
        db.refresh(story)
        
        story_logger.log_user_action(
            user_id=current_user.id,
            action="story_record_created",
            details={
                "story_id": story.id,
                "title": story.title,
                "creation_time": time.time() - start_time
            },
            story_id=story.id,
            request_id=request_id
        )
        
        # Generate story content in background
        story_data_with_ids = story_data.model_dump()
        story_data_with_ids['user_id'] = current_user.id
        background_tasks.add_task(generate_story_content, story.id, story_data_with_ids, db, request_id)
        
        return story
        
    except HTTPException:
        raise
    except Exception as e:
        story_logger.log_error(
            error_type="story_creation_error",
            error_message=str(e),
            context={"story_data": story_data.model_dump()},
            user_id=current_user.id,
            request_id=request_id
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while creating the story"
        )

async def generate_story_content(story_id: int, story_data: dict, db: Session, request_id: str = None):
    if not request_id:
        request_id = str(uuid.uuid4())
        
    user_id = story_data.get('user_id', 0)
    start_time = time.time()
    
    story_logger.log_story_generation_start(
        story_id=story_id,
        user_id=user_id,
        expected_pages=max(2, int(story_data.get('reading_time', 2))),
        request_id=request_id
    )
    
    try:
        # Initialize services
        story_generator = StoryGeneratorService()
        moderator = ContentModeratorService()
        
        # Generate story pages with images and moderation
        pages = await story_generator.generate_complete_story_with_images_and_moderation(
            story_data, moderator, request_id
        )
        
        pages_generated = len(pages)
        pages_approved = 0
        
        # Save pages (moderation already done in the generator)
        for page_content in pages:
            # Check if page passed moderation (if moderation was included)
            moderation_result = page_content.get('moderation')
            if moderation_result and not moderation_result.get('safe', True):
                story_logger.log_user_action(
                    user_id=user_id,
                    action="page_content_rejected",
                    details={
                        "page_number": page_content.get('page_number'),
                        "reason": moderation_result.get('reason'),
                        "concerns": moderation_result.get('concerns', [])
                    },
                    story_id=story_id,
                    request_id=request_id
                )
                continue
            
            page = models.StoryPage(
                story_id=story_id,
                page_number=page_content.get('page_number'),
                text=page_content['text'],
                image_url=page_content.get('image_url'),  # Now includes generated images
                choices=page_content.get('choices') if story_data.get('is_interactive') else None
            )
            db.add(page)
            pages_approved += 1
        
        db.commit()
        
        total_time = time.time() - start_time
        
        # Update story status to indicate completion
        story = db.query(models.Story).filter(models.Story.id == story_id).first()
        if story:
            # Count actual pages created
            page_count = db.query(models.StoryPage).filter(models.StoryPage.story_id == story_id).count()
            if page_count == 0:
                story.title = f"{story.title} (Content Moderation Failed)"
                story_logger.log_user_action(
                    user_id=user_id,
                    action="story_generation_failed",
                    details={"reason": "all_pages_rejected_by_moderation"},
                    story_id=story_id,
                    request_id=request_id
                )
            else:
                story_logger.log_user_action(
                    user_id=user_id,
                    action="story_pages_saved",
                    details={"pages_saved": page_count},
                    story_id=story_id,
                    request_id=request_id
                )
            db.commit()
        
        story_logger.log_story_generation_complete(
            story_id=story_id,
            user_id=user_id,
            pages_generated=pages_generated,
            pages_approved=pages_approved,
            total_time=total_time,
            request_id=request_id
        )
            
    except Exception as e:
        total_time = time.time() - start_time
        
        story_logger.log_error(
            error_type="background_story_generation_error",
            error_message=str(e),
            context={
                "story_id": story_id,
                "story_data": story_data,
                "execution_time": total_time
            },
            user_id=user_id,
            story_id=story_id,
            request_id=request_id
        )
        
        # Mark story as failed
        story = db.query(models.Story).filter(models.Story.id == story_id).first()
        if story:
            story.title = f"{story.title} (Generation Failed)"
            db.commit()
            
        story_logger.log_user_action(
            user_id=user_id,
            action="story_generation_failed",
            details={"reason": "generation_error", "error": str(e)},
            story_id=story_id,
            request_id=request_id
        )

@router.get("/", response_model=List[schemas.StoryList])
def list_stories(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    stories = db.query(models.Story)\
        .filter(models.Story.user_id == current_user.id)\
        .order_by(models.Story.created_at.desc())\
        .offset(skip)\
        .limit(limit)\
        .all()
    return stories

@router.get("/{story_id}", response_model=schemas.Story)
def get_story(
    story_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    story_logger.log_user_action(
        user_id=current_user.id,
        action="story_access_requested",
        details={"story_id": story_id},
        story_id=story_id
    )
    
    story = db.query(models.Story)\
        .filter(models.Story.id == story_id, models.Story.user_id == current_user.id)\
        .first()
    
    if not story:
        story_logger.log_user_action(
            user_id=current_user.id,
            action="story_access_denied",
            details={"story_id": story_id, "reason": "not_found_or_no_access"},
            story_id=story_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    story_logger.log_user_action(
        user_id=current_user.id,
        action="story_accessed",
        details={
            "story_id": story_id,
            "title": story.title,
            "page_count": len(story.pages) if story.pages else 0
        },
        story_id=story_id
    )
    
    return story

@router.post("/{story_id}/choice")
def make_story_choice(
    story_id: int,
    choice: schemas.StoryProgressUpdate,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    story_logger.log_user_action(
        user_id=current_user.id,
        action="story_choice_made",
        details={
            "story_id": story_id,
            "new_page": choice.current_page
        },
        story_id=story_id
    )
    
    # Verify story ownership
    story = db.query(models.Story)\
        .filter(models.Story.id == story_id, models.Story.user_id == current_user.id)\
        .first()
    
    if not story:
        story_logger.log_user_action(
            user_id=current_user.id,
            action="story_choice_denied",
            details={"story_id": story_id, "reason": "story_not_found"},
            story_id=story_id
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    # Get or create progress
    progress = db.query(models.StoryProgress)\
        .filter(
            models.StoryProgress.story_id == story_id,
            models.StoryProgress.user_id == current_user.id
        )\
        .first()
    
    if not progress:
        progress = models.StoryProgress(
            user_id=current_user.id,
            story_id=story_id,
            current_page=1,
            path_taken=[1]
        )
        db.add(progress)
        story_logger.log_user_action(
            user_id=current_user.id,
            action="story_progress_created",
            details={"story_id": story_id},
            story_id=story_id
        )
    
    # Update progress
    old_page = progress.current_page
    progress.current_page = choice.current_page
    if choice.current_page not in progress.path_taken:
        progress.path_taken = progress.path_taken + [choice.current_page]
    
    db.commit()
    db.refresh(progress)
    
    story_logger.log_user_action(
        user_id=current_user.id,
        action="story_progress_updated",
        details={
            "story_id": story_id,
            "old_page": old_page,
            "new_page": progress.current_page,
            "path_length": len(progress.path_taken)
        },
        story_id=story_id
    )
    
    return {"status": "success", "current_page": progress.current_page}

@router.delete("/{story_id}")
def delete_story(
    story_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    story = db.query(models.Story)\
        .filter(models.Story.id == story_id, models.Story.user_id == current_user.id)\
        .first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    db.delete(story)
    db.commit()
    
    return {"status": "success", "message": "Story deleted"}

@router.get("/{story_id}/share", response_model=schemas.StoryShare)
def get_share_link(
    story_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user)
):
    story = db.query(models.Story)\
        .filter(models.Story.id == story_id, models.Story.user_id == current_user.id)\
        .first()
    
    if not story:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Story not found"
        )
    
    # Generate shareable link
    frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")
    share_token = str(uuid.uuid4())  # In production, store this token for validation
    share_url = f"{frontend_url}/story/shared/{story_id}?token={share_token}"
    
    return {"share_url": share_url, "story_id": story_id}