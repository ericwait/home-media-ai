#!/usr/bin/env python3
"""
Home Media AI Web Viewer
A read-only web interface for exploring your media database.
"""
import os
import sys
import re
import hashlib
import secrets
from pathlib import Path
from functools import wraps

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "python"))

import io
import rawpy
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, send_file, Response, session as flask_session, redirect, url_for
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
import logging
from PIL import Image, UnidentifiedImageError

# Configure PIL to handle large images
Image.MAX_IMAGE_PIXELS = None  # Remove size limit for thumbnail generation

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=int(os.environ.get('SESSION_TIMEOUT_HOURS', 24)))

# Authentication configuration
LOGIN_ATTEMPTS = {}  # Track login attempts by IP
MAX_LOGIN_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 60


def check_rate_limit(ip: str) -> bool:
    """Check if IP is rate limited for login attempts."""
    if ip not in LOGIN_ATTEMPTS:
        return True

    attempts, last_attempt = LOGIN_ATTEMPTS[ip]
    if datetime.now() - last_attempt > timedelta(seconds=LOGIN_LOCKOUT_SECONDS):
        # Reset after lockout period
        del LOGIN_ATTEMPTS[ip]
        return True

    return attempts < MAX_LOGIN_ATTEMPTS


def record_login_attempt(ip: str, success: bool):
    """Record a login attempt."""
    if success:
        if ip in LOGIN_ATTEMPTS:
            del LOGIN_ATTEMPTS[ip]
    else:
        if ip in LOGIN_ATTEMPTS:
            attempts, _ = LOGIN_ATTEMPTS[ip]
            LOGIN_ATTEMPTS[ip] = (attempts + 1, datetime.now())
        else:
            LOGIN_ATTEMPTS[ip] = (1, datetime.now())


