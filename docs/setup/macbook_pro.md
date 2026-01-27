# MacBook Pro Setup ("The Server")

## Role

* **Name:** The Server / The Brain
* **Function:** Hosts the core application, database, and user interface.
* **Availability:** Always-on (or Wake-on-LAN capable).

## Hardware Configuration

* **Storage:**
    * **Internal NVMe:** Hosting the OS, Code, PostgreSQL Database (for speed), and Redis.
    * **DAS (Direct Attached Storage):** Hosting generated thumbnails, proxy files, and potentially the vector index if it grows too large.
* **Network:** Wired Ethernet preferred for stable NAS connection.

## Software Stack & Installation

### 1. Prerequisites

* **OS:** macOS (latest stable).
* **Package Manager:** Homebrew (`brew`).
* **Runtime:**
    * Python 3.11+ (via Conda/Mamba recommended).
    * Node.js (for React frontend).

### 2. Database (PostgreSQL)

For optimal performance with large media datasets and vector embeddings, use PostgreSQL 16+ and the `pgvector` extension.

* **Install PostgreSQL and pgvector:**

    ```bash
    # Install PostgreSQL 18 (latest stable)
    brew install postgresql@18
    brew link postgresql@18 --force

    # Install pgvector extension
    brew install pgvector
    ```

* **Initialize and Start:**

    ```bash
    # Start the service
    brew services start postgresql@18
    ```

* **Optimization (Performance Tuning):**
    The configuration file (`postgresql.conf`) is located in your data directory.
    * **Apple Silicon:** `/opt/homebrew/var/postgresql@18/postgresql.conf`
    * **Intel Mac:** `/usr/local/var/postgresql@18/postgresql.conf`

    *Tip: To be 100% sure, run this command after starting the service:*
    `psql postgres -c 'SHOW config_file;'`

    Update the file with these settings:

    ```bash
    # Key settings for a Mac with 32GB RAM:
    shared_buffers = 8GB             # ~25% of RAM
    work_mem = 64MB                 # For complex queries/sorts
    maintenance_work_mem = 1GB      # For index creation (pgvector)
    max_parallel_workers_per_gather = 4
    ```

* **Create Database, User, and Extensions:**
    Connect to the default database: `psql postgres`

    ```sql
    -- 1. Create a superuser for remote admin (replace 'admin' and 'secure_pass')
    CREATE USER admin WITH SUPERUSER PASSWORD 'secure_pass';

    -- 2. Create the project database owned by this user
    CREATE DATABASE home_media OWNER admin;
    \c home_media

    -- 3. Enable required extensions
    CREATE EXTENSION IF NOT EXISTS vector;  -- For CLIP embeddings
    CREATE EXTENSION IF NOT EXISTS ltree;   -- For hierarchical taxonomy
    CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; -- For unique identifiers
    ```

* **Remote Access (Exposing to LAN):**
    To manage the DB from another computer (e.g., DBeaver on Windows), you must modify two files in your data directory (path found via `SHOW config_file;`):

    1. **`postgresql.conf`**: Allow the DB to listen on the network.

        ```ini
        listen_addresses = '*'  # Listen on all interfaces (default is 'localhost' only)
        ```

    2. **`pg_hba.conf`**: Allow the remote computer to connect. Add this line **above** the default local rules:

        ```ini
        # TYPE  DATABASE        USER    ADDRESS                 METHOD
        host    all             all     192.168.1.0/24          scram-sha-256
        ```

        *(Note: Replace `192.168.1.0/24` with your actual home subnet, or the specific IP of your Windows machine).*

    3. **macOS Firewall:**
        If your Mac's firewall is on (System Settings -> Network -> Firewall), you must allow incoming connections.
        * Open Firewall Options.
        * Click `+` to add an application.
        * Press `Cmd+Shift+G` and navigate to `/opt/homebrew/opt/postgresql@18/bin/postgres` (or `/usr/local/...` for Intel).
        * Select the `postgres` binary and ensure it is set to "Allow incoming connections".

    4. **Restart PostgreSQL** for changes to take effect:

        ```bash
        brew services restart postgresql@18
        ```

### 2a. Advanced: Moving Data to External Disk

If your NVMe fills up, you can move the database to your DAS (e.g., `/Volumes/Photos`) while keeping the standard Homebrew configuration. **The Symlink Method** is recommended as it survives package upgrades.

1. **Stop PostgreSQL:**

    ```bash
    brew services stop postgresql@18
    ```

