function generate_thumbnails(varargin)
% GENERATE_THUMBNAILS Generate thumbnails for media files in parallel
%
% Usage:
%   generate_thumbnails()                    % Use all defaults
%   generate_thumbnails('workers', 8)        % Specify number of workers
%   generate_thumbnails('limit', 1000)       % Limit number to process
%   generate_thumbnails('batch_size', 100)   % Batch size for DB commits
%
% Options:
%   'workers'      - Number of parallel workers (default: feature('numcores'))
%   'limit'        - Maximum number of thumbnails to generate (default: inf)
%   'batch_size'   - Number of items to process before DB commit (default: 100)
%   'max_dim'      - Maximum thumbnail dimension (default: 800)
%   'quality'      - JPEG quality 1-100 (default: 85)

    % Load database config from Python config.yaml
    db_config = load_db_config();

    % Parse arguments
    p = inputParser;
    addParameter(p, 'workers', feature('numcores'), @isnumeric);
    addParameter(p, 'limit', inf, @isnumeric);
    addParameter(p, 'batch_size', 100, @isnumeric);
    addParameter(p, 'max_dim', 800, @isnumeric);
    addParameter(p, 'quality', 85, @isnumeric);
    % Database params - use config.yaml values as defaults, allow override
    addParameter(p, 'db_host', db_config.host, @ischar);
    addParameter(p, 'db_port', db_config.port, @isnumeric);
    addParameter(p, 'db_name', db_config.database, @ischar);
    addParameter(p, 'db_user', db_config.user, @ischar);
    addParameter(p, 'db_pass', db_config.password, @ischar);
    parse(p, varargin{:});

    opts = p.Results;

    fprintf('Starting thumbnail generation with %d workers...\n', opts.workers);

    % Connect to database using JDBC
    fprintf('Connecting to database %s@%s:%d...\n', opts.db_name, opts.db_host, opts.db_port);

    % Setup MySQL JDBC driver
    % Download from: https://dev.mysql.com/downloads/connector/j/
    % Or use: https://repo1.maven.org/maven2/mysql/mysql-connector-java/8.0.33/mysql-connector-java-8.0.33.jar
    jdbc_driver = 'com.mysql.cj.jdbc.Driver';
    jdbc_url = sprintf('jdbc:mysql://%s:%d/%s?characterEncoding=UTF-8&serverTimezone=UTC', ...
        opts.db_host, opts.db_port, opts.db_name);

    try
        conn = database(opts.db_name, opts.db_user, opts.db_pass, ...
            jdbc_driver, jdbc_url);
    catch ME
        fprintf('JDBC connection failed. Trying alternative method...\n');
        fprintf('Error: %s\n', ME.message);
        fprintf('\nTo fix this, download MySQL Connector/J:\n');
        fprintf('1. Download from: https://dev.mysql.com/downloads/connector/j/\n');
        fprintf('2. Extract mysql-connector-java-X.X.XX.jar\n');
        fprintf('3. Add to MATLAB path: javaaddpath(''/path/to/mysql-connector-java-X.X.XX.jar'')\n');
        fprintf('4. Run this script again\n\n');
        error('Database connection failed');
    end

    if ~isopen(conn)
        error('Failed to connect to database');
    end

    % Query media items without thumbnails
    fprintf('Querying media items without thumbnails...\n');
    query = ['SELECT id, storage_root, directory, filename, file_ext ' ...
             'FROM media WHERE thumbnail_path IS NULL'];

    if ~isinf(opts.limit)
        query = [query ' LIMIT ' num2str(opts.limit)];
    end

    data = fetch(conn, query);
    total = size(data, 1);
    fprintf('Found %d media items without thumbnails\n', total);

    if total == 0
        close(conn);
        return;
    end

    % Convert to structure array for parfor
    media_items = struct();
    for i = 1:total
        media_items(i).id = data{i, 1};
        media_items(i).storage_root = data{i, 2};
        media_items(i).directory = data{i, 3};
        media_items(i).filename = data{i, 4};
        media_items(i).file_ext = data{i, 5};
    end

    % Close main connection (each worker will create its own)
    close(conn);

    % Start parallel pool
    if isempty(gcp('nocreate'))
        parpool(opts.workers);
    end

    % Process in batches
    num_batches = ceil(total / opts.batch_size);
    fprintf('Processing %d batches of ~%d items each\n', num_batches, opts.batch_size);

    total_success = 0;
    total_failed = 0;

    for batch_idx = 1:num_batches
        batch_start = (batch_idx - 1) * opts.batch_size + 1;
        batch_end = min(batch_idx * opts.batch_size, total);
        batch_items = media_items(batch_start:batch_end);
        batch_size_actual = length(batch_items);

        fprintf('Processing batch %d/%d (%d items)...\n', ...
            batch_idx, num_batches, batch_size_actual);

        % Initialize results arrays
        thumbnail_paths = cell(batch_size_actual, 1);
        success_flags = false(batch_size_actual, 1);

        % Process batch in parallel
        tic;
        parfor i = 1:batch_size_actual
            item = batch_items(i);

            try
                % Build full path
                if ~isempty(item.directory) && ~strcmp(item.directory, '')
                    full_path = fullfile(item.storage_root, item.directory, item.filename);
                else
                    full_path = fullfile(item.storage_root, item.filename);
                end

                % Generate thumbnail
                thumb_path = generate_single_thumbnail(full_path, item.filename, ...
                    opts.max_dim, opts.quality);

                if ~isempty(thumb_path)
                    thumbnail_paths{i} = thumb_path;
                    success_flags(i) = true;
                end
            catch ME
                warning('Failed to process media %d: %s', item.id, ME.message);
            end
        end
        batch_time = toc;

        % Count successes in this batch
        batch_success = sum(success_flags);
        batch_failed = batch_size_actual - batch_success;

        % Update database for successful items
        if batch_success > 0
            % Reconnect to database for this batch update
            conn_batch = database(opts.db_name, opts.db_user, opts.db_pass, ...
                'Vendor', 'MySQL', 'Server', opts.db_host, 'PortNumber', opts.db_port);

            for i = 1:batch_size_actual
                if success_flags(i)
                    update_query = sprintf(...
                        'UPDATE media SET thumbnail_path = ''%s'' WHERE id = %d', ...
                        thumbnail_paths{i}, batch_items(i).id);
                    execute(conn_batch, update_query);
                end
            end

            close(conn_batch);
        end

        total_success = total_success + batch_success;
        total_failed = total_failed + batch_failed;

        fprintf('Batch %d complete: %d successful, %d failed (%.2f sec, %.1f items/sec)\n', ...
            batch_idx, batch_success, batch_failed, batch_time, batch_size_actual/batch_time);
    end

    fprintf('\n=== COMPLETE ===\n');
    fprintf('Total: %d successful, %d failed\n', total_success, total_failed);
    fprintf('Success rate: %.1f%%\n', 100 * total_success / total);