def login_required(f):
    """Decorator to require authentication for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not flask_session.get('authenticated'):
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return redirect(url_for('login'))

        return f(*args, **kwargs)
    return decorated_function

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
        config.default_storage_root = PHOTO_ROOT  # Required for config_only strategy

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
        # Normalize separators for cross-platform compatibility
        clean_dir = directory.replace('\\', '/')
        return str(Path(PHOTO_ROOT) / clean_dir / filename)
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
    - month: Filter by month (1-12)
    - unrated: Filter for unrated images only (true/false)
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
        where_clauses = ["m.is_final = TRUE"]  # Only show final images (best version)  # Only show originals
        params = {}

        # Rating filter
        rating_min = request.args.get('rating_min')
        if rating_min:
            where_clauses.append("m.rating >= :rating_min")
            params['rating_min'] = int(rating_min)

        if rating_max := request.args.get('rating_max'):
            r_max = int(rating_max)
            if r_max == 0:
                where_clauses.append("(m.rating <= :rating_max OR m.rating IS NULL)")
            else:
                where_clauses.append("m.rating <= :rating_max")
            params['rating_max'] = r_max

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

        if month := request.args.get('month'):
            where_clauses.append("MONTH(m.created) = :month")
            params['month'] = int(month)

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
            WHERE m.is_final = TRUE
            GROUP BY mt.name
            ORDER BY count DESC
        """)).fetchall()

        # Rating distribution
        rating_stats = session.execute(text("""
            SELECT
                COALESCE(rating, -1) as rating,
                COUNT(*) as count
            FROM media
            WHERE is_final = TRUE
            GROUP BY rating
            ORDER BY rating
        """)).fetchall()

        # Camera usage
        camera_stats = session.execute(text("""
            SELECT
                CONCAT(camera_make, ' ', camera_model) as camera,
                COUNT(*) as count
            FROM media
            WHERE is_final = TRUE
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
            WHERE is_final = TRUE
              AND created IS NOT NULL
            GROUP BY YEAR(created)
            ORDER BY year DESC
        """)).fetchall()

        # GPS count
        gps_count = session.execute(text("""
            SELECT COUNT(*)
            FROM media
            WHERE is_final = TRUE
              AND gps_latitude IS NOT NULL
        """)).scalar()

        return jsonify({
            'by_type': [{'type': r[0], 'count': r[1], 'gb': float(r[2])} for r in type_stats],
            'by_rating': [{'rating': r[0], 'count': r[1]} for r in rating_stats],
            'by_camera': [{'camera': r[0], 'count': r[1]} for r in camera_stats],
            'by_year': [{'year': r[0], 'count': r[1]} for r in year_stats],
            'gps_count': gps_count
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

        # Available months (1-12)
        months = session.execute(text("""
            SELECT DISTINCT MONTH(created) as month
            FROM media
            WHERE created IS NOT NULL
            ORDER BY month
        """)).fetchall()

        return jsonify({
            'cameras': [r[0] for r in cameras],
            'years': [r[0] for r in years],
            'months': [r[0] for r in months],
            'media_types': [r[0] for r in media_types]
        })

    except Exception as e:
        logger.error(f"Error fetching filter options: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/export')
def export_filtered():
    """
    Export filtered images in various formats.

    Query parameters:
    - format: Export format ('json' or 'txt', default 'json')
    - All filter parameters from /api/images (rating_min, camera_make, etc.)
    - limit: Max number of results to export (default 5000, max 10000)

    Returns:
    - JSON format: {filter: {...}, total_count: N, exported_at: "...", image_ids: [...]}
    - TXT format: One path per line (directory/filename without storage_root)
    """
    session = Session()

    try:
        # Parse format parameter
        export_format = request.args.get('format', 'json').lower()
        if export_format not in ('json', 'txt'):
            return jsonify({'error': 'Invalid format. Use "json" or "txt"'}), 400

        # Parse limit
        limit = min(10000, max(1, int(request.args.get('limit', 5000))))

        # Build WHERE clause (same logic as /api/images)
        where_clauses = ["m.is_final = TRUE"]  # Only show final images (best version)
        params = {}
        filter_info = {}

        # Rating filter
        if rating_min := request.args.get('rating_min'):
            where_clauses.append("m.rating >= :rating_min")
            params['rating_min'] = int(rating_min)
            filter_info['rating_min'] = int(rating_min)

        if rating_max := request.args.get('rating_max'):
            r_max = int(rating_max)
            if r_max == 0:
                where_clauses.append("(m.rating <= :rating_max OR m.rating IS NULL)")
            else:
                where_clauses.append("m.rating <= :rating_max")
            params['rating_max'] = r_max
            filter_info['rating_max'] = r_max

        # Media type filter
        if media_type := request.args.get('media_type'):
            where_clauses.append("mt.name = :media_type")
            params['media_type'] = media_type
            filter_info['media_type'] = media_type

        # GPS filter
        if has_gps := request.args.get('has_gps'):
            if has_gps == 'true':
                where_clauses.extend(
                    ("m.gps_latitude IS NOT NULL", "m.gps_longitude IS NOT NULL")
                )
                filter_info['has_gps'] = True

        # Camera filter
        if camera_make := request.args.get('camera_make'):
            where_clauses.append("m.camera_make = :camera_make")
            params['camera_make'] = camera_make
            filter_info['camera_make'] = camera_make

        # Year filter
        if year := request.args.get('year'):
            where_clauses.append("YEAR(m.created) = :year")
            params['year'] = int(year)
            filter_info['year'] = int(year)

        # Month filter
        if month := request.args.get('month'):
            where_clauses.append("MONTH(m.created) = :month")
            params['month'] = int(month)
            filter_info['month'] = int(month)

        where_sql = " AND ".join(where_clauses)

        # Export based on format
        if export_format == 'json':
            # Fetch image IDs only
            query_sql = f"""
                SELECT m.id
                FROM media m
                JOIN media_types mt ON m.media_type_id = mt.id
                WHERE {where_sql}
                ORDER BY m.created DESC
                LIMIT :limit
            """
            params['limit'] = limit

            result = session.execute(text(query_sql), params)
            image_ids = [row[0] for row in result]

            return jsonify({
                'filter': filter_info,
                'total_count': len(image_ids),
                'exported_at': datetime.now().isoformat(),
                'image_ids': image_ids
            })

        else:  # txt format
            # Fetch directory/filename paths (without storage_root)
            query_sql = f"""
                SELECT m.directory, m.filename
                FROM media m
                JOIN media_types mt ON m.media_type_id = mt.id
                WHERE {where_sql}
                ORDER BY m.created DESC
                LIMIT :limit
            """
            params['limit'] = limit

            result = session.execute(text(query_sql), params)

            # Build paths as directory/filename
            paths = []
            for row in result:
                directory, filename = row
                if directory:
                    path = f"{directory}/{filename}"
                else:
                    path = filename
                paths.append(path)

            # Return as plain text
            return Response('\n'.join(paths), mimetype='text/plain')

    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/image/<int:image_id>')
def image_detail(image_id):
    """Render detailed view of a single image."""
    return render_template('image.html', image_id=image_id)


@app.route('/view/<int:image_id>')
def view_image(image_id):
    """View a single image with EXIF overlay and rating capability."""
    return render_template('viewer.html', image_id=image_id)

@app.route('/api/thumbnail/<int:image_id>')
def get_thumbnail(image_id):
    """Generate and serve a thumbnail for an image (checking cache first)."""
    session = Session()

    try:
        # Get image path components from database
        result = session.execute(
            text("""
                SELECT storage_root, directory, filename, thumbnail_path
                FROM media
                WHERE id = :id
            """),
            {'id': image_id}
        )
        row = result.fetchone()

        if not row:
            logger.warning(f"Image {image_id} not found in database")
            return "Not found", 404

        storage_root, directory, filename, thumbnail_path = row

        # Check for cached thumbnail first
        if thumbnail_path:
            try:
                # Construct path: /thumbnails/<thumbnail_path>
                # Normalize path separators and strip leading slashes
                clean_thumb_path = thumbnail_path.replace('\\', '/').lstrip('/')
                thumb_full_path = Path('/thumbnails') / clean_thumb_path

                if thumb_full_path.exists():
                    return send_file(thumb_full_path, mimetype='image/jpeg')
                else:
                    logger.warning(f"Thumbnail recorded at {thumbnail_path} but file not found at {thumb_full_path}")
                    return "Thumbnail file not found", 404
            except PermissionError as e:
                logger.error(f"Permission denied reading thumbnail at {thumb_full_path}: {e}")
                return "Thumbnail permission denied", 403
            except Exception as e:
                logger.error(f"Error serving cached thumbnail {thumb_full_path}: {e}")
                return "Error serving thumbnail", 500


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

        except PermissionError as e:
            logger.error(f"Permission denied reading source file at {mounted_path}: {e}")
            return f"Permission denied reading source file: {mounted_path}", 403
        except FileNotFoundError as e:
            logger.warning(f"Source file not found at {mounted_path}: {e}")
            return f"Source file not found: {mounted_path}", 404
        except UnidentifiedImageError:
            return "Unsupported image format", 415
        except rawpy.LibRawFileUnsupportedError:
            return "Unsupported RAW format", 415
        except Exception as e:
            logger.error(f"Error generating thumbnail from {mounted_path}: {e}")
            return f"Error generating thumbnail: {e}", 500
    except Exception as e:
        logger.error(f"Error fetching thumbnail {image_id}: {e}")
        return "Server error", 500
    finally:
        session.close()


# Authentication routes

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page and handler."""
    if request.method == 'POST':
        ip = request.remote_addr
        if not check_rate_limit(ip):
            return render_template('login.html', error='Too many login attempts. Please wait.')

        username = request.form.get('username', '')
        password = request.form.get('password', '')

        session = Session()
        try:
            from home_media_ai.media import User
            user = session.query(User).filter(
                User.username == username,
                User.is_active == True
            ).first()

            if user and user.check_password(password):
                # Update last login
                user.last_login = datetime.now()
                session.commit()

                flask_session.permanent = True
                flask_session['authenticated'] = True
                flask_session['user_id'] = user.id
                flask_session['username'] = user.username
                flask_session['display_name'] = user.display_name or user.username
                record_login_attempt(ip, True)
                return redirect(url_for('rating_select'))
            else:
                record_login_attempt(ip, False)
                return render_template('login.html', error='Invalid username or password')
        finally:
            session.close()

    return render_template('login.html')


@app.route('/logout')
def logout():
    """Logout handler."""
    flask_session.clear()
    return redirect(url_for('login'))


# Rating workflow endpoints

@app.route('/api/rating/<int:image_id>', methods=['PATCH'])
@login_required
def update_rating(image_id):
    """Update the rating for an image and sync to file metadata."""
    session = Session()

    try:
        data = request.get_json()
        if not data or 'rating' not in data:
            return jsonify({'error': 'Rating value required'}), 400

        rating = int(data['rating'])
        if not 0 <= rating <= 5:
            return jsonify({'error': 'Rating must be between 0 and 5'}), 400

        # Get media object with path components
        from home_media_ai.media import Media
        result = session.execute(
            text("""
                SELECT id, storage_root, directory, filename
                FROM media
                WHERE id = :id
            """),
            {'id': image_id}
        )
        row = result.fetchone()

        if not row:
            return jsonify({'error': 'Image not found'}), 404

        storage_root, directory, filename = row[1], row[2], row[3]

        # Get Media object for rating sync
        media = session.query(Media).filter(Media.id == image_id).first()

        # Resolve file path using web app's path resolution
        file_path = resolve_media_path(storage_root, directory, filename)

        # Sync rating to database and file
        from home_media_ai.rating_sync import sync_rating_to_file
        success = sync_rating_to_file(media, rating, session, file_path=Path(file_path))

        return jsonify({
            'id': image_id,
            'rating': rating,
            'synced_to_file': success
        })

    except Exception as e:
        logger.error(f"Error updating rating: {e}")
        session.rollback()
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/years-months')
def get_years_months():
    """Get available year/month combinations with rating progress."""
    session = Session()

    try:
        result = session.execute(text("""
            SELECT
                YEAR(created) as year,
                MONTH(created) as month,
                COUNT(*) as total,
                SUM(CASE WHEN rating IS NOT NULL AND rating > 0 THEN 1 ELSE 0 END) as rated
            FROM media
            WHERE is_final = TRUE
              AND created IS NOT NULL
            GROUP BY YEAR(created), MONTH(created)
            ORDER BY year DESC, month DESC
        """))

        items = []
        for row in result:
            items.append({
                'year': row[0],
                'month': row[1],
                'total': row[2],
                'rated': row[3],
                'progress': round(row[3] / row[2] * 100, 1) if row[2] > 0 else 0
            })

        return jsonify({'items': items})

    except Exception as e:
        logger.error(f"Error fetching years/months: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/rating-queue')
@login_required
def get_rating_queue():
    """
    Get images for rating workflow with burst detection.

    Query parameters:
    - year: Filter by year (required)
    - month: Filter by month (required)
    - burst_window: Seconds to consider as burst (default 30)
    - start_from: Image ID to start from (for pagination)
    - limit: Number of images to return (default 500, max 5000)
    - unrated_only: Only return unrated images (default false)
    """
    session = Session()

    try:
        year = request.args.get('year')
        month = request.args.get('month')

        if not year or not month:
            return jsonify({'error': 'Year and month are required'}), 400

        year = int(year)
        month = int(month)
        burst_window = int(request.args.get('burst_window', 30))
        start_from = request.args.get('start_from')
        limit = min(5000, max(1, int(request.args.get('limit', 500))))

        # Build query
        where_clauses = [
            "m.is_final = TRUE",  # Show all final images (no children)
            "YEAR(m.created) = :year",
            "MONTH(m.created) = :month"
        ]
        params = {'year': year, 'month': month, 'limit': limit}

        # Rating filter
        if rating_min := request.args.get('rating_min'):
            where_clauses.append("m.rating >= :rating_min")
            params['rating_min'] = int(rating_min)

        if rating_max := request.args.get('rating_max'):
            r_max = int(rating_max)
            if r_max == 0:
                where_clauses.append("(m.rating <= :rating_max OR m.rating IS NULL)")
            else:
                where_clauses.append("m.rating <= :rating_max")
            params['rating_max'] = r_max

        if start_from:
            where_clauses.append("m.id > :start_from")
            params['start_from'] = int(start_from)

        where_sql = " AND ".join(where_clauses)

        query_sql = f"""
            SELECT
                m.id,
                m.storage_root,
                m.directory,
                m.filename,
                m.created,
                m.rating,
                m.width,
                m.height,
                m.camera_make,
                m.camera_model,
                m.thumbnail_path,
                m.is_original,
                m.is_final,
                m.origin_id
            FROM media m
            WHERE {where_sql}
            ORDER BY m.created ASC, m.id ASC
            LIMIT :limit
        """

        result = session.execute(text(query_sql), params)

        images = []
        for row in result.mappings():
            images.append({
                'id': row['id'],
                'storage_root': row['storage_root'],
                'directory': row['directory'],
                'filename': row['filename'],
                'created': row['created'].isoformat() if row['created'] else None,
                'rating': row['rating'],
                'width': row['width'],
                'height': row['height'],
                'camera_make': row['camera_make'],
                'camera_model': row['camera_model'],
                'thumbnail_path': row['thumbnail_path'],
                'is_original': row['is_original'],
                'is_final': row['is_final'],
                'origin_id': row['origin_id']
            })

        # Detect bursts
        bursts = []
        if len(images) > 1:
            current_burst = [images[0]]
            for i in range(1, len(images)):
                prev_time = datetime.fromisoformat(images[i-1]['created']) if images[i-1]['created'] else None
                curr_time = datetime.fromisoformat(images[i]['created']) if images[i]['created'] else None

                if prev_time and curr_time:
                    diff = abs((curr_time - prev_time).total_seconds())
                    if diff <= burst_window:
                        current_burst.append(images[i])
                    else:
                        if len(current_burst) > 1:
                            bursts.append([img['id'] for img in current_burst])
                        current_burst = [images[i]]
                else:
                    if len(current_burst) > 1:
                        bursts.append([img['id'] for img in current_burst])
                    current_burst = [images[i]]

            # Don't forget the last burst
            if len(current_burst) > 1:
                bursts.append([img['id'] for img in current_burst])

        return jsonify({
            'images': images,
            'bursts': bursts,
            'year': year,
            'month': month,
            'burst_window': burst_window
        })

    except Exception as e:
        logger.error(f"Error fetching rating queue: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


@app.route('/api/cached-thumbnail/<int:image_id>')
def get_cached_thumbnail(image_id):
    """Serve cached thumbnail if available, otherwise generate on-the-fly.
    
    This is now just an alias for get_thumbnail which handles caching internally.
    """
    return get_thumbnail(image_id)


@app.route('/rate')
@login_required
def rating_select():
    """Rating workflow - year/month selection page."""
    return render_template('rating_select.html')


@app.route('/rate/<int:year>/<int:month>')
@login_required
def rating_view(year, month):
    """Rating workflow - main rating interface."""
    return render_template('rating.html', year=year, month=month)


@app.route('/relationships')
@login_required
def relationships_view():
    """Visualize parent-child relationships."""
    return render_template('relationships.html')


@app.route('/api/relationships')
@login_required
def api_relationships():
    """Get parent-child relationship data for visualization."""
    session = Session()
    try:
        # Get all images with parent-child relationships
        query = text("""
            SELECT
                m.id,
                m.filename,
                m.is_original,
                m.is_final,
                m.origin_id,
                m.created,
                m.rating,
                m.thumbnail_path
            FROM media m
            WHERE m.origin_id IS NOT NULL OR m.is_final = FALSE
            ORDER BY m.created ASC
        """)

        result = session.execute(query)

        nodes = []
        edges = []
        node_ids = set()

        for row in result.mappings():
            node_id = row['id']
            parent_id = row['origin_id']

            # Add current node
            if node_id not in node_ids:
                nodes.append({
                    'id': node_id,
                    'filename': row['filename'],
                    'is_original': row['is_original'],
                    'is_final': row['is_final'],
                    'rating': row['rating'],
                    'created': row['created'].isoformat() if row['created'] else None
                })
                node_ids.add(node_id)

            # Add parent node if it exists and not already added
            if parent_id and parent_id not in node_ids:
                parent_query = text("SELECT id, filename, is_original, is_final, rating, created FROM media WHERE id = :id")
                parent_result = session.execute(parent_query, {'id': parent_id}).mappings().first()
                if parent_result:
                    nodes.append({
                        'id': parent_id,
                        'filename': parent_result['filename'],
                        'is_original': parent_result['is_original'],
                        'is_final': parent_result['is_final'],
                        'rating': parent_result['rating'],
                        'created': parent_result['created'].isoformat() if parent_result['created'] else None
                    })
                    node_ids.add(parent_id)

            # Add edge
            if parent_id:
                edges.append({
                    'source': parent_id,
                    'target': node_id
                })

        return jsonify({
            'nodes': nodes,
            'edges': edges
        })

    except Exception as e:
        logger.error(f"Error fetching relationships: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        session.close()


if __name__ == '__main__':
    # For development only - use gunicorn in production
    app.run(host='0.0.0.0', port=5100, debug=False)
