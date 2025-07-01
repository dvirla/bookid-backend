from pydantic_ai import Agent, ModelRetry
from pydantic_ai.models.openai import OpenAIModel
from pydantic_ai.providers.azure import AzureProvider
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import os
import time
import uuid
import asyncio
from dotenv import load_dotenv
from utils.logger import story_logger
import logfire
from openai import AzureOpenAI
import json
import cloudinary
import cloudinary.uploader
import httpx

load_dotenv()

logfire.configure(token=os.getenv('LOGFIRE_API_KEY'))
logfire.instrument_pydantic_ai()

class StoryChoice(BaseModel):
    text: str = Field(..., description="The choice text to display")
    next_page: int = Field(..., description="The page number this choice leads to")

class StoryPage(BaseModel):
    page_number: int = Field(..., description="The page number (1-based)")
    text: str = Field(..., description="The story text for this page (100-150 words)")
    choices: Optional[List[StoryChoice]] = Field(None, description="Interactive choices if this is a choice page")
    image_description: Optional[str] = Field(None, description="Description for image generation")
    image_url: Optional[str] = Field(None, description="Generated image URL")

class StoryStructure(BaseModel):
    title: str = Field(..., description="The story title")
    pages: List[StoryPage] = Field(..., description="List of story pages")
    total_pages: int = Field(..., description="Total number of pages in the story")


class StoryGeneratorService:
    def __init__(self):
        self.model = OpenAIModel(
            os.getenv('AZURE_STORY_DEPLOYMENT_NAME'),
            provider=AzureProvider(
                azure_endpoint=os.getenv('AZURE_OPENAI_ENDPOINT'),
                api_version=os.getenv('AZURE_STORY_API_VERSION'),
                api_key=os.getenv('AZURE_OPENAI_API_KEY'),
            ),
        )
        
        # Initialize image generation client
        self.image_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "https://bookid-resource.cognitiveservices.azure.com/")
        self.image_api_version = os.getenv("AZURE_IMAGE_API_VERSION", "2024-04-01-preview")
        self.image_deployment = os.getenv("AZURE_IMAGE_DEPLOYMENT_NAME", "dall-e-3")
        
        self.image_client = AzureOpenAI(
            api_version=self.image_api_version,
            azure_endpoint=self.image_endpoint,
            api_key=os.getenv("AZURE_OPENAI_API_KEY")
        )
        
        # Configure Cloudinary for image optimization
        cloudinary.config(
            cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
            api_key=os.getenv("CLOUDINARY_API_KEY"),
            api_secret=os.getenv("CLOUDINARY_API_SECRET")
        )
    
        self.story_agent = Agent(
            self.model,
            output_type=StoryStructure,
            model_settings={"temperature": float(os.getenv('AZURE_STORY_TEMPERATURE', '0.7'))},
            system_prompt="""You are an expert children's story writer and child development specialist who creates meaningful, educational adventures.

CORE MISSION: Create stories that inspire, teach valuable life lessons, and spark imagination while being age-appropriate and emotionally engaging.

STORYTELLING PRINCIPLES:
- Every story should have a clear, positive message or lesson (friendship, courage, kindness, perseverance, creativity, etc.)
- Create emotional connection through relatable characters and situations
- Build narrative tension with gentle challenges that children can understand
- Include moments of discovery, growth, and triumph
- Use rich sensory details to make scenes vivid and immersive
- Ensure logical story progression with cause-and-effect relationships

AGE-APPROPRIATE CONTENT:
- Adjust complexity, vocabulary, and themes based on the child's age
- Include age-appropriate challenges and solutions
- Use familiar concepts while introducing new ideas gently
- Create characters children can identify with and learn from

EDUCATIONAL VALUE:
- Weave in positive values naturally through the story
- Include opportunities for emotional and social learning
- Encourage curiosity, empathy, and problem-solving
- Show consequences of actions in a constructive way

NARRATIVE STRUCTURE:
- Clear beginning with character introduction and setting
- Engaging middle with challenges and character growth
- Satisfying resolution that reinforces the story's message
- Smooth transitions between pages that maintain engagement
- Each page should advance the story meaningfully"""
        )
        
        self.image_prompt_agent = Agent(
            self.model,
            output_type=str,
            model_settings={"temperature": 0.8},
            system_prompt="""You are an expert at creating DALL-E image prompts for children's book illustrations.
Create vivid, child-friendly, colorful prompts that capture the essence of the story page.

Guidelines:
- Use warm, inviting colors
- Include whimsical, magical elements when appropriate
- Keep content completely child-safe
- Describe scenes that complement the text
- Use art styles like: watercolor, digital illustration, cartoon style
- Avoid any scary, violent, or inappropriate content"""
        )


    async def generate_story(self, story_params: dict, request_id: str = None) -> List[Dict]:
        """Generate a complete story based on parameters"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        expected_pages = max(2, int(story_params['reading_time']))
        hero_age = story_params.get('hero_age', 5)
        min_words, max_words = self.get_age_appropriate_word_count(hero_age)
        
        story_logger.log_user_action(
            user_id=story_params.get('user_id', 0),
            action="story_generation_requested",
            details={
                "expected_pages": expected_pages,
                "theme": story_params['theme'],
                "is_interactive": story_params.get('is_interactive', False),
                "hero_age": hero_age,
                "words_per_page": f"{min_words}-{max_words}"
            },
            request_id=request_id
        )
        
        prompt = f"""Create a meaningful {story_params['theme']} adventure story that teaches valuable life lessons while entertaining and inspiring young readers.

