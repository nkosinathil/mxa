"""
Audio transcription processor using Faster Whisper.
"""
import os
import json
import csv
import tempfile
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from faster_whisper import WhisperModel
import ffmpeg
import imageio_ffmpeg

class AudioTranscriber:
    """Handles audio transcription using Faster Whisper."""
    
    def __init__(self, model_size: str = "base", device: str = "auto", 
                 compute_type: Optional[str] = None):
        self.model_size = model_size
        self.device = self._detect_device(device)
        self.compute_type = compute_type or ("float16" if self.device == "cuda" else "int8")
        self.model = None
        self.ffmpeg_path = self._get_ffmpeg()
        
    def _detect_device(self, device: str) -> str:
        if device == "auto":
            import shutil
            return "cuda" if shutil.which("nvidia-smi") else "cpu"
        return device
    
    def _get_ffmpeg(self) -> str:
        try:
            return imageio_ffmpeg.get_ffmpeg_exe()
        except:
            ffmpeg_path = shutil.which("ffmpeg")
            if ffmpeg_path:
                return ffmpeg_path
            raise RuntimeError("FFmpeg not found. Install imageio-ffmpeg or system ffmpeg.")
    
    def _load_model(self):
        if self.model is None:
            self.model = WhisperModel(self.model_size, device=self.device, 
                                      compute_type=self.compute_type)
    
    def extract_audio_to_wav(self, src: Path, tmp_dir: Path, sr: int = 16000) -> Path:
        """Extract audio from any file to WAV format."""
        out_wav = tmp_dir / f"{src.stem}_16k_mono.wav"
        (
            ffmpeg
            .input(str(src))
            .output(str(out_wav), ac=1, ar=sr, format="wav", vn=None, loglevel="error")
            .overwrite_output()
            .run(cmd=self.ffmpeg_path)
        )
        return out_wav
    
    def transcribe_file(self, audio_path: Path, output_dir: Path, 
                        language: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe a single audio file."""
        self._load_model()
        
        result = {
            "file": str(audio_path),
            "status": "pending",
            "language": None,
            "language_probability": None,
            "duration": None,
            "segments": [],
            "output_files": {}
        }
        
        try:
            with tempfile.TemporaryDirectory(prefix="asr_") as tmpdir:
                tmp = Path(tmpdir)
                
                # Extract audio to WAV
                wav = self.extract_audio_to_wav(audio_path, tmp)
                
                # Detect language
                segments, info = self.model.transcribe(
                    str(wav),
                    language=language,
                    task="transcribe",
                    vad_filter=True
                )
                
                # Collect segments
                seg_list = []
                for seg in segments:
                    seg_list.append({
                        "id": seg.id,
                        "start": seg.start,
                        "end": seg.end,
                        "text": seg.text.strip()
                    })
                
                # Save outputs
                base = output_dir / audio_path.stem
                
                # TXT
                txt_path = base.with_suffix(".txt")
                with open(txt_path, "w", encoding="utf-8") as f:
                    for seg in seg_list:
                        f.write(seg["text"] + "\n")
                
                # JSON
                json_path = base.with_suffix(".json")
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "file": str(audio_path),
                        "language": info.language,
                        "language_probability": info.language_probability,
                        "duration": info.duration,
                        "segments": seg_list
                    }, f, indent=2, ensure_ascii=False)
                
                result.update({
                    "status": "success",
                    "language": info.language,
                    "language_probability": info.language_probability,
                    "duration": info.duration,
                    "segments": seg_list,
                    "output_files": {
                        "txt": str(txt_path),
                        "json": str(json_path)
                    }
                })
                
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        return result

def process_audio_files(file_paths: List[str], output_dir: str, 
                        model_size: str = "base", quiet: bool = False) -> Dict[str, Any]:
    """Process multiple audio files and generate transcripts."""
    def logprint(msg: str):
        if not quiet:
            print(msg, flush=True)
    
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    transcriber = AudioTranscriber(model_size=model_size)
    results = []
    
    logprint(f"Processing {len(file_paths)} audio files with Whisper ({model_size})...")
    
    for i, file_path in enumerate(file_paths, 1):
        logprint(f"[{i}/{len(file_paths)}] Transcribing: {Path(file_path).name}")
        result = transcriber.transcribe_file(Path(file_path), out_dir)
        results.append(result)
        
        if result["status"] == "success":
            logprint(f"  ✓ Language: {result['language']} ({result['language_probability']:.2f})")
        else:
            logprint(f"  ✗ Failed: {result.get('error', 'Unknown error')}")
    
    # Write summary report
    report = {
        "model": model_size,
        "total_files": len(results),
        "successful": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results
    }
    
    with open(out_dir / "_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # CSV summary
    with open(out_dir / "_report.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["file", "status", "language", "probability", "duration"])
        for r in results:
            w.writerow([
                r["file"],
                r["status"],
                r.get("language", ""),
                f"{r.get('language_probability', 0):.3f}" if r.get("language_probability") else "",
                r.get("duration", "")
            ])
    
    logprint(f"\nComplete: {report['successful']}/{report['total_files']} files transcribed")
    logprint(f"Reports: {out_dir / '_report.json'}")
    
    return report