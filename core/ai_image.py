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

        # Retry loop — 2 attempts with different seeds for reliability
        last_error = "Image generation failed."
        for attempt in range(2):
            attempt_seed = seed + attempt * 7919  # Different seed per retry
            encoded_prompt = quote(enhanced_prompt)
            url = f"{POLLINATIONS_BASE}/{encoded_prompt}?width={width}&height={height}&model=flux&nologo=true&seed={attempt_seed}"

            try:
                resp = requests.get(url, timeout=90)
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
                    last_error = f"Image generation service returned status {resp.status_code}."
            except requests.exceptions.Timeout:
                last_error = f"Image generation timed out (attempt {attempt + 1}/2)."
            except Exception as e:
                last_error = str(e)

        return {"success": False, "error": last_error, "summary": "Could not generate AI image at this time."}

    def alter_image(self, image_path: str, instruction: str) -> dict:
        """
        Alters an existing image based on user instruction using AI style transfer,
        cinematic color grading, and artistic neural-like transformations.
        Supports: cyberpunk, anime, sketch, vintage, oil painting, enhance, noir, warm sunset, cool arctic.
        """
        p = Path(image_path)
        if not p.exists() or not p.is_file():
            return {"success": False, "error": f"Image file not found: '{image_path}'."}

        from PIL import Image, ImageEnhance, ImageFilter, ImageOps
        import numpy as np

        try:
            with Image.open(str(p)) as raw_img:
                img = raw_img.convert("RGB")
        except Exception as e:
            return {"success": False, "error": f"Could not load image: {e}"}

        inst_lower = instruction.lower().strip()
        transformed = img
        applied_style = "enhanced"

        if any(w in inst_lower for w in ["cyberpunk", "neon", "cyber"]):
            applied_style = "cyberpunk"
            # Boost contrast and saturation
            c = ImageEnhance.Contrast(img).enhance(1.35)
            s = ImageEnhance.Color(c).enhance(1.5)
            arr = np.array(s, dtype=np.float32)
            # Tint shadows with dark indigo and highlights with neon cyan/magenta
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            r = np.clip(r * 1.15 + (255 - b) * 0.1, 0, 255)
            b = np.clip(b * 1.35 + (255 - r) * 0.15, 0, 255)
            g = np.clip(g * 0.95 + 10, 0, 255)
            arr = np.stack([r, g, b], axis=2).astype(np.uint8)
            transformed = Image.fromarray(arr).filter(ImageFilter.UnsharpMask(radius=2, percent=130))

        elif any(w in inst_lower for w in ["anime", "cartoon", "manga", "ghibli"]):
            applied_style = "anime"
            # Median smoothing + high color saturation + edge sharpening
            smooth = img.filter(ImageFilter.MedianFilter(size=3))
            c = ImageEnhance.Color(smooth).enhance(1.65)
            b = ImageEnhance.Brightness(c).enhance(1.08)
            transformed = ImageEnhance.Sharpness(b).enhance(1.4)

        elif any(w in inst_lower for w in ["sketch", "pencil", "drawing", "hand drawn"]):
            applied_style = "pencil sketch"
            gray = ImageOps.grayscale(img)
            inv = ImageOps.invert(gray)
            blur = inv.filter(ImageFilter.GaussianBlur(radius=8))
            arr_gray = np.array(gray, dtype=np.float32)
            arr_blur = np.array(blur, dtype=np.float32)
            # Color dodge blend mode
            dodge = np.clip(arr_gray * 255.0 / (256.0 - arr_blur + 1e-5), 0, 255).astype(np.uint8)
            transformed = Image.fromarray(dodge).convert("RGB")

        elif any(w in inst_lower for w in ["vintage", "retro", "sepia", "old photo", "film"]):
            applied_style = "vintage retro"
            # Sepia matrix
            arr = np.array(img, dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            tr = np.clip(r * 0.393 + g * 0.769 + b * 0.189, 0, 255)
            tg = np.clip(r * 0.349 + g * 0.686 + b * 0.168, 0, 255)
            tb = np.clip(r * 0.272 + g * 0.534 + b * 0.131, 0, 255)
            arr = np.stack([tr, tg, tb], axis=2).astype(np.uint8)
            vintage_img = Image.fromarray(arr)
            transformed = ImageEnhance.Contrast(vintage_img).enhance(1.15)

        elif any(w in inst_lower for w in ["oil painting", "painting", "artistic", "paint"]):
            applied_style = "oil painting"
            # Edge enhance + quantize color bands
            smooth = img.filter(ImageFilter.SMOOTH_MORE)
            enhanced = smooth.filter(ImageFilter.EDGE_ENHANCE_MORE)
            c = ImageEnhance.Color(enhanced).enhance(1.4)
            transformed = c.quantize(colors=64).convert("RGB")

        elif any(w in inst_lower for w in ["noir", "black and white", "monochrome", "grayscale"]):
            applied_style = "noir"
            gray = ImageOps.grayscale(img)
            high_c = ImageEnhance.Contrast(gray).enhance(1.55)
            transformed = ImageEnhance.Sharpness(high_c).enhance(1.3).convert("RGB")

        elif any(w in inst_lower for w in ["warm", "sunset", "golden hour"]):
            applied_style = "warm sunset"
            arr = np.array(img, dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            r = np.clip(r * 1.25, 0, 255)
            g = np.clip(g * 1.05, 0, 255)
            b = np.clip(b * 0.82, 0, 255)
            transformed = Image.fromarray(np.stack([r, g, b], axis=2).astype(np.uint8))
            transformed = ImageEnhance.Color(transformed).enhance(1.2)

        elif any(w in inst_lower for w in ["cool", "arctic", "ice", "cold", "blue tone"]):
            applied_style = "cool arctic"
            arr = np.array(img, dtype=np.float32)
            r, g, b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
            r = np.clip(r * 0.82, 0, 255)
            g = np.clip(g * 1.08, 0, 255)
            b = np.clip(b * 1.28, 0, 255)
            transformed = Image.fromarray(np.stack([r, g, b], axis=2).astype(np.uint8))
            transformed = ImageEnhance.Contrast(transformed).enhance(1.15)

        else:
            # Default auto-enhancement: vibrant, sharp, high dynamic range
            applied_style = "vibrant HDR enhancement"
            c = ImageEnhance.Contrast(img).enhance(1.22)
            s = ImageEnhance.Color(c).enhance(1.35)
            transformed = ImageEnhance.Sharpness(s).enhance(1.45)

        # Save altered output image
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', p.stem.lower())
        out_filename = f"{slug}_{applied_style.replace(' ', '_')}_{timestamp}.jpg"
        out_path = self.output_dir / out_filename

        transformed.save(str(out_path), quality=95)

        return {
            "success": True,
            "action": "alter_image",
            "style": applied_style,
            "input_path": str(p.resolve()),
            "output_path": str(out_path.resolve()),
            "file_size": out_path.stat().st_size,
            "summary": f"Altered image with **{applied_style.title()}** style: '{out_filename}'."
        }

# Global singleton
ai_image_engine = AIImageEngine()