STORY PARAMETERS:
- Hero: {story_params['hero_name']} (age {hero_age})
- Theme: {story_params['theme']} 
- Total pages: {expected_pages}
- Format: {"Interactive with meaningful choices that affect the story outcome" if story_params.get('is_interactive') else "Linear narrative with clear story progression"}
{f"- Special request: {story_params['special_request']}" if story_params.get('special_request') else ""}

CONTENT REQUIREMENTS:
- Each page: {min_words}-{max_words} words (perfectly tailored for {hero_age}-year-old comprehension)
- Central Message: Choose ONE meaningful theme (courage, friendship, kindness, perseverance, creativity, helping others, etc.)
- Emotional Arc: Show {story_params['hero_name']} facing age-appropriate challenges and growing through the experience
- Educational Value: Naturally weave in positive values and gentle life lessons
- Sensory Details: Rich descriptions that engage imagination and support illustration

STORY STRUCTURE REQUIREMENTS:
- Page 1: Introduce {story_params['hero_name']} in their world, establish the adventure premise
- Middle pages: Build adventure with challenges that teach the chosen lesson
- Final page: Satisfying resolution showing how {story_params['hero_name']} has grown and learned
- Smooth Transitions: Each page should flow naturally to the next with logical progression
- Vivid Scenes: Each page should paint a clear, imaginative picture for illustration

ILLUSTRATION GUIDELINES:
- Provide detailed image_description for each page that captures the emotion and action
- Ensure descriptions support the story's mood and message
- Include specific details about {story_params['hero_name']}'s expressions and body language
- Describe the setting in a way that enhances the story's atmosphere

