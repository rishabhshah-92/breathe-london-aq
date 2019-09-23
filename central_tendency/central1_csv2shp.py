import sys
import os
sys.path.append(r'..\geolocation\helpers')
import arc_road_helpers as arh
import datetime as dt

dirname = r'..\..\..\Data\Intermediate\central_tendency'
#fname = 'central0_drivesummarystats'+dt.date.today().strftime('_%y%b%d')
fname = 'central0_drivesummarystats_19Jul23'
csvtoconvert = os.path.join(dirname,fname+'.csv')
outfc = os.path.join(dirname,fname+".shp")

fieldin_list = ["segid","the_geom","function","name1","pm2_5_med","pm2_5_std","pm2_5_drvct",\
        "co2_med","co2_std","co2_drvct",\
        "no_med","no_std","no_drvct",\
        "bc_med","bc_std","bc_drvct",\
        "o3_med","o3_std","o3_drvct",\
        "no2_med","no2_std","no2_drvct",\
        "speedkmh_med","speedkmh_std","speedkmh_drvct",\
        "pm2_5time_arr","pm2_5mean_arr","no2time_arr","no2mean_arr"\
        ]
#first item must be geometry, field names <= 10 characters
fieldout_list = ["SHAPE@","segid","function","name1","pm2_5_med","pm2_5_std","pm2_5_ct",\
        "co2_med","co2_std","co2_ct",\
        "no_med","no_std","no_ct",\
        "bc_med","bc_std","bc_ct",\
        "o3_med","o3_std","o3_ct",\
        "no2_med","no2_std","no2_ct",\
        "spdkmh_med","spdkmh_std","spdkmh_ct"\
        ]
typeout_list = ["geometry","text","text","text"]+["float","float","short"]*7
order_list = [1,0]+list(range(2,len(fieldout_list))) #index of input fields associated with output

fc = arh.wkt2shp(csvtoconvert,outfc,fieldin_list,fieldout_list,typeout_list,order_list)
print(fc)
