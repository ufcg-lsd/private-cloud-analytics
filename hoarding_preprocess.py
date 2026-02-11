import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import seaborn as sns
import math
from typing import Union

np.set_printoptions(suppress=True)
DIR = os.path.dirname(os.path.abspath(__file__))

# this code assumes the vcpu_utilization column represents the sum of the usage percentage over each vcpu available on a server
# 1 vcpu => vcpu_utilization range 0 - 100
# 2 vcpus => vcpu_utilization range 0 - 200

vm_data_df = pd.read_csv(DIR+'/../data_new/servers_utilization.csv')

# convert timestamps into datetime
vm_data_df["timestamp"] = pd.to_datetime(vm_data_df['timestamp'], unit="s")

# drop unused columns 
vm_data_df = vm_data_df.drop("Unnamed: 0",axis=1)
vm_data_df = vm_data_df.drop("id",axis=1)
vm_data_df = vm_data_df.drop("host_id",axis=1)

# merge with servers_specs to get flavor_id
servers_specs = pd.read_csv(DIR+'/../data_new/servers_specs.csv')
servers_specs = servers_specs.drop_duplicates(subset=['server_id'])
vm_data_df = pd.merge(vm_data_df, servers_specs[['server_id', "flavor_id"]], on='server_id', how="left")

# merge with flavors to get number of vcpus
flavors = pd.read_csv(DIR+'/../data_new/flavors.csv')
flavors = flavors.drop_duplicates(subset=['flavor_id'])
vm_data_df = pd.merge(vm_data_df, flavors[['vcpu', "flavor_id", "flavor_name", "ram"]], on='flavor_id', how="left")

# add a column to "normalize" the vcpu_utilization according to the number of available vcpus
vm_data_df["vcpu_utilization_perc"] = vm_data_df["vcpu_utilization"] / (1*vm_data_df["vcpu"])

# drop unused columns
vm_data_df = vm_data_df.drop("flavor_id",axis=1)
vm_data_df = vm_data_df.drop("flavor_name",axis=1)
vm_data_df = vm_data_df.drop("ram",axis=1)

# vcpu_utilization_perc over 100% in 0.32% of rows
print("rows with vcpu_utilization_perc over 100:",len(vm_data_df[vm_data_df['vcpu_utilization_perc'] > 100]))
print("invalid rows are",(len(vm_data_df[vm_data_df['vcpu_utilization_perc'] > 100])/len(vm_data_df))*100,"of all data")

# violin plot of errors: most between 100% and 110%
sns.violinplot(x=vm_data_df[vm_data_df['vcpu_utilization_perc'] > 100]["vcpu_utilization_perc"])
plt.ylabel("Density", fontsize=12)
plt.show()

# only a very small number of valus above 100% are caused by time gaps and multiple samples being summed as one
# dropping and interpolating should fix these
time_gaps = vm_data_df.sort_values(by=['server_id', 'timestamp'])
time_gaps["time_diff"] = time_gaps.groupby("server_id")["timestamp"].diff()
time_gaps["time_diff"] = time_gaps["time_diff"].dt.total_seconds()
time_gaps = time_gaps.reset_index()

print("rows with vcpu > (125% * nvcpu) and time gap:",len(time_gaps[(time_gaps['vcpu_utilization_perc'] > 100) & (time_gaps['time_diff'] > 320)]))
print(time_gaps[(time_gaps['vcpu_utilization_perc'] > 100) & (time_gaps['time_diff'] > 320)].head(20))

# most values above 100% are on a small number of servers
invalid_report = vm_data_df.groupby('server_id').agg(
    perc_above_100_count=('vcpu_utilization_perc', lambda x: (x > 100).sum()),
    total_rows=("vcpu_utilization", "count"),
    max_real=("vcpu_utilization_perc", "max"),
    max_vcpu=("vcpu_utilization", "max"),
    vcpus=("vcpu", "mean")
).sort_values(by='perc_above_100_count', ascending=False).reset_index()
invalid_report['vcpus'] = invalid_report['vcpus'].astype(int)

# show the vms with the most values above 100%
print("invalid report")
print(invalid_report.head(50))

