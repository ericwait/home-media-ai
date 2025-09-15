"""
Example: Basic media analysis workflow

This script demonstrates the basic workflow of analyzing media files
and searching the results. Perfect for getting started with Home Media AI.
"""

import logging
from pathlib import Path
from home_media_ai import MediaAnalyzer

def main():
    """Run basic media analysis example."""
    
    # Set up logging to see what's happening
    logging.basicConfig(level=logging.INFO)
    
    # Example media directory (replace with your path)
    media_directory = Path("~/Pictures").expanduser()  # or "/path/to/your/photos"
    
    # Check if directory exists
    if not media_directory.exists():
        print(f"Directory not found: {media_directory}")
        print("Please update the media_directory variable with your photos path")
        return
    
    print(f"🔍 Analyzing media in: {media_directory}")
    
    # Initialize the analyzer
    analyzer = MediaAnalyzer(
        media_directory=media_directory,
        database_path="example_media.db"
    )
    
    try:
        # Create database tables
        print("📊 Setting up database...")
        analyzer.create_database()
        
        # Analyze a subset of files (first 10 for this example)
        print("🔬 Starting analysis...")
        results = analyzer.analyze_directory(
            recursive=False,  # Only current directory for this example
            progress=True,
            max_workers=2  # Use fewer workers for example
        )
        
        # Show results summary
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        print(f"\n✅ Analysis complete!")
        print(f"   Successful: {len(successful)}")
        print(f"   Failed: {len(failed)}")
        
        if successful:
            # Calculate average quality
            avg_quality = sum(r.quality_metrics.overall_score for r in successful) / len(successful)
            print(f"   Average quality: {avg_quality:.1f}/100")
            
            # Show some examples
            print(f"\n📸 Sample results:")
            for i, result in enumerate(successful[:3], 1):
                print(f"   {i}. {Path(result.file_path).name}")
                print(f"      Quality: {result.quality_metrics.overall_score:.1f}/100")
                print(f"      Faces: {result.content_results.face_count}")
                if result.content_results.tags:
                    print(f"      Tags: {', '.join(result.content_results.tags[:3])}")
        
        # Demonstrate searching
        print(f"\n🔍 Search examples:")
        
        # Find high-quality images
        high_quality = analyzer.search_files(quality_min=80, limit=5)
        print(f"   High-quality files (>80): {len(high_quality)}")
        
        # Find images with faces
        with_faces = analyzer.search_files(has_faces=True, limit=5)
        print(f"   Files with faces: {len(with_faces)}")
        
        # Show collection statistics
        print(f"\n📈 Collection statistics:")
        stats = analyzer.get_analysis_summary()
        print(f"   Total files: {stats['total_files']}")
        print(f"   Total images: {stats['total_images']}")
        print(f"   Total videos: {stats['total_videos']}")
        print(f"   Average quality: {stats['avg_quality']:.1f}/100")
        print(f"   Files with faces: {stats['files_with_faces']}")
        
        # Check for duplicates
        duplicates = analyzer.find_duplicates()
        if duplicates:
            print(f"   Duplicate groups found: {len(duplicates)}")
        else:
            print(f"   No duplicates found")
        
        print(f"\n🎉 Example complete! Database saved to: example_media.db")
        print(f"    You can now use the CLI: home-media-ai search --min-quality 80")
        
    except Exception as e:
        print(f"❌ Error during analysis: {e}")
        
    finally:
        # Clean up
        analyzer.close()


if __name__ == "__main__":
    main()