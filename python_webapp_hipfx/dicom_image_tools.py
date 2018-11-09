import pydicom
import numpy as np
from PIL.Image import fromarray
from PIL import Image
import os
from os.path import join

logs = []
filename = ''

def clip_pixels(pixels, low, high):
    """clip pixel values below low and above high"""
    pixels[pixels < low] = low
    pixels[pixels > high] = high
    return pixels

def get_window(ds):
    """Return low and high values to be displayed based on WindowCenter and WindowWidth DICOM attributes"""
    center = ds.WindowCenter
    width = ds.WindowWidth
    if hasattr(center,'__iter__'):
        center = center[0]
    if hasattr(width,'__iter__'):
        width = width[0]
    low = center - width/2
    high = center + width/2
    return low, high


def generate_window(pixels):
    """Used to return low and high pixels values to be when WindowCenter and WindowWidth DICOM attributes are not present"""
    center = np.median(pixels)
    low = np.percentile(pixels,0.5)
    high = np.percentile(pixels,99.5)
    return low, high


def log_conv(pixels):
    pixels[pixels <= 1] = 1  #ensure no ln of 0
    return(np.log(pixels))

def norm_pixels(pixels):
    pixels = (pixels - pixels.min()) / (pixels.max()-pixels.min())
    return pixels

def trans_pixels(ds, pixels, to_int = True):
    """
    Transforms the pixel_array from the dicom file specified appropriately, including performing
    logarithmic conversion if specified and windowing the file appropriately.  Then normalizes
    the pixels and multiplies by  as ndarray of 16bit floats from 0-1

    Arguments
    ds: a pydicom dataset
    pixels: ndarray of pixels
    to_int = if true, specifies that after normalizing pixel data from 0-1 it will be multiplied by 255 to return as 8-bit integer
    """    
    pixels.flags.writeable = True

    #invert if needed
    if hasattr(ds, 'PhotometricInterpretation'):
        if ds.PhotometricInterpretation == 'MONOCHROME1':
            pixels = np.invert(pixels)

    if hasattr(ds, 'PixelIntensityRelationship') and ds.PixelIntensityRelationship.lower() == 'log':
        if hasattr(ds,'WindowCenter') and hasattr(ds,"WindowWidth"):
            low, high = get_window(ds)
        else:
            low, high = generate_window(pixels)
        pixels = clip_pixels(pixels, low=low, high=high)
        pixels = log_conv(pixels)
        logs.append(filename)
    else:
        low, high = generate_window(pixels)
        pixels = clip_pixels(pixels, low=low, high=high)


    pixels = norm_pixels(pixels)
    if to_int:
        pixels = (pixels * 255).astype(np.uint8)
    return pixels

def npy_fn(base_fn, row,crop):
    """
    Generates a standard npy filename in format: base_fn + '_s' where S is first initial of side (e.g., 'r' or 'l')
    Appends _lat to end if lateral
    """
    if not crop:
        return base_fn
    
    side = row['side'][0].lower()
    to_return = base_fn + "_" + side

    if row['image_type'].startswith("Cross"):
        to_return += "_lat"
    return to_return

def reverse_pixels(pixel_data):
    """Horizontally flips an array of pixels"""
    for i, each in enumerate(pixel_data):
        pixel_data[i] = each[::-1]
    return pixel_data

def check_region(pixels,row,size=1000):
    """
    Corrects a region if it is out of bounds

    Arguments
    pixels = ndarray of pixel data
    row = Pandas from 
    """
    rows, columns = pixels.shape
    
    if rows < size:
        row['upper'] = 0
        row['lower'] = rows
    if columns < size:
        row['left'] = 0
        row['right'] = columns
        
    if row['left'] < 0:
        row['left'] = 0
        row['right'] = size
    if row['upper'] < 0:
        row['upper'] = 0
        row['lower'] = size

    if row['right'] > columns:
        row['right'] = columns
        row['left'] = columns-size
    if row['lower'] > rows:
        row['lower'] = rows
        row['upper'] = rows - size
        
    return row
    
