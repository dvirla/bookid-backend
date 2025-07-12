from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider
from pydantic_ai import Agent, ImageUrl, BinaryContent
from pydantic import BaseModel, Field
from typing import Dict, Any, Union, List
import os
import time
import uuid
from dotenv import load_dotenv
from app.utils.logger import story_logger
import logfire
import httpx

load_dotenv()

logfire.configure(token=os.getenv('LOGFIRE_API_KEY'))
logfire.instrument_pydantic_ai()

class ModerationResult(BaseModel):
    safe: bool = Field(..., description="Whether the content is safe for children")
    reason: str = Field(..., description="Explanation if content is unsafe, or confirmation if safe")
    age_appropriate: bool = Field(..., description="Whether content is age-appropriate")
    concerns: list[str] = Field(default_factory=list, description="List of specific concerns if any")

class ContentModeratorService:
    def __init__(self):
        self.model = OpenAIModel(
            os.getenv('AZURE_CONTENT_MODERATOR_DEPLOYMENT_NAME'),
            provider=AzureProvider(
                azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
                api_version=os.getenv('AZURE_CONTENT_MODERATOR_API_VERSION'),
                api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            ),
        )
    
        self.moderation_agent = Agent(
            self.model,
            output_type=ModerationResult,
            model_settings={"temperature": os.getenv('AZURE_CONTENT_MODERATOR_TEMPERATURE', '0')},
            system_prompt="""You are a professional content moderator specializing in children's content safety for both text and visual content.

Your role is to evaluate content for appropriateness for children aged 3-12. You must be thorough but not overly restrictive.

SAFE content includes:
- Age-appropriate adventures and exploration
- Friendship and cooperation themes
- Learning and discovery
- Mild challenges that characters overcome
- Fantasy elements like magic, talking animals
- Positive role models and values
- Bright, colorful, child-friendly illustrations
- Whimsical and magical visual elements

UNSAFE content includes:
- Violence, fighting, or physical harm
- Scary/horror themes that could cause nightmares
- Adult themes (romance, dating, adult relationships)
- Death or serious illness
- Inappropriate language or behavior
- Discrimination or bullying
- Complex emotional trauma
- Dark, frightening, or disturbing imagery
- Inappropriate visual content or suggestive imagery
- Overly realistic depictions of danger or threat

For images, also consider:
- Color palette (bright vs. dark/threatening)
- Facial expressions (friendly vs. scary/angry)
- Overall mood and atmosphere
- Age-appropriateness of visual elements

For borderline content, err on the side of safety while providing constructive feedback."""
        )

    
    async def is_safe_request(self, request_data: Dict[str, Any], user_id: int = None, request_id: str = None) -> bool:
        """Check if the story request is appropriate for children"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        story_logger.log_user_action(
            user_id=user_id,
            action="content_moderation_started",
            details={
                "content_type": "story_request",
                "theme": request_data.get('theme'),
                "has_special_request": bool(request_data.get('special_request'))
            },
            request_id=request_id
        )
        
        # First do basic keyword checks
        unsafe_words = ['violence', 'death', 'scary', 'horror', 'adult', 'kill', 'hurt', 'fight']
        
        request_text = f"{request_data.get('theme', '')} {request_data.get('special_request', '')}"
        
        for word in unsafe_words:
            if word in request_text.lower():
                story_logger.log_content_moderation(
                    user_id=user_id,
                    content_type="story_request",
                    is_safe=False,
                    reason=f"Contains unsafe keyword: {word}",
                    request_id=request_id
                )
                return False
        
        # For more complex requests, use AI moderation
        if request_data.get('special_request') and len(request_data.get('special_request', '')) > 20:
            try:
                moderation_result = await self.moderate_story_request(request_data, request_id)
                story_logger.log_content_moderation(
                    user_id=user_id,
                    content_type="story_request",
                    is_safe=moderation_result.safe,
                    reason=moderation_result.reason,
                    request_id=request_id
                )
                return moderation_result.safe
            except Exception as e:
                story_logger.log_error(
                    error_type="ai_moderation_error",
                    error_message=str(e),
                    context={"content_type": "story_request"},
                    user_id=user_id,
                    request_id=request_id
                )
                # Default to safe if moderation fails
                story_logger.log_content_moderation(
                    user_id=user_id,
                    content_type="story_request",
                    is_safe=True,
                    reason="AI moderation failed, defaulted to safe",
                    request_id=request_id
                )
                return True
        
        story_logger.log_content_moderation(
            user_id=user_id,
            content_type="story_request",
            is_safe=True,
            reason="Passed basic keyword checks",
            request_id=request_id
        )
        return True
    
    async def moderate_story_request(self, request_data: Dict[str, Any], request_id: str = None) -> ModerationResult:
        """Moderate a story creation request"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        prompt = f"""Evaluate this children's story request for safety and appropriateness:

Theme: {request_data.get('theme', 'adventure')}
Hero Age: {request_data.get('hero_age', 5)}
Special Request: {request_data.get('special_request', 'None')}
Interactive: {request_data.get('is_interactive', False)}

Determine if this request is appropriate for creating a children's story."""
        
        start_time = time.time()
        
        try:
            result = await self.moderation_agent.run(prompt)
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="content_moderator",
                prompt_length=len(prompt),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            return result.output
        except Exception as e:
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="content_moderator",
                prompt_length=len(prompt),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            
            story_logger.log_error(
                error_type="story_request_moderation_error",
                error_message=str(e),
                context={"request_data": request_data},
                request_id=request_id
            )
            
            # Safe fallback
            return ModerationResult(
                safe=True,
                reason="Moderation service unavailable, approved by default",
                age_appropriate=True,
                concerns=[]
            )
    
    async def moderate_generated_content(self, content: str, age: int = 5, 
                                       user_id: int = None, request_id: str = None) -> ModerationResult:
        """Moderate generated story content"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        prompt = f"""Review this generated children's story content for a {age}-year-old:

Story Content:
{content}

Check for any inappropriate elements, scary content, or age-inappropriate themes."""
        
        start_time = time.time()
        
        try:
            result = await self.moderation_agent.run(prompt)
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="content_moderator",
                prompt_length=len(prompt),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            story_logger.log_content_moderation(
                user_id=user_id,
                content_type="generated_story_content",
                is_safe=result.output.safe,
                reason=result.output.reason,
                request_id=request_id
            )
            
            return result.output
        except Exception as e:
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="content_moderator",
                prompt_length=len(prompt),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            
            story_logger.log_error(
                error_type="content_moderation_error",
                error_message=str(e),
                context={"content_length": len(content), "age": age},
                user_id=user_id,
                request_id=request_id
            )
            
            # Safe fallback
            fallback_result = ModerationResult(
                safe=True,
                reason="Moderation service unavailable, approved by default",
                age_appropriate=True,
                concerns=[]
            )
            
            story_logger.log_content_moderation(
                user_id=user_id,
                content_type="generated_story_content",
                is_safe=True,
                reason="Moderation service failed, defaulted to safe",
                request_id=request_id
            )
            
            return fallback_result
    
    async def moderate_image(self, image_url: str, context: str = None, age: int = 5, 
                           user_id: int = None, request_id: str = None) -> ModerationResult:
        """Moderate a generated image for child safety"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        # Create prompt with image
        prompt_parts = [
            f"Review this generated children's story illustration for a {age}-year-old child.",
            ImageUrl(url=image_url)
        ]
        
        if context:
            prompt_parts.insert(1, f"Story context: {context}")
        
        prompt_parts.append(
            "Evaluate the image for child safety, checking for any scary, inappropriate, "
            "or age-inappropriate visual elements. Consider colors, expressions, themes, and overall mood."
        )
        
        start_time = time.time()
        
        try:
            story_logger.log_ai_interaction(
                agent_type="image_content_moderator",
                prompt_length=len(str(prompt_parts)),
                success=True,
                request_id=request_id
            )
            
            result = await self.moderation_agent.run(prompt_parts)
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="image_content_moderator",
                prompt_length=len(str(prompt_parts)),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            story_logger.log_content_moderation(
                user_id=user_id,
                content_type="generated_image",
                is_safe=result.output.safe,
                reason=result.output.reason,
                request_id=request_id
            )
            
            return result.output
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="image_content_moderator",
                prompt_length=len(str(prompt_parts)),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            
            story_logger.log_error(
                error_type="image_moderation_error",
                error_message=str(e),
                context={"image_url": image_url, "context": context, "age": age},
                user_id=user_id,
                request_id=request_id
            )
            
            # Safe fallback
            fallback_result = ModerationResult(
                safe=True,
                reason="Image moderation service unavailable, approved by default",
                age_appropriate=True,
                concerns=[]
            )
            
            story_logger.log_content_moderation(
                user_id=user_id,
                content_type="generated_image",
                is_safe=True,
                reason="Image moderation service failed, defaulted to safe",
                request_id=request_id
            )
            
            return fallback_result
    
    async def moderate_story_page_with_image(self, page_text: str, image_url: str, age: int = 5,
                                           user_id: int = None, request_id: str = None) -> ModerationResult:
        """Moderate both text and image content of a story page together"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        prompt_parts = [
            f"Review this complete story page for a {age}-year-old child, including both text and image:",
            f"Story text: {page_text}",
            ImageUrl(url=image_url),
            "Evaluate both the text content and the visual content together. Check for consistency, "
            "appropriateness, and any elements that might be inappropriate or scary for children. "
            "Consider how the text and image work together to create the overall experience."
        ]
        
        start_time = time.time()
        
        try:
            story_logger.log_ai_interaction(
                agent_type="page_content_moderator",
                prompt_length=len(str(prompt_parts)),
                success=True,
                request_id=request_id
            )
            
            result = await self.moderation_agent.run(prompt_parts)
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="page_content_moderator",
                prompt_length=len(str(prompt_parts)),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            story_logger.log_content_moderation(
                user_id=user_id,
                content_type="story_page_with_image",
                is_safe=result.output.safe,
                reason=result.output.reason,
                request_id=request_id
            )
            
            return result.output
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="page_content_moderator",
                prompt_length=len(str(prompt_parts)),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            
            story_logger.log_error(
                error_type="page_moderation_error",
                error_message=str(e),
                context={"text_length": len(page_text), "image_url": image_url, "age": age},
                user_id=user_id,
                request_id=request_id
            )
            
            # Safe fallback
            fallback_result = ModerationResult(
                safe=True,
                reason="Page moderation service unavailable, approved by default",
                age_appropriate=True,
                concerns=[]
            )
            
            story_logger.log_content_moderation(
                user_id=user_id,
                content_type="story_page_with_image",
                is_safe=True,
                reason="Page moderation service failed, defaulted to safe",
                request_id=request_id
            )
            
            return fallback_result
    
    async def moderate_complete_story(self, pages: List[Dict], user_id: int = None, 
                                    request_id: str = None) -> Dict[str, Any]:
        """Moderate a complete story with all pages and images"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        results = {
            "overall_safe": True,
            "page_results": [],
            "concerns": [],
            "total_pages": len(pages),
            "moderated_pages": 0
        }
        
        story_logger.log_user_action(
            user_id=user_id,
            action="complete_story_moderation_started",
            details={"total_pages": len(pages)},
            request_id=request_id
        )
        
        for page in pages:
            try:
                page_result = None
                
                # If page has both text and image, moderate together
                if page.get('image_url') and page.get('text'):
                    page_result = await self.moderate_story_page_with_image(
                        page['text'], 
                        page['image_url'], 
                        age=5,  # Default age, could be parameterized
                        user_id=user_id, 
                        request_id=request_id
                    )
                # If only text, moderate text only
                elif page.get('text'):
                    page_result = await self.moderate_generated_content(
                        page['text'], 
                        age=5,
                        user_id=user_id, 
                        request_id=request_id
                    )
                # If only image, moderate image only
                elif page.get('image_url'):
                    page_result = await self.moderate_image(
                        page['image_url'], 
                        context=f"Story page {page.get('page_number')}", 
                        age=5,
                        user_id=user_id, 
                        request_id=request_id
                    )
                
                if page_result:
                    results["page_results"].append({
                        "page_number": page.get('page_number'),
                        "safe": page_result.safe,
                        "reason": page_result.reason,
                        "concerns": page_result.concerns
                    })
                    
                    if not page_result.safe:
                        results["overall_safe"] = False
                        results["concerns"].extend(page_result.concerns)
                    
                    results["moderated_pages"] += 1
                    
            except Exception as e:
                story_logger.log_error(
                    error_type="page_moderation_failed",
                    error_message=str(e),
                    context={"page_number": page.get('page_number')},
                    user_id=user_id,
                    request_id=request_id
                )
                # Continue with other pages
                continue
        
        story_logger.log_user_action(
            user_id=user_id,
            action="complete_story_moderation_completed",
            details={
                "overall_safe": results["overall_safe"],
                "total_pages": results["total_pages"],
                "moderated_pages": results["moderated_pages"],
                "total_concerns": len(results["concerns"])
            },
            request_id=request_id
        )
        
        return results