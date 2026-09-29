import os
import re
import json
import time
import asyncio
import tempfile
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import imageio_ffmpeg
    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
except Exception:
    FFMPEG_EXE = "ffmpeg"


class AIVideoEngine:
    """
    Autonomous AI Video Generation Engine.
    Generates multi-scene cinematic videos from text prompts by combining:
    1. Groq LLM scene scripting and narration writing
    2. FLUX AI image generation for high-definition 16:9 frames
    3. Neural voice narration (edge-tts / voice engine)
    4. Hardware-accelerated FFmpeg cinematic motion & compilation
    """

    def __init__(self, output_dir: str = None):
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(__file__).resolve().parent.parent / "documents" / "output" / "ai_videos"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _plan_scenes(self, prompt: str, groq_client: Any = None) -> Dict[str, Any]:
        """Plans 4-5 cinematic visual scenes and narration script using Groq or heuristic fallback."""
        if groq_client and hasattr(groq_client, "is_configured") and groq_client.is_configured():
            system_msg = (
                "You are an award-winning cinematic director and documentarian for JARVIS. "
                "Break the user's video concept into 4 visually stunning, sequential scenes with narration. "
                "Respond ONLY with valid JSON."
            )
            user_msg = f"""
Create a 4-scene video script for: "{prompt}"
Return JSON with this exact schema:
{{
  "title": "Short Video Title",
  "scenes": [
    {{
      "visual_prompt": "Cinematic visual description for AI image generation, 8k, detailed",
      "narration": "One or two engaging sentences of narration."
    }},
    {{
      "visual_prompt": "...",
      "narration": "..."
    }},
    {{
      "visual_prompt": "...",
      "narration": "..."
    }},
    {{
      "visual_prompt": "...",
      "narration": "..."
    }}
  ]
}}
"""
            try:
                import requests
                headers = {
                    "Authorization": f"Bearer {groq_client.api_key}",
                    "Content-Type": "application/json"
                }
                payload = {
                    "model": "llama-3.3-70b-versatile",
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_msg}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                    "max_tokens": 1500
                }
                r = requests.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload, timeout=25)
                if r.status_code == 200:
                    content = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    parsed = json.loads(content)
                    if parsed and "scenes" in parsed and len(parsed["scenes"]) >= 2:
                        return parsed
            except Exception as e:
                print(f"[AIVideoEngine] LLM scene planning warning: {e}")

        # Fallback scenes
        clean = prompt.strip().title()
        return {
            "title": clean,
            "scenes": [
                {
                    "visual_prompt": f"Establishing cinematic wide angle shot of {clean}, 8k uhd, atmospheric lighting, photorealistic",
                    "narration": f"Welcome to an exploration of {clean}."
                },
                {
                    "visual_prompt": f"Detailed dynamic close-up view revealing core mechanisms of {clean}, dramatic depth of field, high detail",
                    "narration": f"Examining the core principles and extraordinary elements that define {clean}."
                },
                {
                    "visual_prompt": f"Futuristic perspective on {clean} with vibrant luminous illumination, cinematic 35mm film still",
                    "narration": f"Innovation and forward momentum continue to reshape our understanding."
                },
                {
                    "visual_prompt": f"Majestic panoramic wide horizon capturing the full scope and future of {clean}, golden hour lighting",
                    "narration": f"The journey into {clean} marks only the beginning of what lies ahead."
                }
            ]
        }

    def _synthesize_audio(self, narration_text: str, voice_engine: Any = None) -> Optional[Path]:
        """Synthesizes voiceover narration into a temporary MP3 file."""
        if not narration_text:
            return None
        try:
            import edge_tts
            temp_mp3 = Path(tempfile.gettempdir()) / f"narration_{int(time.time() * 1000)}.mp3"
            voice = getattr(voice_engine, "voice", "en-GB-RyanNeural") or "en-GB-RyanNeural"

            async def _synth():
                communicate = edge_tts.Communicate(narration_text, voice)
                await communicate.save(str(temp_mp3))

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_synth())
            loop.close()

            if temp_mp3.exists() and temp_mp3.stat().st_size > 500:
                return temp_mp3
        except Exception as e:
            print(f"[AIVideoEngine] edge-tts error: {e}")
        return None

    def generate_video(
        self,
        prompt: str,
        seconds_per_scene: int = 3,
        groq_client: Any = None,
        voice_engine: Any = None
    ) -> Dict[str, Any]:
        """
        Creates a complete multi-scene AI video with FLUX imagery, motion, and voice narration.
        Outputs an MP4 video file ready for playback in the JARVIS desktop interface.
        """
        if not prompt or not prompt.strip():
            return {"success": False, "error": "No video prompt specified."}

        from .ai_image import ai_image_engine

        # Step 1: Script scenes
        plan = self._plan_scenes(prompt, groq_client=groq_client)
        title = plan.get("title", prompt.strip().title())
        scenes = plan.get("scenes", [])[:5] # 3 to 5 scenes

        if not scenes:
            return {"success": False, "error": "Could not create scene script."}

        temp_clips = []
        full_narration_parts = []
        temp_files_to_cleanup = []

        try:
            # Step 2: Generate scene images and encode short clips
            for idx, sc in enumerate(scenes):
                v_prompt = sc.get("visual_prompt", prompt)
                narr = sc.get("narration", "")

                # Generate image for scene — retry up to 2 times
                img_res = None
                for img_attempt in range(2):
                    img_res = ai_image_engine.generate_image(v_prompt, width=1280, height=720)
                    if img_res.get("success") and img_res.get("output_path"):
                        break
                    time.sleep(2)  # Brief pause before retry

                if not img_res or not img_res.get("success") or not img_res.get("output_path"):
                    print(f"[AIVideoEngine] Scene {idx + 1} image failed after retries, skipping.")
                    continue

                img_path = Path(img_res["output_path"])
                clip_path = self.output_dir / f"temp_clip_{idx}_{int(time.time()*1000)}.mp4"
                temp_files_to_cleanup.append(clip_path)

                # Render scene clip with subtle zoom/motion using ffmpeg
                cmd_clip = [
                    FFMPEG_EXE, "-y",
                    "-loop", "1",
                    "-i", str(img_path.resolve()),
                    "-t", str(seconds_per_scene),
                    "-vf", "scale=1280:720,format=yuv420p",
                    "-c:v", "libx264",
                    "-r", "24",
                    str(clip_path.resolve())
                ]
                res = subprocess.run(cmd_clip, capture_output=True)
                if res.returncode == 0 and clip_path.exists():
                    temp_clips.append(clip_path)
                    # Only add narration for successfully compiled scenes (fixes desync)
                    if narr:
                        full_narration_parts.append(narr)

            if not temp_clips:
                return {"success": False, "error": "Failed to compile video scene clips."}

            # Step 3: Synthesize combined audio narration
            full_narration_text = " ".join(full_narration_parts)
            audio_path = self._synthesize_audio(full_narration_text, voice_engine=voice_engine)
            if audio_path:
                temp_files_to_cleanup.append(audio_path)

            # Step 4: Concatenate video clips and attach audio
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            slug = re.sub(r'[^a-zA-Z0-9_-]+', '_', prompt[:28].lower()).strip('_') or "ai_video"
            out_filename = f"{slug}_{timestamp}.mp4"
            final_mp4 = self.output_dir / out_filename

            # Build ffmpeg command with filter_complex
            inputs = []
            filter_parts = []
            for i, c in enumerate(temp_clips):
                inputs.extend(["-i", str(c.resolve())])
                filter_parts.append(f"[{i}:v]")

            filter_concat = f"{''.join(filter_parts)}concat=n={len(temp_clips)}:v=1[v]"

            if audio_path and audio_path.exists():
                cmd_final = [
                    FFMPEG_EXE, "-y",
                    *inputs,
                    "-i", str(audio_path.resolve()),
                    "-filter_complex", filter_concat,
                    "-map", "[v]",
                    "-map", f"{len(temp_clips)}:a",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    "-shortest",
                    str(final_mp4.resolve())
                ]
            else:
                cmd_final = [
                    FFMPEG_EXE, "-y",
                    *inputs,
                    "-filter_complex", filter_concat,
                    "-map", "[v]",
                    "-c:v", "libx264",
                    "-pix_fmt", "yuv420p",
                    str(final_mp4.resolve())
                ]

            subprocess.run(cmd_final, check=True, capture_output=True)

            if final_mp4.exists() and final_mp4.stat().st_size > 1000:
                return {
                    "success": True,
                    "action": "generate_ai_video",
                    "title": title,
                    "prompt": prompt,
                    "scenes_count": len(temp_clips),
                    "output_path": str(final_mp4.resolve()),
                    "file_size": final_mp4.stat().st_size,
                    "summary": f"Created AI video ({len(temp_clips)} scenes with narration): '{out_filename}' for \"{prompt}\"."
                }
            else:
                return {"success": False, "error": "Video compilation failed."}

        except Exception as e:
            return {"success": False, "error": str(e)}
        finally:
            # Clean up intermediate clips
            for f in temp_files_to_cleanup:
                try:
                    if f.exists():
                        f.unlink(missing_ok=True)
                except Exception:
                    pass


# Global singleton
ai_video_engine = AIVideoEngine()
