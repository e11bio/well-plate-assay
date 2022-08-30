import xml.etree.ElementTree as ET
import pandas as pd
import numpy as np

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
        meta_wells = np.empty(96,object)
        for well in elem.findall('Wells/Well'):
            well_index = int(well.find('WellIndex').text)
            meta_wells[well_index] = well.find('Quality').text
        meta_data[meta_name] = meta_wells
    return meta_data, meta_data_info

def well_ind_to_id(ind):
    row_col = np.unravel_index(ind,(8,12))
    letters = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H']
    well_id = f"{letters[row_col[0]]}{row_col[1]+1}"
    return well_id