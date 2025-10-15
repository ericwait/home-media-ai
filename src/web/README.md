# Home Media AI Web Viewer

A read-only Flask web application for browsing and exploring your home media database. This service provides a visual interface to view photos, filter by metadata, and explore your media collection stored in MariaDB.

## Features

- Browse photos with thumbnail previews
- Filter by rating, camera, year, media type, and GPS data
- View detailed EXIF metadata
- Responsive gallery interface
- Support for RAW image formats (CR2, NEF, ARW, DNG, RAF)
- Read-only access for safe browsing

## Prerequisites

- Synology NAS with Container Manager (Docker/Docker Compose)
- MariaDB database with `home_media_ai` schema already set up
- Media files stored on accessible volume (e.g., `/volume1/photo/RAW`)
- User account with read access to media files

## Installation on Synology NAS

### Step 1: Prepare Configuration

Before deploying, you need to configure the environment variables in [docker-compose.yml](docker-compose.yml).

#### 1.1 Database Connection String

Update the `HOME_MEDIA_AI_URI` environment variable (line 12):

```yaml
HOME_MEDIA_AI_URI=mariadb+mariadbconnector://USERNAME:PASSWORD@NAS_IP:3306/home_media_ai
```

Replace:
- `USERNAME`: Your MariaDB username
- `PASSWORD`: Your MariaDB password (URL-encode special characters)
- `NAS_IP`: IP address of your NAS or `127.0.0.1` if database is on same NAS
- `3306`: MariaDB port (change if your database uses a different port)

**Example:**
```yaml
HOME_MEDIA_AI_URI=mariadb+mariadbconnector://media_user:SecurePass123@192.168.1.100:3306/home_media_ai
```

**Note:** Special characters in passwords should be URL-encoded:
- Space → `%20`
- `!` → `%21`
- `#` → `%23`
- `@` → `%40`

#### 1.2 User and Group ID

Update the `user` field (line 10) to match a NAS user that has read access to your media files:

```yaml
user: "UID:GID"
```

To find your user's UID and GID:
1. SSH into your Synology NAS
2. Run: `id YOUR_USERNAME`
3. Use the uid and gid values shown

**Example:**
```yaml
user: "1034:65539"  # Example: media_user
```

This ensures the container can read your media files with proper permissions.

#### 1.3 Media Directory Path

Update the volume mount (line 19) to point to your actual media directory:

```yaml
volumes:
  - /volume1/photo/RAW:/mnt/media
```

Replace `/volume1/photo/RAW` with the actual path to your media files on the NAS. The `:/mnt/media` part should remain unchanged as it's the mount point inside the container.

**Examples:**
```yaml
- /volume1/photos:/mnt/media          # If photos are in /volume1/photos
- /volume2/media/photos:/mnt/media    # If photos are on volume2
```

**Important:** The paths stored in your MariaDB database must match the container's internal path structure. If your database contains paths like `/volume1/photo/RAW/2024/IMG_001.jpg`, you should mount `/volume1/photo/RAW` to `/mnt/media`.

### Step 2: Deploy Using Container Manager

1. **Open Container Manager** on your Synology NAS (in Package Center, it may be called "Container Manager" or "Docker")

2. **Navigate to Projects** in the left sidebar

3. **Create New Project:**
   - Click "Create"
   - Enter project name: `home-media-viewer`
   - Set path: Choose a location to store the project files

4. **Upload Files:**
   - Copy all files from this directory to the project folder:
     - `docker-compose.yml`
     - `Dockerfile`
     - `app.py`
     - `requirements.txt`
     - `env.txt` (optional reference)
     - `templates/` directory with HTML files

5. **Build and Start:**
   - Container Manager will automatically detect the `docker-compose.yml`
   - Click "Build" to build the Docker image
   - Once built, click "Start" to launch the container

### Step 3: Verify Deployment

1. **Check Container Status:**
   - In Container Manager, go to "Container" section
   - Verify `home-media-viewer` is running (green status)

2. **Check Logs:**
   - Click on the container name
   - Go to "Logs" tab
   - Look for startup messages and any errors

3. **Access Web Interface:**
   - Open browser and navigate to: `http://YOUR_NAS_IP:5100`
   - You should see the Home Media AI gallery interface

## Changing the Web Server Port

The web service port is currently set to **5100**. If you need to change it, you must update **three locations**:

1. **docker-compose.yml** (line 9) - External port mapping:
   ```yaml
   ports:
     - "5100:5100"  # Change first 5100 to your desired port
   ```

2. **docker-compose.yml** (line 9) - Internal port mapping:
   ```yaml
   ports:
     - "5100:5100"  # Change second 5100 to match
   ```

   **Note:** If using `network_mode: host`, the container uses the host's network directly. The port mapping becomes informational, but you should still ensure both values match.

