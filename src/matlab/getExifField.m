function value = getExifField(exifData, fieldName, defaultValue)
    % Extract field from ExifTool JSON structure
    % Try field name without prefix first, then with common prefixes
    
    % List of possible field names (ExifTool may or may not include group prefix)
    possibleFields = {
        fieldName,
        strrep(fieldName, ' ', ''),  % Remove spaces
        strrep(fieldName, '_', ''),  % Remove underscores
    };
    
    % Get all field names from the struct
    allFields = fieldnames(exifData);
    
    % Try exact matches first
    for i = 1:length(possibleFields)
        field = possibleFields{i};
        if isfield(exifData, field)
            value = exifData.(field);
            value = convertToType(value, defaultValue);
            return;
        end
    end
    
    % Try case-insensitive partial match
    for i = 1:length(allFields)
        structField = allFields{i};
        for j = 1:length(possibleFields)
            if contains(lower(structField), lower(possibleFields{j}))
                value = exifData.(structField);
                value = convertToType(value, defaultValue);
                return;
            end
        end
    end
    
    % Field not found, return default
    value = defaultValue;
end

function converted = convertToType(value, defaultValue)
    % Convert value to match the type of defaultValue
    
    % Check type of defaultValue
    if isnumeric(defaultValue) && isnan(defaultValue)
        % Numeric field expected
        if isnumeric(value)
            converted = double(value);
        elseif ischar(value) || isstring(value)
            converted = str2double(value);
            if isnan(converted)
                converted = defaultValue;
            end
        else
            converted = defaultValue;
        end
        
    elseif isstring(defaultValue) || ischar(defaultValue)
        % String field expected
        if ischar(value) || isstring(value)
            converted = string(value);
        elseif isnumeric(value)
            converted = string(num2str(value));
        else
            converted = defaultValue;
        end
        
    else
        % Unknown type, return as-is
        converted = value;
    end
end

