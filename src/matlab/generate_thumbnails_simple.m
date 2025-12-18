function generate_thumbnails_simple(varargin)
% GENERATE_THUMBNAILS_SIMPLE Generate thumbnails using Python for DB access
%
% This version uses Python for database queries and updates, making it easier
% to run without JDBC driver setup. The heavy lifting (image processing) is
% still done in parallel by MATLAB.
%
% Usage:
%   generate_thumbnails_simple()                    % Use all defaults
%   generate_thumbnails_simple('workers', 16)       % Specify workers
%   generate_thumbnails_simple('limit', 1000)       % Limit for testing
%
% Options:
%   'workers'      - Number of parallel workers (default: feature('numcores'))
%   'limit'        - Maximum number to process (default: inf)
%   'batch_size'   - Batch size for processing (default: 200)
%   'max_dim'      - Maximum thumbnail dimension (default: 800)
%   'quality'      - JPEG quality 1-100 (default: 85)

    % Parse arguments
    p = inputParser;
    addParameter(p, 'workers', feature('numcores'), @isnumeric);
    addParameter(p, 'limit', inf, @isnumeric);
    addParameter(p, 'batch_size', 200, @isnumeric);
    addParameter(p, 'max_dim', 800, @isnumeric);
    addParameter(p, 'quality', 85, @isnumeric);
    parse(p, varargin{:});

    opts = p.Results;

    fprintf('Starting thumbnail generation with %d workers...\n', opts.workers);

    % Get Python helper script path
    script_dir = fileparts(mfilename('fullpath'));
    python_helper = fullfile(script_dir, 'thumbnail_db_helper.py');

    % Check if Python helper exists
    if ~isfile(python_helper)
        error('Python helper script not found: %s\nPlease run from the correct directory.', python_helper);
    end

    % Query database via Python to get list of media items
    fprintf('Querying database for media without thumbnails...\n');
    limit_arg = '';
    if ~isinf(opts.limit)
        limit_arg = sprintf('--limit %d', opts.limit);
    end

    cmd = sprintf('python "%s" query %s', python_helper, limit_arg);
    [status, output] = system(cmd);

    if status ~= 0
        error('Failed to query database:\n%s', output);
    end

    % Parse JSON output
    media_items = jsondecode(output);
    total = length(media_items);
    fprintf('Found %d media items without thumbnails\n', total);

    if total == 0
        return;
    end

    % Start parallel pool
    pool = gcp('nocreate');
    if isempty(pool)
        parpool(opts.workers);
    elseif pool.NumWorkers ~= opts.workers
        delete(pool);
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

        % Initialize results
        media_ids = zeros(batch_size_actual, 1);
        thumbnail_paths = cell(batch_size_actual, 1);
        success_flags = false(batch_size_actual, 1);

        % Process batch in parallel
        tic;
        parfor i = 1:batch_size_actual
            item = batch_items(i);

            try
                % Build full path
                if ~isempty(item.directory) && ~strcmp(item.directory, 'null')
                    full_path = fullfile(item.storage_root, item.directory, item.filename);
                else
                    full_path = fullfile(item.storage_root, item.filename);
                end

                % Generate thumbnail
                thumb_path = generate_thumbnail_file(full_path, item.filename, ...
                    opts.max_dim, opts.quality);

                if ~isempty(thumb_path)
                    media_ids(i) = item.id;
                    thumbnail_paths{i} = thumb_path;
                    success_flags(i) = true;
                end
            catch ME
                % Silent failure - will be counted as failed
            end
        end
        batch_time = toc;

        % Count successes
        batch_success = sum(success_flags);
        batch_failed = batch_size_actual - batch_success;

        % Update database via Python for successful items
        if batch_success > 0
            fprintf('Updating database for %d successful thumbnails...\n', batch_success);

            % Create temporary JSON file with updates
            temp_file = tempname;
            updates = struct('media_id', {}, 'thumbnail_path', {});
            update_idx = 1;
            for i = 1:batch_size_actual
                if success_flags(i)
                    updates(update_idx).media_id = media_ids(i);
                    updates(update_idx).thumbnail_path = thumbnail_paths{i};
                    update_idx = update_idx + 1;
                end
            end

            % Write updates to temp file
            fid = fopen(temp_file, 'w');
            fprintf(fid, '%s', jsonencode(updates));
            fclose(fid);

            % Call Python to update database
            cmd = sprintf('python "%s" update "%s"', python_helper, temp_file);
            [status, output] = system(cmd);

            % Clean up temp file
            delete(temp_file);

            if status ~= 0
                warning('Failed to update database:\n%s', output);
            end
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

function thumb_path = generate_thumbnail_file(source_path, filename, max_dim, quality)
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

        % Apply histogram normalization
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

        % Save in same directory as source
        [source_dir, ~, ~] = fileparts(source_path);
        thumb_full_path = fullfile(source_dir, thumb_filename);

        % Write JPEG
        imwrite(img, thumb_full_path, 'JPEG', 'Quality', quality);

        % Return relative path
        [~, parent_name] = fileparts(source_dir);
        if ~isempty(parent_name)
            thumb_path = fullfile(parent_name, thumb_filename);
        else
            thumb_path = thumb_filename;
        end

    catch
        % Return empty on any error
        thumb_path = '';
    end
end

function img_out = normalize_histogram(img)
    % Apply histogram normalization

    img_out = img;

    try
        img_double = double(img);

        for c = 1:size(img, 3)
            channel = img_double(:,:,c);
            low_cutoff = prctile(channel(:), 2);
            high_cutoff = prctile(channel(:), 98);
            channel = (channel - low_cutoff) / (high_cutoff - low_cutoff);
            channel = max(0, min(1, channel));
            img_double(:,:,c) = channel * 255;
        end

        img_out = uint8(img_double);
    catch
        img_out = img;
    end
end
