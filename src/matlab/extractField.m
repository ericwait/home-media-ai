function value = extractField(info, fieldName, dataType)
    % Extract field from EXIF info struct
    if isfield(info, fieldName)
        value = info.(fieldName);
        if strcmp(dataType, 'string')
            value = string(value);
        elseif strcmp(dataType, 'double')
            value = double(value);
        end
    else
        if strcmp(dataType, 'string')
            value = "";  % Empty string instead of missing
        else
            value = NaN;
        end
    end
end
