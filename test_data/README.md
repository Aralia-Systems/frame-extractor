# Test Data

This folder contains sample video files for testing the frame-extractor package in isolation.

## Usage

Place your test video files (`.mp4`, `.avi`, `.mov`, etc.) in this directory.

Example:
```bash
# Place video file here
test_data/sample_video.mp4
```

Then run the standalone test script:
```bash
python -m frame_extractor test_data/sample_video.mp4
```

## Notes

- Videos are not committed to version control (.gitignore should exclude this folder)
- Use realistic video files to test extraction quality
- Video format should be compatible with FFmpeg
