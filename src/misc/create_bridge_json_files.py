# --- create_bridge_json_files.py ---
#
# This Python script connects to a SQLite database containing bridge data, 
# retrieves records and column names, then processes each record to create
#  JSON files for each bridge, incorporating specific annotations and 
# pre-computed warning zone limits, utilizing multiprocessing for 
# parallel processing.

# Created by: Andy Carter, PE
# Created - 2024.02.14
# Last revised - 2024.02.21

import sqlite3
import json
import base64
import difflib
import ast
from multiprocessing import Pool

# .......................................
# Function to get the cross section title
def fn_get_cross_section_title(nhd_name, name, ref):
    """
    Generate the cross section title based on input parameters.

    Parameters:
    - nhd_name (str): The name associated with the NHD (National Hydrography Dataset).
    - name (str): The road name.
    - ref (str): The reference name associated with the road.

    Returns:
    - str_title_label (str): The generated cross section title.

    Description:
    This function generates a title for the cross section based on the provided input parameters.
    It prioritizes the road name and reference name, considering their similarity and whether both are present.
    If the NHD name is available and not starting with '99', it is also incorporated into the title.
    """
    # Assign input parameters to local variables
    str_nhd_name = nhd_name
    str_road_name = name
    str_road_ref_name = ref

    # Initialize flags and title label
    b_have_road_name = False
    b_have_ref_name = False
    str_title_label = ''

    # Check if road name exists
    if str_road_name != None:
        str_title_label = str_road_name
        b_have_road_name = True

    # Check if reference name exists
    if str_road_ref_name != None:
        b_have_ref_name = True
        if b_have_road_name:
            # Compare road name and reference name for similarity
            seq=difflib.SequenceMatcher(a=str_road_name, b=str_road_ref_name)
            flt_name_match_score = seq.ratio()
            # If names are significantly different, include reference name in title
            if flt_name_match_score < 0.9:
                str_title_label += ' (' + str_road_ref_name + ')'
        else:
            str_title_label = str_road_ref_name

    # Include NHD name in title if available and not a default value
    if str_nhd_name != None:
        if str_nhd_name[:2] != '99':
            if b_have_road_name or b_have_ref_name:
                str_title_label += ' @ ' + str_nhd_name
            else:
                str_title_label = str_nhd_name

    return str_title_label
# .......................................


