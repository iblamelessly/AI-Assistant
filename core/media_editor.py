import os
import re
import sys
import time
import shutil
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageDraw, ImageFont

class MediaEditor:
    """
    Autonomous Image and Video Editing Engine for Jarvis.
    Supports:
    - Image Editing: Resize, Crop, Rotate, Flip, Color Adjustments, Artistic Filters,
      Watermarks/Text overlay, Format Conversion, and Optimization.
    - Video Editing: Trimming, Resizing, Audio Extraction (MP3), Muting, Frame Extraction
      (Snapshot), Format Conversion (MP4/GIF), and Speed Adjustment.
    - Safe non-destructive processing: always preserves source files and outputs to dedicated media directory.
    """

    SUPPORTED_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tiff"}
    SUPPORTED_VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".avi", ".webm", ".flv", ".wmv", ".m4v"}

    def __init__(self, base_output_dir: str = None):
        self.workspace_dir = Path(os.getcwd())
        self.output_dir = Path(base_output_dir) if base_output_dir else self.workspace_dir / "media" / "output"
        self.uploads_dir = self.workspace_dir / "media" / "uploads"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.uploads_dir.mkdir(parents=True, exist_ok=True)
        self._ffmpeg_bin = None

    def get_ffmpeg_bin(self) -> Optional[str]:
        """Locates embedded or system FFmpeg binary."""
        if self._ffmpeg_bin and os.path.exists(self._ffmpeg_bin):
            return self._ffmpeg_bin

        # 1. Try imageio_ffmpeg
        try:
            import imageio_ffmpeg
            exe = imageio_ffmpeg.get_ffmpeg_exe()
            if exe and os.path.exists(exe):
                self._ffmpeg_bin = exe
                return self._ffmpeg_bin
        except Exception:
            pass

        # 2. Try system PATH
        sys_ffmpeg = shutil.which("ffmpeg")
        if sys_ffmpeg:
            self._ffmpeg_bin = sys_ffmpeg
            return self._ffmpeg_bin

        # 3. Check common Windows installation paths
        common_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin" / "ffmpeg.exe",
            Path("C:/ffmpeg/bin/ffmpeg.exe"),
            Path("C:/Program Files/ffmpeg/bin/ffmpeg.exe")
        ]
        for p in common_paths:
            if p.exists():
                self._ffmpeg_bin = str(p)
                return self._ffmpeg_bin

        return None

    def _generate_output_path(self, source_path: str, action: str, ext: str = None) -> Path:
        """Generates unique, timestamped output filename preserving source stem."""
        src = Path(source_path)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        target_ext = ext if ext else src.suffix
        if not target_ext.startswith("."):
            target_ext = f".{target_ext}"
        out_name = f"{src.stem}_{action}_{timestamp}{target_ext}"
        return self.output_dir / out_name

    # =========================================================================
    # IMAGE EDITING OPERATIONS
    # =========================================================================

    def resize_image(self, image_path: str, width: int, height: int = None, output_path: str = None) -> Dict[str, Any]:
        """Resizes image to specified dimensions. If height is None, maintains aspect ratio."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            with Image.open(src) as img:
                orig_w, orig_h = img.size
                if height is None:
                    aspect = orig_h / orig_w
                    new_h = max(1, int(width * aspect))
                    new_w = width
                else:
                    new_w, new_h = width, height

                resized = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                dest = Path(output_path) if output_path else self._generate_output_path(src, f"resized_{new_w}x{new_h}")
                resized.save(dest, quality=95)

            return {
                "success": True,
                "action": "resize_image",
                "original_dimensions": f"{orig_w}x{orig_h}",
                "new_dimensions": f"{new_w}x{new_h}",
                "output_path": str(dest),
                "summary": f"Resized image from {orig_w}x{orig_h} to {new_w}x{new_h}. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to resize image: {e}"}

    def crop_image(self, image_path: str, left: int, top: int, right: int, bottom: int, output_path: str = None) -> Dict[str, Any]:
        """Crops image within specified pixel bounding box (left, top, right, bottom)."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            with Image.open(src) as img:
                orig_w, orig_h = img.size
                # Boundary clamping
                l = max(0, min(orig_w - 1, left))
                t = max(0, min(orig_h - 1, top))
                r = max(l + 1, min(orig_w, right))
                b = max(t + 1, min(orig_h, bottom))

                cropped = img.crop((l, t, r, b))
                dest = Path(output_path) if output_path else self._generate_output_path(src, f"crop_{r-l}x{b-t}")
                cropped.save(dest, quality=95)

            return {
                "success": True,
                "action": "crop_image",
                "crop_box": [l, t, r, b],
                "dimensions": f"{r-l}x{b-t}",
                "output_path": str(dest),
                "summary": f"Cropped image to {r-l}x{b-t} px. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to crop image: {e}"}

    def rotate_image(self, image_path: str, degrees: float, output_path: str = None) -> Dict[str, Any]:
        """Rotates image counter-clockwise by specified degrees."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            with Image.open(src) as img:
                # expand=True ensures the entire rotated image fits without cropping corners
                rotated = img.rotate(degrees, expand=True, resample=Image.Resampling.BICUBIC)
                dest = Path(output_path) if output_path else self._generate_output_path(src, f"rot_{int(degrees)}")
                rotated.save(dest, quality=95)

            return {
                "success": True,
                "action": "rotate_image",
                "degrees": degrees,
                "output_path": str(dest),
                "summary": f"Rotated image by {degrees}°. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to rotate image: {e}"}

    def flip_image(self, image_path: str, direction: str = "horizontal", output_path: str = None) -> Dict[str, Any]:
        """Flips image horizontally (mirror) or vertically."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            d = direction.lower().strip()
            method = Image.Transpose.FLIP_LEFT_RIGHT if d in ["horizontal", "h", "left_right", "mirror"] else Image.Transpose.FLIP_TOP_BOTTOM

            with Image.open(src) as img:
                flipped = img.transpose(method)
                dest = Path(output_path) if output_path else self._generate_output_path(src, f"flip_{d}")
                flipped.save(dest, quality=95)

            return {
                "success": True,
                "action": "flip_image",
                "direction": d,
                "output_path": str(dest),
                "summary": f"Flipped image {d}ly. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to flip image: {e}"}

    def apply_filter(self, image_path: str, filter_type: str, output_path: str = None) -> Dict[str, Any]:
        """
        Applies aesthetic or processing filter to image:
        'grayscale', 'sepia', 'blur', 'sharpen', 'edge_enhance', 'contour', 'invert', 'emboss'.
        """
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            f_type = filter_type.lower().strip()

            with Image.open(src) as img:
                # Convert RGBA to RGB for filters that require 3 channels
                orig_mode = img.mode
                work_img = img.convert("RGB") if orig_mode in ["RGBA", "P"] else img

                if f_type in ["grayscale", "gray", "bw", "black and white"]:
                    filtered = ImageOps.grayscale(work_img)
                elif f_type == "sepia":
                    # Classic warm sepia matrix transform
                    gray = ImageOps.grayscale(work_img)
                    filtered = ImageOps.colorize(gray, black="#2e1d0c", white="#ffd599")
                elif f_type in ["blur", "gaussian_blur"]:
                    filtered = work_img.filter(ImageFilter.GaussianBlur(radius=3))
                elif f_type == "sharpen":
                    filtered = work_img.filter(ImageFilter.SHARPEN)
                elif f_type in ["edge_enhance", "edges"]:
                    filtered = work_img.filter(ImageFilter.EDGE_ENHANCE_MORE)
                elif f_type == "contour":
                    filtered = work_img.filter(ImageFilter.CONTOUR)
                elif f_type == "emboss":
                    filtered = work_img.filter(ImageFilter.EMBOSS)
                elif f_type in ["invert", "negative"]:
                    filtered = ImageOps.invert(work_img)
                else:
                    return {"success": False, "error": f"Unknown filter: {filter_type}. Available: grayscale, sepia, blur, sharpen, edge_enhance, contour, emboss, invert."}

                dest = Path(output_path) if output_path else self._generate_output_path(src, f"filter_{f_type}")
                filtered.save(dest, quality=95)

            return {
                "success": True,
                "action": "apply_filter",
                "filter": f_type,
                "output_path": str(dest),
                "summary": f"Applied '{f_type}' filter. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to apply filter: {e}"}

    def adjust_image(
        self,
        image_path: str,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        sharpness: float = 1.0,
        output_path: str = None
    ) -> Dict[str, Any]:
        """Adjusts brightness, contrast, saturation, and sharpness factors (1.0 = normal)."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            with Image.open(src) as img:
                out = img
                if brightness != 1.0:
                    out = ImageEnhance.Brightness(out).enhance(brightness)
                if contrast != 1.0:
                    out = ImageEnhance.Contrast(out).enhance(contrast)
                if saturation != 1.0:
                    out = ImageEnhance.Color(out).enhance(saturation)
                if sharpness != 1.0:
                    out = ImageEnhance.Sharpness(out).enhance(sharpness)

                dest = Path(output_path) if output_path else self._generate_output_path(src, "adjusted")
                out.save(dest, quality=95)

            return {
                "success": True,
                "action": "adjust_image",
                "adjustments": {
                    "brightness": brightness,
                    "contrast": contrast,
                    "saturation": saturation,
                    "sharpness": sharpness
                },
                "output_path": str(dest),
                "summary": f"Adjusted image color/contrast parameters. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to adjust image: {e}"}

    def add_watermark(
        self,
        image_path: str,
        text: str,
        position: str = "bottom-right",
        color: str = "white",
        font_size: int = 28,
        output_path: str = None
    ) -> Dict[str, Any]:
        """Overlays text watermark onto image with subtle drop shadow for readability."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            with Image.open(src).convert("RGBA") as img:
                overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
                draw = ImageDraw.Draw(overlay)

                # Try finding Windows TrueType font, or fallback to default
                font = None
                font_candidates = [
                    Path("C:/Windows/Fonts/arial.ttf"),
                    Path("C:/Windows/Fonts/segoeui.ttf"),
                    Path("C:/Windows/Fonts/calibri.ttf")
                ]
                for fc in font_candidates:
                    if fc.exists():
                        try:
                            font = ImageFont.truetype(str(fc), font_size)
                            break
                        except Exception:
                            pass
                if not font:
                    font = ImageFont.load_default()

                # Calculate text dimensions
                bbox = draw.textbbox((0, 0), text, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]

                margin = 25
                pos = position.lower()
                if "top-left" in pos:
                    x, y = margin, margin
                elif "top-right" in pos:
                    x, y = img.width - tw - margin, margin
                elif "center" in pos:
                    x, y = (img.width - tw) // 2, (img.height - th) // 2
                elif "bottom-left" in pos:
                    x, y = margin, img.height - th - margin
                else: # bottom-right default
                    x, y = img.width - tw - margin, img.height - th - margin

                # Draw subtle shadow for high contrast on any background
                draw.text((x + 2, y + 2), text, font=font, fill=(0, 0, 0, 180))
                draw.text((x, y), text, font=font, fill=(255, 255, 255, 220) if color == "white" else (0, 0, 0, 220))

                watermarked = Image.alpha_composite(img, overlay)
                if src.suffix.lower() in [".jpg", ".jpeg"]:
                    watermarked = watermarked.convert("RGB")

                dest = Path(output_path) if output_path else self._generate_output_path(src, "watermarked")
                watermarked.save(dest, quality=95)

            return {
                "success": True,
                "action": "add_watermark",
                "watermark_text": text,
                "position": position,
                "output_path": str(dest),
                "summary": f"Added watermark '{text}' at {position}. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to add watermark: {e}"}

    def convert_image(self, image_path: str, target_format: str, output_path: str = None) -> Dict[str, Any]:
        """Converts image to target format (png, jpg, webp, bmp, gif)."""
        try:
            src = Path(image_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Image not found: {image_path}"}

            fmt = target_format.lower().lstrip(".")
            with Image.open(src) as img:
                dest = Path(output_path) if output_path else self._generate_output_path(src, "converted", f".{fmt}")
                if fmt in ["jpg", "jpeg"] and img.mode in ["RGBA", "P"]:
                    img = img.convert("RGB")
                img.save(dest, quality=95)

            return {
                "success": True,
                "action": "convert_image",
                "target_format": fmt,
                "output_path": str(dest),
                "summary": f"Converted {src.name} to .{fmt} format. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to convert image: {e}"}

    # =========================================================================
    # VIDEO EDITING OPERATIONS
    # =========================================================================

    def _run_ffmpeg_cmd(self, args: List[str]) -> Tuple[bool, str, str]:
        """Runs ffmpeg command synchronously and captures stdout/stderr."""
        ffmpeg_exe = self.get_ffmpeg_bin()
        if not ffmpeg_exe:
            return False, "", "FFmpeg is not installed. Please wait for FFmpeg setup to finish."

        cmd = [ffmpeg_exe, "-y"] + args
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            if p.returncode == 0:
                return True, p.stdout, p.stderr
            else:
                return False, p.stdout, p.stderr
        except subprocess.TimeoutExpired:
            return False, "", "Video processing timed out after 120 seconds."
        except Exception as e:
            return False, "", str(e)

    def trim_video(self, video_path: str, start_time: str, end_time: str, output_path: str = None) -> Dict[str, Any]:
        """
        Trims video from start_time to end_time.
        Times can be seconds (e.g. '10', '45.5') or timestamp ('00:01:15').
        """
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            dest = Path(output_path) if output_path else self._generate_output_path(src, f"trimmed_{start_time}_to_{end_time}")
            # Use re-encoding for frame-accurate cut
            args = ["-ss", str(start_time), "-to", str(end_time), "-i", str(src), "-c:v", "libx264", "-c:a", "aac", str(dest)]
            ok, out, err = self._run_ffmpeg_cmd(args)

            if not ok or not dest.exists():
                return {"success": False, "error": err or "FFmpeg trimming failed", "summary": f"Failed to trim video: {err}"}

            return {
                "success": True,
                "action": "trim_video",
                "start": start_time,
                "end": end_time,
                "output_path": str(dest),
                "summary": f"Trimmed video from {start_time} to {end_time}. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to trim video: {e}"}

    def resize_video(self, video_path: str, scale_or_width: int = 720, output_path: str = None) -> Dict[str, Any]:
        """Resizes video width to target pixels (e.g. 720, 1080) preserving aspect ratio."""
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            dest = Path(output_path) if output_path else self._generate_output_path(src, f"scaled_{scale_or_width}p")
            vf = f"scale={scale_or_width}:-2"
            args = ["-i", str(src), "-vf", vf, "-c:a", "copy", str(dest)]
            ok, out, err = self._run_ffmpeg_cmd(args)

            if not ok or not dest.exists():
                return {"success": False, "error": err or "FFmpeg scaling failed", "summary": f"Failed to resize video: {err}"}

            return {
                "success": True,
                "action": "resize_video",
                "width": scale_or_width,
                "output_path": str(dest),
                "summary": f"Resized video to width {scale_or_width}px. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to resize video: {e}"}

    def extract_audio(self, video_path: str, format: str = "mp3", output_path: str = None) -> Dict[str, Any]:
        """Extracts audio track from video as MP3 or WAV."""
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            ext = f".{format.lstrip('.')}"
            dest = Path(output_path) if output_path else self._generate_output_path(src, "audio", ext)
            args = ["-i", str(src), "-vn", "-q:a", "2", str(dest)]
            ok, out, err = self._run_ffmpeg_cmd(args)

            if not ok or not dest.exists():
                return {"success": False, "error": err or "Audio extraction failed", "summary": f"Failed to extract audio: {err}"}

            return {
                "success": True,
                "action": "extract_audio",
                "format": format,
                "output_path": str(dest),
                "summary": f"Extracted audio track as {format.upper()}. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to extract audio: {e}"}

    def mute_video(self, video_path: str, output_path: str = None) -> Dict[str, Any]:
        """Removes all audio tracks from video (produces silent video)."""
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            dest = Path(output_path) if output_path else self._generate_output_path(src, "muted")
            args = ["-i", str(src), "-an", "-c:v", "copy", str(dest)]
            ok, out, err = self._run_ffmpeg_cmd(args)

            if not ok or not dest.exists():
                return {"success": False, "error": err or "Muting video failed", "summary": f"Failed to mute video: {err}"}

            return {
                "success": True,
                "action": "mute_video",
                "output_path": str(dest),
                "summary": f"Muted video audio track. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to mute video: {e}"}

    def extract_frame(self, video_path: str, timestamp_sec: float = 0.0, output_path: str = None) -> Dict[str, Any]:
        """Captures a high-resolution snapshot/thumbnail frame from video at timestamp."""
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            dest = Path(output_path) if output_path else self._generate_output_path(src, f"snapshot_{int(timestamp_sec)}s", ".jpg")
            args = ["-ss", str(timestamp_sec), "-i", str(src), "-vframes", "1", "-q:v", "2", str(dest)]
            ok, out, err = self._run_ffmpeg_cmd(args)

            if not ok or not dest.exists():
                return {"success": False, "error": err or "Frame extraction failed", "summary": f"Failed to capture frame: {err}"}

            return {
                "success": True,
                "action": "extract_frame",
                "timestamp": timestamp_sec,
                "output_path": str(dest),
                "summary": f"Captured video snapshot at {timestamp_sec}s. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to extract frame: {e}"}

    def convert_video(self, video_path: str, target_format: str = "mp4", output_path: str = None) -> Dict[str, Any]:
        """Converts video to MP4, GIF, WebM, or MKV."""
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            fmt = target_format.lower().lstrip(".")
            dest = Path(output_path) if output_path else self._generate_output_path(src, "converted", f".{fmt}")

            if fmt == "gif":
                # High quality GIF with palette generation
                args = ["-i", str(src), "-vf", "fps=12,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse", str(dest)]
            else:
                args = ["-i", str(src), str(dest)]

            ok, out, err = self._run_ffmpeg_cmd(args)
            if not ok or not dest.exists():
                return {"success": False, "error": err or "Conversion failed", "summary": f"Failed to convert video: {err}"}

            return {
                "success": True,
                "action": "convert_video",
                "format": fmt,
                "output_path": str(dest),
                "summary": f"Converted video to .{fmt}. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to convert video: {e}"}

    def adjust_video_speed(self, video_path: str, speed: float = 2.0, output_path: str = None) -> Dict[str, Any]:
        """Changes playback speed of video (e.g. 0.5x slow-mo or 2.0x fast-forward)."""
        try:
            src = Path(video_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"Video not found: {video_path}"}

            dest = Path(output_path) if output_path else self._generate_output_path(src, f"speed_{speed}x")
            setpts = 1.0 / speed
            filter_complex = f"[0:v]setpts={setpts}*PTS[v];[0:a]atempo={speed}[a]"
            args = ["-i", str(src), "-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]", str(dest)]
            ok, out, err = self._run_ffmpeg_cmd(args)

            if not ok or not dest.exists():
                return {"success": False, "error": err or "Speed adjustment failed", "summary": f"Failed to adjust video speed: {err}"}

            return {
                "success": True,
                "action": "adjust_video_speed",
                "speed": speed,
                "output_path": str(dest),
                "summary": f"Changed video playback speed to {speed}x. Saved to `{dest.name}`."
            }
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to adjust video speed: {e}"}

    # =========================================================================
    # MEDIA METADATA & INSPECTION
    # =========================================================================

    def inspect_media(self, media_path: str) -> Dict[str, Any]:
        """Inspects media file returning dimensions, format, file size, and attributes."""
        try:
            src = Path(media_path).expanduser().resolve()
            if not src.exists():
                return {"success": False, "error": f"File not found: {media_path}"}

            ext = src.suffix.lower()
            size_kb = round(src.stat().st_size / 1024, 1)

            if ext in self.SUPPORTED_IMAGE_EXTS:
                with Image.open(src) as img:
                    w, h = img.size
                    mode = img.mode
                    fmt = img.format
                return {
                    "success": True,
                    "type": "image",
                    "path": str(src),
                    "name": src.name,
                    "format": fmt,
                    "dimensions": f"{w}x{h}",
                    "width": w,
                    "height": h,
                    "mode": mode,
                    "size_kb": size_kb,
                    "summary": f"Image '{src.name}': {w}x{h} px, format {fmt}, {size_kb} KB."
                }

            if ext in self.SUPPORTED_VIDEO_EXTS:
                return {
                    "success": True,
                    "type": "video",
                    "path": str(src),
                    "name": src.name,
                    "extension": ext,
                    "size_kb": size_kb,
                    "summary": f"Video '{src.name}': {ext.upper()} format, {size_kb} KB."
                }

            return {"success": False, "error": f"Unsupported media format: {ext}"}
        except Exception as e:
            return {"success": False, "error": str(e), "summary": f"Failed to inspect media: {e}"}

# Global singleton instance
media_editor = MediaEditor()
