"""
Frame extractor command-line interface.

Usage:
    python -m frame_extractor [video_file] [options]
    python frame_extractor/__main__.py [video_file] [options]
    
Examples:
    python -m frame_extractor                                      # Auto-find first .mp4 (CPU mode)
    python -m frame_extractor test_data/video.mp4                 # Process specific file (CPU mode)
    python -m frame_extractor --list                               # List available videos
    python -m frame_extractor --with-hw-accel                      # Use hardware acceleration
    python -m frame_extractor test_data/video.mp4 --with-hw-accel  # Process with GPU
    python -m frame_extractor --debug                              # Debug logging

Note: CLI mode defaults to CPU-only processing (no hardware acceleration) for compatibility.
      Use --with-hw-accel to enable NVIDIA hardware acceleration if available.
"""

import sys
import argparse
import logging
from pathlib import Path

# Handle both module execution (python -m frame_extractor) and script execution (python __main__.py)
if __name__ == '__main__' and __package__ == '':
    # Direct script execution - add parent directory to path
    sys.path.insert(0, str(Path(__file__).parent.parent))

from frame_extractor import FrameExtractor


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def find_test_videos(test_data_dir='test_data'):
    """Find all .mp4 files in test_data directory."""
    # Look for test_data relative to project root, not current working directory
    if not Path(test_data_dir).is_absolute():
        # Find project root (parent of frame_extractor package)
        project_root = Path(__file__).parent.parent
        test_data_path = project_root / test_data_dir
    else:
        test_data_path = Path(test_data_dir)
    
    if not test_data_path.exists():
        logger.error(f"test_data directory not found: {test_data_path.absolute()}")
        return []
    
    videos = list(test_data_path.glob('*.mp4'))
    return sorted(videos)


def list_videos():
    """List all available test videos."""
    videos = find_test_videos()
    
    if not videos:
        print("No .mp4 files found in test_data/")
        print(f"test_data path: {Path('test_data').absolute()}")
        return
    
    print("\nAvailable test videos:")
    print("-" * 60)
    for i, video in enumerate(videos, 1):
        size_mb = video.stat().st_size / (1024 * 1024)
        print(f"{i}. {video.name:<40} ({size_mb:.1f} MB)")
    print("-" * 60)


def process_video(video_path, use_hw_acceleration=True):
    """Process a video file using FrameExtractor."""
    video_path = Path(video_path)
    
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return False
    
    if video_path.suffix.lower() != '.mp4':
        logger.warning(f"File is not .mp4: {video_path.suffix}")
    
    logger.info(f"Processing video: {video_path}")
    logger.info(f"Video size: {video_path.stat().st_size / (1024*1024):.1f} MB")
    logger.info(f"Hardware acceleration: {'enabled (GPU)' if use_hw_acceleration else 'disabled (CPU only)'}")
    
    try:
        with FrameExtractor(str(video_path), use_hw_acceleration=use_hw_acceleration) as extractor:
            logger.info("Starting frame extraction...")
            extract_time, identify_time = extractor.process_frames()
            
            # Display results
            print("\n" + "=" * 60)
            print("FRAME EXTRACTION RESULTS")
            print("=" * 60)
            print(f"Video file:              {video_path.name}")
            print(f"Total frames extracted:  {len(extractor.filenames)}")
            print(f"Selected frame indices:  {extractor.image_index_list}")
            print(f"Selected filenames:      {extractor.get_filenames_to_process()}")
            print(f"Extraction time:         {extract_time:.2f} seconds")
            print(f"Identification time:     {identify_time:.2f} seconds")
            print(f"Total processing time:   {extract_time + identify_time:.2f} seconds")
            print("=" * 60)
            
            # Show mean intensity values
            if extractor.mean_intensity:
                print(f"\nMean intensity values (first 10):")
                for i, intensity in enumerate(extractor.mean_intensity[:10]):
                    print(f"  Frame {i:3d}: {intensity:7.2f}")
                if len(extractor.mean_intensity) > 10:
                    print(f"  ... and {len(extractor.mean_intensity) - 10} more frames")
            
            print(f"\nSelected frames kept in: {video_path.parent}")
            print("Unwanted frames automatically deleted.")
            print("\n")
            
        return True
        
    except Exception as e:
        logger.error(f"Error processing video: {e}", exc_info=True)
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Frame extractor - Extract and analyze frames from video files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    parser.add_argument(
        'video',
        nargs='?',
        help='Path to video file (auto-finds first .mp4 if not specified)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available test videos in test_data/'
    )
    
    parser.add_argument(
        '--no-hw-accel',
        action='store_true',
        help='Disable NVIDIA hardware acceleration (CPU only) [This is the default]'
    )
    
    parser.add_argument(
        '--with-hw-accel',
        action='store_true',
        help='Enable NVIDIA hardware acceleration (if available)'
    )
    
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Handle --list option
    if args.list:
        list_videos()
        return 0
    
    # Find video to process
    if args.video:
        video_path = args.video
    else:
        videos = find_test_videos()
        if not videos:
            print("Error: No .mp4 files found in test_data/")
            print("\nUsage: Place a .mp4 video file in test_data/ directory")
            print("       python -m frame_extractor")
            return 1
        video_path = str(videos[0])
        logger.info(f"Auto-selected first video: {video_path}")
    
    # Process the video
    # Default for CLI testing: no hardware acceleration (more compatible)
    use_hw_acceleration = args.with_hw_accel
    success = process_video(video_path, use_hw_acceleration=use_hw_acceleration)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())
