# frame-extractor

Extracts frames from an MP4 video with FFmpeg, identifies key frames by intensity analysis, and keeps only selected frames.

## Install

```bash
pip install -r requirements.txt
```

## Run

```bash
python -m frame_extractor path/to/video.mp4
```

Or in code:

```python
from frame_extractor import FrameExtractor

with FrameExtractor("path/to/video.mp4") as extractor:
	extract_time, identify_time = extractor.process_frames()
	selected_files = extractor.get_filenames_to_process()
```

## Failure Handling

The extractor now explicitly handles these failure modes:

1. FFmpeg hang/lockup: extraction is bounded by a timeout and raises a clear timeout exception.
2. Stale frame contamination: only frames created in the current run are analyzed.
3. No extracted frames: raises a clear exception if FFmpeg returns success but no frame files are produced.
4. Reference-frame edge case: exactly two extrema now raises an "insufficient cycles" exception instead of an index crash.
5. Index boundary correctness: frame index validation now uses an exclusive upper bound to prevent out-of-range indexing.
6. Partial-failure cleanup: when processing fails partway through, context-manager cleanup removes files created by that failed run.

## Notes

1. Hardware acceleration is optional and can be enabled with `use_hw_acceleration=True`.
2. Processing creates `intensity_histogram.png` when enough data is available.
3. If processing never starts, cleanup is a no-op by design.

## Testing

Run all tests:

```bash
c:/github/frame-extractor/venv/Scripts/python.exe -m pytest -q
```

Run integration tests only:

```bash
c:/github/frame-extractor/venv/Scripts/python.exe -m pytest -q -m integration
```

Run real-data tests only (uses `test_data/input.mp4`):

```bash
c:/github/frame-extractor/venv/Scripts/python.exe -m pytest -q -m realdata
```

Run tests via helper script:

```bash
c:/github/frame-extractor/venv/Scripts/python.exe testing/run_tests.py
```