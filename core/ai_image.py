import os
import re
import time
import requests
from pathlib import Path
from urllib.parse import quote

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"

STYLE_ENHANCEMENTS = {
    "photorealistic": "photorealistic, 8k uhd, highly detailed, professional DSLR photography, sharp focus, cinematic lighting",
    "photo": "realistic photo, 8k, natural lighting, high resolution, detailed texture",
    "anime": "anime style, makoto shinkai, studio ghibli, vibrant vivid colors, clean linework",
    "cyberpunk": "cyberpunk aesthetic, neon holographic lights, futuristic dark city, octane render",
    "3d": "3D render, Unreal Engine 5, volumetric lighting, raytraced, 8k CGI",
    "sketch": "fine graphite pencil sketch, detailed crosshatching, hand drawn on paper, artistic monochrome",
    "watercolor": "delicate watercolor painting, soft fluid washes, expressive pigment, fine art paper",
    "oil painting": "rich textured oil painting, visible impasto brushstrokes, classical masterpiece, dramatic chiaroscuro",
    "fantasy": "epic high fantasy illustration, ethereal magical glow, majestic atmosphere, digital concept art",
    "minimalist": "minimalist aesthetic, clean geometry, elegant modern composition, subtle palette",
    "cinematic": "cinematic film still, 35mm lens, depth of field, dramatic color grading, anamorphic flare",
}

class AIImageEngine:
    """
    Autonomous AI image generation and enhancement engine using FLUX / Pollinations.
    Free, high-speed, and production-grade without requiring third-party API keys.
    """

    def __init__(self, output_dir: str = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).resolve().parent.parent / "documents" / "output" / "ai_images"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_image(self, prompt: str, style: str = "", width: int = 1024, height: int = 768) -> dict:
        """
        Generates an AI image from a text prompt with optional style enhancement.
        Saves locally and returns path for immediate rendering in JARVIS UI.
        """
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No prompt provided."}

        clean_prompt = prompt.strip()

        # Enhance with chosen style keywords
        enhanced_prompt = clean_prompt
        matched_style = None

        if style:
            s_key = style.lower().strip()
            if s_key in STYLE_ENHANCEMENTS:
                enhanced_prompt = f"{clean_prompt}, {STYLE_ENHANCEMENTS[s_key]}"
                matched_style = s_key
            else:
                enhanced_prompt = f"{clean_prompt}, {style}, highly detailed"
                matched_style = style
        else:
            # Check if any style keywords are naturally embedded in the user prompt
            p_lower = clean_prompt.lower()
            for key, enhancement in STYLE_ENHANCEMENTS.items():
                if re.search(rf"\b{re.escape(key)}\b", p_lower):
                    enhanced_prompt = f"{clean_prompt}, {enhancement}"
                    matched_style = key
                    break
            if not matched_style:
                enhanced_prompt = f"{clean_prompt}, high quality, detailed, 8k"

        seed = int(time.time() * 1000) % 10000000
        encoded_prompt = quote(enhanced_prompt)
        url = f"{POLLINATIONS_BASE}/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={seed}"

        try:
            resp = requests.get(url, timeout=45)
            if resp.status_code == 200 and len(resp.content) > 1000:
                slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', clean_prompt[:28].lower()).strip('_') or "ai_image"
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"{slug}_{timestamp}.jpg"
                out_path = self.output_dir / filename

                with open(out_path, "wb") as f:
                    f.write(resp.content)

                style_label = f" ({matched_style.title()} style)" if matched_style else ""
                return {
                    "success": True,
                    "action": "generate_ai_image",
                    "prompt": clean_prompt,
                    "style": matched_style or "default",
                    "output_path": str(out_path.resolve()),
                    "file_size": out_path.stat().st_size,
                    "summary": f"Created AI image{style_label}: '{filename}' for \"{clean_prompt}\"."
                }
            else:
                return {
                    "success": False,
                    "error": f"Image generation service returned status {resp.status_code}.",
                    "summary": "Could not generate AI image at this time."
                }
        except requests.exceptions.Timeout:
            return {"success": False, "error": "Image generation timed out after 45s."}
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global singleton
ai_image_engine = AIImageEngine()
