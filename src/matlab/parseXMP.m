function [keywords, hierKeywords, rating] = parseXMP(xmpPath)
    % Parse XMP sidecar file for keywords and rating
    
    keywords = {};
    hierKeywords = {};
    rating = NaN;
    
    % Read XMP file as text
    xmpText = fileread(xmpPath);
    
    % Extract rating (Darktable uses xmp:Rating)
    ratingMatch = regexp(xmpText, 'xmp:Rating="(\d+)"', 'tokens');
    if ~isempty(ratingMatch)
        rating = str2double(ratingMatch{1}{1});
    end
    
    % Extract keywords - return as cell array of char (not string)
    keywordMatch = regexp(xmpText, '<dc:subject>\s*<rdf:Bag>(.*?)</rdf:Bag>', 'tokens', 'dotexceptnewline');
    if ~isempty(keywordMatch)
        liItems = regexp(keywordMatch{1}{1}, '<rdf:li>(.*?)</rdf:li>', 'tokens');
        keywords = cellfun(@(x) x{1}, liItems, 'UniformOutput', false);
    end
    
    % Extract hierarchical keywords
    hierMatch = regexp(xmpText, '<lr:hierarchicalSubject>\s*<rdf:Bag>(.*?)</rdf:Bag>', 'tokens', 'dotexceptnewline');
    if ~isempty(hierMatch)
        liItems = regexp(hierMatch{1}{1}, '<rdf:li>(.*?)</rdf:li>', 'tokens');
        hierKeywords = cellfun(@(x) x{1}, liItems, 'UniformOutput', false);
    end
end
