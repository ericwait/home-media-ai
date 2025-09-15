"""
Example: Quality-based photo organization

This script demonstrates how to use Home Media AI to organize photos
based on quality scores, helping you identify the best and worst photos
in your collection.
"""

import shutil
from pathlib import Path
from home_media_ai import MediaAnalyzer

def organize_by_quality(analyzer, output_base_dir="organized_photos"):
    """Organize photos into quality-based folders."""
    
    output_dir = Path(output_base_dir)
    
    # Create quality-based directories
    excellent_dir = output_dir / "excellent" / "(90-100)"
    good_dir = output_dir / "good" / "(70-89)"
    average_dir = output_dir / "average" / "(50-69)"
    poor_dir = output_dir / "poor" / "(0-49)"
    
    for dir_path in [excellent_dir, good_dir, average_dir, poor_dir]:
        dir_path.mkdir(parents=True, exist_ok=True)
    
    # Get all analyzed files
    all_files = analyzer.search_files(limit=None)
    
    # Organize by quality score
    organized_count = 0
    
    for file_info in all_files:
        quality_score = file_info.get('overall_score')
        if quality_score is None:
            continue
            
        source_path = Path(file_info['file_path'])
        if not source_path.exists():
            continue
        
        # Determine destination based on quality
        if quality_score >= 90:
            dest_dir = excellent_dir
            quality_label = "excellent"
        elif quality_score >= 70:
            dest_dir = good_dir
            quality_label = "good"
        elif quality_score >= 50:
            dest_dir = average_dir
            quality_label = "average"
        else:
            dest_dir = poor_dir
            quality_label = "poor"
        
        # Copy file to quality-based directory
        dest_path = dest_dir / source_path.name
        
        # Handle name conflicts
        counter = 1
        while dest_path.exists():
            stem = source_path.stem
            suffix = source_path.suffix
            dest_path = dest_dir / f"{stem}_{counter}{suffix}"
            counter += 1
        
        try:
            shutil.copy2(source_path, dest_path)
            organized_count += 1
            print(f"📁 {quality_label:>8} ({quality_score:5.1f}): {source_path.name}")
        except Exception as e:
            print(f"❌ Failed to copy {source_path.name}: {e}")
    
    return organized_count


def find_cleanup_candidates(analyzer):
    """Find photos that might be candidates for cleanup."""
    
    print("🔍 Finding cleanup candidates...")
    
    # Very low quality images
    very_poor = analyzer.search_files(max_quality=20, limit=50)
    print(f"📉 Very poor quality (≤20): {len(very_poor)} files")
    
    # Blurry images (if we can identify them)
    # Note: This would require access to individual quality metrics
    
    # Duplicates
    duplicates = analyzer.find_duplicates()
    duplicate_count = sum(len(group) - 1 for group in duplicates)  # -1 to keep one copy
    print(f"🔄 Duplicate files: {duplicate_count} files could be removed")
    
    # Calculate potential space savings
    if very_poor:
        poor_size_mb = sum(f.get('file_size_bytes', 0) for f in very_poor) / (1024 * 1024)
        print(f"💾 Poor quality files: {poor_size_mb:.1f} MB")
    
    if duplicates:
        duplicate_size_mb = 0
        for group in duplicates:
            group_size = sum(f.get('file_size_bytes', 0) for f in group)
            duplicate_size_mb += group_size * (len(group) - 1) / (1024 * 1024)
        print(f"💾 Duplicate space waste: {duplicate_size_mb:.1f} MB")
    
    return very_poor, duplicates


def main():
    """Run quality-based organization example."""
    
    # Example media directory
    media_directory = Path("~/Pictures").expanduser()
    
    if not media_directory.exists():
        print(f"Directory not found: {media_directory}")
        print("Please update the media_directory variable")
        return
    
    print(f"📊 Quality-based photo organization")
    print(f"🔍 Source: {media_directory}")
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(
        media_directory=media_directory,
        database_path="quality_analysis.db"
    )
    
    try:
        # Ensure database exists
        analyzer.create_database()
        
        # Check if we have analyzed files
        stats = analyzer.get_analysis_summary()
        if stats['total_files'] == 0:
            print("⚠️  No analyzed files found. Please run analysis first:")
            print("   home-media-ai analyze /path/to/your/photos")
            return
        
        print(f"📈 Found {stats['total_files']} analyzed files")
        print(f"📊 Average quality: {stats['avg_quality']:.1f}/100")
        
        # Show quality distribution
        excellent = analyzer.search_files(quality_min=90)
        good = analyzer.search_files(quality_min=70, quality_max=89.9)
        average = analyzer.search_files(quality_min=50, quality_max=69.9)
        poor = analyzer.search_files(quality_max=49.9)
        
        print(f"\n📊 Quality distribution:")
        print(f"   Excellent (90-100): {len(excellent)} files")
        print(f"   Good      (70-89):  {len(good)} files")
        print(f"   Average   (50-69):  {len(average)} files")
        print(f"   Poor      (0-49):   {len(poor)} files")
        
        # Organize photos by quality
        print(f"\n📁 Organizing photos by quality...")
        organized_count = organize_by_quality(analyzer)
        print(f"✅ Organized {organized_count} photos into quality folders")
        
        # Find cleanup candidates
        print(f"\n🧹 Cleanup recommendations:")
        very_poor, duplicates = find_cleanup_candidates(analyzer)
        
        if very_poor:
            print(f"\n📝 Very poor quality files (consider reviewing):")
            for file_info in very_poor[:10]:  # Show first 10
                quality = file_info.get('overall_score', 0)
                filename = Path(file_info['file_path']).name
                print(f"   {quality:5.1f}: {filename}")
            if len(very_poor) > 10:
                print(f"   ... and {len(very_poor) - 10} more")
        
        if duplicates:
            print(f"\n🔄 Duplicate groups (consider removing extras):")
            for i, group in enumerate(duplicates[:5], 1):  # Show first 5 groups
                size_mb = group[0].get('file_size_bytes', 0) / (1024 * 1024)
                print(f"   Group {i}: {len(group)} files, {size_mb:.1f} MB each")
                for file_info in group:
                    filename = Path(file_info['file_path']).name
                    print(f"     {filename}")
            if len(duplicates) > 5:
                print(f"   ... and {len(duplicates) - 5} more groups")
        
        print(f"\n🎉 Quality organization complete!")
        print(f"   Organized photos saved to: organized_photos/")
        print(f"   Database: quality_analysis.db")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        
    finally:
        analyzer.close()


if __name__ == "__main__":
    main()