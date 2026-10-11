"""
ReimagineAI - OpenAI Service
Handles interactions with OpenAI APIs (chat completions and vision)
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
        image_base64: Optional[str] = None,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Get a chat completion from GPT-4, optionally with an image.
        response_format is passed through to the API when given
        (e.g. {"type": "json_object"} for JSON mode).
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
            
            extra_args: Dict[str, Any] = {}
            if response_format is not None:
                extra_args["response_format"] = response_format

            response = await self.client.chat.completions.create(
                model=self.gpt_model,
                messages=formatted_messages,
                max_tokens=1500,
                temperature=0.7,
                **extra_args,
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"Error in chat completion: {e}")
            raise

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
