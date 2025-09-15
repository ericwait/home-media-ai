"""
Command-line interface for Home Media AI.

This module provides a comprehensive CLI for analyzing media files,
searching content, and managing the media database.

Commands:
    analyze: Analyze media files or directories
    search: Search analyzed media files
    stats: Show database statistics
    duplicates: Find duplicate files
    export: Export analysis results
    
Example:
    $ home-media-ai analyze /path/to/photos --recursive --progress
    $ home-media-ai search --has-faces --min-quality 80
    $ home-media-ai stats
"""

import click
import json
import sys
from pathlib import Path
from typing import Optional

from home_media_ai import MediaAnalyzer, MediaDatabase
from home_media_ai.config import get_config, load_config_file
from home_media_ai.utils import setup_logging, format_file_size


@click.group()
@click.option('--config', '-c', type=click.Path(exists=True), help='Configuration file path')
@click.option('--database', '-d', type=str, help='Database file path')
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option('--quiet', '-q', is_flag=True, help='Suppress non-essential output')
@click.pass_context
def main(ctx, config, database, verbose, quiet):
    """Home Media AI - Analyze and search your media collection.
    
    This tool helps you analyze large collections of images and videos,
    evaluating quality and identifying content for easy searching.
    
    Examples:
        home-media-ai analyze /path/to/photos
        home-media-ai search --has-faces --min-quality 80
        home-media-ai stats
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Load configuration
    if config:
        load_config_file(config)
    
    config_obj = get_config()
    
    # Override database path if specified
    if database:
        config_obj.database.path = database
    
    # Set up logging
    if quiet:
        log_level = 'WARNING'
    elif verbose:
        log_level = 'DEBUG'
    else:
        log_level = config_obj.processing.log_level
    
    setup_logging(log_level)
    
    # Store configuration in context
    ctx.obj['config'] = config_obj
    ctx.obj['database_path'] = database


@main.command()
@click.argument('path', type=click.Path(exists=True))
@click.option('--recursive/--no-recursive', default=True, help='Search subdirectories')
@click.option('--images/--no-images', default=True, help='Include image files')
@click.option('--videos/--no-videos', default=True, help='Include video files')
@click.option('--progress/--no-progress', default=True, help='Show progress bar')
@click.option('--workers', '-w', type=int, help='Number of worker threads')
@click.option('--force', '-f', is_flag=True, help='Re-analyze already processed files')
@click.pass_context
def analyze(ctx, path, recursive, images, videos, progress, workers, force):
    """Analyze media files in the specified directory.
    
    This command analyzes all media files in the given directory,
    evaluating quality and identifying content. Results are stored
    in the database for later searching.
    
    PATH: Directory containing media files to analyze
    
    Examples:
        home-media-ai analyze /home/user/photos
        home-media-ai analyze /media/videos --workers 8 --no-progress
        home-media-ai analyze . --no-recursive --images --no-videos
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Override worker count if specified
    if workers:
        config.processing.max_workers = workers
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(
        media_directory=path,
        database_path=database_path,
        config=config
    )
    
    # Create database tables
    analyzer.create_database()
    
    click.echo(f"Analyzing media files in: {path}")
    click.echo(f"Database: {database_path or config.database.path}")
    click.echo(f"Workers: {config.processing.max_workers}")
    
    try:
        # Analyze directory
        results = analyzer.analyze_directory(
            recursive=recursive,
            include_images=images,
            include_videos=videos,
            progress=progress,
            max_workers=config.processing.max_workers
        )
        
        # Summary statistics
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        click.echo(f"\nAnalysis complete:")
        click.echo(f"  Total files: {len(results)}")
        click.echo(f"  Successful: {len(successful)}")
        click.echo(f"  Failed: {len(failed)}")
        
        if successful:
            avg_quality = sum(r.quality_metrics.overall_score for r in successful) / len(successful)
            total_time = sum(r.processing_time for r in results)
            click.echo(f"  Average quality: {avg_quality:.1f}/100")
            click.echo(f"  Total time: {total_time:.1f} seconds")
        
        if failed:
            click.echo(f"\nFailed files:")
            for result in failed[:10]:  # Show first 10 failures
                click.echo(f"  {result.file_path}: {result.error_message}")
            if len(failed) > 10:
                click.echo(f"  ... and {len(failed) - 10} more")
        
    except Exception as e:
        click.echo(f"Error during analysis: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


@main.command()
@click.argument('file_path', type=click.Path(exists=True))
@click.option('--show-details', '-d', is_flag=True, help='Show detailed analysis results')
@click.pass_context
def analyze_file(ctx, file_path, show_details):
    """Analyze a single media file.
    
    This command analyzes a single image or video file and displays
    the quality and content analysis results.
    
    FILE_PATH: Path to the media file to analyze
    
    Examples:
        home-media-ai analyze-file /path/to/photo.jpg
        home-media-ai analyze-file video.mp4 --show-details
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(database_path=database_path, config=config)
    analyzer.create_database()
    
    click.echo(f"Analyzing file: {file_path}")
    
    try:
        result = analyzer.analyze_file(file_path)
        
        if result.success:
            click.echo(f"\nAnalysis successful:")
            click.echo(f"  Quality score: {result.quality_metrics.overall_score:.1f}/100")
            click.echo(f"  Faces detected: {result.content_results.face_count}")
            click.echo(f"  Objects detected: {result.content_results.object_count}")
            click.echo(f"  Processing time: {result.processing_time:.2f} seconds")
            
            if result.content_results.tags:
                click.echo(f"  Tags: {', '.join(result.content_results.tags)}")
            
            if show_details:
                click.echo(f"\nDetailed results:")
                click.echo(f"  Quality metrics: {result.quality_metrics.to_dict()}")
                click.echo(f"  Content results: {result.content_results.to_dict()}")
        else:
            click.echo(f"Analysis failed: {result.error_message}", err=True)
            sys.exit(1)
    
    except Exception as e:
        click.echo(f"Error analyzing file: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


@main.command()
@click.option('--min-quality', type=float, help='Minimum quality score')
@click.option('--max-quality', type=float, help='Maximum quality score')
@click.option('--has-faces/--no-faces', default=None, help='Filter by presence of faces')
@click.option('--min-faces', type=int, help='Minimum number of faces')
@click.option('--has-objects/--no-objects', default=None, help='Filter by presence of objects')
@click.option('--object-class', multiple=True, help='Filter by object class (can specify multiple)')
@click.option('--tag', multiple=True, help='Filter by tag (can specify multiple)')
@click.option('--has-text/--no-text', default=None, help='Filter by presence of text')
@click.option('--limit', '-l', type=int, help='Maximum number of results')
@click.option('--output', '-o', type=click.Path(), help='Save results to file')
@click.option('--format', type=click.Choice(['table', 'json', 'csv']), default='table', help='Output format')
@click.pass_context
def search(ctx, min_quality, max_quality, has_faces, min_faces, has_objects, 
          object_class, tag, has_text, limit, output, format):
    """Search analyzed media files based on quality and content criteria.
    
    This command searches the database for media files matching the
    specified criteria and displays the results.
    
    Examples:
        home-media-ai search --min-quality 80 --has-faces
        home-media-ai search --tag outdoor --tag nature --limit 20
        home-media-ai search --object-class person --min-faces 2
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(database_path=database_path, config=config)
    
    try:
        results = analyzer.search_files(
            quality_min=min_quality,
            quality_max=max_quality,
            has_faces=has_faces,
            min_face_count=min_faces,
            object_classes=list(object_class) if object_class else None,
            tags=list(tag) if tag else None,
            has_text=has_text,
            limit=limit
        )
        
        if not results:
            click.echo("No files found matching the specified criteria.")
            return
        
        click.echo(f"Found {len(results)} matching files:")
        
        if format == 'table':
            # Display results in table format
            for i, result in enumerate(results, 1):
                quality_score = result.get('overall_score', 'N/A')
                face_count = result.get('face_count', 0)
                object_count = result.get('object_count', 0)
                tags = result.get('tags', [])
                
                click.echo(f"\n{i}. {result['filename']}")
                click.echo(f"   Path: {result['file_path']}")
                click.echo(f"   Quality: {quality_score}")
                click.echo(f"   Faces: {face_count}, Objects: {object_count}")
                if tags:
                    click.echo(f"   Tags: {', '.join(tags[:5])}")
                    if len(tags) > 5:
                        click.echo(f"         ... and {len(tags) - 5} more")
        
        elif format == 'json':
            output_data = json.dumps(results, indent=2, default=str)
            if output:
                with open(output, 'w') as f:
                    f.write(output_data)
                click.echo(f"Results saved to: {output}")
            else:
                click.echo(output_data)
        
        elif format == 'csv':
            import csv
            import io
            
            output_stream = io.StringIO()
            if results:
                writer = csv.DictWriter(output_stream, fieldnames=results[0].keys())
                writer.writeheader()
                for result in results:
                    # Convert complex fields to strings
                    row = {}
                    for key, value in result.items():
                        if isinstance(value, (list, dict)):
                            row[key] = json.dumps(value)
                        else:
                            row[key] = value
                    writer.writerow(row)
            
            csv_output = output_stream.getvalue()
            if output:
                with open(output, 'w') as f:
                    f.write(csv_output)
                click.echo(f"Results saved to: {output}")
            else:
                click.echo(csv_output)
    
    except Exception as e:
        click.echo(f"Error searching files: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


@main.command()
@click.pass_context
def stats(ctx):
    """Show database statistics and summary information.
    
    This command displays comprehensive statistics about the analyzed
    media collection including file counts, quality metrics, and content data.
    
    Examples:
        home-media-ai stats
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(database_path=database_path, config=config)
    
    try:
        summary = analyzer.get_analysis_summary()
        
        click.echo("Media Collection Statistics:")
        click.echo("=" * 40)
        
        # File counts
        click.echo(f"Total files: {summary['total_files']:,}")
        click.echo(f"  Images: {summary['total_images']:,}")
        click.echo(f"  Videos: {summary['total_videos']:,}")
        
        # Storage
        total_size_gb = summary['total_size_gb']
        if total_size_gb > 1000:
            click.echo(f"Total size: {total_size_gb/1000:.1f} TB")
        else:
            click.echo(f"Total size: {total_size_gb:.1f} GB")
        
        # Quality statistics
        if summary['total_files'] > 0:
            click.echo(f"\nQuality Statistics:")
            click.echo(f"Average quality score: {summary['avg_quality']:.1f}/100")
        
        # Content statistics
        if summary['files_with_faces'] > 0 or summary['files_with_text'] > 0:
            click.echo(f"\nContent Statistics:")
            if summary['files_with_faces'] > 0:
                face_percentage = (summary['files_with_faces'] / summary['total_files']) * 100
                click.echo(f"Files with faces: {summary['files_with_faces']:,} ({face_percentage:.1f}%)")
            
            if summary['files_with_text'] > 0:
                text_percentage = (summary['files_with_text'] / summary['total_files']) * 100
                click.echo(f"Files with text: {summary['files_with_text']:,} ({text_percentage:.1f}%)")
        
        # Database info
        db_stats = summary['database_stats']
        if 'min_quality_score' in db_stats and 'max_quality_score' in db_stats:
            click.echo(f"\nQuality Range:")
            click.echo(f"Lowest quality: {db_stats['min_quality_score']:.1f}/100")
            click.echo(f"Highest quality: {db_stats['max_quality_score']:.1f}/100")
    
    except Exception as e:
        click.echo(f"Error getting statistics: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


@main.command()
@click.option('--show-paths', '-p', is_flag=True, help='Show file paths for duplicates')
@click.option('--output', '-o', type=click.Path(), help='Save results to file')
@click.pass_context
def duplicates(ctx, show_paths, output):
    """Find potential duplicate files based on content hash.
    
    This command identifies files that have identical content based on
    their MD5 hash, helping you find and manage duplicate files.
    
    Examples:
        home-media-ai duplicates
        home-media-ai duplicates --show-paths
        home-media-ai duplicates --output duplicates.json
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(database_path=database_path, config=config)
    
    try:
        duplicate_groups = analyzer.find_duplicates()
        
        if not duplicate_groups:
            click.echo("No duplicate files found.")
            return
        
        total_duplicates = sum(len(group) for group in duplicate_groups)
        click.echo(f"Found {len(duplicate_groups)} groups with {total_duplicates} duplicate files:")
        
        output_data = []
        
        for i, group in enumerate(duplicate_groups, 1):
            group_size_mb = sum(file['file_size_bytes'] for file in group) / (1024 * 1024)
            wasted_space_mb = group_size_mb * (len(group) - 1)  # Keep one copy
            
            click.echo(f"\nGroup {i}: {len(group)} files ({group_size_mb:.1f} MB total, "
                      f"{wasted_space_mb:.1f} MB wasted)")
            
            group_data = {
                'group_id': i,
                'file_count': len(group),
                'total_size_mb': group_size_mb,
                'wasted_space_mb': wasted_space_mb,
                'files': group
            }
            
            if show_paths:
                for file in group:
                    click.echo(f"  {file['file_path']}")
            
            output_data.append(group_data)
        
        # Calculate total wasted space
        total_wasted_mb = sum(group['wasted_space_mb'] for group in output_data)
        if total_wasted_mb > 1000:
            click.echo(f"\nTotal wasted space: {total_wasted_mb/1000:.1f} GB")
        else:
            click.echo(f"\nTotal wasted space: {total_wasted_mb:.1f} MB")
        
        # Save to file if requested
        if output:
            with open(output, 'w') as f:
                json.dump(output_data, f, indent=2, default=str)
            click.echo(f"\nDuplicate information saved to: {output}")
    
    except Exception as e:
        click.echo(f"Error finding duplicates: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


@main.command()
@click.argument('output_path', type=click.Path())
@click.option('--format', type=click.Choice(['json', 'csv']), default='json', help='Export format')
@click.option('--include-raw', is_flag=True, help='Include raw analysis data')
@click.pass_context
def export(ctx, output_path, format, include_raw):
    """Export analysis results to a file.
    
    This command exports all analysis results from the database to
    a JSON or CSV file for external analysis or backup purposes.
    
    OUTPUT_PATH: Path where exported data should be saved
    
    Examples:
        home-media-ai export analysis_results.json
        home-media-ai export results.csv --format csv
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(database_path=database_path, config=config)
    
    try:
        click.echo(f"Exporting analysis results to: {output_path}")
        
        analyzer.export_results(
            output_path=output_path,
            format=format,
            include_raw_data=include_raw
        )
        
        click.echo("Export completed successfully.")
    
    except Exception as e:
        click.echo(f"Error exporting results: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


@main.command()
@click.argument('backup_path', type=click.Path())
@click.pass_context
def backup(ctx, backup_path):
    """Create a backup of the analysis database.
    
    This command creates a complete backup of the database containing
    all analysis results, which can be restored later if needed.
    
    BACKUP_PATH: Path where database backup should be saved
    
    Examples:
        home-media-ai backup /backup/media_analysis_backup.db
        home-media-ai backup ~/backups/$(date +%Y%m%d)_media.db
    """
    config = ctx.obj['config']
    database_path = ctx.obj.get('database_path')
    
    # Initialize analyzer
    analyzer = MediaAnalyzer(database_path=database_path, config=config)
    
    try:
        click.echo(f"Creating database backup: {backup_path}")
        
        analyzer.backup_database(backup_path)
        
        click.echo("Backup completed successfully.")
    
    except Exception as e:
        click.echo(f"Error creating backup: {e}", err=True)
        sys.exit(1)
    
    finally:
        analyzer.close()


if __name__ == '__main__':
    main()