%% User Settings
outputBaseDir = 'C:\Users\ericw\OneDrive\Pictures';
rawDir = '\\tiger\photo\RAW';
dateStart = datetime(2025,01,01);
dateEnd   = datetime(2026,01,01);
minRating = 4;

%% Make connection to database
conn = database('mariaDB');

% Set query to execute on the database
query = sprintf(['SELECT id, created, file_ext, directory, filename, rating ' ...
    'FROM home_media_ai.media ' ...
    'WHERE created >= ''%s'' AND created < ''%s'' ' ...
    'AND rating >= %d ' ...
    'AND is_removed = 0'], ...
    string(dateStart, 'yyyy-MM-dd'), ...
    string(dateEnd, 'yyyy-MM-dd'), ...
    minRating);

% Execute query and fetch results
data = fetch(conn, query);

% Close connection to database
close(conn);

% Clear variables
clear conn query

if isempty(data)
    disp('No images found matching criteria.');
    return;
end

% --- Prioritize JPGs for identical timestamps/filenames ---
% 1. Ensure 'created' is datetime for reliable sorting
if iscell(data.created)
    % MariaDB might return strings
    try
        data.created = datetime(data.created);
    catch
        data.created = datetime(data.created, 'InputFormat', 'yyyy-MM-dd HH:mm:ss');
    end
end

% 2. Extract base filenames and extension priority
[~, baseNames, ~] = cellfun(@fileparts, data.filename, 'UniformOutput', false);
data.base_name = baseNames;

% Priority: JPG/JPEG = 1, others = 2
isJpg = strcmpi(data.file_ext, '.jpg') | strcmpi(data.file_ext, '.jpeg');
data.priority = 2 - isJpg; 

% 3. Sort so JPGs come first for each (created, base_name) pair
data = sortrows(data, {'created', 'base_name', 'priority'});

% 4. Keep only the first (best) version for each unique photo
[~, uniqueIdx] = unique(data(:, {'created', 'base_name'}), 'stable');
data = data(uniqueIdx, :);

numImages = height(data);
fprintf('Found %d unique images to process.\n', numImages);

%% Process Images

% Setup parallel pool and data queue for progress
try
    pool = gcp; % Get current pool or create one
catch
    warning('Unable to start parallel pool. Running in serial might fail if parfor is used.');
end

q = parallel.pool.DataQueue;
afterEach(q, @(idx) fprintf('Processed up to index: %d\n', idx));

% Loop through data in parallel
parfor rowIndex = 1:numImages
% for rowIndex = 1:numImages
    % Send progress update every 10 images
    if mod(rowIndex, 10) == 0
        send(q, rowIndex);
    end

    row = data(rowIndex, :);
    
    % Skip videos
    fileExt = row.file_ext{1};
    if strcmpi(fileExt, '.avi') || strcmpi(fileExt, '.mp4') || strcmpi(fileExt, '.mov')
        % fprintf('Skipping video: %s\n', row.filename{1});
        continue;
    end

    % Construct Source Path
    % Handle potential empty directory (though schema says varchar)
    if ismissing(row.directory) || isempty(row.directory{1})
        srcDir = '';
    else
        srcDir = row.directory{1};
    end
    
    filePathIn = fullfile(rawDir, srcDir, row.filename{1});

    % Construct Output Path
    % Structure: Month/Rating (e.g., 2025-01/5-star)
    rawDate = row.created;
    if iscell(rawDate)
        % If it's a cell, it's likely a string from the DB
        try
            creationDate = datetime(rawDate{1});
        catch
            % Try specifying format if default fails (MariaDB default)
            creationDate = datetime(rawDate{1}, 'InputFormat', 'yyyy-MM-dd HH:mm:ss');
        end
    elseif isdatetime(rawDate)
        % If it's already a datetime object
        creationDate = rawDate;
    else
        % warning('Unknown date format for %s', row.filename{1});
        continue;
    end
    
    monthStr = string(creationDate, 'yyyy-MM');
    ratingStr = sprintf('%d-star', row.rating);
    
    destDir = fullfile(outputBaseDir, monthStr, ratingStr);
    
    % Ensure destination directory exists
    % Use [~,~] = mkdir(...) to suppress warnings if it already exists
    if ~exist(destDir, 'dir')
        [~, ~, ~] = mkdir(destDir);
    end
    
    % Destination filename (change extension to .jpg)
    [~, name, ~] = fileparts(row.filename{1});
    destFilename = [name, '.jpg'];
    filePathOut = fullfile(destDir, destFilename);

    % Skip if already exists
    if exist(filePathOut, 'file')
        % fprintf('Skipping existing: %s\n', destFilename);
        continue;
    end

    % Read and Write Image
    try
        % Read image
        im = imread(filePathIn);
        
        % Handle orientation
        try
            % Suppress warnings (e.g. XMP compliance) during metadata read
            origWarn = warning('off', 'all');
            try
                info = imfinfo(filePathIn);
            catch
                info = [];
            end
            warning(origWarn);
            
            if ~isempty(info) && isfield(info, 'Orientation')
                im = orientImage(im, info.Orientation);
            end
        catch err
            warning(err.message)
            % If reading metadata fails, proceed with unrotated image
        end
        
        % Ensure uint8
        im = im2uint8(im);
        
        % Write high quality JPEG (Quality 95)
        imwrite(im, filePathOut, 'jpg', 'Quality', 95);
        
    catch exception
        % warning('Unable to process %s: %s', filePathIn, exception.message);
    end
end

disp('Export complete.');