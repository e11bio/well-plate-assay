from pathlib import Path
import zarr
from wellplate.elements import read_nd2
from cellpose import models
from tqdm.notebook import tqdm
import shutil
from skimage.measure import regionprops,label
import numpy as np

def nd2_file_2_zarr_result_file(nd2_file):
  # Get zarr output file name.
  nd2_file = Path(nd2_file)
  return nd2_file.parents[0]/f"{nd2_file.stem}.zarr"

def run_cellpose(nd2_file, cell_channel, flow_threshold=0.9, cellprob_threshold=-5, diameter=None, redo=False):
  result_file = nd2_file_2_zarr_result_file(nd2_file)
  output = zarr.open(result_file)
  # read nd2 file.
  im_data, channel_names, colormaps = read_nd2(nd2_file)
  print(f"Preparing to run Cellpose on channel {cell_channel} for {im_data.shape[0]} wells")
  channel_ind = channel_names.index(cell_channel)
  model = models.Cellpose(gpu=True, model_type="nuclei")
  for well_ind in tqdm(range(im_data.shape[0]), desc='Processing well'):
    # check if data is already present, unless redo is requested.
    mask_path = Path(f'cells/masks/well {well_ind}/channel {cell_channel}')
    if (mask_path not in output) | redo==True:
      # remove previous data if present.
      if (mask_path in output) & redo==True: shutil.rmtree(result_file/mask_path)
      # run cellpose.
      im=im_data[well_ind,channel_ind,:,:].to_numpy()
      masks, flows, styles, diams = model.eval(im,diameter=diameter, flow_threshold=flow_threshold, cellprob_threshold=cellprob_threshold)
      # store mask data.
      well_group = output.require_group(mask_path.parents[0])
      array = well_group.require_dataset(mask_path.name,data=masks,shape = masks.shape,chunks=(5000,5000), dtype='i2')

def calculate_intensities_channel(nd2_file, cell_channel, int_channel, redo=False):
  # get result zarr file. 
  result_file = nd2_file_2_zarr_result_file(nd2_file)
  output = zarr.open(result_file)
  # read nd2 file.
  im_data, channel_names, colormaps = read_nd2(nd2_file)
  # get intensity channel index.
  channel_ind = channel_names.index(int_channel)
  for well_ind in tqdm(range(im_data.shape[0]), desc='Processing well'):
    # check if data is already present, unless redo is requested.
    int_path = Path(f'cells/intensities/well {well_ind}/channel {int_channel}')
    if (int_path not in output) | redo==True:
      # remove previous data if present.
      if (int_path in output) & redo==True: 
          shutil.rmtree(result_file/int_path)
      # get mask.
      mask_im = output[f'cells/masks/well {well_ind}/channel {cell_channel}'][:]
      # get image.
      int_im = im_data[well_ind,channel_ind,:,:].to_numpy()
      # get region intensities.
      props = regionprops(mask_im, int_im)
      values = np.array([region["mean_intensity"] for region in props])
      # store.
      well_group = output.require_group(int_path.parents[0])
      array = well_group.require_dataset(int_path.name,data=values,shape = values.shape,chunks=(50000,), dtype='f')
      # Background values.
      bg_path = Path(f'cells/background/well {well_ind}/channel {int_channel}/')
      if (bg_path in output) & redo==True: shutil.rmtree(result_file/bg_path)
      bg_pixs = int_im[mask_im==0]
      values = np.array([bg_pixs.mean(),bg_pixs.std()])
      well_group = output.require_group(bg_path.parents[0])
      array = well_group.require_dataset(bg_path.name,data=values,shape = values.shape,chunks=(10,), dtype='f')