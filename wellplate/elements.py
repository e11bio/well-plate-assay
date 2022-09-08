import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np
import nd2
from matplotlib.colors import LinearSegmentedColormap
import csv


def read_plate_xml(file_loc):
    # get tree
    tree = ET.parse(file_loc)
    root = tree.getroot()
    # get active preset.
    preset_index = int(root.find("Presets/PresetIndex").text)
    # read all label info.
    labels = read_labels(root,preset_index)
    # read all meta data.
    meta_data,meta_data_info = read_meta_data(root,preset_index)
    return meta_data, meta_data_info, labels

def read_plate_csv(file_loc):
    with open(file_loc, 'r') as file:
        # find labels
        meta_data= pd.DataFrame()
        meta_data['well'] = [well_ind_to_id(i) for i in range(96)]
        values=[]
        read_values = False
        read_lines = 0
        reader = csv.reader(file)
        for i, row in enumerate(reader):
            if read_values:
                values.append(row[start_ind:start_ind+12])
                read_lines+=1
                if read_lines==8:
                    meta_data[name] = np.array(values).flatten()
                    read_lines=0
                    read_values=False
            if ('Selection' in row) & (read_values==False):
                start_ind = row.index('Selection')
                name = row[start_ind+1]
                # get values.
                values=[]
                read_values=True # start reading values on next line
    return meta_data

def read_plate_gsheet(gc, file_name, tab_name, label_word='SELECTION'):
    meta_data = pd.DataFrame([])
    # get well IDs.
    meta_data['well'] = [ well_ind_to_id(i) for i in range(96)]
    # get data.
    data = np.array(gc.open(file_name).worksheet(tab_name).get_all_values())
    # get labels
    label_indices = np.argwhere(data==label_word)
    # get values.
    for label_ind in label_indices:
        name = data[label_ind[0], label_ind[1]+1]
        values = data[label_ind[0]+1: label_ind[0]+9, label_ind[1]:label_ind[1]+12]
        values[values=='']='none'
        #store.
        meta_data[name] = values.flatten()
    return meta_data

def read_labels(root, preset_index):
    labels = []
    for elem in root.findall(f"./WellplateMetadata_{preset_index}/Labels/"):
        # get tag info.
        label_name = elem.find('Name').text
        label_color = elem.find('Color').text
        # get well info.
        search_str = f"./WellplateMetadata_1/Labels/Label[Name='{label_name}']/Wells/WellIndex"
        label_wells_ind = np.unique(np.array([int(elem.text) for elem in root.findall(search_str)]))
        label_wells_id = [well_ind_to_id(ind) for ind in label_wells_ind]
        labels.append({'name':label_name, 'tag_color':label_color,'well_indices':label_wells_ind,'well_ids':label_wells_id})
    labels = pd.DataFrame(labels).drop_duplicates(subset='name')
    return labels

def read_meta_data(root, preset_index):
    meta_data = pd.DataFrame([])
    # get well IDs.
    meta_data['well'] = [ well_ind_to_id(i) for i in range(96)]
    meta_data_info = []
    for elem in root.findall(f"./WellplateMetadata_{preset_index}/Quantities/Quantity"):
        # get meta info.
        meta_name = elem.find('Name').text
        meta_desc = elem.find('Desc').text
        meta_data_info.append({'name':meta_name,'desc':meta_desc})
        # get value each well.
        meta_wells = ['None' for i in range(96)]
        for well in elem.findall('Wells/Well'):
            well_index = int(well.find('WellIndex').text)
            quality = well.find('Quality')
            if quality is not None:
                meta_wells[well_index] = quality.text
        
        meta_data[meta_name] = meta_wells
    return meta_data, meta_data_info

def well_ind_to_id(ind):
    row_col = np.unravel_index(ind,(8,12))
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    well_id = f"{letters[row_col[0]]}{row_col[1]+1}"
    return well_id

def read_nd2(file_loc):
    colormaps = []
    names = []
    with nd2.ND2File(file_loc) as f:
        for channel in f.metadata.channels:
            name = channel.channel.name
            r = (channel.channel.colorRGB & 0xff)/255
            g = ((channel.channel.colorRGB & 0xff00) >> 8)/255
            b = ((channel.channel.colorRGB & 0xff0000) >> 16)/255
            a = 1
            colors = [[0,0,0],[r,g,b]]
            # process colormaps. 
            colormaps.append(LinearSegmentedColormap.from_list('testCmap', colors, N=2**16))
            names.append(name)
        xarr = f.to_xarray(delayed=True)
    return xarr, names, colormaps