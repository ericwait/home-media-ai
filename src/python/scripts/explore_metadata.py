#!/usr/bin/env python3
"""
Test script for EXIF and XMP metadata extraction.

Run from project root:
    python tests/test_exif_extractor.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "python"))

from home_media_ai import ExifExtractor


def test_single_file(file_path: str):
    """Test metadata extraction on a single file.

    Args:
        file_path: Path to the image file to test.
    """
    print("=" * 70)
    print(f"Testing: {file_path}")
    print("=" * 70)

    if not Path(file_path).exists():
        print(f"ERROR: File not found: {file_path}")
        return

    # Check for XMP sidecar
    xmp_path = Path(file_path).with_suffix(f'{Path(file_path).suffix}.xmp')
    if xmp_path.exists():
        print(f"✓ XMP sidecar found: {xmp_path}")
    else:
        print(f"✗ No XMP sidecar found: {xmp_path}")

    print()

    # Extract metadata
    extractor = ExifExtractor()
    metadata = extractor.extract_metadata(file_path)

    if not metadata:
        print("WARNING: No metadata extracted")
        return

    # Display results
    print("Extracted Metadata:")
    print("-" * 70)

    # Rating (most important for your use case)
    if 'rating' in metadata:
        print(f"★ Rating: {metadata['rating']}/5 stars")
    else:
        print("  Rating: Not set")

    # GPS
    if 'gps_latitude' in metadata and 'gps_longitude' in metadata:
        lat = metadata['gps_latitude']
        lon = metadata['gps_longitude']
        alt = metadata.get('gps_altitude', 'N/A')
        print(f"📍 GPS: ({lat:.6f}, {lon:.6f})")
        print(f"   Altitude: {alt}m")
        print(f"   Map: https://www.google.com/maps?q={lat},{lon}")
    else:
        print("  GPS: Not available")

    # Camera equipment
    if 'camera_make' in metadata or 'camera_model' in metadata:
        make = metadata.get('camera_make', 'Unknown')
        model = metadata.get('camera_model', 'Unknown')
        lens = metadata.get('lens_model', 'N/A')
        print(f"📷 Camera: {make} {model}")
        print(f"   Lens: {lens}")

    # Image dimensions
    if 'width' in metadata and 'height' in metadata:
        width = metadata['width']
        height = metadata['height']
        megapixels = (width * height) / 1_000_000
        print(f"🖼️  Dimensions: {width}×{height} ({megapixels:.1f} MP)")

    # Exposure settings (from JSON metadata field)
    exposure_parts = []
    if 'aperture' in metadata:
        exposure_parts.append(f"f/{metadata['aperture']:.1f}")
    if 'shutter_speed' in metadata:
        exposure_parts.append(metadata['shutter_speed'])
    if 'iso' in metadata:
        exposure_parts.append(f"ISO {metadata['iso']}")
    if 'focal_length' in metadata:
        exposure_parts.append(f"{metadata['focal_length']:.0f}mm")

    if exposure_parts:
        print(f"⚙️  Exposure: {' | '.join(exposure_parts)}")

    # Keywords (useful for taxonomy)
    if 'keywords' in metadata:
        keywords = metadata['keywords']
        print(f"🏷️  Keywords: {', '.join(keywords[:10])}")
        if len(keywords) > 10:
            print(f"   ... and {len(keywords) - 10} more")

    # Hierarchical keywords (taxonomy hints!)
    if 'hierarchical_keywords' in metadata:
        hier = metadata['hierarchical_keywords']
        print("🌳 Hierarchical Keywords:")
        for kw in hier[:5]:
            print(f"   • {kw}")
        if len(hier) > 5:
            print(f"   ... and {len(hier) - 5} more")

    # Software
    if 'software' in metadata:
        print(f"💻 Software: {metadata['software']}")

    print()
    print("Raw metadata dictionary:")
    print("-" * 70)
    for key, value in sorted(metadata.items()):
        if key in ['keywords', 'hierarchical_keywords']:
            print(f"  {key}: [{len(value)} items]")
        else:
            print(f"  {key}: {value}")

    print("=" * 70)
    print()


def test_directory(directory: str, max_files: int = 5):
    """Test metadata extraction on multiple files in a directory.

    Args:
        directory: Path to directory containing images.
        max_files: Maximum number of files to test.
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"ERROR: Directory not found: {directory}")
        return

    # Find image files
    extensions = {'.jpg', '.jpeg', '.png', '.dng', '.cr2', '.nef', '.arw'}
    image_files = [
        f for f in dir_path.iterdir()
        if f.is_file() and f.suffix.lower() in extensions
    ]

    if not image_files:
        print(f"No image files found in {directory}")
        return

    print(f"Found {len(image_files)} image files")
    print(f"Testing first {min(max_files, len(image_files))} files...")
    print()

    for i, file_path in enumerate(image_files[:max_files], 1):
        print(f"\n[{i}/{min(max_files, len(image_files))}]")
        test_single_file(str(file_path))


