"""
ReimagineAI - Gemini Image Service
Uses Google's Gemini API for room redesign (text-and-image-to-image)
"""
import base64
import asyncio
from typing import List, Optional
from google import genai
from google.genai import types
from ..config import get_settings

settings = get_settings()


class GeminiImageService:
    """
    Service for generating room redesigns using Gemini's image editing.
    """
    
    def __init__(self):
        self.api_key = settings.gemini_api_key
        self.model = settings.gemini_model
        if self.api_key:
            self.client = genai.Client(api_key=self.api_key)
        else:
            self.client = None
    
    # Style descriptions for interior design
    STYLES = {
        "modern": "modern interior design with clean lines, minimalist furniture, neutral colors, contemporary lighting",
        "minimalist": "minimalist design with white walls, very simple furniture, lots of empty space, zen atmosphere",
        "industrial": "industrial style with exposed brick, metal pipes, concrete floors, Edison bulbs",
        "scandinavian": "Scandinavian design with light wood, white and gray colors, cozy textiles, hygge feel",
        "bohemian": "bohemian style with colorful textiles, lots of plants, eclectic furniture, artistic vibe",
        "traditional": "traditional design with classic furniture, rich wood, elegant fabrics, timeless elegance",
        "contemporary": "contemporary style with current trends, mixed materials, bold accent colors",
        "rustic": "rustic design with reclaimed wood, natural stone, warm earth tones, cabin feel",
        "futuristic": "futuristic style with sleek white surfaces, LED lighting, high-tech materials, sci-fi aesthetic",
        "mid_century_modern": "mid-century modern with retro furniture, organic shapes, warm wood tones, 1950s-60s aesthetic",
        "coastal": "coastal design with light blues and whites, natural textures, beach-inspired, airy and bright",
        "art_deco": "art deco style with geometric patterns, bold colors, gold accents, glamorous 1920s feel",
    }
    
    async def redesign_room(
        self,
        image_base64: str,
        style: str = "modern",
        custom_prompt: str = "",
        num_outputs: int = 4,
    ) -> List[str]:
        """
        Redesign a room using Gemini's image editing capabilities.
        """
        if not self.client:
            print("Gemini API key not set")
            return []
        
        style_desc = self.STYLES.get(style.lower(), self.STYLES["modern"])
        
        # Build the prompt
        if custom_prompt:
            prompt = f"""Edit this room photo: {custom_prompt}
Apply {style.replace('_', ' ')} interior design style.
Keep the room layout and structure, but transform the style, colors, and furniture.
Make it look like a professional interior design photo."""
        else:
            prompt = f"""Transform this room into {style.replace('_', ' ')} style interior design.
{style_desc}.
Keep the basic room layout and structure, but change the style, colors, furniture, and decor.
Make it look like a professional interior design magazine photo."""
        
        try:
            # Decode the base64 image
            image_bytes = base64.b64decode(image_base64)
            
            # Create image part for Gemini
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            )
            
            results = []
            
            # Generate ONE image to avoid rate limits on free tier
            # If you have billing enabled, increase this
            max_images = min(num_outputs, 1)  # LIMITED TO 1 FOR FREE TIER
            
            for i in range(max_images):
                try:
                    print(f"Generating image {i+1}/{max_images} with model: {self.model}")
                    
                    # Call Gemini with image editing
                    response = self.client.models.generate_content(
                        model=self.model,  # Use model from settings
                        contents=[prompt, image_part],
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                        )
                    )
                    
                    # Extract generated image from response
                    for part in response.candidates[0].content.parts:
                        if part.inline_data is not None:
                            img_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                            mime_type = part.inline_data.mime_type or "image/png"
                            data_url = f"data:{mime_type};base64,{img_base64}"
                            results.append(data_url)
                            print(f"✓ Generated image {i+1}")
                            break
                    
                    # Wait between requests to avoid rate limits
                    if i < max_images - 1:
                        await asyncio.sleep(2)
                            
                except Exception as e:
                    print(f"Gemini generation {i+1} error: {e}")
                    continue
            
            print(f"Generated {len(results)} room redesign images with Gemini")
            return results
            
        except Exception as e:
            print(f"Gemini redesign error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def generate_from_prompt(
        self,
        prompt: str,
        style: str = "modern",
        num_outputs: int = 4,
    ) -> List[str]:
        """
        Generate room design images from text prompt only (no input image).
        """
        if not self.client:
            print("Gemini API key not set")
            return []
        
        style_desc = self.STYLES.get(style.lower(), self.STYLES["modern"])
        
        full_prompt = f"""Generate a professional interior design photograph:
{prompt}

Style: {style_desc}
Quality: Photorealistic, high-end interior design magazine quality, 
natural lighting, architectural digest style, warm and inviting atmosphere."""
        
        results = []
        
        # Generate ONE image to avoid rate limits
        max_images = min(num_outputs, 1)
        
        try:
            for i in range(max_images):
                try:
                    print(f"Generating image {i+1}/{max_images} with model: {self.model}")
                    
                    response = self.client.models.generate_content(
                        model=self.model,
                        contents=[full_prompt],
                        config=types.GenerateContentConfig(
                            response_modalities=["TEXT", "IMAGE"],
                        )
                    )
                    
                    for part in response.candidates[0].content.parts:
                        if part.inline_data is not None:
                            img_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                            mime_type = part.inline_data.mime_type or "image/png"
                            data_url = f"data:{mime_type};base64,{img_base64}"
                            results.append(data_url)
                            print(f"✓ Generated image {i+1}")
                            break
                    
                    if i < max_images - 1:
                        await asyncio.sleep(2)
                            
                except Exception as e:
                    print(f"Gemini text-to-image {i+1} error: {e}")
                    continue
            
            print(f"Generated {len(results)} room images from prompt with Gemini")
            return results
            
        except Exception as e:
            print(f"Gemini text-to-image error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def edit_room(
        self,
        image_base64: str,
        edit_instruction: str,
        style: str = "modern",
    ) -> List[str]:
        """
        Make PRECISE edits to a room image.
        Only changes what the user specifically asks for.
        
        Args:
            image_base64: Base64 encoded image (can be original or previously generated)
            edit_instruction: User's specific request (e.g., "make the walls dark blue")
            style: Optional style hint
        """
        if not self.client:
            print("Gemini API key not set")
            return []
        
        # Create a precise edit prompt - ONLY change what's asked
        prompt = f"""IMPORTANT: Make ONLY the specific change requested. Do NOT change anything else.

User's request: "{edit_instruction}"

Rules:
1. ONLY modify exactly what the user asked for
2. Keep ALL other elements exactly the same (furniture, layout, decorations, lighting)
3. If user says "make walls blue" - ONLY change the walls, nothing else
4. Maintain the exact same room layout, furniture positions, and decorations
5. The result should look like the same room with just that one change

Make the edit now."""
        
        try:
            # Decode the base64 image
            image_bytes = base64.b64decode(image_base64)
            
            # Create image part for Gemini
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/jpeg"
            )
            
            results = []
            
            try:
                print(f"Editing image with instruction: {edit_instruction[:50]}...")
                print(f"Using model: {self.model}")
                
                # Call Gemini with precise edit instruction
                response = self.client.models.generate_content(
                    model=self.model,
                    contents=[prompt, image_part],
                    config=types.GenerateContentConfig(
                        response_modalities=["TEXT", "IMAGE"],
                    )
                )
                
                # Extract generated image from response
                for part in response.candidates[0].content.parts:
                    if part.inline_data is not None:
                        img_base64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                        mime_type = part.inline_data.mime_type or "image/png"
                        data_url = f"data:{mime_type};base64,{img_base64}"
                        results.append(data_url)
                        print(f"✓ Generated edited image")
                        break
                        
            except Exception as e:
                print(f"Gemini edit error: {e}")
            
            print(f"Generated {len(results)} edited images with Gemini")
            return results
            
        except Exception as e:
            print(f"Gemini edit error: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_available_styles(self) -> List[dict]:
        """Get list of available design styles."""
        return [
            {"id": key, "name": key.replace("_", " ").title(), "description": value[:80] + "..."}
            for key, value in self.STYLES.items()
        ]


# Singleton instance
gemini_service = GeminiImageService()
