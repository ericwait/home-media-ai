function [storageRoot, relativeDir] = parseStoragePath(fullPath)
    % Parse full path into storage_root and relative directory
    % Hardcoded for \\tiger\photo\RAW storage
    % Inputs:
    %   fullPath - Full UNC path
    % Outputs:
    %   storageRoot - Always "tiger/photo/RAW"
    %   relativeDir - Relative directory with forward slashes
    
    storageRoot = "tiger/photo/RAW";
    
    % Normalize path separators to forward slash
    fullPath = char(fullPath);
    fullPath = strrep(fullPath, '\', '/');
    
    % Remove the UNC prefix
    prefix = '//tiger/photo/RAW/';
    
    if startsWith(fullPath, prefix, 'IgnoreCase', true)
        % Extract everything after the storage root
        relativePath = extractAfter(fullPath, prefix);
        
        % Remove filename to get directory only
        [relativeDir, ~, ~] = fileparts(relativePath);
        relativeDir = string(relativeDir);
    else
        warning('Path does not start with expected storage root: %s', fullPath);
        relativeDir = "";
    end
end