Create a story that parents will love reading with their children and that children will remember fondly."""
        
        start_time = time.time()
        
        try:
            story_logger.log_ai_interaction(
                agent_type="story_generator",
                prompt_length=len(prompt),
                success=True,
                request_id=request_id
            )
            
            result = await self.story_agent.run(prompt)
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="story_generator",
                prompt_length=len(prompt),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            # Convert StoryStructure to the format expected by the router
            pages = []
            for page in result.output.pages:
                page_dict = {
                    "page_number": page.page_number,
                    "text": page.text,
                    "choices": None,
                    "image_description": page.image_description,
                    "image_url": None
                }
                
                if page.choices:
                    page_dict["choices"] = [
                        {"text": choice.text, "next_page": choice.next_page}
                        for choice in page.choices
                    ]
                
                pages.append(page_dict)
            
            story_logger.log_user_action(
                user_id=story_params.get('user_id', 0),
                action="story_pages_generated",
                details={
                    "pages_count": len(pages),
                    "has_choices": any(p.get('choices') for p in pages),
                    "execution_time": execution_time
                },
                request_id=request_id
            )
            
            return pages
            
        except ModelRetry as e:
            execution_time = time.time() - start_time
            story_logger.log_ai_interaction(
                agent_type="story_generator",
                prompt_length=len(prompt),
                success=False,
                execution_time=execution_time,
                error=f"Model retry: {str(e)}",
                request_id=request_id
            )
            story_logger.log_error(
                error_type="model_retry",
                error_message=str(e),
                context={"expected_pages": expected_pages},
                user_id=story_params.get('user_id', 0),
                request_id=request_id
            )
            raise
        except Exception as e:
            execution_time = time.time() - start_time
            story_logger.log_ai_interaction(
                agent_type="story_generator",
                prompt_length=len(prompt),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            story_logger.log_error(
                error_type="story_generation_error",
                error_message=str(e),
                context={"expected_pages": expected_pages, "story_params": story_params},
                user_id=story_params.get('user_id', 0),
                request_id=request_id
            )
            # Fallback to simplified story structure
            return self._create_fallback_story(story_params, request_id)
    
    def _create_fallback_story(self, story_params: dict, request_id: str = None) -> List[Dict]:
        """Create a meaningful fallback story if AI generation fails"""
        page_count = max(2, int(story_params['reading_time']))
        hero_name = story_params['hero_name']
        hero_age = story_params.get('hero_age', 5)
        theme = story_params['theme']
        min_words, max_words = self.get_age_appropriate_word_count(hero_age)
        
        # Create a simple but meaningful story about kindness and helping others
        # Ensure text meets age-appropriate word count ({min_words}-{max_words} words)
        pages = []
        for i in range(page_count):
            if i == 0:
                if max_words >= 80:
                    text = f"Meet {hero_name}, a wonderful {hero_age}-year-old who loves exploring and helping others. One beautiful day, {hero_name} decided to go on a special {theme} adventure to spread kindness and make new friends. The sun was shining brightly, birds were singing cheerfully, and {hero_name} felt excited about all the wonderful things that might happen on this magical journey."
                else:
                    text = f"Meet {hero_name}, a wonderful {hero_age}-year-old who loves helping others. Today, {hero_name} goes on a {theme} adventure to make new friends!"
                image_desc = f"A happy {hero_age}-year-old child named {hero_name} with a bright smile, wearing colorful adventure clothes, standing in a magical {theme}-themed setting with warm, inviting colors"
            elif i == page_count - 1:
                if max_words >= 80:
                    text = f"{hero_name} smiled with joy, feeling proud of all the kind acts and new friendships made during this wonderful {theme} adventure. {hero_name} learned that the best adventures happen when we help others and spread happiness wherever we go. What a magical day it had been! {hero_name} couldn't wait to tell everyone about all the wonderful friends made and kindness shared."
                else:
                    text = f"{hero_name} smiled with joy! The {theme} adventure was amazing. {hero_name} made new friends and helped others. What a wonderful day!"
                image_desc = f"{hero_name} beaming with happiness, surrounded by new friends in a beautiful {theme} setting, with warm golden light showing the joy of friendship and kindness"
            else:
                middle_actions = [
                    f"Along the way, {hero_name} met someone who needed help and offered a helping hand with a warm smile. The act of kindness made both {hero_name} and the new friend feel wonderfully happy.",
                    f"{hero_name} discovered that being brave and kind creates the most amazing adventures. Every person {hero_name} helped became a new friend, making the {theme} journey even more special.",
                    f"With each step, {hero_name} found new ways to spread joy and kindness. The {theme} world seemed to sparkle brighter with every good deed and every new friendship that bloomed."
                ]
                text = middle_actions[min(i-1, len(middle_actions)-1)]
                image_desc = f"{hero_name} interacting kindly with a friend in a beautiful {theme} environment, showing warmth, friendship, and the magic of caring for others"
            
            page = {
                "page_number": i + 1,
                "text": text,
                "choices": None,
                "image_description": image_desc,
                "image_url": None
            }
            pages.append(page)
        
        story_logger.log_user_action(
            user_id=story_params.get('user_id', 0),
            action="fallback_story_created",
            details={
                "pages_count": len(pages),
                "reason": "ai_generation_failed",
                "theme": "kindness_and_friendship"
            },
            request_id=request_id
        )
        
        return pages
    
    async def create_image_prompt(self, page_text: str, story_params: dict, 
                                image_description: str = None, request_id: str = None) -> str:
        """Generate an image prompt from page text"""
        if not request_id:
            request_id = str(uuid.uuid4())
            
        if image_description:
            base_description = image_description
        else:
            base_description = f"Scene from a {story_params['theme']} children's story featuring {story_params['hero_name']}"
        
        prompt = f"""Create a DALL-E image prompt for this children's story illustration:

