import logging
import sys
from datetime import datetime
from typing import Dict, Any, Optional
import json
import os

# Ensure logs directory exists before any logging
os.makedirs('logs', exist_ok=True)

class StoryLogger:
    """Centralized logging for story creation flow"""
    
    def __init__(self):
        self.logger = logging.getLogger('bookid_stories')
        self.logger.setLevel(logging.INFO)
        
        if not self.logger.handlers:
            # Console handler
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(logging.INFO)
            
            # File handler for persistent logging
            file_handler = logging.FileHandler('logs/story_creation.log')
            file_handler.setLevel(logging.INFO)
            
            # Formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(formatter)
            file_handler.setFormatter(formatter)
            
            self.logger.addHandler(console_handler)
            self.logger.addHandler(file_handler)
    
    def log_story_request(self, user_id: int, story_data: Dict[str, Any], request_id: str = None):
        """Log initial story creation request"""
        log_data = {
            "event": "story_request_initiated",
            "user_id": user_id,
            "request_id": request_id,
            "story_params": {
                "theme": story_data.get('theme'),
                "hero_name": story_data.get('hero_name'),
                "hero_age": story_data.get('hero_age'),
                "reading_time": story_data.get('reading_time'),
                "is_interactive": story_data.get('is_interactive'),
                "has_special_request": bool(story_data.get('special_request'))
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.info(f"Story Request: {json.dumps(log_data)}")
    
    def log_content_moderation(self, user_id: int, content_type: str, is_safe: bool, 
                             reason: str = None, request_id: str = None):
        """Log content moderation results"""
        log_data = {
            "event": "content_moderation",
            "user_id": user_id,
            "request_id": request_id,
            "content_type": content_type,
            "is_safe": is_safe,
            "reason": reason,
            "timestamp": datetime.utcnow().isoformat()
        }
        level = logging.WARNING if not is_safe else logging.INFO
        self.logger.log(level, f"Content Moderation: {json.dumps(log_data)}")
    
    def log_story_generation_start(self, story_id: int, user_id: int, 
                                 expected_pages: int, request_id: str = None):
        """Log start of story generation process"""
        log_data = {
            "event": "story_generation_started",
            "story_id": story_id,
            "user_id": user_id,
            "request_id": request_id,
            "expected_pages": expected_pages,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.info(f"Story Generation Started: {json.dumps(log_data)}")
    
    def log_ai_interaction(self, agent_type: str, prompt_length: int, 
                          success: bool, execution_time: float = None,
                          error: str = None, request_id: str = None):
        """Log AI agent interactions"""
        log_data = {
            "event": "ai_interaction",
            "agent_type": agent_type,
            "request_id": request_id,
            "prompt_length": prompt_length,
            "success": success,
            "execution_time_seconds": execution_time,
            "error": error,
            "timestamp": datetime.utcnow().isoformat()
        }
        level = logging.ERROR if not success else logging.INFO
        self.logger.log(level, f"AI Interaction: {json.dumps(log_data)}")
    
    def log_story_generation_complete(self, story_id: int, user_id: int,
                                    pages_generated: int, pages_approved: int,
                                    total_time: float = None, request_id: str = None):
        """Log completion of story generation"""
        log_data = {
            "event": "story_generation_completed",
            "story_id": story_id,
            "user_id": user_id,
            "request_id": request_id,
            "pages_generated": pages_generated,
            "pages_approved": pages_approved,
            "success_rate": pages_approved / pages_generated if pages_generated > 0 else 0,
            "total_time_seconds": total_time,
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.info(f"Story Generation Complete: {json.dumps(log_data)}")
    
    def log_error(self, error_type: str, error_message: str, context: Dict[str, Any] = None,
                  user_id: int = None, story_id: int = None, request_id: str = None):
        """Log errors with context"""
        log_data = {
            "event": "error",
            "error_type": error_type,
            "error_message": error_message,
            "user_id": user_id,
            "story_id": story_id,
            "request_id": request_id,
            "context": context or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.error(f"Error: {json.dumps(log_data)}")
    
    def log_user_action(self, user_id: int, action: str, details: Dict[str, Any] = None,
                       story_id: int = None, request_id: str = None):
        """Log user actions throughout the flow"""
        log_data = {
            "event": "user_action",
            "user_id": user_id,
            "action": action,
            "story_id": story_id,
            "request_id": request_id,
            "details": details or {},
            "timestamp": datetime.utcnow().isoformat()
        }
        self.logger.info(f"User Action: {json.dumps(log_data)}")

# Global logger instance
story_logger = StoryLogger()