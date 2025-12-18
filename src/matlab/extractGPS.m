function gpsValue = extractGPS(info, fieldName, refFieldName)
    % Extract GPS coordinate and convert to decimal degrees
    if isfield(info, fieldName)
        dms = info.(fieldName);
        if length(dms) == 3
            gpsValue = dms(1) + dms(2)/60 + dms(3)/3600;
            
            % Handle hemisphere
            if nargin > 2 && isfield(info, refFieldName)
                ref = info.(refFieldName);
                if strcmp(ref, 'S') || strcmp(ref, 'W')
                    gpsValue = -gpsValue;
                end
            end
        else
            gpsValue = NaN;
        end
    else
        gpsValue = NaN;
    end
end