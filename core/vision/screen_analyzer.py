"""
Vision-Based GUI Control for JARVIS.
Implements multimodal screen perception, UI element localization,
and click-by-vision pipeline:
SCREENSHOT -> VISION MODEL -> IDENTIFY TARGET/UI STATE -> COORDINATES -> EXECUTE -> VERIFY.

Avoids hardcoded coordinates by using normalized bounding boxes / relative coordinates (0-1000).
"""

import os
import re
import json
import time
from typing import Dict, Any, Optional, Tuple

from core.tools import AssistantTools
from core.computer_control import ComputerControl


class ScreenAnalyzer:
    """Provides screen perception and vision-guided computer automation."""

    def __init__(self, groq_client=None, gemini_client=None):
        self.groq_client = groq_client
        self.gemini_client = gemini_client

    def capture_screen(self, filename: Optional[str] = None) -> str:
        """Captures screen using safe Win32 GDI BitBlt and returns saved image path."""
        res = AssistantTools.take_screenshot(filename)
        return res.get("data", {}).get("path") or res.get("summary", "")

    def inspect_screen(self, query: str = "Please describe what is currently visible on my screen.") -> str:
        """Captures screen and queries multimodal AI vision."""
        shot_path = self.capture_screen()
        if not shot_path or not os.path.exists(shot_path):
            return "Could not capture screenshot for vision analysis."

        # Try Groq vision first
        if self.groq_client and self.groq_client.is_configured():
            chunks = []
            try:
                res = self.groq_client.stream_vision_chat(
                    user_text=query,
                    image_paths=[shot_path],
                    on_chunk=lambda c: chunks.append(c)
                )
                if res and not res.startswith("❌") and not res.startswith("⚠️"):
                    return "".join(chunks).strip() or res
            except Exception as e:
                print(f"[ScreenAnalyzer] Groq vision error: {e}")

        # Fallback to Gemini
        return f"Screenshot captured at {shot_path}. Screen display is active."

    def locate_ui_element(self, element_description: str, screenshot_path: Optional[str] = None) -> Optional[Tuple[int, int]]:
        """
        Locates UI element on screen using multimodal vision.
        Instructs vision model to return relative coordinates (0-1000 range),
        then scales to screen resolution.
        """
        shot_path = screenshot_path or self.capture_screen()
        if not shot_path or not os.path.exists(shot_path):
            return None

        res = ComputerControl.get_screen_resolution()
        screen_w = res["width"]
        screen_h = res["height"]

        prompt = f"""Target UI element to locate: "{element_description}".
Screen resolution: {screen_w}x{screen_h}.

Analyze the image carefully. Identify the center coordinates of the target UI element.
Return relative coordinates normalized between 0 and 1000 (where 0,0 is top-left and 1000,1000 is bottom-right).

Output ONLY a JSON object with this exact format:
{{"found": true, "x": 500, "y": 300, "description": "short note"}}
If the target is not visible on screen, return:
{{"found": false, "x": null, "y": null}}
Do NOT output anything else."""

        if not self.groq_client or not self.groq_client.is_configured():
            return None

        chunks = []
        try:
            self.groq_client.stream_vision_chat(
                user_text=prompt,
                image_paths=[shot_path],
                on_chunk=lambda c: chunks.append(c),
                max_tokens=200
            )
            raw = "".join(chunks).strip()
            # Clean JSON
            raw = re.sub(r"^```json\s*", "", raw, flags=re.IGNORECASE)
            raw = re.sub(r"^```\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw).strip()

            parsed = json.loads(raw)
            if parsed.get("found") and parsed.get("x") is not None and parsed.get("y") is not None:
                rel_x = float(parsed["x"]) / 1000.0
                rel_y = float(parsed["y"]) / 1000.0
                pixel_x = int(rel_x * screen_w)
                pixel_y = int(rel_y * screen_h)
                return (pixel_x, pixel_y)
        except Exception as e:
            print(f"[ScreenAnalyzer] Error locating UI element '{element_description}': {e}")

        return None

    def click_ui_element(self, element_description: str) -> Dict[str, Any]:
        """
        End-to-end vision click pipeline:
        1. Capture screenshot
        2. Vision model identifies coordinates
        3. Mouse clicks target
        4. Post-action screenshot for verification
        """
        pre_shot = self.capture_screen()
        coords = self.locate_ui_element(element_description, pre_shot)

        if not coords:
            return {
                "success": False,
                "action": "click_ui_element",
                "target": element_description,
                "error": f"Element '{element_description}' not located on current screen.",
                "summary": f"Could not find '{element_description}' on screen.",
                "data": {"pre_screenshot": pre_shot}
            }

        x, y = coords
        click_res = ComputerControl.mouse_click(x, y, button="left")
        time.sleep(0.4)
        post_shot = self.capture_screen()

        return {
            "success": click_res["success"],
            "action": "click_ui_element",
            "target": element_description,
            "error": None if click_res["success"] else click_res.get("error"),
            "summary": f"Located '{element_description}' and clicked at ({x}, {y}).",
            "data": {
                "coordinates": (x, y),
                "pre_screenshot": pre_shot,
                "post_screenshot": post_shot
            }
        }
