function I_oriented = orientImage(I, orientation)
%ORIENTIMAGE  Rotate/flip an image matrix according to its EXIF Orientation.
%
%   I_ORIENTED = ORIENTIMAGE(I, ORIENTATION) performs the operation using
%   the numeric value provided by ORIENTATION. ORIENTATION must be one of
%   the eight EXIF orientation codes (1–8).
%
%   The function supports all common image data types supported by MATLAB
%   (`uint8`, `uint16`, `double`, etc.) and preserves the original class.
%
%   Example
%       % Read a JPEG that was taken in portrait mode
%       I  = imread('portrait.jpg');
%       info = imfinfo('portrait.jpg');
%       if isfield(info, 'Orientation')
%           I_upright = orientImage(I, info.Orientation);
%       else
%           I_upright = I;
%       end
%       imshow(I_upright);
%
%   EXIF Orientation values (from ISO 12233):
%        1 - Top-left (normal)                -> no change
%        2 - Mirror horizontal                -> fliplr(I)
%        3 - Rotate 180°                      -> rot90(I,2)
%        4 - Mirror vertical                  -> flipud(I)
%        5 - Transpose + mirror horizontal    -> rot90(fliplr(I), 1)
%        6 - Rotate 90° clockwise             -> rot90(I, -1)
%        7 - Transpose + mirror vertical      -> rot90(fliplr(I), -1)
%        8 - Rotate 90° counter‑clockwise     -> rot90(I, 1)
%
%   See also imread, imfinfo, rot90, flipud, fliplr

    % ----------------------- Input handling --------------------------------
    if nargin < 2
        error('orientImage requires two arguments: image matrix and orientation value.');
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
            I_oriented = flipud(I);
        case 5                                  % Reflect about vertical axis and then rotate 90° counterclockwise
            I_oriented = rot90(fliplr(I), 1);
        case 6                                  % Rotate 90° clockwise
            I_oriented = rot90(flipud(I), 1);
        case 7                                  % Reflect about vertical axis and then rotate 90° clockwise
            I_oriented = rot90(fliplr(I), -1);
        case 8                                  % Rotate 90° counterclockwise
            I_oriented = rot90(flipud(I), 1);
        otherwise
            error(['Unknown EXIF orientation value: ', num2str(ori), ...
                   '. Expected one of 1–8.']);
    end
end