def analyze_ratings_distribution(directory: str):
    """Analyze rating distribution across all files in a directory.

    Useful for understanding your existing rating dataset before ML training.

    Args:
        directory: Path to directory containing images.
    """
    dir_path = Path(directory)

    if not dir_path.exists():
        print(f"ERROR: Directory not found: {directory}")
        return

    print("=" * 70)
    print(f"Analyzing ratings in: {directory}")
    print("=" * 70)

    # Find all image files
    extensions = {'.jpg', '.jpeg', '.png', '.dng', '.cr2', '.nef', '.arw'}
    image_files = [
        f for f in dir_path.rglob('*')
        if f.is_file() and f.suffix.lower() in extensions
    ]

    print(f"Found {len(image_files)} image files\n")

    extractor = ExifExtractor()
    rating_counts = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, None: 0}

    for i, file_path in enumerate(image_files, 1):
        if i % 100 == 0:
            print(f"Processed {i}/{len(image_files)} files...")

        try:
            metadata = extractor.extract_metadata(str(file_path))
            rating = metadata.get('rating')
            rating_counts[rating] = rating_counts.get(rating, 0) + 1
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print()
    print("Rating Distribution:")
    print("-" * 70)

    total_rated = sum(count for rating, count in rating_counts.items() if rating is not None)

    for rating in [5, 4, 3, 2, 1, 0, None]:
        count = rating_counts[rating]
        if count > 0:
            stars = "★" * rating if rating else "(unrated)"
            percentage = (count / len(image_files)) * 100
            bar = "█" * int(percentage / 2)
            print(f"  {stars:12} {count:5} files  {percentage:5.1f}%  {bar}")

    print("-" * 70)
    print(f"Total files: {len(image_files)}")
    print(f"Rated files: {total_rated} ({(total_rated/len(image_files)*100):.1f}%)")
    print(f"Unrated files: {rating_counts[None]} ({(rating_counts[None]/len(image_files)*100):.1f}%)")

    # ML training recommendations
    print()
    print("ML Training Dataset Analysis:")
    print("-" * 70)

    if total_rated < 100:
        print("⚠️  Warning: Less than 100 rated images")
        print("   Recommend rating more images before training")
    elif total_rated < 500:
        print("✓ Sufficient for initial model training")
        print("  More rated images will improve accuracy")
    else:
        print("✓ Good dataset size for model training")

    # Check class imbalance
    max_count = max(rating_counts[r] for r in [1, 2, 3, 4, 5] if rating_counts[r] > 0)
    min_count = min(rating_counts[r] for r in [1, 2, 3, 4, 5] if rating_counts[r] > 0)

    if max_count > 0 and min_count > 0:
        imbalance_ratio = max_count / min_count
        if imbalance_ratio > 10:
            print(f"⚠️  Warning: Significant class imbalance (ratio: {imbalance_ratio:.1f}:1)")
            print("   Consider stratified sampling or oversampling minority classes")
        elif imbalance_ratio > 5:
            print(f"⚠️  Moderate class imbalance (ratio: {imbalance_ratio:.1f}:1)")
            print("   Monitor model performance on minority classes")
        else:
            print(f"✓ Reasonable class balance (ratio: {imbalance_ratio:.1f}:1)")

    print("=" * 70)


def main():
    """Main test function with interactive menu."""
    print("EXIF Extractor Test Suite")
    print("=" * 70)
    print()
    print("Options:")
    print("  1. Test single file")
    print("  2. Test directory (first 5 files)")
    print("  3. Analyze rating distribution in directory")
    print()

    choice = input("Select option (1-3) or enter file/directory path: ").strip()

    if choice == '1':
        file_path = input("Enter image file path: ").strip()
        test_single_file(file_path)

    elif choice == '2':
        directory = input("Enter directory path: ").strip()
        test_directory(directory)

    elif choice == '3':
        directory = input("Enter directory path: ").strip()
        analyze_ratings_distribution(directory)

    elif Path(choice).exists():
        if Path(choice).is_file():
            test_single_file(choice)
        elif Path(choice).is_dir():
            test_directory(choice)

    else:
        print(f"Invalid option or path: {choice}")


if __name__ == "__main__":
    main()
