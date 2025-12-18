function data = readImage(filePath)
    % Reads an image and returns a table row with metadata
    % Inputs:
    %   filePath - Full path to image file
    % Outputs:
    %   data - 1-row table matching media schema
    
    % Initialize empty row
    data = table();
    
    % Check if file exists
    if ~isfile(filePath)
        warning('File not found: %s', filePath);
        return;
    end
    
    % Get file info
    fileInfo = dir(filePath);
    
    % Parse path components
    [pathStr, name, ext] = fileparts(filePath);
    data.filename = string(strcat(name, ext));
    data.file_ext = string(ext);
    data.file_path = string(filePath);
    
    % Extract storage_root and relative directory
    [data.storage_root, data.directory] = parseStoragePath(filePath);
    
    % Generate thumbnail path: directory\filename_thumb.jpg
    thumbFilename = sprintf('%s_thumb.jpg', name);
    data.thumbnail_path = string(fullfile(data.directory, thumbFilename));
    data.thumbnail_path = strrep(data.thumbnail_path, '/', '\');  % Use backslashes
    
    % File properties
    data.file_size = fileInfo.bytes;
    data.file_hash = string(computeFileHash(filePath));
    
    % Initialize EXIF structure
    exifStruct = struct();
    
    % Image metadata using ExifTool
    try
        exifData = readExifWithExifTool(filePath);
        
        % Dimensions
        data.width = getExifField(exifData, 'ImageWidth', NaN);
        data.height = getExifField(exifData, 'ImageHeight', NaN);
        if ~isnan(data.width)
            exifStruct.width = data.width;
        end
        if ~isnan(data.height)
            exifStruct.height = data.height;
        end
        
        % Camera/lens info
        data.camera_make = getExifField(exifData, 'Make', "");
        data.camera_model = getExifField(exifData, 'Model', "");
        data.lens_model = getExifField(exifData, 'LensModel', "");
        
        if data.camera_make ~= ""
            exifStruct.camera_make = char(data.camera_make);
        end
        if data.camera_model ~= ""
            exifStruct.camera_model = char(data.camera_model);
        end
        if data.lens_model ~= ""
            exifStruct.lens_model = char(data.lens_model);
        end
        
        % GPS data (ExifTool returns decimal degrees directly)
        data.gps_latitude = getExifField(exifData, 'GPSLatitude', NaN);
        data.gps_longitude = getExifField(exifData, 'GPSLongitude', NaN);
        data.gps_altitude = getExifField(exifData, 'GPSAltitude', NaN);
        
        if ~isnan(data.gps_latitude)
            exifStruct.gps_latitude = data.gps_latitude;
        end
        if ~isnan(data.gps_longitude)
            exifStruct.gps_longitude = data.gps_longitude;
        end
        if ~isnan(data.gps_altitude)
            exifStruct.gps_altitude = data.gps_altitude;
        end
        
        % Camera settings
        aperture = getExifField(exifData, 'Aperture', NaN);
        if ~isnan(aperture)
            exifStruct.aperture = aperture;
        end
        
        shutterSpeed = getExifField(exifData, 'ShutterSpeed', "");
        if shutterSpeed ~= ""
            exifStruct.shutter_speed = char(shutterSpeed);
        end
        
        iso = getExifField(exifData, 'ISO', NaN);
        if ~isnan(iso)
            exifStruct.iso = iso;
        end
        
        focalLength = getExifField(exifData, 'FocalLength', NaN);
        if ~isnan(focalLength)
            exifStruct.focal_length = focalLength;
        end
        
        orientation = getExifField(exifData, 'Orientation', NaN);
        if ~isnan(orientation)
            exifStruct.orientation = orientation;
        end
        
        software = getExifField(exifData, 'Software', "");
        if software ~= ""
            exifStruct.software = char(software);
        end
        
        % Creation date from EXIF
        % Try multiple date fields in order of preference
        dateStr = getExifField(exifData, 'DateTimeOriginal', "");
        if dateStr == ""
            dateStr = getExifField(exifData, 'CreateDate', "");
        end
        if dateStr == ""
            dateStr = getExifField(exifData, 'ModifyDate', "");
        end
        
        if dateStr ~= ""
            try
                data.created = datetime(dateStr, 'InputFormat', 'yyyy:MM:dd HH:mm:ss');
            catch
                % Try alternative format
                data.created = datetime(dateStr, 'InputFormat', 'yyyy-MM-dd HH:mm:ss');
            end
        else
            data.created = datetime(fileInfo.datenum, 'ConvertFrom', 'datenum');
        end
        
    catch ME
        warning('Could not read EXIF from %s: %s', filePath, ME.message);
        data.width = NaN;
        data.height = NaN;
        data.camera_make = "";
        data.camera_model = "";
        data.lens_model = "";
        data.gps_latitude = NaN;
        data.gps_longitude = NaN;
        data.gps_altitude = NaN;
        data.created = datetime(fileInfo.datenum, 'ConvertFrom', 'datenum');
    end
    
    % Try to read XMP sidecar for keywords
    xmpPath = strrep(filePath, ext, '.xmp');
    if isfile(xmpPath)
        try
            [keywords, hierKeywords, rating] = parseXMP(xmpPath);
            if ~isempty(keywords)
                exifStruct.keywords = keywords;
            end
            if ~isempty(hierKeywords)
                exifStruct.hierarchical_keywords = hierKeywords;
            end
            if ~isnan(rating)
                data.rating = rating;
                exifStruct.rating = rating;
            end
        catch ME
            warning('Could not parse XMP from %s: %s', xmpPath, ME.message);
        end
    end
    
    % Store EXIF as JSON - ALWAYS use string() wrapper
    data.exif_data = string(jsonencode(exifStruct));
    
    % Default values for tracking fields (will be updated in collectData)
    data.media_type_id = determineMediaType(ext);
    data.is_original = 1;   % Default to original
    data.is_final = 1;      % Default to final (updated later)
    data.origin_id = NaN;   % No parent (updated later)
    
    if ~isfield(exifStruct, 'rating')
        data.rating = NaN;
    end
    
    data.is_removed = 0;
end