sns.barplot(invalid_report.head(30), y="server_id", x="perc_above_100_count")
plt.xlabel('Number of errors', fontsize=12)
plt.show()

# store the server_ids in order to ignore these vms during the gap analysis
to_ignore_vm = invalid_report.head(11)["server_id"].unique()

# there are a lot of NaN values
print("vcpu_utilization NAs:",vm_data_df["vcpu_utilization"].isna().sum())

# most of them seem to be on servers without any valid data anyway,
# dropping and interpolating should just treat these as large gaps
nan_report = vm_data_df.groupby('server_id').agg(
    na_count=('vcpu_utilization', lambda x: (x.isna()).sum()),
    non_na_count=('vcpu_utilization', lambda x: (x.notna()).sum())
).sort_values(by=['na_count'], ascending=[False]).reset_index()
#print(nan_report.head(50))

vm_data_df = vm_data_df.sort_values(by=['server_id', 'timestamp'])

# show large gaps before pre-processing
# gaps at this point of the analysis come with the data and are not caused by pre-processing
gaps = vm_data_df.sort_values(by=['server_id', 'timestamp']).dropna()
gaps["time_diff"] = gaps.groupby("server_id")["timestamp"].diff()
gaps["time_diff"] = gaps["time_diff"].dt.total_seconds()
gaps = gaps[gaps['time_diff'] > 750] #4000
gaps["timestamp_d"] = pd.to_datetime(gaps["timestamp"]).dt.to_period(freq="D")

# all existing gaps affect a high number of vms, most likely downtime or sampling issues
sns.stripplot(data=gaps, x="timestamp_d", y="time_diff")
plt.show()

# --------------------
# begin pre-processing
# --------------------

# store these timestamps in order to ignore them during the gap analysis
to_ignore_ts = gaps["timestamp"].unique().round('5min')

# this moves 12:01:05 to 12:00:00 and 12:04:50 to 12:05:00
vm_data_df["timestamp"] = vm_data_df["timestamp"].dt.round('5min')

# drop vcpu_utilization values above 100%
#vm_data_df = vm_data_df[vm_data_df["vcpu_utilization_perc"] <= 100]
vm_data_df.loc[vm_data_df['vcpu_utilization_perc'] > 100, 'vcpu_utilization'] = np.nan
vm_data_df.loc[vm_data_df['vcpu_utilization_perc'] > 100, 'vcpu_utilization_perc'] = np.nan

# collapse duplicates
agg_logic = {col: 'mean' if vm_data_df[col].dtype.kind in 'iufc' else 'first' 
             for col in vm_data_df.columns if col not in ['server_id', 'timestamp']}
vm_data_df = vm_data_df.groupby(['server_id', 'timestamp']).agg(agg_logic).reset_index()

vm_data_df = vm_data_df.set_index("timestamp")

# resample, this leaves missing intervals as NaN.
vm_data_df = vm_data_df.groupby('server_id').resample('5min').asfreq()

# forward fill the number of vcpus to avoid NaNs
vm_data_df['vcpu'] = vm_data_df.groupby(level=0)['vcpu'].ffill()

# reset the index to avoid having NaNs in the server_id column
vm_data_df = vm_data_df.drop(columns=['server_id']).reset_index(level=0)

# show large gaps after resampling by dropping NaNs
# we're ignoring the vms most affected by the out of range vcpu_utilization values and the pre-existing gaps
# this shows the gaps created on the average vm by resampling and dropping out of range vcpu_utilization values
gaps = vm_data_df.reset_index(level="timestamp").reset_index(drop=True).sort_values(by=['server_id', 'timestamp']).dropna()
gaps["time_diff"] = gaps.groupby("server_id")["timestamp"].diff()
gaps["time_diff"] = gaps["time_diff"].dt.total_seconds()
gaps = gaps[gaps['time_diff'] > 300]
gaps = gaps[~gaps['timestamp'].isin(to_ignore_ts)]
gaps = gaps[~gaps['server_id'].isin(to_ignore_vm)]

# most of the new gaps are short and can be interpolated
#sns.stripplot(data=gaps, x="timestamp", y="time_diff")
#plt.show()

