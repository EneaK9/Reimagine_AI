"""
ReimagineAI - OpenAI Service
Handles all interactions with OpenAI APIs (GPT-4 and DALL-E 3)
"""
import openai
from openai import AsyncOpenAI
from typing import List, Optional, Dict, Any
import base64
import httpx
from ..config import get_settings

settings = get_settings()


class OpenAIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.gpt_model = settings.gpt_model
        
    # ============ System Prompts ============
    
    SYSTEM_PROMPT = """You are ReimagineAI, an expert interior design assistant. Your role is to help users redesign their rooms and spaces.

Your capabilities:
1. Analyze room photos and provide design suggestions
2. Understand user preferences for styles (modern, minimalist, industrial, etc.)
3. Suggest furniture arrangements and color schemes
4. Create detailed prompts for generating redesigned room images

When a user describes changes or uploads a photo:
1. Acknowledge their request
2. Ask clarifying questions if needed (room type, budget, style preference)
3. Provide specific, actionable design suggestions
4. Generate a detailed image prompt for DALL-E to create the redesigned room

Always be:
- Friendly and encouraging
- Specific with design terminology
- Practical with suggestions
- Creative but realistic

When generating image prompts, include:
- Room type and dimensions feel
- Lighting (natural, warm, cool)
- Color palette
- Furniture styles and materials
- Decorative elements
- Atmosphere and mood

Format your response as:
1. Brief acknowledgment of the request
2. Your design suggestions (2-3 bullet points)
3. [IMAGE_PROMPT]: A detailed prompt for generating the redesigned room (this will be used by DALL-E)
"""

    # ============ Chat Completion ============
    
    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        image_base64: Optional[str] = None
    ) -> str:
        """
        Get a chat completion from GPT-4, optionally with an image.
        """
        try:
            # Prepare messages with system prompt
            formatted_messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ]
            
            # Add conversation history (text only - we don't store images in history)
            for msg in messages:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # If there's a new image with the current message, modify the last user message
            if image_base64 and formatted_messages:
                # Find the last user message and add the image to it
                for i in range(len(formatted_messages) - 1, -1, -1):
                    if formatted_messages[i]["role"] == "user":
                        text_content = formatted_messages[i]["content"]
                        formatted_messages[i] = {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": text_content},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/jpeg;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                        break
            
            response = await self.client.chat.completions.create(
                model=self.gpt_model,
                messages=formatted_messages,
                max_tokens=1500,
                temperature=0.7
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error in chat completion: {e}")
            raise
    
    # ============ Image Generation ============
    
    async def generate_room_images(
        self,
        prompt: str,
        num_images: int = 4,
        size: str = "1024x1024",
        quality: str = "standard"
    ) -> List[str]:
        """
        Generate room design images using DALL-E 3.
        Returns list of image URLs.
        
        Note: DALL-E 3 only generates 1 image per request,
        so we make multiple requests for variations.
        """
        image_urls = []
        
        # Enhanced prompt for interior design
        enhanced_prompt = f"""Interior design photograph, professional real estate photography style:
{prompt}

Style: Photorealistic, high-end interior design magazine quality, 
natural lighting, architectural digest style, 8K resolution, 
shot with wide-angle lens, warm and inviting atmosphere."""
        
        try:
            for i in range(num_images):
                # Add slight variation to each prompt
                variation_prompt = enhanced_prompt
                if i > 0:
                    variations = [
                        "from a different angle",
                        "with slightly warmer lighting",
                        "with more emphasis on the seating area",
                        "highlighting the decorative elements"
                    ]
                    variation_prompt += f"\n\nVariation: {variations[i-1]}"
                
                response = await self.client.images.generate(
                    model=self.dalle_model,
                    prompt=variation_prompt,
                    size=size,
                    quality=quality,
                    n=1  # DALL-E 3 only supports n=1
                )
                
                image_urls.append(response.data[0].url)
                
        except Exception as e:
            print(f"Error generating images: {e}")
            raise
        
        return image_urls
    
    # ============ Extract Image Prompt from Chat ============
    
    def extract_image_prompt(self, chat_response: str) -> Optional[str]:
        """
        Extract the [IMAGE_PROMPT] section from the chat response.
        """
        if "[IMAGE_PROMPT]:" in chat_response:
            parts = chat_response.split("[IMAGE_PROMPT]:")
            if len(parts) > 1:
                return parts[1].strip()
        return None
    
    # ============ Analyze Room Image ============
    
    async def analyze_room_image(self, image_base64: str) -> Dict[str, Any]:
        """
        Analyze a room image and return detected elements.
        """
        analysis_prompt = """Analyze this room image and provide:
1. Room type (living room, bedroom, kitchen, etc.)
2. Current style (modern, traditional, etc.)
3. Main furniture pieces visible
4. Color palette
5. Lighting conditions
6. Suggested improvements

Format as JSON."""
        
        try:
            response = await self.client.chat.completions.create(
                model=self.gpt_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": analysis_prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}"
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000
            )
            
            return {"analysis": response.choices[0].message.content}
            
        except Exception as e:
            print(f"Error analyzing image: {e}")
            raise


# Singleton instance
openai_service = OpenAIService()
