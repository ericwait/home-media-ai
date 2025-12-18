function storageMap = getDefaultStorageRootMap()
    % Define default storage root mappings
    % Map: UNC/local path prefix -> storage root identifier
    
    storageMap = containers.Map('KeyType', 'char', 'ValueType', 'char');
    
    % Add your storage mappings here
    storageMap('\\tiger\photo\RAW') = 'tiger/photo/RAW';
    storageMap('\\tiger\photo\JPEG') = 'tiger/photo/JPEG';
    
    % Add more as needed:
    % storageMap('C:\Photos') = 'local/photos';
    % storageMap('/mnt/nas/photos') = 'nas/photos';
end
