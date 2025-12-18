function mediaTypeId = determineMediaType(ext)
    % Map file extension to media_type_id based on database schema
    % 1=raw_image, 2=jpeg, 3=png, 4=tiff, 5=heic
    
    ext = lower(ext);
    
    % Raw formats
    rawExts = {'.dng', '.cr2', '.nef', '.arw', '.orf', '.rw2', '.raw', '.crw', '.cr3'};
    if ismember(ext, rawExts)
        mediaTypeId = 1;
        return;
    end
    
    % JPEG
    if ismember(ext, {'.jpg', '.jpeg'})
        mediaTypeId = 2;
        return;
    end
    
    % PNG
    if strcmp(ext, '.png')
        mediaTypeId = 3;
        return;
    end
    
    % TIFF
    if ismember(ext, {'.tif', '.tiff'})
        mediaTypeId = 4;
        return;
    end
    
    % HEIC/HEIF
    if ismember(ext, {'.heic', '.heif'})
        mediaTypeId = 5;
        return;
    end
    
    % Unknown image format
    warning('Unknown image extension %s, defaulting to media_type_id=2 (JPEG)', ext);
    mediaTypeId = 2;
end
