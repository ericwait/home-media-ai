#!/usr/bin/env python3
"""
Home Media AI Web Viewer
A read-only web interface for exploring your media database.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import io
import rawpy
from flask import Flask, render_template, request, jsonify, send_file
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from PIL import Image, UnidentifiedImageError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)

# Database connection
DATABASE_URI = os.getenv('HOME_MEDIA_AI_URI')
if not DATABASE_URI:
    raise ValueError("HOME_MEDIA_AI_URI environment variable not set")

engine = create_engine(DATABASE_URI, pool_pre_ping=True)
Session = sessionmaker(bind=engine)

# Photo root directory (where images are stored)
# This can be overridden by environment variable or uses default
PHOTO_ROOT = os.getenv('HOME_MEDIA_AI_PHOTO_ROOT', '/mnt/media')

# Try to load configuration for advanced path mapping
try:
    from home_media_ai.config import PathResolver, Config

    # Create config with web service settings
    config = Config.load()
    # Override with environment variable if set
    if PHOTO_ROOT:
        config.web.media_root = PHOTO_ROOT

    path_resolver = PathResolver(config)
    USE_PATH_RESOLVER = True
    logger.info(f"Path resolver loaded with mappings: {config.storage_roots}")
except ImportError:
    USE_PATH_RESOLVER = False
    path_resolver = None
    logger.warning("Path resolver not available, using simple path construction")


def resolve_media_path(storage_root, directory, filename):
    """Resolve media path components to local filesystem path.

    Args:
        storage_root: Database storage root
        directory: Directory within storage root
        filename: Filename

    Returns:
        str: Resolved local path
    """
    if USE_PATH_RESOLVER:
        # Use configuration-based path resolution
        try:
            return str(path_resolver.resolve_path(storage_root, directory, filename))
        except Exception as e:
            logger.warning(f"Path resolver failed: {e}, falling back to simple construction")

    # Fallback: simple path construction using PHOTO_ROOT
    if directory:
        return str(Path(PHOTO_ROOT) / directory / filename)
    else:
        return str(Path(PHOTO_ROOT) / filename)


@app.route('/')
def index():
    """Main gallery view with filters."""
    return render_template('index.html')


@app.route('/api/images')
def get_images():
    """
    API endpoint to fetch images with filters.

    Query parameters:
    - page: Page number (default 1)
    - per_page: Images per page (default 50)
    - rating_min: Minimum rating (0-5)
    - rating_max: Maximum rating (0-5)
    - media_type: Filter by media type (raw_image, jpeg, etc.)
    - has_gps: Filter for images with GPS data (true/false)
    - camera_make: Filter by camera manufacturer
    - year: Filter by year
    - sort: Sort field (created, rating, camera_make)
    - order: Sort order (asc, desc)
    """
    session = Session()

    try:
        # Parse query parameters
        page = max(1, int(request.args.get('page', 1)))
        per_page = min(100, max(1, int(request.args.get('per_page', 50))))
        offset = (page - 1) * per_page

        # Build WHERE clause based on filters
        where_clauses = ["m.is_original = TRUE"]  # Only show originals
        params = {}

        # Rating filter
        rating_min = request.args.get('rating_min')
        if rating_min:
            where_clauses.append("m.rating >= :rating_min")
            params['rating_min'] = int(rating_min)

        if rating_max := request.args.get('rating_max'):
            where_clauses.append("m.rating <= :rating_max")
            params['rating_max'] = int(rating_max)

        # Media type filter
        if media_type := request.args.get('media_type'):
            where_clauses.append("mt.name = :media_type")
            params['media_type'] = media_type

        # GPS filter
        has_gps = request.args.get('has_gps')
        if has_gps == 'true':
            where_clauses.extend(
                ("m.gps_latitude IS NOT NULL", "m.gps_longitude IS NOT NULL")
            )
        # Camera filter
        if camera_make := request.args.get('camera_make'):
            where_clauses.append("m.camera_make = :camera_make")
            params['camera_make'] = camera_make

        if year := request.args.get('year'):
            where_clauses.append("YEAR(m.created) = :year")
            params['year'] = int(year)

        where_sql = " AND ".join(where_clauses)

        # Sorting
        sort_field = request.args.get('sort', 'created')
        sort_order = request.args.get('order', 'desc').upper()

        valid_sorts = {
            'created': 'm.created',
            'rating': 'm.rating',
            'camera_make': 'm.camera_make',
            'file_size': 'm.file_size'
        }

        sort_column = valid_sorts.get(sort_field, 'm.created')
        order_by_sql = f"{sort_column} {sort_order}"

        # Count total matching images
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM media m
            JOIN media_types mt ON m.media_type_id = mt.id
            WHERE {where_sql}
        """

        result = session.execute(text(count_sql), params)
        if result is None:
            total = 0
        else:
            total = result.fetchone()[0] if result else 0

        # Fetch images
        query_sql = f"""
            SELECT
                m.id,
                m.directory,
                m.filename,
                m.file_hash,
                m.created,
                m.rating,
                m.width,
                m.height,
                m.camera_make,
                m.camera_model,
                m.gps_latitude,
                m.gps_longitude,
                mt.name as media_type
            FROM media m
            JOIN media_types mt ON m.media_type_id = mt.id
            WHERE {where_sql}
            ORDER BY {order_by_sql}
            LIMIT :limit OFFSET :offset
        """

        params['limit'] = per_page
        params['offset'] = offset

        result = session.execute(text(query_sql), params)

        images = []
        images.extend(
            {
                'id': row['id'],
                'file_path': Path.joinpath(
                    Path('/mnt/media'), row['directory'], row['filename']
                ).as_posix(),
                'file_hash': row['file_hash'],
                'created': (
                    row['created'].isoformat() if row['created'] else None
                ),
                'rating': row['rating'],
                'width': row['width'],
                'height': row['height'],
                'camera_make': row['camera_make'],
                'camera_model': row['camera_model'],
                'has_gps': row['gps_latitude'] is not None,
                'media_type': row['media_type'],
            }
            for row in result.mappings()
        )
        return jsonify({
            'images': images,
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page
        })

    except Exception as e:
        logger.error(f"Error fetching images: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/image/<int:image_id>')
def get_image_detail(image_id):
    """Get detailed information about a specific image."""
    session = Session()

    try:
        query_sql = """
            SELECT
                m.*,
                mt.name as media_type
            FROM media m
            JOIN media_types mt ON m.media_type_id = mt.id
            WHERE m.id = :image_id
        """

        result = session.execute(text(query_sql), {'image_id': image_id})
        if row := result.mappings().fetchone():
            return jsonify(dict(row))

        else:
            return jsonify({'error': 'Image not found'}), 404

    except Exception as e:
        logger.error(f"Error fetching image detail: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/stats')
def get_stats():
    """Get database statistics for dashboard."""
    session = Session()

    try:
        # Total images by type
        type_stats = session.execute(text("""
            SELECT
                mt.name,
                COUNT(*) as count,
                SUM(m.file_size) / (1024*1024*1024) as total_gb
            FROM media m
            JOIN media_types mt ON m.media_type_id = mt.id
            WHERE m.is_original = TRUE
            GROUP BY mt.name
            ORDER BY count DESC
        """)).fetchall()

        # Rating distribution
        rating_stats = session.execute(text("""
            SELECT
                COALESCE(rating, -1) as rating,
                COUNT(*) as count
            FROM media
            WHERE is_original = TRUE
            GROUP BY rating
            ORDER BY rating
        """)).fetchall()

        # Camera usage
        camera_stats = session.execute(text("""
            SELECT
                CONCAT(camera_make, ' ', camera_model) as camera,
                COUNT(*) as count
            FROM media
            WHERE is_original = TRUE
              AND camera_make IS NOT NULL
            GROUP BY camera_make, camera_model
            ORDER BY count DESC
            LIMIT 10
        """)).fetchall()

        # Images per year
        year_stats = session.execute(text("""
            SELECT
                YEAR(created) as year,
                COUNT(*) as count
            FROM media
            WHERE is_original = TRUE
              AND created IS NOT NULL
            GROUP BY YEAR(created)
            ORDER BY year DESC
        """)).fetchall()

        return jsonify({
            'by_type': [{'type': r[0], 'count': r[1], 'gb': float(r[2])} for r in type_stats],
            'by_rating': [{'rating': r[0], 'count': r[1]} for r in rating_stats],
            'by_camera': [{'camera': r[0], 'count': r[1]} for r in camera_stats],
            'by_year': [{'year': r[0], 'count': r[1]} for r in year_stats]
        })

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/filters')
def get_filter_options():
    """Get available filter options (camera makes, years, etc.)."""
    session = Session()

    try:
        # Available camera makes
        cameras = session.execute(text("""
            SELECT DISTINCT camera_make
            FROM media
            WHERE camera_make IS NOT NULL
            ORDER BY camera_make
        """)).fetchall()

        # Available years
        years = session.execute(text("""
            SELECT DISTINCT YEAR(created) as year
            FROM media
            WHERE created IS NOT NULL
            ORDER BY year DESC
        """)).fetchall()

        # Media types
        media_types = session.execute(text("""
            SELECT DISTINCT name
            FROM media_types
            ORDER BY name
        """)).fetchall()

        return jsonify({
            'cameras': [r[0] for r in cameras],
            'years': [r[0] for r in years],
            'media_types': [r[0] for r in media_types]
        })

    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/image/<int:image_id>')
def image_detail(image_id):
    """Render detailed view of a single image."""
    return render_template('image.html', image_id=image_id)

@app.route('/api/thumbnail/<int:image_id>')
def get_thumbnail(image_id):
    """Generate and serve a thumbnail for an image."""
    session = Session()

    try:
        # Get image path components from database
        result = session.execute(
            text("""
                SELECT storage_root, directory, filename
                FROM media
                WHERE id = :id
            """),
            {'id': image_id}
        )
        row = result.fetchone()

        if not row:
            logger.warning(f"Image {image_id} not found in database")
            return "Not found", 404

        storage_root, directory, filename = row

        if not filename:
            logger.warning(f"No filename for image {image_id}")
            return "No filename", 404

        # Resolve path using path resolver (with mappings) or fallback to simple construction
        mounted_path = resolve_media_path(storage_root, directory, filename)
        logger.debug(f"Resolved path for image {image_id}: {mounted_path}")

        # Generate thumbnail
        try:
            if str(mounted_path).lower().endswith(('.cr2', '.nef', '.arw', '.dng', '.raf')):
                # RAW file → decode with rawpy
                with rawpy.imread(mounted_path) as raw:
                    rgb = raw.postprocess(
                        use_camera_wb=True,
                        no_auto_bright=True,
                        output_bps=8
                    )
                img = Image.fromarray(rgb)
            else:
                # Non-RAW → Pillow can handle directly
                img = Image.open(mounted_path)

            # Normalize mode
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')

            # Shrink to fit within 400x400
            img.thumbnail((400, 400), Image.Resampling.LANCZOS)

            # Save to memory as JPEG
            output = io.BytesIO()
            img.save(output, format='JPEG', quality=85)
            output.seek(0)

            return send_file(output,
                            mimetype='image/jpeg',
                            as_attachment=False,
                            download_name='thumb.jpg')

        except PermissionError:
            return "Permission denied on mounted path", 403
        except UnidentifiedImageError:
            return "Unsupported image format", 415
        except rawpy.LibRawFileUnsupportedError:
            return "Unsupported RAW format", 415
        except Exception as e:
            return f"Error generating thumbnail: {e}", 500
    except Exception as e:
        logger.error(f"Error fetching thumbnail {image_id}: {e}")
        return "Server error", 500
    finally:
        session.close()


if __name__ == '__main__':
    # For development only - use gunicorn in production
    app.run(host='0.0.0.0', port=5100, debug=False)