2. **Move the Data:**
    Identify your current data directory.
    * **Intel Mac:** `/usr/local/var/postgresql@18`
    * **Apple Silicon:** `/opt/homebrew/var/postgresql@18`

    ```bash
    # Example (Intel Mac): Move to DAS
    # Ensure destination folder parent exists first!
    mkdir -p /Volumes/Photos/postgres_data
    sudo rsync -av /usr/local/var/postgresql@18 /Volumes/Photos/postgres_data/
    ```

3. **Backup & Link:**

    ```bash
    # Rename old folder (keep as backup)
    # Note: Adjust path based on your CPU type (see above)
    mv /usr/local/var/postgresql@18 /usr/local/var/postgresql@18.bak

    # Create the symbolic link
    # The source is the FULL path to the moved 'postgresql@18' folder
    ln -s /Volumes/Photos/postgres_data/postgresql@18 /usr/local/var/postgresql@18
    ```

4. **Restart:**

    ```bash
    brew services start postgresql@18
    ```

### 3. Message Queue (Redis)

Redis brokers the "jobs" between the Mac (Server) and the Alienware (Worker).

* **Install & Start:**

    ```bash
    brew install redis
    brew services start redis
    ```

* **Configuration (Remote Access):**
    By default, Redis only listens on localhost. To let the Alienware connect:
    1. Edit `/usr/local/etc/redis.conf` (Intel) or `/opt/homebrew/etc/redis.conf`.
    2. Find `bind 127.0.0.1 ::1` and change to `bind 0.0.0.0` (or your specific LAN IP).
    3. **Security (Crucial):** Find `requirepass foobared`, uncomment it, and set a strong password.
        `requirepass my_secure_redis_password`
    4. **Restart:** `brew services restart redis`

### 4. Application Services (Process Management)

Use **PM2** (Process Manager 2) to keep your Backend and Frontend running in the background and restarting automatically on boot/crash.

* **Install PM2:**

    ```bash
    npm install -g pm2
    ```

* **Setup Backend (FastAPI):**
    Navigate to the project root. We have provided a startup script in `scripts/server_startup.sh`.

    ```bash
    # Make the script executable
    chmod +x scripts/server_startup.sh

    # Start with PM2
    pm2 start scripts/server_startup.sh --name "home-media-api"
    ```

* **Setup Frontend (React):**

    ```bash
    # Build the production assets
    cd src/react-client
    npm run build

    # Serve with a static file server
    pm2 start "npx serve -s build -l 3000" --name "home-media-ui"
    ```

* **Persistence (Start on Boot):**

    ```bash
    pm2 save
    pm2 startup
    # (Copy/paste the command output by 'pm2 startup' to lock it in)
    ```

### 5. Mounting the Vault (NAS)

The Mac needs a reliable, high-performance connection to the Synology NAS (The Vault) to scan files.

* **Protocol Choice:**
    * **SMB:** Standard for macOS. Good compatibility, but metadata operations (listing 100k files) can be slow.
    * **NFS:** **Recommended for scanning.** Much faster directory listing ("stat") performance.

* **Mount Point:**
    Establish a consistent path, e.g., `/Volumes/media`.

* **Auto-Mounting (The Robust Way):**
    macOS Finder mounts are flaky. Use the **OS X automounter** (`auto_master`) for rock-solid connections.

    1. **Edit `auto_master`:**
        `sudo nano /etc/auto_master`
        Add this line to the end:
        `/-                      auto_nfs        -nobrowse,nosuid`

    2. **Create Map File:**
        `sudo nano /etc/auto_nfs`
        Add the mapping (change IP and Path):
        `/System/Volumes/Data/mnt/nas -fstype=nfs,noowners,nolock,hard,bg,intr,rw 192.168.1.100:/volume1/photos`

    3. **Apply:**
        `sudo automount -vc`

    *Alternatively, for a simpler setup, add the SMB share to "Login Items" in System Settings, though this requires a logged-in user.*

## Deployment Steps (Draft)

```bash
# 1. Clone Repo
git clone ...

# 2. Setup Environment
mamba env create -f environment.yaml

# 3. Start Services
brew services start postgresql@18
brew services start redis

# 4. Run Server
uvicorn src.python.main:app --reload
```

## Appendix A: Troubleshooting Remote Access

If you cannot connect from DBeaver/Windows:

1. **Check IP Reachability:**
    * On Windows: `ping <MAC_IP_ADDRESS>`
    * If this fails, check network isolation or VPN settings.

2. **Verify Port Listening:**
    * On Mac, run: `netstat -an | grep 5432`
    * You should see `tcp4 0 0 *.5432 *.* LISTEN`.
    * If you see `127.0.0.1.5432`, then `listen_addresses = '*'` is not set correctly in `postgresql.conf`.

