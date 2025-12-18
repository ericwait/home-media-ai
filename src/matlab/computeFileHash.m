function hash = computeFileHash(filePath)
    % Compute SHA-256 hash of file
    import java.security.MessageDigest;
    import java.io.FileInputStream;
    
    fis = FileInputStream(filePath);
    md = MessageDigest.getInstance('SHA-256');
    
    bufferSize = 8192;
    buffer = zeros(1, bufferSize, 'uint8');
    
    while true
        numRead = fis.read(buffer);
        if numRead < 0
            break;
        end
        md.update(buffer, 0, numRead);
    end
    
    fis.close();
    
    hashBytes = typecast(md.digest(), 'uint8');
    hash = lower(sprintf('%02x', hashBytes));
    hash = string(hash);
end