Story Context:
- Theme: {story_params['theme']}
- Hero: {story_params['hero_name']} (age {story_params['hero_age']})
- Base description: {base_description}
- Page text excerpt: {page_text[:200]}...

Create a detailed, child-friendly image prompt that captures the magical essence of this scene. Include art style suggestions and ensure the content is completely appropriate for children."""
        
        start_time = time.time()
        
        try:
            result = await self.image_prompt_agent.run(prompt)
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="image_prompt_generator",
                prompt_length=len(prompt),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            return result.output
        except Exception as e:
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="image_prompt_generator",
                prompt_length=len(prompt),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            
            story_logger.log_error(
                error_type="image_prompt_generation_error",
                error_message=str(e),
                context={"page_text_length": len(page_text)},
                request_id=request_id
            )
            
            # Fallback to simple description
            fallback_prompt = f"Colorful children's book illustration of {story_params['hero_name']} in a {story_params['theme']} adventure, digital art style, bright and cheerful"
            
            story_logger.log_user_action(
                user_id=story_params.get('user_id', 0),
                action="image_prompt_fallback_used",
                details={"reason": str(e)},
                request_id=request_id
            )
            
            return fallback_prompt
    
    async def optimize_image_for_web(self, image_url: str, request_id: str = None) -> str:
        """Optimize image through Cloudinary for faster web loading"""
        try:
            # Upload to Cloudinary with optimization
            result = cloudinary.uploader.upload(
                image_url,
                quality="auto:good",  # Automatic quality optimization
                fetch_format="auto",  # Automatic format selection (WebP, AVIF)
                width=800,  # Resize for web display
                height=800,
                crop="fill",  # Maintain aspect ratio
                gravity="center",
                flags="progressive"  # Progressive loading
            )
            
            # Return optimized URL
            optimized_url = result.get('secure_url', image_url)
            
            story_logger.log_user_action(
                user_id=0,
                action="image_optimized",
                details={
                    "original_url": image_url,
                    "optimized_url": optimized_url,
                    "file_size_bytes": result.get('bytes', 0)
                },
                request_id=request_id
            )
            
            return optimized_url
            
        except Exception as e:
            story_logger.log_error(
                error_type="image_optimization_failed",
                error_message=str(e),
                context={"original_url": image_url},
                request_id=request_id
            )
            # Return original URL if optimization fails
            return image_url
    
    def get_age_appropriate_word_count(self, age: int) -> tuple[int, int]:
        """Calculate appropriate word count range based on child's age"""
        if age <= 3:
            return (20, 40)   # Very simple, few words
        elif age <= 5:
            return (40, 80)   # Simple sentences
        elif age <= 7:
            return (80, 120)  # Short paragraphs
        elif age <= 9:
            return (120, 180) # Longer paragraphs
        elif age <= 12:
            return (180, 250) # More complex stories
        else:
            return (200, 300) # Young adult level
    
    async def generate_image(self, image_prompt: str, story_params: dict, 
                           consistency_details: dict = None, request_id: str = None) -> str:
        """Generate an image using DALL-E 3 with consistency emphasis"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Build consistent prompt with character and setting details
        consistent_prompt = self._build_consistent_prompt(image_prompt, story_params, consistency_details)
        
        start_time = time.time()
        
        try:
            story_logger.log_ai_interaction(
                agent_type="image_generator",
                prompt_length=len(consistent_prompt),
                success=True,
                request_id=request_id
            )
            
            # Add timeout to prevent hanging (60 seconds for DALL-E)
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        self.image_client.images.generate,
                        model=self.image_deployment,
                        prompt=consistent_prompt,
                        n=1,
                        style="vivid",
                        quality="hd",  # Higher quality for better consistency
                        size="1024x1024"  # Square format for better UI display
                    ),
                    timeout=120.0  # 60 second timeout
                )
            except asyncio.TimeoutError:
                raise Exception("Image generation timed out after 60 seconds")
            
            execution_time = time.time() - start_time
            raw_image_url = json.loads(result.model_dump_json())['data'][0]['url']
            
            # Optimize image for faster web loading
            optimized_image_url = await self.optimize_image_for_web(raw_image_url, request_id)
            
            story_logger.log_ai_interaction(
                agent_type="image_generator",
                prompt_length=len(consistent_prompt),
                success=True,
                execution_time=execution_time,
                request_id=request_id
            )
            
            story_logger.log_user_action(
                user_id=story_params.get('user_id', 0),
                action="image_generated",
                details={
                    "raw_image_url": raw_image_url,
                    "optimized_image_url": optimized_image_url,
                    "execution_time": execution_time
                },
                request_id=request_id
            )
            
            return optimized_image_url
            
        except Exception as e:
            execution_time = time.time() - start_time
            
            story_logger.log_ai_interaction(
                agent_type="image_generator",
                prompt_length=len(consistent_prompt),
                success=False,
                execution_time=execution_time,
                error=str(e),
                request_id=request_id
            )
            
            story_logger.log_error(
                error_type="image_generation_error",
                error_message=str(e),
                context={"story_params": story_params},
                user_id=story_params.get('user_id', 0),
                request_id=request_id
            )
            
            raise
    
    def _build_consistent_prompt(self, base_prompt: str, story_params: dict, 
                               consistency_details: dict = None) -> str:
        """Build a consistent image prompt with character and setting details"""
        
        # Define consistent character appearance
        hero_name = story_params['hero_name']
        hero_age = story_params['hero_age']
        theme = story_params['theme']
        
        # Base consistency details for the story
        if not consistency_details:
            consistency_details = {
                "character_description": f"a {hero_age}-year-old child with friendly features",
                "art_style": "colorful digital illustration, children's book art style",
                "color_palette": "bright, warm, and cheerful colors",
                "mood": "magical and whimsical"
            }
        
        # Build the enhanced prompt with strong consistency emphasis
        consistent_prompt = f"""{base_prompt}