# ---------------------------
# Function to process a single record
def fn_process_record(args):
    
    """
    Process a single record to generate a JSON file with specific annotations and warning zone limits.

    Parameters:
    - args (tuple): A tuple containing the record and column names.

    Description:
    This function takes a tuple of record and column names as input.
    It extracts relevant information from the record, creates annotations, 
    computes warning zone limits, and generates a JSON file for each record 
    with the processed data.
    """
    
    try:
        # Unpack arguments
        record, columns = args
        
        # Output directory for JSON files (Hard coded)
        str_json_out_header = r"E:\working\bridge_json_20240215"
        
        # Fields to keep in the output JSON
        list_fields_to_keep = ['uuid', 'sta', 'ground_elv', 'deck_elev', 'low_ch_elv',
                               'hand_r', 'min_low_ch', 'min_ground'] 
        
        # Initialize dictionary to store processed data
        record_dict = {}
        
        # Map columns to record values
        for column, value in zip(columns, record):
            if isinstance(value, bytes):
                value = base64.b64encode(value).decode('utf-8')
            if column in list_fields_to_keep:
                record_dict[column] = value
        
        # Create static annotation layer
        
        # Get the title name of the cross section
        str_nhd_name = record[columns.index('nhd_name')]
        str_name = record[columns.index('name')]
        str_ref = record[columns.index('ref')]
        str_anno_title = fn_get_cross_section_title(str_nhd_name, str_name, str_ref)
        
        # Generate latitude and longitude annotations
        str_lon = str(record[columns.index('longitude')])
        str_lat = str(record[columns.index('latitude')])
        str_coords = '(' + str_lat + ',' + str_lon + ')'
        str_anno_latlong ='Lat/Long: ' +  str_coords
        
        # Generate NBI annotation
        str_nbi = str(record[columns.index('nbi_asset')])
        str_anno_nbi = 'NBI: ' + str_nbi
        
        # Generate COMID annotation
        str_comid = str(record[columns.index('feature_id')])
        str_anno_comid = 'NWM COMID: ' + str_comid
        
        # Add static annotation layers to record_dict
        record_dict['anno_xs_title'] = str_anno_title
        record_dict['anno_latlong'] = str_anno_latlong
        record_dict['anno_nbi'] = str_anno_nbi
        record_dict['anno_comid'] = str_anno_comid
        
        # Pre-compute the warning zone limits
        
        # Distance to buffer ground below lowest elevation
        flt_buffer_ground = 1.0 
        
        list_ground_elv = ast.literal_eval(record[columns.index('ground_elv')])
        list_depth_from_min = [x - min(list_ground_elv) for x in list_ground_elv]
        
        flt_min_low_ch = record[columns.index('min_low_ch')]
        flt_min_ground = record[columns.index('min_ground')]
        
        flt_dist_to_low_ch = flt_min_low_ch - flt_min_ground
        
        list_zones = [flt_buffer_ground * -1, 0.5, 2.0, 5.0]
        list_zone_limits = []
        
        flt_zone_top_depth = max(list_depth_from_min)
        flt_bottom_depth = flt_dist_to_low_ch - list_zones[1]
        
        list_zone_limits.append(flt_zone_top_depth)
        list_zone_limits.append(flt_bottom_depth)
        
        if flt_dist_to_low_ch > list_zones[1]:
            flt_zone_top_depth = flt_dist_to_low_ch - list_zones[1]
            if flt_dist_to_low_ch > list_zones[2]:
                flt_bottom_depth = flt_dist_to_low_ch - list_zones[2]
            else:
                flt_bottom_depth = list_zones[0]
            list_zone_limits.append(flt_bottom_depth)
        
        if flt_dist_to_low_ch > list_zones[2]:
            flt_zone_top_depth = flt_dist_to_low_ch - list_zones[2]
            if flt_dist_to_low_ch > list_zones[3]:
                flt_bottom_depth = flt_dist_to_low_ch - list_zones[3]
            else:
                flt_bottom_depth = list_zones[0]
            list_zone_limits.append(flt_bottom_depth)
        
        if flt_dist_to_low_ch > list_zones[3]:
            list_zone_limits.append(list_zones[0])
            
        list_zone_limits = [round(limit, 2) for limit in list_zone_limits]
        
        # Add warning zone limits to record_dict
        record_dict['zone_limits'] = str(list_zone_limits)
        
        # Get the UUID
        uuid_index = columns.index('uuid')
        uuid_value = record[uuid_index]
    
        # Convert record to JSON format
        json_data = json.dumps(record_dict, indent=4)
    
        # Write JSON data to a file
        str_json_out = str_json_out_header + '\\' + uuid_value + '.json'
        with open(str_json_out, 'w') as json_file:
            json_file.write(json_data)
    except:
        print('Error found.')

# ---------------------------


# Main function
def main():
    
    # --------
    # ***** Hard coded to local sqlite file *****
    str_dbase = r'C:\Users\civil\dev\tx-bridge-plot\src\static\gis_data\tx-bridge-geom.sqlite'
    
    # ***** Hard coded table name of bridge data *****
    str_table_name = 'merged_output_3857'
    
    # NOTE - bridge database also available at ... s3://txbridge-data/test-upload/tx-bridge-geom.sqlite
    # NOTE - bridge database also available at ... https://txbridge-data.s3.amazonaws.com/test-upload/tx-bridge-geom.sqlite
    # --------
    
    # Connect to the SQLite database
    conn = sqlite3.connect(str_dbase)
    cursor = conn.cursor()

    # Retrieve column names
    cursor.execute("PRAGMA table_info(" + str_table_name + ")")
    columns = [column[1] for column in cursor.fetchall()]

    # Retrieve all records
    cursor.execute("SELECT * FROM " + str_table_name)
    records = cursor.fetchall()

    # Close the database connection
    conn.close()

   # Use multiprocessing to process records in parallel
    with Pool() as pool:
        pool.map(fn_process_record, [(record, columns) for record in records])

if __name__ == "__main__":
    main()
