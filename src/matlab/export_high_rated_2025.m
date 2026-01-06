%% User Settings
outputBaseDir = 'C:\Users\ericw\OneDrive\Pictures';
rawDir = '\\tiger\photo\RAW';
dateStart = datetime(2025,01,01);
dateEnd   = datetime(2026,01,01);
minRating = 4;

%% Make connection to database
conn = database('mariaDB');

% Set query to execute on the database
query = sprintf(['SELECT id, ' ...
    '   created, ' ...
    '\tfile_ext, ' ...
    '   directory, ' ...
    '\tfilename, ' ...
    '   rating ' ...
    'FROM home_media_ai.media ' ...
    'WHERE created >= \'%s\' AND created < \'%s\' ' ...
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

%% Process Images
if isempty(data)
    disp('No images found matching criteria.');
    return;
end

fprintf('Found %d images to process.\n', height(data));

% Use parallel pool if available, otherwise regular for loop
% Checking for parallel pool (optional, matching sandbox style)
% q = parallel.pool.DataQueue;
% afterEach(q, @(x)(fprintf('%d, ', x)));

% Loop through data
for rowIndex = 1:height(data)
    % Progress indication
    if mod(rowIndex, 10) == 0
        fprintf('Processing %d / %d\n', rowIndex, height(data));
    end

    row = data(rowIndex, :);
    
    % Skip videos
    fileExt = row.file_ext{1};
    if strcmpi(fileExt, '.avi') || strcmpi(fileExt, '.mp4') || strcmpi(fileExt, '.mov')
        fprintf('Skipping video: %s\n', row.filename{1});
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
        warning('Unknown date format for %s', row.filename{1});
        continue;
    end
    
    monthStr = string(creationDate, 'yyyy-MM');
    ratingStr = sprintf('%d-star', row.rating);
    
    destDir = fullfile(outputBaseDir, monthStr, ratingStr);
    
    % Ensure destination directory exists
    if ~exist(destDir, 'dir')
        mkdir(destDir);
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
        
        % Ensure uint8
        im = im2uint8(im);
        
        % Write high quality JPEG (Quality 95)
        imwrite(im, filePathOut, 'jpg', 'Quality', 95);
        
    catch exception
        warning('Unable to process %s: %s', filePathIn, exception.message);
    end
end

disp('Export complete.');
