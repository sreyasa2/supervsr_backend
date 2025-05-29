import logging
import subprocess
import os
import signal
import atexit
import tempfile
import shutil
import time
import threading
from collections import deque
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

class StreamManager:
    """
    Manages RTSP-to-HLS streaming processes via FFmpeg, with thread-safe
    state management and cleaned-up resource handling.
    """

    # Configurable parameters
    HLS_SEGMENT_TIME = 2             # seconds per HLS segment
    HLS_LIST_SIZE = 5                # number of segments in playlist
    PROBE_SIZE = 5_000_000           # bytes to probe input stream
    ANALYZE_DURATION = 5_000_000     # microseconds to analyze input
    TIMEOUT_USEC = 5_000_000         # socket I/O timeout in microseconds
    LOG_HISTORY_SIZE = 100           # number of stderr lines to keep
    VERIFY_TIMEOUT = 10              # seconds to wait for HLS readiness

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.streams: Dict[str, str] = {}                # stream_id -> rtsp_url
        self.temp_dirs: Dict[str, str] = {}              # stream_id -> temp directory
        self.processes: Dict[str, subprocess.Popen] = {} # stream_id -> process
        self.status: Dict[str, Dict[str, Any]] = {}      # stream_id -> {status, error}
        self.ffmpeg_logs: Dict[str, deque] = {}          # stream_id -> recent stderr lines
        atexit.register(self.stop_all)

    def _log_ffmpeg(self, process: subprocess.Popen, stream_id: str) -> None:
        def reader():
            while True:
                line = process.stderr.readline()
                if not line:
                    break
                text = line.strip()
                with self._lock:
                    dq = self.ffmpeg_logs.setdefault(stream_id, deque(maxlen=self.LOG_HISTORY_SIZE))
                    dq.append(text)
        t = threading.Thread(target=reader, daemon=True)
        t.start()

    def _launch_ffmpeg(self, stream_id: str, rtsp_url: str, output_dir: str) -> None:
        playlist = os.path.join(output_dir, 'playlist.m3u8')
        cmd = [
            'ffmpeg',
            '-probesize', str(self.PROBE_SIZE),
            '-analyzeduration', str(self.ANALYZE_DURATION),
            '-rtsp_transport', 'tcp',
            '-timeout', str(self.TIMEOUT_USEC),
            '-i', rtsp_url,
            '-c:v', 'copy',
            '-bsf:v', 'hevc_mp4toannexb',
            '-tag:v', 'hvc1',
            '-c:a', 'aac',
            '-b:a', '128k',
            '-f', 'hls',
            '-hls_time', str(self.HLS_SEGMENT_TIME),
            '-hls_list_size', str(self.HLS_LIST_SIZE),
            '-hls_flags', 'delete_segments+append_list+independent_segments',
            '-hls_allow_cache', '0',
            '-hls_segment_filename', os.path.join(output_dir, 'seg%03d.ts'),
            '-fflags', '+nobuffer+genpts',
            '-flags', 'low_delay',
            '-max_delay', '500000',
            '-start_at_zero',
            '-y',
            playlist
        ]
        creationflags = 0
        if os.name == 'nt':
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=1,
            universal_newlines=True,
            preexec_fn=(os.setsid if os.name != 'nt' else None),
            creationflags=creationflags
        )
        with self._lock:
            self.processes[stream_id] = proc
            self.ffmpeg_logs[stream_id] = deque(maxlen=self.LOG_HISTORY_SIZE)
        self._log_ffmpeg(proc, stream_id)

    def _verify_hls(self, stream_id: str, output_dir: str, timeout: int) -> bool:
        playlist = os.path.join(output_dir, 'playlist.m3u8')
        end = time.time() + timeout
        while time.time() < end:
            if not os.path.exists(playlist):
                time.sleep(0.5)
                continue
            try:
                files = os.listdir(output_dir)
                ts = [f for f in files if f.endswith('.ts')]
                if not ts:
                    time.sleep(0.5)
                    continue
                with open(playlist, 'r') as f:
                    data = f.read()
                if data.startswith('#EXTM3U'):
                    return True
            except Exception:
                time.sleep(0.5)
        return False

    def start_stream(self, stream_id: str, rtsp_url: str) -> bool:
        with self._lock:
            if stream_id in self.streams:
                return False
            self.streams[stream_id] = rtsp_url
            self.status[stream_id] = {"status": "init", "error": None}
        temp = tempfile.mkdtemp(prefix=f"stream_{stream_id}_")
        with self._lock:
            self.temp_dirs[stream_id] = temp
        try:
            self._launch_ffmpeg(stream_id, rtsp_url, temp)
        except OSError as e:
            with self._lock:
                self.status[stream_id] = {"status": "error", "error": str(e)}
            self.stop_stream(stream_id)
            return False
        if not self._verify_hls(stream_id, temp, self.VERIFY_TIMEOUT):
            with self._lock:
                self.status[stream_id] = {"status": "error", "error": "HLS setup timeout"}
            self.stop_stream(stream_id)
            return False
        with self._lock:
            self.status[stream_id] = {"status": "running", "error": None}
        return True

    def get_stream_status(self, stream_id: str) -> Dict[str, Any]:
        with self._lock:
            if stream_id not in self.status:
                return {"status": "unknown", "error": "not found"}
            stat = self.status[stream_id].copy()
            proc = self.processes.get(stream_id)
        if proc and proc.poll() is not None:
            logs = list(self.ffmpeg_logs.get(stream_id, []))[-5:]
            stat = {"status": "error", "error": f"Process exited. Logs: {logs}"}
            self.stop_stream(stream_id)
        return stat

    def get_latest_frame(self, stream_id: str) -> Optional[str]:
        with self._lock:
            d = self.temp_dirs.get(stream_id)
        if not d or not os.path.isdir(d):
            return None
        ts = [f for f in os.listdir(d) if f.endswith('.ts')]
        if not ts:
            return None
        seg = os.path.join(d, sorted(ts)[-1])
        out = os.path.join(d, f"{stream_id}_latest.jpg")
        cmd = ['ffmpeg', '-i', seg, '-frames:v', '1', '-q:v', '2', out, '-y']
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return out
        except subprocess.CalledProcessError:
            return None

    def stop_stream(self, stream_id: str) -> None:
        with self._lock:
            proc = self.processes.pop(stream_id, None)
            temp = self.temp_dirs.pop(stream_id, None)
            self.streams.pop(stream_id, None)
            self.status.pop(stream_id, None)
            self.ffmpeg_logs.pop(stream_id, None)
        if proc:
            try:
                if os.name != 'nt':
                    os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
                else:
                    proc.send_signal(signal.CTRL_BREAK_EVENT)
                proc.wait(5)
            except Exception:
                proc.kill()
        if temp and os.path.isdir(temp):
            shutil.rmtree(temp, ignore_errors=True)

    def stop_all(self) -> None:
        with self._lock:
            ids = list(self.streams.keys())
        for sid in ids:
            self.stop_stream(sid)
