%% User Settings

maxSize = 1024;
dateStart = datetime(2025,01,01);
dateEnd   = datetime(2026,01,01);

%% Make connection to database
conn = database('mariaDB');

%Set query to execute on the database
query = ['SELECT id, ' ...
    '   created, ' ...
    '	file_ext, ' ...
    '	is_original, ' ...
    '	is_final, ' ...
    '   is_removed, ' ...
    '	origin_id, ' ...
    '   directory, ' ...
    '	filename, ' ...
    '	thumbnail_path ' ...
    'FROM home_media_ai.media'];

% Execute query and fetch results
data = fetch(conn,query);

% Close connection to database
close(conn)

% Clear variables
clear conn query

%% Do stuff
rawDir = '\\tiger\photo\RAW';
tumbDir = '\\tiger\docker\home-media-viewer\thumbnails';

q = parallel.pool.DataQueue;
afterEach(q, @(x)(fprintf('%d, ', x)));
indexList = find(data.created >= dateStart & data.created <= dateEnd & data.is_removed==0);
parfor r = 1:length(indexList)
    rowIndex = indexList(r);
    if mod(rowIndex, 1e3) ==0
        send(q, rowIndex);
    end
    if rowIndex == 76768
        continue
    end

    filePathIn  = fullfile(rawDir, data.directory{rowIndex}, data.filename{rowIndex});
    filePathOut = fullfile(tumbDir, data.directory{rowIndex});
    if ~exist(filePathOut, "dir")
        mkdir(filePathOut);
    end
    [~, fileName, fileExt] = fileparts(data.filename{rowIndex});
    filePathOut = fullfile(filePathOut, [fileName, '_thumb.jpg']);
    if exist(filePathOut, "file")
        continue
    end

    try
        im = im2uint8(imread(filePathIn));
    catch exception
        warning(sprintf('Unable to read %s: %s', filePathIn, exception.message));
        continue
    end

    resizeFactor = min([maxSize./size(im,1:2), 1]);
    im           = imresize(im, resizeFactor);

    try
        imwrite(im, filePathOut, 'jpg');
    catch exception
        warning(sprintf('Unable to write %s: %s', filePathIn, exception.message));
    end
end
