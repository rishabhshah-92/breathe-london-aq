#This program is an air quality monitoring data post-processing and analysis routine
#prepared by Environmental Defense Fund.

#For details on how to use this program refer to the doc/ folder in each root
#subfolder.

#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, either version 3 of the License, or
#(at your option) any later version.   This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details at root level in LICENSE.txt
#or see http://www.gnu.org/licenses/.

from google.cloud import bigquery
from google.oauth2 import service_account
import glob
import os
import sys
import numpy as np
import pandas as pd
import datetime as dt
import matplotlib.pyplot as plt
credentials = service_account.Credentials.from_service_account_file(r"..\..\..\pks\street-view-air-quality-london-dc8f329b26cf.json")
project_id = 'street-view-air-quality-london'
client = bigquery.Client(credentials=credentials,project=project_id)
location = 'EU'
pct_list = [5,25,50,75,95] #selected percentiles
percentile_str = ''.join([",percentile_cont(SAFE_DIVIDE(conc_expected-conc_sub_expected,conc_sub_expected)*100,{0}) over (partition by n_sub) as p{1:02}t".format(pct/100, pct) for pct in pct_list])
field_str = ''.join([', ANY_VALUE(p{0:02}t) as p{0:02}t'.format(pct) for pct in pct_list])
for species in ['NO2']:
#for species in ['NO2', 'NOx', 'PM2.5 Palas','CO2 dry','NO']:
    if species == 'NO2':
        pid = 133
        unit = 'ppb'
    elif species == 'NOx':
        pid = 163
        unit = 'ug/m3'
    elif species == 'NO':
        pid = 45
        unit = 'ppm'
    elif species == 'PM2.5 Palas':
        pid = 3
        unit = 'ug/m3'
    elif species == 'PM2.5 PDR':
        pid = 140
        unit = 'ug/m3'
    elif species == 'CO2 dry':
        pid = 33
        unit = 'ppm'
        ymin = 400
    elif species == 'O3':
        pid = 127
        unit = 'ppb'
    plt.rcParams.update({'font.size':14})
    fig,axes = plt.subplots(1,2,figsize=(12,6))
    ###############################################################
    #Evaluate segment medians for Apr-Oct 2019 monitoring period
    #include only segments with min 75 drives in period
    #select segments
    qry_str = """
            with cte0 as
        (
        --calc expected values using all N passes (~truth) and assign idx for subsampling
        select segid, hour1stamp, value_median as conc_1hr
        ,row_number() over (partition by segid) as idx
        ,percentile_cont(value_median, 0.5) over (partition by segid) as conc_expected
        from UK.snap4_drivepass_1hr_medians
        where hour1stamp >= '2019-04-08' and parameter_id = {0}
        --generate subsample index arrays, M per segment and n samples
        )
        , cte1 as
        (
        select segid, n
        ,trial_id
        --arrays of top n drive indices ordered by random number without replacement
        ,array_agg(idx) over (partition by segid,trial_id order by rid rows between current row and 9 following) as sample_arr10
        ,array_agg(idx) over (partition by segid,trial_id order by rid ROWS BETWEEN CURRENT ROW AND 34 FOLLOWING) as sample_arr35
        ,rid
        ,min(rid) over (partition by segid,trial_id) as minrid
        from (
          --make M copies of the passes for M trials, each trial will have a different random selection of n passes
          select segid, max(idx) over (partition by segid) as N --total number of passes
                    ,idx
          ,rand() as rid --random number assigned to each record
          ,trial_id
          from cte0
          ,unnest(generate_array(1,500)) trial_id --number of trials
          --order by segid, rid
          )
        --limit to segments with at least 75 drives
        where N >= 75
        )
        , cte2 as
        (
        --union results for different n
        select segid, trial_id, N
        , 10 as n_sub, sample_arr10 as sample_arr
        from cte1
        where rid = minrid
        union all
        select segid, trial_id, N
        , 35 as n_sub, sample_arr35 as sample_arr
        from cte1
        where rid = minrid
         )
 , cte3 as
 (
 --join concentration data to the expanded subsamples
 select segid, n_sub, trial_id, conc_expected
 ,ANY_VALUE(conc_sub_expected) as conc_sub_expected
 from (
     select a.segid, b.n_sub, b.trial_id
     , a.conc_expected
     --calc expected values over subsample trials
     ,percentile_cont(conc_1hr,0.5) over (partition by a.segid, b.n_sub, b.trial_id) as conc_sub_expected
     --concentration data
     from cte0 a
     join
     --expanded subsample trials
     (select segid, trial_id, n_sub, sample_idx
     from cte2, unnest(sample_arr) sample_idx) b
     on a.segid = b.segid and a.idx = b.sample_idx
     )
 group by segid, n_sub, trial_id, conc_expected
 )
 --calc summary statistics on bias %
 select function, n_sub, cte3.segid
 , conc_expected
 , conc_sub_expected
 , SAFE_DIVIDE(conc_expected-conc_sub_expected,conc_sub_expected)*100 as diffpct
 , (conc_expected-conc_sub_expected) as diff
 , CUME_DIST() OVER (partition by cte3.segid, n_sub order by cte3.segid, n_sub, SAFE_DIVIDE(conc_expected-conc_sub_expected,conc_sub_expected)) as cumulfrac
 , 1-(CUME_DIST() OVER (partition by cte3.segid, n_sub order by cte3.segid, n_sub, SAFE_DIVIDE(conc_expected-conc_sub_expected,conc_sub_expected)*100)) as exceedpct
 from cte3
 join UK.greaterlondon_roads_wgs84_split30m b
 on cte3.segid = b.segid
 order by function, n_sub, segid, diffpct
    """.format(pid)
    print(species)
    destinationtable_str = 'drivebias2_{0}_sampleuncertainty_byfunction_{1}.csv'.format(species.replace(' ','_'),dt.date.today().strftime('%Y%b%d'))
    destinationcsv_str = os.path.join(r'..\..\..\..\Data\Intermediate\temporal_bias',destinationtable_str)
    qry_job = client.query(qry_str,location=location,job_config=bigquery.QueryJobConfig())
    df = qry_job.to_dataframe()
    df.to_csv(destinationcsv_str,index=False)
    df = pd.read_csv(destinationcsv_str)
    
    #plots
    ax = axes[0]
    df_a = df[(df['n_sub']==10) & (df['function']=='A Road')]
    df_b = df[(df['n_sub']==10) & (df['function']=='Local Road')]
    ax.plot(df_a['diffpct'],df_a['exceedpct'],'b.',label='A Road')
    ax.plot(df_b['diffpct'],df_b['exceedpct'],'r.',label='Local Road')
    ax.set_ylabel('Exceedance probability (%)')
    ax.set_xlabel('Difference % (M(all) - M(sub))/M(sub)')
    ax.title.set_text('{0} uncertainty by function, N = 10'.format(species))

    ax = axes[1]
    df_a = df[(df['n_sub']==35) & (df['function']=='A Road')]
    df_b = df[(df['n_sub']==35) & (df['function']=='Local Road')]
    ax.plot(df_a['diffpct'],df_a['exceedpct'],'b.',label='A Road')
    ax.plot(df_b['diffpct'],df_b['exceedpct'],'r.',label='Local Road')
    ax.set_xlabel('Difference % (M(all) - M(sub))/M(sub)')
    ax.legend(loc='right')
    ax.title.set_text('{0} uncertainty by function, N = 35'.format(species))
    fig.tight_layout()
    fig.savefig(r'..\charts\mobile_sampleuncertainty_byfunction_{0}_{1}.png'.format(species.replace(' ','_'),dt.date.today().strftime('%Y%b%d')))