sns.violinplot(x=gaps["time_diff"])
plt.xlabel('Gap (s)', fontsize=12)
plt.ylabel("Density", fontsize=12)
plt.show()

# interpolating all gaps below 4200s will leave only a few gaps that will split blocks during the block analysis
gaps = vm_data_df.reset_index(level="timestamp").reset_index(drop=True).sort_values(by=['server_id', 'timestamp']).dropna()
gaps["time_diff"] = gaps.groupby("server_id")["timestamp"].diff()
gaps["time_diff"] = gaps["time_diff"].dt.total_seconds()
gaps = gaps[gaps['time_diff'] > 4200]
gaps = gaps[~gaps['timestamp'].isin(to_ignore_ts)]
gaps = gaps[~gaps['server_id'].isin(to_ignore_vm)]
#sns.stripplot(data=gaps, x="timestamp", y="time_diff")
#plt.show()

# gap example before interpolation
gaps = vm_data_df.reset_index(level="timestamp").reset_index(drop=True).sort_values(by=['server_id', 'timestamp']).dropna()
gaps["time_diff"] = gaps.groupby("server_id")["timestamp"].diff()
gaps["time_diff"] = gaps["time_diff"].dt.total_seconds()
gaps = gaps[gaps['time_diff'] < 4200]
gaps = gaps[gaps['time_diff'] > 3000]
gaps = gaps[~gaps['timestamp'].isin(to_ignore_ts)]
gaps = gaps[~gaps['server_id'].isin(to_ignore_vm)]

#print(gaps.head(10))
single_vm = vm_data_df[vm_data_df['server_id'] == "154e9009-edec-4157-8fac-1ba548163eb0"].reset_index()
single_vm = single_vm.sort_values(by=['server_id', 'timestamp'])
index = single_vm[single_vm['timestamp'] == "2024-05-24 23:35:00"].index.values.astype(int)[0]
print("index:",index)
print("gap before interpolation:")
print(single_vm.loc[index-20:].head(25))

vm_data_df = vm_data_df.reset_index(level="timestamp").reset_index(drop=True).sort_values(by=['server_id', 'timestamp'])

# interpolate
def fill_with_hard_limit(
        df_or_series: Union[pd.DataFrame, pd.Series], limit: int,
        fill_method='interpolate',
        **fill_method_kwargs) -> Union[pd.DataFrame, pd.Series]:
    try:
        df = df_or_series.to_frame()
    except AttributeError:
        df = df_or_series
    mask = pd.DataFrame(True, index=df.index, columns=df.columns)
    grp = (df.notnull() != df.shift().notnull()).cumsum()
    grp['ones'] = 1
    for col in df.columns:
        mask.loc[:, col] = (
                (grp.groupby(col)['ones'].transform('count') <= limit)
                | df[col].notnull()
        )
    method = getattr(df, fill_method)
    out = method(limit=limit, **fill_method_kwargs)[mask]
    if isinstance(df_or_series, pd.Series):
        return out.loc[:, out.columns[0]]
    return out

vm_data_df = fill_with_hard_limit(vm_data_df, 14)

gaps = vm_data_df.dropna()
gaps["time_diff"] = gaps.groupby("server_id")["timestamp"].diff()
gaps["time_diff"] = gaps["time_diff"].dt.total_seconds()
gaps = gaps[gaps['time_diff'] > 300]
gaps = gaps[~gaps['timestamp'].isin(to_ignore_ts)]
gaps = gaps[~gaps['server_id'].isin(to_ignore_vm)]
#sns.stripplot(data=gaps, x="timestamp", y="time_diff")
#plt.show()

# gap example after interpolation
single_vm = vm_data_df[vm_data_df['server_id'] == "154e9009-edec-4157-8fac-1ba548163eb0"].reset_index()
single_vm = single_vm.sort_values(by=['server_id', 'timestamp'])
index = single_vm[single_vm['timestamp'] == "2024-05-24 23:35:00"].index.values.astype(int)[0]
print("index:",index)
print("gap after interpolation:")
print(single_vm.loc[index-20:].head(25))

#vm_data_df.to_csv(DIR+'/pre-processed.csv', index=False)