3. **Check Port Accessibility:**
    * On Windows (PowerShell): `Test-NetConnection -ComputerName <MAC_IP_ADDRESS> -Port 5432`
    * If `TcpTestSucceeded` is `False`, the Mac Firewall is likely blocking the connection. Re-check Step 2a.3 (adding `postgres` binary to firewall whitelist).

4. **Check Authentication Logs:**
    * **Intel Mac:** `tail -f /usr/local/var/log/postgresql@18.log`
    * **Apple Silicon:** `tail -f /opt/homebrew/var/log/postgresql@18.log`
    * *(Note: If not found there, check inside your data directory `.../var/postgresql@18/`)*.
    * Try to connect. If you see "no pg_hba.conf entry", your `pg_hba.conf` subnet rule is wrong.
    * If you see "password authentication failed", double-check your credentials.

5. **Common Error: `FATAL: setsockopt(TCP_NODELAY) failed: Invalid argument`**
    * **Cause:** This is a macOS-specific issue caused by third-party network filters (e.g., **Little Snitch**, **LuLu**, **ESET**) interfering with socket creation. It can also happen if the IPv6 stack is misconfigured.
    * **Fix 1 (Force IPv4):**
        * Open `postgresql.conf`.
        * Change `listen_addresses = '*'` to `listen_addresses = '0.0.0.0'`.
        * Restart PostgreSQL.
    * **Fix 2 (Bind to Specific IP - Recommended if Fix 1 fails):**
        * Find your Mac's actual IP (e.g., `192.168.1.50`).
        * Set `listen_addresses = '192.168.1.50'` (replace with your IP).
        * This often bypasses "global" network filter hooks.
    * **Fix 3 (Check Network Filters):**
        * Go to **System Settings -> Network**.
        * Look for a "Filters" or "VPN & Filters" section.
        * If any content filters or proxies are listed (even if "Disabled"), remove them to test.

    6. **Common Error: Firewall Blocks Connection (Even when "Allowed")**
        * **Cause:** The macOS Application Firewall often ignores rules for **symlinks** (which Homebrew uses extensively). It requires the *actual* binary path.
        * **Fix:**
            1. Remove the existing `postgres` entry from Firewall settings.
            2. Find the real path by running:

                ```bash
                # Intel Mac
                readlink -f /usr/local/opt/postgresql@18/bin/postgres
                # Apple Silicon
                readlink -f /opt/homebrew/opt/postgresql@18/bin/postgres
                ```

            3. The output will look like `/usr/local/Cellar/postgresql@18/18.x/bin/postgres`.
            4. Add **THAT** specific file to the Firewall allowance list.
            5. Restart PostgreSQL.

        * **Fix 2 (The "Nuclear" Option - CLI):**
            If the GUI fails, use the command line tool `socketfilterfw` to force the rule.

            ```bash
            # 1. Get the real path
            REAL_PATH=$(readlink -f /usr/local/opt/postgresql@18/bin/postgres)

            # 2. Add it to the firewall (enter password when prompted)
            sudo /usr/libexec/ApplicationFirewall/socketfilterfw --add "$REAL_PATH"

            # 3. Unblock it explicitly
            sudo /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp "$REAL_PATH"

            # 4. Restart the firewall agent to apply changes
            sudo pkill -HUP socketfilterfw
            ```

    * **Fix 4 (Deep Clean):**
        * Run `systemextensionsctl list` and `kextstat | grep -v com.apple` in terminal.
        * Look for *any* third-party name (Cisco, CrowdStrike, LuLu, Little Snitch). If found, you must uninstall that software completely.

    7. **Common Error: Service Won't Start After Moving Data**
        * **Symptoms:** `netstat` shows nothing on port 5432. `brew services list` shows status `error` or `stopped`.
        * **Fix 1 (Check Permissions):**
            Ensure your user has full control over the external folder.
            `chown -R $(whoami) /Volumes/Photos/postgres_data`
        * **Fix 2 (Check Symlink Nesting):**
            Run `ls -l /usr/local/var/postgresql@18` (or `/opt/homebrew...`).
            It should point to a folder that *directly contains* `postgresql.conf`.
            * *Wrong:* Symlink -> `/Volumes/Photos/postgres_data/postgresql@18/postgresql@18`
            * *Right:* Symlink -> `/Volumes/Photos/postgres_data/postgresql@18`
        * **Fix 3 (Check Log File):**
            Since the service isn't starting, check the log to see why.
            `tail -n 50 /usr/local/var/log/postgresql@18.log`