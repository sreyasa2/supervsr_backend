# tasks/stream_manager.py

import logging
import subprocess
import os
import signal
import atexit
import tempfile
import shutil
import time
import json

logger = logging.getLogger(__name__)

class StreamManager:
    def __init__(self):
        self.streams = {}       # stream_id -> rtsp_url
        self.temp_dirs = {}     # stream_id -> temp directory
        self.processes = {}     # stream_id -> subprocess.Popen
        self.stream_status = {} # stream_id -> status info
        
        # Register cleanup on exit
        atexit.register(self.stop_all)

    def _verify_hls_stream(self, stream_id, playlist_path, max_retries=3):
        """Verify HLS stream is working by checking playlist and segments"""
        for attempt in range(max_retries):
            if not os.path.exists(playlist_path):
                logger.warning(f"Attempt {attempt + 1}: Playlist not found for {stream_id}")
                time.sleep(2)
                continue

            # Check if segments are being created
            segments = [f for f in os.listdir(os.path.dirname(playlist_path)) if f.endswith('.ts')]
            if not segments:
                logger.warning(f"Attempt {attempt + 1}: No segments found for {stream_id}")
                time.sleep(2)
                continue

            # Try to read the playlist
            try:
                with open(playlist_path, 'r') as f:
                    content = f.read()
                    if '#EXTM3U' in content and len(segments) > 0:
                        logger.info(f"HLS stream verified for {stream_id}")
                        return True
            except Exception as e:
                logger.error(f"Error reading playlist for {stream_id}: {e}")

            time.sleep(2)

        return False

    def start_stream(self, stream_id, rtsp_url):
        if stream_id in self.streams:
            logger.info(f"Stream {stream_id} already running.")
            return

        # Create temp directory for this stream
        temp_dir = tempfile.mkdtemp(prefix=f'stream_{stream_id}_')
        self.temp_dirs[stream_id] = temp_dir
        self.streams[stream_id] = rtsp_url
        self.stream_status[stream_id] = {"status": "initializing", "error": None}

        # Start FFmpeg process to convert RTSP to HLS
        playlist_path = os.path.join(temp_dir, 'playlist.m3u8')
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', rtsp_url,
            '-c:v', 'copy',  # Copy video stream without re-encoding
            '-c:a', 'aac',   # Convert audio to AAC
            '-f', 'hls',
            '-hls_time', '2',  # 2 second segments
            '-hls_list_size', '3',  # Keep 3 segments
            '-hls_flags', 'delete_segments',  # Delete old segments
            '-hls_segment_type', 'mpegts',  # Use MPEG-TS segments
            '-hls_allow_cache', '0',  # Disable caching
            playlist_path
        ]
        
        try:
            process = subprocess.Popen(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid
            )
            self.processes[stream_id] = process
            
            # Wait for HLS stream to be ready
            if self._verify_hls_stream(stream_id, playlist_path):
                self.stream_status[stream_id] = {"status": "running", "error": None}
                logger.info(f"Started HLS stream for {stream_id}")
                return True
            else:
                raise Exception("Failed to verify HLS stream")
            
        except Exception as e:
            error_msg = f"Failed to start HLS stream for {stream_id}: {e}"
            logger.error(error_msg)
            self.stream_status[stream_id] = {"status": "error", "error": str(e)}
            self.stop_stream(stream_id)
            return False

    def get_stream_status(self, stream_id):
        """Get the current status of a stream"""
        return self.stream_status.get(stream_id, {"status": "unknown", "error": None})

    def get_latest_frame(self, stream_id):
        """Get the latest frame from the HLS stream"""
        if stream_id not in self.streams:
            return None

        status = self.get_stream_status(stream_id)
        if status["status"] != "running":
            logger.warning(f"Stream {stream_id} not running (status: {status['status']})")
            return None

        temp_dir = self.temp_dirs[stream_id]
        frame_path = os.path.join(temp_dir, 'frame.jpg')
        
        # Get the latest segment
        segments = sorted([f for f in os.listdir(temp_dir) if f.endswith('.ts')])
        if not segments:
            logger.error(f"No segments available for stream {stream_id}")
            return None
            
        latest_segment = os.path.join(temp_dir, segments[-1])
        
        # Extract frame from latest segment
        ffmpeg_cmd = [
            'ffmpeg',
            '-i', latest_segment,
            '-vframes', '1',
            '-y',
            frame_path
        ]
        
        try:
            process = subprocess.run(
                ffmpeg_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5
            )
            
            if process.returncode == 0 and os.path.exists(frame_path):
                return frame_path
            else:
                logger.error(f"Failed to extract frame for stream {stream_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error extracting frame for stream {stream_id}: {e}")
            return None

    def stop_stream(self, stream_id):
        # Stop FFmpeg process
        if stream_id in self.processes:
            process = self.processes[stream_id]
            try:
                os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            except:
                process.terminate()
            del self.processes[stream_id]
        
        # Clean up temp directory
        if stream_id in self.temp_dirs:
            try:
                shutil.rmtree(self.temp_dirs[stream_id])
            except Exception as e:
                logger.error(f"Failed to clean up temp directory for stream {stream_id}: {e}")
            del self.temp_dirs[stream_id]
            
        if stream_id in self.streams:
            del self.streams[stream_id]
            
        if stream_id in self.stream_status:
            del self.stream_status[stream_id]
            
        logger.info(f"Stopped stream {stream_id}")

    def stop_all(self):
        for stream_id in list(self.streams.keys()):
            self.stop_stream(stream_id)
