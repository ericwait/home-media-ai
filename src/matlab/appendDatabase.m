function appendDatabase(dataConnName, directoryPath, dryRun)
    % Appends data from directory to the database
    
    if nargin < 3
        dryRun = false;
    end
    
    % Connect to database FIRST
    conn = database(dataConnName);
    
    % Get existing file paths AND hashes to skip scanning files already in DB
    fprintf('Querying database for existing files...\n');
    existingFiles = fetch(conn, 'SELECT file_path, file_hash FROM home_media_ai.media');
    existingPathSet = string(existingFiles.file_path);
    existingHashSet = string(existingFiles.file_hash);
    fprintf('Found %d existing files in database\n', length(existingPathSet));
    
    % Collect data from directory (passing existing paths to skip)
    fprintf('Scanning directory: %s\n', directoryPath);
    newData = collectData(directoryPath, existingPathSet);
    
    if isempty(newData)
        fprintf('No new images found.\n');
        close(conn);
        return;
    end
    
    % Check for duplicates by hash (using the hashes we already fetched)
    fprintf('Checking for hash duplicates...\n');
    
    isDuplicateByHash = ismember(newData.file_hash, existingHashSet);
    
    % Also check for duplicates within the new data itself
    [~, uniqueIdx] = unique(newData.file_hash, 'stable');
    isDuplicateInternal = true(height(newData), 1);
    isDuplicateInternal(uniqueIdx) = false;
    
    % Combined duplicate check
    isDuplicate = isDuplicateByHash | isDuplicateInternal;
    uniqueData = newData(~isDuplicate, :);
    
    fprintf('Found %d new images (%d duplicate hashes in DB, %d duplicates in batch)\n', ...
            height(uniqueData), sum(isDuplicateByHash), sum(isDuplicateInternal));
    
    if dryRun
        fprintf('\n=== DRY RUN MODE ===\n');
        fprintf('Would insert %d rows:\n', height(uniqueData));
        if height(uniqueData) > 0
            disp(uniqueData(:, {'filename', 'file_ext', 'is_original', 'is_final', 'camera_model'}));
        end
        
        if sum(isDuplicateInternal) > 0
            fprintf('\nDuplicate files within batch:\n');
            dupData = newData(isDuplicateInternal, :);
            disp(dupData(:, {'file_path', 'file_hash'}));
        end
        
        close(conn);
        return;
    end
    
    if height(uniqueData) == 0
        fprintf('No new data to insert - all files already in database.\n');
        close(conn);
        return;
    end
    
    % Build hash -> origin_hash mapping for relationship tracking
    hashToOriginHash = containers.Map('KeyType', 'char', 'ValueType', 'char');
    
    for i = 1:height(uniqueData)
        if ~isnan(uniqueData.origin_id(i))
            childHash = char(uniqueData.file_hash(i));
            newDataIdx = find(strcmp(newData.file_hash, uniqueData.file_hash(i)), 1);
            if ~isempty(newDataIdx)
                originalParentIdx = newData.origin_id(newDataIdx);
                if ~isnan(originalParentIdx) && originalParentIdx <= height(newData)
                    parentHash = char(newData.file_hash(originalParentIdx));
                    hashToOriginHash(childHash) = parentHash;
                end
            end
        end
    end
    
    % Split into originals and derivatives based on hash mapping
    hasOriginInBatch = false(height(uniqueData), 1);
    for i = 1:height(uniqueData)
        childHash = char(uniqueData.file_hash(i));
        if hashToOriginHash.isKey(childHash)
            hasOriginInBatch(i) = true;
        end
    end
    
    % Split data
    originalsData = uniqueData(~hasOriginInBatch, :);
    derivativesData = uniqueData(hasOriginInBatch, :);
    
    % Temporarily set origin_id to NULL for all
    originalsData.origin_id(:) = NaN;
    derivativesData.origin_id(:) = NaN;
    
    % FIX: Convert missing columns to proper string arrays
    stringCols = {'camera_make', 'camera_model', 'lens_model', 'thumbnail_path'};
    for i = 1:length(stringCols)
        col = stringCols{i};
        if ismember(col, originalsData.Properties.VariableNames)
            colData = originalsData.(col);
            if isa(colData, 'missing')
                originalsData.(col) = repmat("", height(originalsData), 1);
            else
                originalsData.(col) = string(colData);
                originalsData.(col)(ismissing(originalsData.(col))) = "";
            end
        end
        if ~isempty(derivativesData) && ismember(col, derivativesData.Properties.VariableNames)
            colData = derivativesData.(col);
            if isa(colData, 'missing')
                derivativesData.(col) = repmat("", height(derivativesData), 1);
            else
                derivativesData.(col) = string(colData);
                derivativesData.(col)(ismissing(derivativesData.(col))) = "";
            end
        end
    end
    
    % FIX: Convert logical columns to double
    logicalCols = {'is_original', 'is_final', 'is_removed'};
    for i = 1:length(logicalCols)
        col = logicalCols{i};
        if ismember(col, originalsData.Properties.VariableNames)
            originalsData.(col) = double(originalsData.(col));
        end
        if ~isempty(derivativesData) && ismember(col, derivativesData.Properties.VariableNames)
            derivativesData.(col) = double(derivativesData.(col));
        end
    end
    
    try
        % Phase 1: Insert originals in batches
        if height(originalsData) > 0
            fprintf('Inserting %d originals...\n', height(originalsData));
            
            % Double-check for duplicates in originals batch
            [~, uniqueOrigIdx] = unique(originalsData.file_hash, 'stable');
            if length(uniqueOrigIdx) < height(originalsData)
                warning('Found %d duplicate hashes within originals batch, removing...', ...
                        height(originalsData) - length(uniqueOrigIdx));
                originalsData = originalsData(uniqueOrigIdx, :);
            end
            
            batchSize = 500;
            numBatches = ceil(height(originalsData) / batchSize);
            
            for batch = 1:numBatches
                startIdx = (batch - 1) * batchSize + 1;
                endIdx = min(batch * batchSize, height(originalsData));
                batchData = originalsData(startIdx:endIdx, :);
                
                fprintf('  Batch %d/%d (%d rows)...\n', batch, numBatches, height(batchData));
                
                if ~isopen(conn)
                    fprintf('  Reconnecting to database...\n');
                    conn = database(dataConnName);
                end
                
                sqlwrite(conn, 'media', batchData);
            end
            
            fprintf('Successfully inserted %d originals.\n', height(originalsData));
        end
        
        % Phase 2: Insert derivatives in batches (WITHOUT origin_id to avoid trigger)
        if height(derivativesData) > 0
            fprintf('Processing %d derivatives...\n', height(derivativesData));

            % Double-check for duplicates in derivatives batch
            [~, uniqueDerivIdx] = unique(derivativesData.file_hash, 'stable');
            if length(uniqueDerivIdx) < height(derivativesData)
                warning('Found %d duplicate hashes within derivatives batch, removing...', ...
                        height(derivativesData) - length(uniqueDerivIdx));
                derivativesData = derivativesData(uniqueDerivIdx, :);
            end

            % Build hash -> ID mapping
            allHashes = unique([originalsData.file_hash; derivativesData.file_hash]);
            hashList = "'" + strjoin(allHashes, "','") + "'";

            % Reconnect if needed
            if ~isopen(conn)
                fprintf('Reconnecting to database...\n');
                conn = database(dataConnName);
            end

            query = sprintf('SELECT id, file_hash FROM home_media_ai.media WHERE file_hash IN (%s)', hashList);
            allFiles = fetch(conn, query);

            if isempty(allFiles) || height(allFiles) == 0
                warning('No parent files found in database for derivatives');
                hashToId = containers.Map('KeyType', 'char', 'ValueType', 'double');
            else
                hashToId = containers.Map(string(allFiles.file_hash), allFiles.id);
            end

            % Set origin_id for derivatives
            foundParents = 0;
            originIdMap = containers.Map('KeyType', 'char', 'ValueType', 'double');

            for i = 1:height(derivativesData)
                childHash = char(derivativesData.file_hash(i));

                if hashToOriginHash.isKey(childHash)
                    parentHash = hashToOriginHash(childHash);

                    if hashToId.isKey(parentHash)
                        originIdMap(childHash) = hashToId(parentHash);
                        foundParents = foundParents + 1;
                    end
                end
            end

            fprintf('Found parents for %d/%d derivatives\n', foundParents, height(derivativesData));

            % CLEAR origin_id before insert to avoid trigger issues
            derivativesData.origin_id(:) = NaN;

            % Insert derivatives in batches WITHOUT origin_id
            fprintf('Inserting %d derivatives...\n', height(derivativesData));

            batchSize = 500;
            numBatches = ceil(height(derivativesData) / batchSize);

            for batch = 1:numBatches
                startIdx = (batch - 1) * batchSize + 1;
                endIdx = min(batch * batchSize, height(derivativesData));
                batchData = derivativesData(startIdx:endIdx, :);

                fprintf('  Batch %d/%d (%d rows)...\n', batch, numBatches, height(batchData));

                % Reconnect if needed
                if ~isopen(conn)
                    fprintf('  Reconnecting to database...\n');
                    conn = database(dataConnName);
                end

                sqlwrite(conn, 'media', batchData);
            end

            fprintf('Successfully inserted %d derivatives.\n', height(derivativesData));

            % Now update origin_id in a single batch UPDATE statement
            if ~originIdMap.isempty
                fprintf('Updating origin_id relationships...\n');

                if ~isopen(conn)
                    fprintf('Reconnecting to database...\n');
                    conn = database(dataConnName);
                end

                % DISABLE TRIGGERS
                execute(conn, 'SET @DISABLE_TRIGGERS = 1');

                % Build CASE statement for batch update
                hashes = originIdMap.keys();
                caseStatements = cell(length(hashes), 1);
                hashesForWhere = cell(length(hashes), 1);

                for i = 1:length(hashes)
                    childHash = hashes{i};
                    parentId = originIdMap(childHash);
                    caseStatements{i} = sprintf('WHEN file_hash = ''%s'' THEN %d', childHash, parentId);
                    hashesForWhere{i} = sprintf('''%s''', childHash);
                end

                % Execute batch update
                updateQuery = sprintf(['UPDATE home_media_ai.media SET origin_id = CASE %s END ' ...
                                      'WHERE file_hash IN (%s)'], ...
                                      strjoin(caseStatements, ' '), ...
                                      strjoin(hashesForWhere, ','));

                execute(conn, updateQuery);

                % RE-ENABLE TRIGGERS
                execute(conn, 'SET @DISABLE_TRIGGERS = 0');

                fprintf('Updated origin_id for %d derivatives.\n', length(hashes));
            end
        end
        
    catch ME
        fprintf('Error inserting data: %s\n', ME.message);
        close(conn);
        rethrow(ME);
    end
    
    % Close connection
    close(conn);
end
