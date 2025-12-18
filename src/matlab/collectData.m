function data = collectData(directoryPath, existingPathSet)
    % Loops over image files, establishes parent-child relationships, and sets flags
    % Inputs:
    %   directoryPath - Directory to scan
    %   existingPathSet - (optional) Set of file paths already in database to skip
    
    if nargin < 2
        existingPathSet = string.empty;
    end
    
    % Supported image extensions only
    validExts = {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.heic', '.heif', ...
                 '.dng', '.cr2', '.nef', '.arw', '.orf', '.rw2', '.raw', '.crw', '.cr3'};
    
    rawExts = {'.dng', '.cr2', '.nef', '.arw', '.orf', '.rw2', '.raw', '.crw', '.cr3'};
    
    allFiles = dir(fullfile(directoryPath, '**', '*.*'));
    isFile = ~[allFiles.isdir];
    files = allFiles(isFile);
    
    data = table();
    fprintf('Found %d files in %s\n', length(files), directoryPath);
    
    % Pass 1: Read all images (skip files already in DB)
    validCount = 0;
    skippedCount = 0;
    
    for i = 1:length(files)
        [~, ~, ext] = fileparts(files(i).name);
        
        if ismember(lower(ext), validExts)
            filePath = fullfile(files(i).folder, files(i).name);
            
            % Skip if file path already exists in database
            if ~isempty(existingPathSet) && ismember(string(filePath), existingPathSet)
                skippedCount = skippedCount + 1;
                if mod(skippedCount, 100) == 0
                    fprintf('Skipped %d files already in database\n', skippedCount);
                end
                continue;
            end
            
            validCount = validCount + 1;
            
            try
                rowData = readImage(filePath);
                data = [data; rowData];
                
                if mod(validCount, 100) == 0
                    fprintf('Processed %d new images\n', validCount);
                end
            catch ME
                warning('Error processing %s: %s', filePath, ME.message);
            end
        end
    end
    
    if skippedCount > 0
        fprintf('Skipped %d files already in database\n', skippedCount);
    end
    
    if isempty(data)
        fprintf('No new images found.\n');
        return;
    end
    
    fprintf('Pass 1 complete: Read %d images\n', height(data));
    
    % Pass 2: Establish parent-child relationships
    % Build lookup map: base_filename -> indices
    baseNames = cellfun(@(x) extractBefore(x, strlength(x) - strlength(extractAfter(x, '.')) + 1), ...
                        cellstr(data.filename), 'UniformOutput', false);
    
    % For each file, find its origin
    for i = 1:height(data)
        currentExt = lower(char(data.file_ext(i)));
        currentBase = baseNames{i};
        currentDir = data.directory(i);
        
        % Skip if this is already a raw file (can't have an origin)
        if ismember(currentExt, rawExts)
            continue;
        end
        
        % Look for a raw file with the same base name in the same directory
        for j = 1:height(data)
            if i == j
                continue;
            end
            
            candidateExt = lower(char(data.file_ext(j)));
            candidateBase = baseNames{j};
            candidateDir = data.directory(j);
            
            % Check: same directory, same base name, candidate is raw
            if strcmp(currentDir, candidateDir) && ...
               strcmp(currentBase, candidateBase) && ...
               ismember(candidateExt, rawExts)
                
                % Found the origin!
                data.is_original(i) = 0;
                data.origin_id(i) = j;  % Store index (will need ID after DB insert)
                break;
            end
        end
    end
    
    fprintf('Pass 2 complete: Established parent-child relationships\n');
    
    % Pass 3: Set is_final flags
    % A file is final only if no other file has it as an origin
    hasChildren = false(height(data), 1);
    
    for i = 1:height(data)
        if ~isnan(data.origin_id(i))
            parentIdx = data.origin_id(i);
            hasChildren(parentIdx) = true;
        end
    end
    
    data.is_final = ~hasChildren;
    
    fprintf('Pass 3 complete: Set is_final flags\n');
    fprintf('Summary: %d originals, %d derivatives, %d final\n', ...
            sum(data.is_original), sum(~data.is_original), sum(data.is_final));
    
    fprintf('Successfully collected data from %d images\n', height(data));
end