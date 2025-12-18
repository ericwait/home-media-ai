function exifData = readExifWithExifTool(filePath)
    % Use ExifTool to extract EXIF as JSON
    % Requires exiftool to be in system PATH
    % Download from: https://exiftool.org/
    
    % Call exiftool with -j (JSON), -n (numeric GPS)
    [status, result] = system(sprintf('exiftool -j -n "%s"', filePath));
    
    if status ~= 0
        error('ExifTool failed: %s', result);
    end
    
    % Remove any BOM or whitespace
    result = strtrim(result);
    
    try
        % Parse JSON output (returns array with one element)
        exifArray = jsondecode(result);
        
        if isempty(exifArray)
            error('ExifTool returned empty result');
        end
        
        % Get first element (should be a struct)
        if iscell(exifArray)
            exifData = exifArray{1};
        elseif isstruct(exifArray)
            if ~isempty(exifArray)
                exifData = exifArray(1);
            else
                error('Empty struct array from ExifTool');
            end
        else
            error('Unexpected data type from ExifTool: %s', class(exifArray));
        end
        
    catch ME
        fprintf('ExifTool JSON output:\n%s\n', result);
        rethrow(ME);
    end
end