def crop_pixels(pixels,row):
    """Crops pixel data by region boundaries, and flips it if it's a left hip"""
    row = check_region(pixels, row)
    
    return pixels[int(row['upper']):int(row['lower']),int(row['left']):int(row['right'])]


def resize_pixels(pixels, size=1000):
    """ensure image is square and shape = (size, size)"""

    rows,columns = pixels.shape
    if rows < columns:
        #print("rows < columns")
        start_idx = int((columns - rows)/2)
        end_idx = columns-start_idx
        pixels = pixels[:,start_idx:end_idx]
    if columns < rows:
        #print("columns < rows")
        start_idx = int((rows-columns)/2)
        end_idx = rows-start_idx
        pixels = pixels[start_idx:end_idx,:]
    if pixels.shape[0] != size:
        pixel_copy = pixels / pixels.max()
        image = fromarray((pixel_copy*255).astype(np.uint8), mode="L")
        image = image.resize((size,size), Image.ANTIALIAS)
        pixels = np.array(image)/255 * pixels.max()
        
    return pixels
                          
def convert_npy(image_fn,in_dir,out_dir, data, crop=True, flip=True, by_accession = False):
    """
    Load the dicom specified, crop and process the regions appropriately, and save as a numpy ndarray in the specified directory

    Arguments
    image_fn  = filename of dcm to convert
    in_dir = input directory
    out_dir = output directory
    data = classification dataframe to use to do conversion
    crop = True if you'd like to crop image to size specified by bounding box parameters in data
    flip = True if you'd like to flip horizontal image as appropriate (e.g., flip lefts to be rights)
    by_accession = True if you'd like to save images in folders by accession number (instead of saving all files in same folder) 
    """
    
    fn_base = image_fn.split(".")[0]
    
    result_df = data[data["filename"] == fn_base]
    if result_df.shape[0] == 0:
        return

    if np.isnan(result_df.iloc[0]['left']):
        #then this file doesn't have bounding box and shouldn't be processed
        return
        
    dicom = pydicom.dcmread(in_dir + image_fn)

    for idx, each in result_df.iterrows():                
                
        pixels = dicom.pixel_array
        pixels.flags.writeable = True

        if crop:
            pixels = crop_pixels(pixels,each)
            pixels = resize_pixels(pixels)
            if each['image_type'].startswith('Cross Table'):
                pixels = np.rot90(pixels)
            if flip and each['side'] == "Left":
                pixels = reverse_pixels(pixels)

        #transform and normalize pixels
        pixels = trans_pixels(dicom,pixels)

        
        out_fn = npy_fn(fn_base, each, crop)
        this_out_dir = out_dir
        if by_accession:
            this_out_dir = join(out_dir,str(each['accession']).split('.')[0])
            if not os.path.isdir(this_out_dir):
                os.mkdir(this_out_dir)
            
        np.save(join(this_out_dir,out_fn),pixels)

        # Add logic to avoid saving more than one image if not cropping
        if crop == False:
            break

        
import time

"""The following allows some basic testing of above methods by converting dicoms to jpgs when run as python script"""
if __name__ == '__main__':
    in_dir = input("Folder of dicom files: ")
    out_dir = input("Folder to save jpg files: ")

    then = time.time()
    files = os.listdir(in_dir)

    logs = []

    for each in files:
        try:
            if ".dcm" in each.lower():
                filename = each
                print(each)

                ds = pydicom.dcmread(join(in_dir,each))
                pixels = trans_pixels(ds,ds.pixel_array)

                image = fromarray(pixels)
                jpg_fn = each.split(".")[0] + ".jpeg"
                image.save(join(out_dir,jpg_fn))
        except Exception as e:
            print(e)

    time = time.time() - then
    print(time)

    print("\nLogarithmic files: ")
    for each in logs:
        print(each)

        