CHARACTER CONSISTENCY - CRITICAL:
{consistency_details.get('character_details', f'Show the same child {hero_name} in every image')}

VISUAL SPECIFICATIONS:
- Art style: {consistency_details.get('art_style', 'consistent digital illustration, children book art style')}
- Colors: {consistency_details.get('color_palette', 'bright, warm colors with consistent lighting')}
- Mood: {consistency_details.get('mood', 'cheerful and child-friendly')}
- Theme: {theme} adventure setting with appropriate props and background

CONSISTENCY REQUIREMENTS:
- {consistency_details.get('consistency_note', f'Keep {hero_name} looking identical in all images')}
- Same facial features, hair style, and clothing throughout the story
- Consistent artistic style and color scheme
- High-quality children's book illustration

Quality: Professional children's book illustration, engaging and safe for kids."""
        
        return consistent_prompt
    
    def extract_consistency_details(self, story_structure: StoryStructure, story_params: dict) -> dict:
        """Extract detailed consistency details for highly consistent character appearance"""
        hero_age = story_params['hero_age']
        hero_name = story_params['hero_name']
        
        # Create detailed character description based on age
        if hero_age <= 3:
            character_desc = f"a very young toddler named {hero_name}, chubby cheeks, large round eyes, curly hair, wearing simple colorful clothes"
        elif hero_age <= 5:
            character_desc = f"a {hero_age}-year-old child named {hero_name}, round face, bright curious eyes, shoulder-length hair, wearing a bright colored t-shirt and shorts"
        elif hero_age <= 8:
            character_desc = f"a {hero_age}-year-old child named {hero_name}, friendly smile, medium-length brown hair, wearing an adventure outfit with a small backpack"
        else:
            character_desc = f"a {hero_age}-year-old child named {hero_name}, confident expression, neat hair, wearing practical adventure clothing"
            
        return {
            "character_description": character_desc,
            "character_details": f"ALWAYS show the same child - {character_desc}. Keep the character's appearance EXACTLY the same in every image",
            "art_style": "consistent digital illustration style, children's book art, same artistic technique throughout",
            "color_palette": "warm, bright colors - consistent lighting and color scheme",
            "mood": "cheerful, magical, and child-friendly atmosphere",
            "consistency_note": f"CRITICAL: The main character {hero_name} must look identical in every image - same face, same hair, same clothing style",
            "story_title": story_structure.title
        }
    
    async def generate_complete_story_with_images(self, story_params: dict, request_id: str = None) -> List[Dict]:
        """Generate a complete story with images for each page"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Generate the story structure first
        pages = await self.generate_story(story_params, request_id)
        
        # Extract consistency details for image generation
        story_structure = StoryStructure(
            title=f"{story_params['hero_name']}'s {story_params['theme']} Adventure",
            pages=[StoryPage(**page) for page in pages],
            total_pages=len(pages)
        )
        consistency_details = self.extract_consistency_details(story_structure, story_params)
        
        # Generate images for each page with better error handling
        for page in pages:
            page_number = page.get('page_number', 'unknown')
            try:
                if page.get('image_description'):
                    story_logger.log_user_action(
                        user_id=story_params.get('user_id', 0),
                        action="page_image_generation_started",
                        details={"page_number": page_number},
                        request_id=request_id
                    )
                    
                    # Create enhanced image prompt
                    image_prompt = await self.create_image_prompt(
                        page['text'], 
                        story_params, 
                        page['image_description'], 
                        request_id
                    )
                    
                    # Generate the image with consistency and timeout
                    image_url = await self.generate_image(
                        image_prompt, 
                        story_params, 
                        consistency_details, 
                        request_id
                    )
                    
                    page['image_url'] = image_url
                    
                    story_logger.log_user_action(
                        user_id=story_params.get('user_id', 0),
                        action="page_image_generated",
                        details={
                            "page_number": page_number,
                            "image_url": image_url
                        },
                        request_id=request_id
                    )
                else:
                    page['image_url'] = None
                    
            except asyncio.TimeoutError as e:
                story_logger.log_error(
                    error_type="page_image_generation_timeout",
                    error_message=f"Image generation timed out for page {page_number}: {str(e)}",
                    context={
                        "page_number": page_number,
                        "timeout_seconds": 60
                    },
                    user_id=story_params.get('user_id', 0),
                    request_id=request_id
                )
                page['image_url'] = None
                
            except Exception as e:
                story_logger.log_error(
                    error_type="page_image_generation_failed",
                    error_message=f"Image generation failed for page {page_number}: {str(e)}",
                    context={
                        "page_number": page_number,
                        "error_type": type(e).__name__
                    },
                    user_id=story_params.get('user_id', 0),
                    request_id=request_id
                )
                # Continue with other pages even if one image fails
                page['image_url'] = None
        
        story_logger.log_user_action(
            user_id=story_params.get('user_id', 0),
            action="complete_story_with_images_generated",
            details={
                "total_pages": len(pages),
                "images_generated": sum(1 for p in pages if p.get('image_url')),
                "story_title": story_structure.title
            },
            request_id=request_id
        )
        
        return pages
    
    async def generate_complete_story_with_images_and_moderation(self, story_params: dict, 
                                                               content_moderator=None, 
                                                               request_id: str = None) -> List[Dict]:
        """Generate a complete story with images and content moderation"""
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Generate the story with images first
        pages = await self.generate_complete_story_with_images(story_params, request_id)
        
        # If content moderator is provided, validate all pages
        if content_moderator:
            story_logger.log_user_action(
                user_id=story_params.get('user_id', 0),
                action="story_moderation_started",
                details={"total_pages": len(pages)},
                request_id=request_id
            )
            
            try:
                moderation_results = await content_moderator.moderate_complete_story(
                    pages, 
                    user_id=story_params.get('user_id', 0), 
                    request_id=request_id
                )
                
                # Add moderation results to the response
                for page in pages:
                    page_moderation = next(
                        (r for r in moderation_results["page_results"] 
                         if r["page_number"] == page["page_number"]), 
                        None
                    )
                    if page_moderation:
                        page["moderation"] = {
                            "safe": page_moderation["safe"],
                            "reason": page_moderation["reason"],
                            "concerns": page_moderation["concerns"]
                        }
                
                story_logger.log_user_action(
                    user_id=story_params.get('user_id', 0),
                    action="story_moderation_completed",
                    details={
                        "overall_safe": moderation_results["overall_safe"],
                        "total_pages": moderation_results["total_pages"],
                        "concerns_count": len(moderation_results["concerns"])
                    },
                    request_id=request_id
                )
                
            except Exception as e:
                story_logger.log_error(
                    error_type="story_moderation_integration_error",
                    error_message=str(e),
                    context={"story_params": story_params},
                    user_id=story_params.get('user_id', 0),
                    request_id=request_id
                )
                # Continue without moderation if it fails
                pass
        
        return pages