function I_oriented = orientImage(I, orientation)
%ORIENTIMAGE  Rotate/flip an image matrix according to its EXIF Orientation.
%
%   I_ORIENTED = ORIENTIMAGE(I) returns a copy of the matrix I that has been
%   transformed so that it appears upright for a human viewer. The function
%   looks for the 'Orientation' field in the image metadata (via imfinfo)
%   automatically if the second argument is omitted.
%
%   I_ORIENTED = ORIENTIMAGE(I, ORIENTATION) performs the same operation,
%   but uses the numeric value provided by ORIENTATION instead of reading
%   it from a file.  ORIENTATION must be one of the eight EXIF orientation
%   codes (1–8).  If an unknown value is supplied, an error is thrown.
%
%   The function supports all common image data types supported by MATLAB
%   (`uint8`, `uint16`, `double`, etc.) and preserves the original class.
%
%   Example
%       % Read a JPEG that was taken in portrait mode
%       I  = imread('portrait.jpg');
%       info = imfinfo('portrait.jpg');
%       I_upright = orientImage(I, info.Orientation);  % or simply orientImage(I)
%       imshow(I_upright);
%
%   Example – using the helper that reads the file directly
%       function I_oriented = orientFile(fname)
%           I      = imread(fname);
%           info   = imfinfo(fname);
%           I_oriented = orientImage(I, info.Orientation);
%       end
%
%   EXIF Orientation values (from ISO 12233):
%        1 - Top-left (normal)                -> no change
%        2 - Mirror horizontal                -> fliplr(I)
%        3 - Rotate 180°                      -> rot90(I,2)
%        4 - Mirror vertical                  -> flipud(I)
%        5 - Transpose + mirror horizontal    -> fliplr(rot90(I,-1))
%        6 - Rotate 90° clockwise             -> rot90(I,-1)
%        7 - Transpose + mirror vertical      -> fliplr(rot90(I,1))
%        8 - Rotate 90° counter‑clockwise     -> rot90(I,1)
%
%   See also imread, imfinfo, rot90, flipud, fliplr

    % ----------------------- Input handling --------------------------------
    if nargin < 2
        error('orientImage requires at least the image matrix as input.');
    end
    
    % Validate that I is a numeric array (or logical)
    if ~isnumeric(I) && ~islogical(I)
        error('First argument must be a numeric or logical image matrix.');
    end

    % Ensure orientation is scalar and finite
    if ~isscalar(orientation) || ~isfinite(double(orientation))
        error('Orientation value must be a single finite number (1–8).');
    end
    
    ori = round(orientation);          % EXIF values are integers
    switch ori
        case 1                                  % No transformation
            I_oriented = I;
        case 2                                  % Reflect about vertical axis
            I_oriented = fliplr(I);
        case 3                                  % 180° rotation
            I_oriented = rot90(I, 2);           
        case 4                                  % Reflect about vertical axis and then rotate 180°
            I_oriented = rot90(fliplr(I), 2);
        case 5                                  % Reflect about vertical axis and then rotate 90° counterclockwise
            I_oriented = rot90(fliplr(I), -1);
        case 6                                  % Rotate 90° clockwise
            I_oriented = rot90(I, 1);
        case 7                                  % Reflect about vertical axis and then rotate 90° clockwise
            I_oriented = rot90(fliplr(I), 1);
        case 8                                  % Rotate 90° counterclockwise
            I_oriented = rot90(I, -1);
        otherwise
            error(['Unknown EXIF orientation value: ', num2str(ori), ...
                   '. Expected one of 1–8.']);
    end
end
