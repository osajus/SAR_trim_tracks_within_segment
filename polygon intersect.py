import geopandas as gp
import pandas as pd
import matplotlib.pyplot as plt
import openpyxl
import random
from shapely.geometry import Point, LineString, Polygon

##### CHANGE THESE VARIABLES #####

# Local spatial reference to the area of interest
# Lookup here: https://spatialreference.org/ref/epsg/
EPSG_LOCAL = 32617 

# Path and file name of the SARTopo export containing the segment and the search gps tracks
# Use double backspaces in the path.  i.e. "C:\\Users\\username\\Desktop\\"
FILE_PATH = ".\\"
FILE_NAME = "track-intersects.json"

OUTPUT_FILE = "output_intersected.geojson"

# Number of searchers
SEARCHERS = 5

# Effective Sweep Width (ESW) in meters
ESW = 11

# Do you wish to see the graphic plots when you run this program
# True = Yes, False = No
SHOW_PLOTS = False


##### DO NOT CHANGE BELOW THIS LINE #####

# WGS84 spatial reference - This is what SARTopo uses
EPSG_WGS84 = 4326

def main():
    # Read the SARTopo export containing the segment and the search gps tracks
    import_gdf = gp.read_file(FILE_PATH + FILE_NAME)

    # Convert the export from WGS84 to the local spatial reference
    import_gdf = import_gdf.to_crs(epsg=EPSG_LOCAL)

    # Extract the polygon representing the search segment
    segment_gdf = import_gdf[import_gdf.geometry.geom_type == 'Polygon']

    # Remove extraneous data that comes from SARTopo.  Only interested in the 
    # segment name (title) and the boundary (geometry)
    segment_gdf = segment_gdf[['title', 'geometry']]


    # For debugging, showing myself what the segment looks like
    if SHOW_PLOTS:
        segment_gdf.plot(alpha=0.2)
        plt.show()

    # Extract the search gps tracks
    search_tracks_gdf = import_gdf[import_gdf.geometry.geom_type == 'LineString']
    search_tracks_gdf = search_tracks_gdf[['title', 'geometry']]

    # Create a list to hold the parts of the intersected search tracks
    intersections = []

    # Set up a pandas dataframe to be used to create a spreadsheet later
    spreadsheet = []

    # Loop through each search segment
    for segment_idx, segment in segment_gdf.iterrows():

        # Determine if the segment is self-intersecting
        if segment.geometry.is_valid == False:
            print(f"Segment {segment.title} is self-intersecting.")
            print("We can try to fix it, but it may significantly alter the polygon.")
            
            # Apply the fix to see the difference
            area_before = segment.geometry.area
            segment_new = segment.geometry.buffer(0)
            area_after = segment.geometry.area

            # Present the difference and ask if the user wants to continue
            print(f"     Area before: {area_before:.2f} | Area after: {area_after:.2f} | Delta: {(area_before - area_after) / area_before * 100:.2f}%")
            #BUG - Change this back
            #user_input = input(f"Do you want to and fix it? (Enter : Y or N) ")
            user_input = 'y'

            if user_input.lower() != 'y':
                # If the user declines, skip this segment
                print(f"Skipping segment {segment.title}.")
                continue
            
            # Otherwise, apply the fix and re-check it
            segment.geometry = segment_new

        if segment.geometry.is_valid == False:
            # If it's still not fixed, skip it
            print(f"Segment {segment.title} is still self-intersecting. Skipping.")
            continue
                    
        # Loop through each search track
        for track_idx, track in search_tracks_gdf.iterrows():
            # Intersect the search track with the segment
            intersected_track = track.geometry.intersection(segment.geometry)
            # Get the length of the intersected track
            intersected_length = intersected_track.length

            # Convert the intersected track to a GeoDataFrame
            intersected_track_gdf = gp.GeoDataFrame({'geometry': [intersected_track]}, crs=EPSG_LOCAL)

            # Split the multi-line string into individual line strings
            intersected_track_gdf = intersected_track_gdf.explode(index_parts=True)

            # Calculate statistics about the intersected track
            # Track length (TL) within segment
            # In other words, the summation of all the bisected line segments
            tl_m = intersected_length
            tl_ft = tl_m * 3.280839895

            # Total Track Length (TTL) or Effort (Z) = TL * Number of searchers
            ttl_m = tl_m * SEARCHERS
            ttl_ft = tl_ft * SEARCHERS

            # Area effectively searched (AES) = TTL * Effective Sweep Width (ESW)
            aes_ft = ttl_ft * (ESW * 3.280839895)
            aes_m = ttl_m * ESW

            area_sq_m = segment.geometry.area
            area_sq_ft = segment.geometry.area * 10.7639104167
            
            c = aes_m / area_sq_m

            # Only append data if track length is greater than 0
            if tl_m != 0:
                # Print the data to the console
                #print(f"\r\nSegment: {segment.title}")
                #print(f"     TL within segment: {round(tl_m, 2)} (m) | {round(tl_ft)} (ft)")
                #print(f"     TTL within segment: {round(ttl_m, 2)} (m) | {round(ttl_ft)} (ft)")
                #print(f"     Area effectively searched: {round(aes_m, 2)} (m\u00b2) | {round(aes_ft, 2)} (ft\u00b2)")
                #print(f"     Coverage: {round(c * 100, 2)}%\n\r")

                # Add the data to the 'description' column so it's imported back into SARTopo 
                #intersected_track_gdf['description'] = f"TL within segment: {round(tl_m, 2)} (m) | {round(tl_ft, 2)} (ft)\nTTL within segment: {round(ttl_m, 2)} (m) | {round(ttl_ft, 2)} (ft)\nArea effectively searched: {round(aes_m, 2)} (m) | {round(aes_ft, 2)} (ft)\nCoverage: {round(c * 100, 2)}%"
                
                # Add the data row to the spreadsheet
                new_spreadsheet_row = {"Segment Name": segment.title, "Segment Area": area_sq_m, "Searchers": SEARCHERS, "ESW (meters)": ESW, "TL (meters)": tl_m, "TTL (meters)": ttl_m, "AES (sq meters)": aes_m, "Coverage": c}
                spreadsheet.append(new_spreadsheet_row)
               
                # For each line segment, print the line length
                #for idx, row in intersected_track_gdf.iterrows():
                #    print(f"Line {idx} length: {row.geometry.length}")


                # Retain the title of the search track
                i = 1 
                for idx, row in intersected_track_gdf.iterrows():
                    # Track name (as imported), what segment it's in, and an incremental number
                    # This is to prevent duplicate track names
                    intersected_track_gdf.at[idx, 'title'] = f"{track.title} - {segment.title}{i}"
                    i += 1
                    
                # Create a random color for the intersected track and assign to the 'color' column
                intersected_track_gdf['fill'] = "#%06x" % random.randint(0, 0xFFFFFF)

                # Append this intersected track to the list of intersected tracks
                intersections.append(intersected_track_gdf)
            
    # Convert the list of data rows to a single DataFrame
    spreadsheet = pd.DataFrame(spreadsheet)
    print("\r\n" + spreadsheet.to_string() + "\r\n")

    # Convert the list of intersected tracks to a single GeoDataFrame
    intersections_gdf = gp.GeoDataFrame(pd.concat(intersections), crs=EPSG_LOCAL)
    intersections_gdf.set_index('title', inplace=True)

    # For debugging, showing myself what the intersected tracks look like
    if SHOW_PLOTS:
        ax = segment_gdf.plot(color='red', alpha=0.2)
        intersections_gdf.plot(ax=ax, color='blue')
        plt.show()

    # Write the intersected tracks to a file
    intersections_gdf.to_crs(epsg=EPSG_WGS84).to_file(FILE_PATH + "\\output_intersected.geojson", driver='GeoJSON')
    print(f"GeoJSON file written to {FILE_PATH}{OUTPUT_FILE}")

    # Write the spreadsheet to an Excel file
    spreadsheet.to_excel(FILE_PATH + "output_intersected.xlsx", index=False)
    print(f"Excel file written to {FILE_PATH}output_intersected.xlsx \r\n")

if __name__ == "__main__":
    main()

#243
