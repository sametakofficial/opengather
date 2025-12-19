"""
FFProbe Plugin - Extract media file metadata

Session 11 - Stage: DATA, Mode: per_job
"""
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from archiverr.core.plugins.sdk import OutputPlugin, PluginResult

from .utils.parsers import parse_bitrate, parse_duration, parse_fps, parse_int_safe


class FFProbePlugin(OutputPlugin):
    """
    DATA stage plugin - extracts media metadata using ffprobe.
    
    Provides:
    - job.plugins.ffprobe.video
    - job.plugins.ffprobe.audio
    - job.plugins.ffprobe.container
    """

    def __init__(self, config: dict[str, Any]):
        super().__init__(config)
        self.name = "ffprobe"

    def execute(self, job: Any, services: Any) -> PluginResult:
        """
        Extract media metadata using ffprobe (Session 11 signature).
        
        Args:
            job: JobState with input.value
            services: PluginServices
            
        Returns:
            PluginResult with video, audio, container data
        """
        started_at = datetime.now()

        # Get input path from job
        input_path = job.input.value if hasattr(job.input, 'value') else str(job.input)
        is_virtual = job.input.data.get('source') == 'virtual' if hasattr(job.input, 'data') else False

        # Skip virtual paths - ffprobe cannot analyze non-existent files
        if is_virtual:
            self.debug("Skipping virtual path", path=input_path)
            return self._not_supported_result()

        if not input_path or not Path(input_path).exists():
            return self._error_result()

        try:
            # Run ffprobe
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                input_path
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode != 0:
                return self._error_result()

            data = json.loads(result.stdout)

            self.debug("Analysis complete", streams=len(data.get('streams', [])))

            # Parse streams
            video_stream = None
            audio_streams = []

            for stream in data.get('streams', []):
                if stream.get('codec_type') == 'video' and not video_stream:
                    video_stream = stream
                elif stream.get('codec_type') == 'audio':
                    audio_streams.append(stream)

            # Extract video info
            video = {}
            if video_stream:
                video = {
                    'codec': video_stream.get('codec_name', ''),
                    'codec_long': video_stream.get('codec_long_name', ''),
                    'profile': video_stream.get('profile', ''),
                    'level': video_stream.get('level', ''),
                    'width': parse_int_safe(str(video_stream.get('width', 0))),
                    'height': parse_int_safe(str(video_stream.get('height', 0))),
                    'resolution': f"{video_stream.get('height', 0)}p",
                    'aspect_ratio': video_stream.get('display_aspect_ratio', ''),
                    'bit_depth': parse_int_safe(str(video_stream.get('bits_per_raw_sample', 8)), default=8),
                    'pix_fmt': video_stream.get('pix_fmt', ''),
                    'fps': parse_fps(video_stream.get('r_frame_rate', '0/1')),
                    'duration': parse_duration(str(video_stream.get('duration', 0))),
                    'bitrate': parse_bitrate(str(video_stream.get('bit_rate', 0)))
                }

            # Extract audio info
            audio: list[dict[str, Any]] = []
            for stream in audio_streams:
                audio.append({
                    'codec': stream.get('codec_name', ''),
                    'codec_long': stream.get('codec_long_name', ''),
                    'channels': parse_int_safe(str(stream.get('channels', 0))),
                    'channel_layout': stream.get('channel_layout', ''),
                    'sample_rate': stream.get('sample_rate', ''),
                    'bitrate': parse_bitrate(str(stream.get('bit_rate', 0))),
                    'language': stream.get('tags', {}).get('language', '')
                })

            # Extract container info
            format_info = data.get('format', {})
            container = {
                'format': format_info.get('format_name', ''),
                'duration': parse_duration(str(format_info.get('duration', 0))),
                'size': parse_int_safe(str(format_info.get('size', 0))),
                'bitrate': parse_bitrate(str(format_info.get('bit_rate', 0)))
            }

            # Log extracted info
            if video:
                self.info("Video stream found",
                         codec=video.get('codec'),
                         resolution=f"{video.get('width')}x{video.get('height')}")
            self.debug("Audio streams", count=len(audio))
            self.debug("Container format", format=container.get('format'))

            result_data = {
                'video': video,
                'audio': audio,
                'container': container
            }

            # Update plugin state via services (Session 17: snake_case API)
            if hasattr(services, 'update_plugin'):
                services.update_plugin(data=result_data)

            return PluginResult.success_result(data=result_data, started_at=started_at)

        except Exception as e:
            self.error("FFProbe failed", error=str(e))
            return PluginResult.error_result(str(e), started_at=started_at)

    def _error_result(self) -> PluginResult:
        """Return error result"""
        return PluginResult.error_result("Input path invalid", started_at=datetime.now())

    def _not_supported_result(self) -> PluginResult:
        """Return skipped result for virtual paths"""
        return PluginResult.skipped_result("Virtual path not supported", started_at=datetime.now())