3. **app.py** (line 424) - Flask development server port:
   ```python
   app.run(host='0.0.0.0', port=5100, debug=False)  # Change 5100
   ```

   **Note:** In production with gunicorn, the port is set in [Dockerfile](Dockerfile) line 27:
   ```dockerfile
   CMD ["gunicorn", "--bind", "0.0.0.0:5100", ...]
   ```

   The internal gunicorn port (5000) should typically stay as-is unless you need to change the internal routing.

**Example: Changing to port 8080:**
```yaml
# docker-compose.yml
ports:
  - "8080:8080"
```
```python
# app.py
app.run(host='0.0.0.0', port=8080, debug=False)
```

After changing ports, rebuild the container in Container Manager.

## Configuration Reference

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `HOME_MEDIA_AI_URI` | MariaDB connection string | None | **Yes** |
| `PHOTO_ROOT` | Internal container path for media | `/mnt/media` | No |
| `FLASK_ENV` | Flask environment mode | `production` | No |

### Volume Mounts

The container needs read-only access to your media files:

```yaml
volumes:
  - /host/path/to/media:/mnt/media:ro
```

- Left side: Path on your NAS
- Right side: Path inside container (should be `/mnt/media`)
- `:ro` suffix: Read-only mount (recommended for safety)

### Network Mode

The service uses `network_mode: host` which means it shares the host's network stack. This simplifies networking on Synology but means the container uses the host's ports directly.

## Troubleshooting

### Container Won't Start

1. **Check logs** in Container Manager
2. **Verify database connection:**
   - Ensure MariaDB is running
   - Test connection string with a database client
   - Check firewall rules on database port
3. **Check user permissions:**
   - Verify UID:GID has read access to media directory
   - Test by SSHing as that user and running `ls /volume1/photo/RAW`

### Images Not Loading

1. **Check volume mount:**
   - Verify the host path exists: `/volume1/photo/RAW`
   - Check container can access: `docker exec home-media-viewer ls /mnt/media`
2. **Check database paths:**
   - Ensure paths in database match container's internal structure
   - Database path `/volume1/photo/RAW/IMG.jpg` requires mount at `/volume1/photo/RAW:/mnt/media`

### Permission Errors

1. **Verify user/group ID:**
   - Check the `user:` field in docker-compose.yml
   - Ensure that user has read permissions on media files
2. **Check file ownership:**
   ```bash
   ls -la /volume1/photo/RAW
   ```

### Can't Connect to Web Interface

1. **Check port is not in use:**
   ```bash
   netstat -tuln | grep 5100
   ```
2. **Check firewall rules** on Synology
3. **Verify network_mode** allows host access
4. **Try localhost:**
   - From NAS: `curl http://localhost:5100`
   - From network: `curl http://NAS_IP:5100`

### Database Connection Errors

1. **Check connection string format:**
   - Must include: `mariadb+mariadbconnector://`
   - URL-encode special characters in password
2. **Test database connectivity:**
   ```bash
   mysql -h NAS_IP -u USERNAME -p -D home_media_ai
   ```
3. **Check database user privileges:**
   ```sql
   SHOW GRANTS FOR 'USERNAME'@'%';
   ```

## Development

For local development or testing changes:

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set environment variables:**
   ```bash
   export HOME_MEDIA_AI_URI="mariadb+mariadbconnector://user:pass@host:3306/home_media_ai"
   export PHOTO_ROOT="/path/to/local/media"
   ```

3. **Run development server:**
   ```bash
   python app.py
   ```

4. **Access at:** `http://localhost:5100`

## Architecture

- **Web Framework:** Flask 3.1.2
- **Database:** SQLAlchemy 2.0.40 with MariaDB connector
- **Web Server:** Gunicorn (production) with 4 workers
- **Image Processing:** Pillow + rawpy (for RAW formats)
- **Base Image:** Python 3.11-slim

## Security Notes

- Container runs as non-root user (defined by `user:` field)
- Media directory mounted read-only (`:ro`)
- All routes are read-only; no write operations to database or files
- Database connection uses environment variables (never hardcoded)

## Files Overview

| File | Description |
|------|-------------|
| [docker-compose.yml](docker-compose.yml) | Container orchestration and configuration |
| [Dockerfile](Dockerfile) | Container image build instructions |
| [app.py](app.py) | Main Flask application with API routes |
| [requirements.txt](requirements.txt) | Python package dependencies |
| [templates/](templates/) | HTML templates for web interface |
| [env.txt](env.txt) | Example environment configuration (reference only) |

## License

Part of the Home Media AI project.