end

function db_config = load_db_config()
    % Load database configuration from Python config.yaml
    % Searches in standard locations

    % Search paths (same as Python Config.load())
    script_dir = fileparts(mfilename('fullpath'));
    search_paths = {
        fullfile(pwd, 'config.yaml');
        fullfile(script_dir, '..', 'python', 'config.yaml');
        fullfile(script_dir, '..', '..', 'config.yaml');
    };

    config_file = '';
    for i = 1:length(search_paths)
        if isfile(search_paths{i})
            config_file = search_paths{i};
            break;
        end
    end

    if isempty(config_file)
        error('Could not find config.yaml. Please create one in the project root or current directory.');
    end

    fprintf('Loading config from: %s\n', config_file);

    % Read YAML file manually (no external libraries needed)
    fid = fopen(config_file, 'r');
    if fid == -1
        error('Could not open config file: %s', config_file);
    end

    % Read line by line and find database.uri
    db_uri = '';
    in_database_section = false;

    while ~feof(fid)
        line = fgetl(fid);
        if ~ischar(line)
            break;
        end

        % Trim whitespace and skip comments
        line = strtrim(line);
        if isempty(line) || line(1) == '#'
            continue;
        end

        % Check if we're in database section
        if contains(line, 'database:')
            in_database_section = true;
            continue;
        end

        % If we're in database section and find uri
        if in_database_section && contains(line, 'uri:')
            % Extract the URI value
            parts = strsplit(line, ':');
            if length(parts) >= 2
                % Join everything after first colon (in case password has colons)
                uri_part = strjoin(parts(2:end), ':');
                % Remove quotes and whitespace
                db_uri = strtrim(strrep(strrep(uri_part, '"', ''), '''', ''));
                break;
            end
        end

        % Exit database section if we hit another top-level key
        if in_database_section && ~startsWith(line, ' ') && ~startsWith(line, '\t')
            in_database_section = false;
        end
    end

    fclose(fid);

    if isempty(db_uri)
        error('Could not find database.uri in config file');
    end

    fprintf('Found database URI in config\n');

    % Parse database URI
    % Format: mariadb+mariadbconnector://user:password@host:port/database
    pattern = '.*://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)';
    tokens = regexp(db_uri, pattern, 'tokens');

    if isempty(tokens)
        error('Could not parse database URI: %s', db_uri);
    end

    tokens = tokens{1};
    db_config.user = tokens{1};
    db_config.password = tokens{2};
    db_config.host = tokens{3};
    db_config.port = str2double(tokens{4});
    db_config.database = tokens{5};

    fprintf('Database config: %s@%s:%d/%s\n', ...
        db_config.user, db_config.host, db_config.port, db_config.database);
end

function thumb_path = generate_single_thumbnail(source_path, filename, max_dim, quality)
    % Generate a single thumbnail
    % Returns relative path or empty on failure

    thumb_path = '';

    % Check if file exists
    if ~isfile(source_path)
        return;
    end

    try
        % Read image
        img = imread(source_path);

        % Convert to RGB if needed
        if size(img, 3) == 1
            img = repmat(img, [1 1 3]);
        end

        % Apply histogram normalization for uniform appearance
        img = normalize_histogram(img);

        % Resize maintaining aspect ratio
        [h, w, ~] = size(img);
        scale = max_dim / max(h, w);
        if scale < 1
            new_size = round([h, w] * scale);
            img = imresize(img, new_size);
        end

        % Create thumbnail filename
        [~, name, ~] = fileparts(filename);
        thumb_filename = [name '_thumb.jpg'];

        % Save thumbnail in same directory as source
        [source_dir, ~, ~] = fileparts(source_path);
        thumb_full_path = fullfile(source_dir, thumb_filename);

        % Write JPEG
        imwrite(img, thumb_full_path, 'JPEG', 'Quality', quality);

        % Return relative path (just the filename for same directory)
        [~, dir_name] = fileparts(source_dir);
        if ~isempty(dir_name)
            thumb_path = fullfile(dir_name, thumb_filename);
        else
            thumb_path = thumb_filename;
        end

    catch ME
        warning('Error generating thumbnail: %s', ME.message);
    end
end

function img_out = normalize_histogram(img)
    % Apply histogram normalization similar to Python version
    % Uses adaptive histogram equalization on each channel

    img_out = img;

    try
        % Convert to double for processing
        img_double = double(img);

        % Process each channel separately
        for c = 1:size(img, 3)
            channel = img_double(:,:,c);

            % Simple contrast stretch (similar to autocontrast with cutoff)
            low_cutoff = prctile(channel(:), 2);
            high_cutoff = prctile(channel(:), 98);

            channel = (channel - low_cutoff) / (high_cutoff - low_cutoff);
            channel = max(0, min(1, channel));  % Clip to [0, 1]

            img_double(:,:,c) = channel * 255;
        end

        img_out = uint8(img_double);
    catch
        % If normalization fails, return original
        img_out = img;
    end
end
