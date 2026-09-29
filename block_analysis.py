import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mtick
from matplotlib.ticker import FuncFormatter
import seaborn as sns
import math

plt.rcParams["font.family"] = ["Times New Roman"]
LW=1.7

np.set_printoptions(suppress=True)
DIR = os.path.dirname(os.path.abspath(__file__))

# uncomment to create the pre-processed_hourly file, skip if present
"""
# open pre-preprocessed file
vm_data_df = pd.read_csv(DIR+'/pre-processed.csv')
vm_data_df = vm_data_df.dropna()

# convert to datetime
vm_data_df["timestamp"] = pd.to_datetime(vm_data_df['timestamp'])

# resample at a 1-hour interval replacing the values with the 95th percentile
vm_data_df["timestamp"] = vm_data_df["timestamp"].dt.floor('h')
agg_logic = {}
for col in vm_data_df.columns:
    if col in ['server_id', 'timestamp']:
        continue
    if col in ['vcpu_utilization', 'ram_utilization', 'vcpu_utilization_perc']:
        agg_logic[col] = lambda x: x.quantile(0.95)
    else:
        agg_logic[col] = 'first'
hourly_df = vm_data_df.groupby(['server_id', 'timestamp']).agg(agg_logic).reset_index()

print(hourly_df.head(20))

hourly_df.to_csv(DIR+'/pre-processed_hourly.csv', index=False)
"""

def decimal_to_percent(x, pos):
    x = x*100
    return "{:.0f}%".format(x)

def add_percent(x, pos):
    return "{:.0f}%".format(x)

def add_percent_keep_decimals(x, pos):
    return "{:.1f}%".format(x)

decimal_to_percent_formatter = FuncFormatter(decimal_to_percent)
add_percent_formatter = FuncFormatter(add_percent)

# open pre-processed file
vm_data_df = pd.read_csv(DIR+'/pre-processed_hourly.csv')
vm_data_df = vm_data_df.dropna()

# convert to datetime
vm_data_df["timestamp"] = pd.to_datetime(vm_data_df['timestamp'], utc=True)

# find the vms to exclude from "time until meaningful" metric
timestamps = vm_data_df.groupby("timestamp").agg(
    vm_count=("server_id","count")
).sort_values(by="timestamp")
# consistent number of vms on first few hours (118), just exlude those server_ids 
#print(timestamps.head(20))
# first day is 2024-05-23
existing_server_ids = vm_data_df[vm_data_df["timestamp"] < "2024-05-24"]["server_id"].unique()
print("excluding",len(existing_server_ids),"servers")

print(vm_data_df.head(10))
print((vm_data_df.head(10)['vcpu_utilization_perc'] > 10).sum()/(vm_data_df.head(10)['vcpu_utilization_perc']).count())

# % threshold analysis, use it to determine vcpu_perc threshold
t_range = np.arange(0, 101, 1)
#active_counts = [(vm_data_df['vcpu_utilization_perc'] > t).sum() for t in t_range]
active_counts = [(vm_data_df['vcpu_utilization_perc'] > t).sum()/vm_data_df['vcpu_utilization_perc'].count() for t in t_range]
fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
ax.yaxis.set_major_formatter(decimal_to_percent_formatter)
ax.xaxis.set_major_formatter(add_percent_formatter)
plt.plot(t_range, active_counts, linewidth=LW)
plt.axvline(10, color='red', linestyle='--', label='Recommended (10%)', lw=LW)
plt.xlabel('vCPU utilization threshold', fontname="serif", fontsize=10)
plt.ylabel('Meaningful hours', fontname="serif", fontsize=10)
plt.xticks(fontname = 'serif', fontsize=9)
plt.yticks(fontname = 'serif', fontsize=9)
plt.grid(True, alpha=1, ls=":", linewidth=0.5)
plt.savefig(DIR+'/new_formatted_plots/active_vs_threshold.png', bbox_inches='tight')
plt.show()

THRESHOLD_VCPU = 10

# assign a label
vm_data_df["is_active_hour"] = vm_data_df["vcpu_utilization_perc"] >= THRESHOLD_VCPU

# heatmap plot for usage patterns
heatmap_df = vm_data_df.copy(deep=True)
heatmap_df['timestamp'] = heatmap_df['timestamp'].dt.tz_convert('America/Sao_Paulo')
heatmap_df['hour'] = heatmap_df['timestamp'].dt.hour
heatmap_df['day_of_week'] = heatmap_df['timestamp'].dt.day_name()
day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
heatmap_df['day_of_week'] = pd.Categorical(heatmap_df['day_of_week'], categories=day_order, ordered=True)
heatmap_data = heatmap_df.pivot_table(
    index='day_of_week', 
    columns='hour', 
    values='vcpu_utilization_perc',
    aggfunc='mean'
)
fig, ax = plt.subplots(figsize=(7, 3.2), dpi=300)
sns.heatmap(
    heatmap_data, cmap="YlGnBu", annot=False,
    xticklabels=2,  # label every other hour so ticks don't crowd
    cbar_kws={'label': 'Avg P95 vCPU %'}, ax=ax
)
# sns.heatmap turns the spines off by default -- put a border back
# around the colored area (and match it on the colorbar)
for spine in ax.spines.values():
    spine.set_visible(True)
    spine.set_edgecolor('black')
    spine.set_linewidth(0.6)
plt.xlabel('Hour of Day', fontname="serif", fontsize=10)
plt.ylabel('Day of Week', fontname="serif", fontsize=10)
plt.xticks(fontname='serif', fontsize=9, rotation=0)
plt.yticks(fontname='serif', fontsize=9, rotation=0)
cbar = ax.collections[0].colorbar
cbar.ax.tick_params(labelsize=9, labelfontfamily="serif")
cbar.ax.set_ylabel("Average P95 vCPU utilization", fontname="serif")
cbar.ax.yaxis.set_major_formatter(add_percent_keep_decimals)
for spine in cbar.ax.spines.values():
    spine.set_visible(True)
    spine.set_edgecolor('black')
    spine.set_linewidth(0.6)
plt.savefig(DIR+'/new_formatted_plots/heatmap.png', bbox_inches='tight')
plt.show()

# daily hours threshold analysis, use it to determine minimum number of active hours in a day
daily_active_counts = vm_data_df.groupby(['server_id', vm_data_df['timestamp'].dt.date])['is_active_hour'].sum()
thresholds = np.arange(0, 25)
days_remaining = [(daily_active_counts >= t).sum() for t in thresholds]
servers_remaining = [daily_active_counts[daily_active_counts >= t].index.get_level_values(0).nunique() for t in thresholds]
fig, ax1 = plt.subplots(figsize=(6, 3), dpi=300)
ax1.set_xlabel('Meaningful Hours Required per Day')
ax1.set_ylabel('Total Meaningful Days Across VMs')
plt.xlabel('Meaningful Hours Required per Day', fontname="serif", fontsize=10)
plt.ylabel('Total Meaningful Days Across VMs', fontname="serif", fontsize=10)
ax1.plot(thresholds, days_remaining, lw=LW)
ax1.grid(True, alpha=1, ls=":", linewidth=0.5)
plt.xticks(thresholds)
plt.xticks(fontname = 'serif', fontsize=9)
plt.yticks(fontname = 'serif', fontsize=9)
plt.axvline(2, color='red', linestyle='--', lw=LW)
fig.tight_layout()
plt.savefig(DIR+'/new_formatted_plots/meaningful_day_threshold.png', bbox_inches='tight')
plt.show()

THRESHOLD_HOURS = 2

# create the new day-granularity dataframe
daily_summary = vm_data_df.groupby(['server_id', vm_data_df['timestamp'].dt.date]).agg(
    active_hours_count=('is_active_hour', 'sum')
).reset_index()
daily_summary['label'] = np.where(daily_summary['active_hours_count'] >= 2, "Meaningful", "Idle")
daily_summary = daily_summary[['server_id', 'timestamp', 'label']].copy()
daily_summary.rename(columns={'timestamp': 'date'}, inplace=True)

# idle "bridge" analysis to count idle weekends as active
daily_summary['date'] = pd.to_datetime(daily_summary['date'])
daily_summary = daily_summary.sort_values(['server_id', 'date'])
n_values = range(0, 11)
block_counts = []
for n in n_values:
    temp_df = daily_summary.copy()
    temp_df['prev_date'] = temp_df.groupby('server_id')['date'].shift(1)
    temp_df['date_gap'] = (temp_df['date'] - temp_df['prev_date']).dt.days
    temp_df['is_meaningful'] = temp_df['label'] == "Meaningful"
    meaningful_only = temp_df[temp_df['is_meaningful']].copy()
    meaningful_only['gap_to_prev_meaningful'] = (meaningful_only['date'] - 
                                                meaningful_only.groupby('server_id')['date'].shift(1)).dt.days
    num_blocks = (meaningful_only['gap_to_prev_meaningful'] > (n + 1)).sum() + meaningful_only['server_id'].nunique()
    block_counts.append(num_blocks)

plt.figure(figsize=(6, 3), dpi=300)
plt.plot(n_values, block_counts, lw=LW)
plt.xlabel('Maximum Idle Days Tolerated')
plt.ylabel('Total Number of Meaningful Blocks')
plt.xlabel('Maximum idle days tolerated', fontname="serif", fontsize=10)
plt.ylabel('Number of meaningful blocks', fontname="serif", fontsize=10)
plt.xticks(n_values)
plt.xticks(fontname = 'serif', fontsize=9)
plt.yticks(fontname = 'serif', fontsize=9)
plt.axvline(3, color='red', linestyle='--', lw=LW)
plt.grid(True, alpha=1, ls=":", linewidth=0.5)
plt.savefig(DIR+'/new_formatted_plots/blocks_vs_gaps.png', bbox_inches='tight')
plt.show()

THRESHOLD_GAP = 3

# BLOCK ANALYSIS

# block creation
daily_summary = daily_summary.sort_values(['server_id', 'date'])
daily_summary['date'] = pd.to_datetime(daily_summary['date'])

time_gap = daily_summary['date'].diff() > pd.Timedelta(days=THRESHOLD_GAP+1)
label_change = daily_summary['label'] != daily_summary['label'].shift()
server_change = daily_summary['server_id'] != daily_summary['server_id'].shift()
daily_summary['block_id_seq'] = (time_gap | label_change | server_change).cumsum()
blocks_df = daily_summary.groupby('block_id_seq').agg(
    server_id=('server_id', 'first'),
    label=('label', 'first'),
    begin_date=('date', 'min'),
    end_date=('date', 'max')
).reset_index(drop=True)
blocks_df['duration'] = (blocks_df['end_date'] - blocks_df['begin_date']).dt.days +1
blocks_df = blocks_df.sort_values(by=['server_id', 'begin_date'])

# change short idle gaps into meaningful (prevent weekends from fragmenting long meaningful blocks)
blocks_df['gap_days_prev'] = (blocks_df['begin_date'] - blocks_df.groupby('server_id')['end_date'].shift(1)).dt.days
blocks_df['gap_days_next'] = (blocks_df.groupby('server_id')['begin_date'].shift(-1) - blocks_df['end_date']).dt.days
blocks_df.loc[(blocks_df['label'] == 'Idle') & (blocks_df['duration'] <= 3) & (blocks_df['gap_days_prev'] <= 1) & (blocks_df['gap_days_next'] <= 1), 'label'] = 'Meaningful'

# merge adjacent meaningful blocks (merge short idle gaps into longer meaningful blocks)
time_gap = blocks_df['gap_days_prev'] > 1
label_change = blocks_df['label'] != blocks_df['label'].shift()
server_change = blocks_df['server_id'] != blocks_df['server_id'].shift()
blocks_df['block_id'] = (time_gap | label_change | server_change).cumsum()
blocks_df = blocks_df.groupby('block_id').agg(
    server_id=('server_id', 'first'),
    label=('label', 'first'),
    begin_date=('begin_date', 'min'),
    end_date=('end_date', 'max'),
    duration=("duration","sum")
).reset_index(drop=True)

# meaningful/idle ratio metrics and plot
ratio = blocks_df[blocks_df["label"] == "Meaningful"]["duration"].sum() / blocks_df[blocks_df["label"] == "Idle"]["duration"].sum()
print(f"Ratio over entire dataset: {ratio}")
usage_totals = blocks_df.groupby(['server_id', 'label'])['duration'].sum().unstack(fill_value=0)
plt.figure(figsize=(6, 5), dpi=300)
sns.scatterplot(
    data=usage_totals, 
    x='Meaningful', 
    y='Idle', 
    alpha=0.6, 
    s=60,
    edgecolor='w'
)
max_val = max(usage_totals['Meaningful'].max(), usage_totals['Idle'].max())
plt.plot([0, max_val], [0, max_val], color='grey', linestyle='--', lw=LW)
plt.xlabel('Total days of meaningful use', fontname="serif", fontsize=10)
plt.ylabel('Total days of idle use', fontname="serif", fontsize=10)
plt.xticks(fontname = 'serif', fontsize=9)
plt.yticks(fontname = 'serif', fontsize=9)
plt.grid(True, alpha=1, ls=":", linewidth=0.5)
plt.tight_layout()
plt.savefig(DIR+'/new_formatted_plots/ratio_scatter.png', bbox_inches='tight')
plt.show()

# "time until first meaningful block" metric

# leading-block / following-block pairing, restricted to newborn
# servers (excludes existing_server_ids, which have no assignable
# creation date)
ordered_blocks = blocks_df[~blocks_df.server_id.isin(existing_server_ids)].sort_values(['server_id', 'begin_date'])
firsts = ordered_blocks.groupby('server_id').nth(0)
seconds = ordered_blocks.groupby('server_id').nth(1)
comparison_df = pd.merge(firsts, seconds, on='server_id', suffixes=('_1st', '_2nd'))

candidates = comparison_df.loc[
    (comparison_df['label_1st'] == 'Meaningful') & (comparison_df['label_2nd'] == 'Idle'),
    ['duration_1st', 'duration_2nd']
].copy()

# leading-block cutoff analysis: find the duration that best separates
# leading-block durations from meaningful block durations generally
# (equivalent to the two-sample Kolmogorov-Smirnov statistic). This
# decides which leading blocks represent setup activity rather than
# genuine first use, based only on the block's own duration.
leading_durations = candidates['duration_1st']
all_meaningful_durations = blocks_df.loc[blocks_df['label'] == 'Meaningful', 'duration']
cutoff_grid = np.arange(1, int(max(leading_durations.max(), all_meaningful_durations.max())) + 1)
ecdf_leading = np.array([(leading_durations <= d).mean() for d in cutoff_grid])
ecdf_all = np.array([(all_meaningful_durations <= d).mean() for d in cutoff_grid])
separation = np.abs(ecdf_leading - ecdf_all)

fig, ax = plt.subplots(figsize=(6, 4), dpi=300)
ax.yaxis.set_major_formatter(decimal_to_percent_formatter)
plt.plot(cutoff_grid, separation, linewidth=LW)
plt.axvline(4, color='red', linestyle='--', lw=LW)
plt.xlabel('Candidate leading-block cutoff (days)', fontname="serif", fontsize=10)
plt.ylabel('Distributional separation', fontname="serif", fontsize=10)
plt.xticks(fontname='serif', fontsize=9)
plt.yticks(fontname='serif', fontsize=9)
plt.xlim(0, 30)
plt.grid(True, alpha=1, ls=":", linewidth=0.5)
plt.savefig(DIR+'/new_formatted_plots/setup_cutoff_separation.png', bbox_inches='tight')
plt.show()

SETUP_CUTOFF_DAYS = 4

reclassified = candidates[candidates['duration_1st'] <= SETUP_CUTOFF_DAYS]

print(f"Leading blocks <= {SETUP_CUTOFF_DAYS}d (would be reclassified): {len(reclassified)} of {len(candidates)}")
print("\nFollowing idle block duration among those reclassified:")
print(f"  min={reclassified['duration_2nd'].min():.0f}d, "
      f"median={reclassified['duration_2nd'].median():.0f}d, "
      f"mean={reclassified['duration_2nd'].mean():.1f}d, "
      f"max={reclassified['duration_2nd'].max():.0f}d")
for n in [1, 2, 3, 5, 7, 14, 30]:
    count = (reclassified['duration_2nd'] <= n).sum()
    print(f"  followed by idle block <= {n:>2}d: {count:>3} ({count / len(reclassified):.1%})")

# relabel first meaningful block as idle if its own duration is <= SETUP_CUTOFF_DAYS
setup_mask = (
    (comparison_df['label_1st'] == 'Meaningful') &
    (comparison_df['label_2nd'] == 'Idle') &
    (comparison_df['duration_1st'] <= SETUP_CUTOFF_DAYS)
)
servers_to_relabel = comparison_df.loc[setup_mask, 'server_id'].tolist()
mask = (ordered_blocks['server_id'].isin(servers_to_relabel)) & (ordered_blocks['begin_date'] == ordered_blocks.groupby('server_id')['begin_date'].transform('min'))
ordered_blocks.loc[mask, 'label'] = 'Idle'
# find days before first meaningful block
server_birth = ordered_blocks.groupby('server_id')['begin_date'].min().reset_index()
server_birth.columns = ['server_id', 'birth_date']
meaningful_starts = ordered_blocks[ordered_blocks['label'] == 'Meaningful'].groupby('server_id')['begin_date'].min().reset_index()
meaningful_starts.columns = ['server_id', 'first_meaningful_date']
latency_df = pd.merge(server_birth, meaningful_starts, on='server_id', how='left')
latency_df['activation_latency'] = (latency_df['first_meaningful_date'] - latency_df['birth_date']).dt.days
# remove servers with no meaningful blocks
#latency_df['activation_latency'] = latency_df['activation_latency'].dropna()

# get servers with no meaningful blocks
bad_servers = latency_df[latency_df['first_meaningful_date'].isna()]["server_id"]
bad_server_blocks = ordered_blocks[ordered_blocks["server_id"].isin(bad_servers)]
print(f"should be zero:{len(bad_server_blocks[bad_server_blocks["label"] == "Meaningful"])}")
bad_server_durations = bad_server_blocks.groupby("server_id").agg(
    first_begin=("begin_date","min"),
    last_end=("end_date","max")
)
bad_server_durations["activation_latency"] = (bad_server_durations['last_end'] - bad_server_durations['first_begin']).dt.days
latency_df = latency_df.dropna()

# changed from this vvv
#latency_df = latency_df.drop(["birth_date","first_meaningful_date"], axis=1).reset_index()
#bad_server_durations = bad_server_durations.drop(["first_begin","last_end"], axis=1).reset_index()
# to this vvv for the latency to flavor correlation
latency_df["timestamp"] = latency_df["first_meaningful_date"]
bad_server_durations["timestamp"] = bad_server_durations["last_end"]
latency_df = latency_df.drop(["birth_date","first_meaningful_date"], axis=1).reset_index()
bad_server_durations = bad_server_durations.drop(["first_begin","last_end"], axis=1).reset_index()

print(latency_df.head(5))
print(bad_server_durations.head(5))

latency_df = pd.concat([latency_df, bad_server_durations])

print("unique ids:",len(latency_df["server_id"].unique()))
print("total rows:",len(latency_df["server_id"]))
print("^^^ they should be the same ^^^")

print(f"Median number of days before first meaningful block:{latency_df['activation_latency'].median()}")
print(f"Mean number of days before first meaningful block:{latency_df['activation_latency'].mean()}")

fig, ax = plt.subplots(figsize=(6,3), dpi=300)
sns.ecdfplot(data=latency_df, x='activation_latency', ax=ax, lw=LW)
plt.xlabel('Days until first meaningful use', fontsize=10, fontname="serif")
plt.ylabel('Proportion of servers', fontsize=10, fontname="serif")
plt.xticks(fontname = 'serif', fontsize=9)
plt.yticks(fontname = 'serif', fontsize=9)
ax.yaxis.set_major_formatter(decimal_to_percent_formatter)
plt.grid(True, alpha=1, ls=":", linewidth=0.5)
plt.savefig(DIR+'/new_formatted_plots/days_until.png', bbox_inches='tight')
plt.show()

print(latency_df.head(5))

# latency to vm-size correlation
# remove exit() to show plots
exit()

latency_df['timestamp'] = latency_df['timestamp'] + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
latency_df = latency_df.sort_values('timestamp').reset_index(drop=True)

# merge with servers_specs to get flavor_id
servers_specs = pd.read_csv(DIR+'/../data_new/servers_specs.csv')
servers_specs["timestamp"] = pd.to_datetime(servers_specs['timestamp'], unit="s") # added timestamp conversion
servers_specs = servers_specs.sort_values(by=['timestamp']).reset_index(drop=True) # added sort
latency_df = pd.merge_asof(
    latency_df,
    servers_specs[['server_id', 'timestamp', 'flavor_id']],
    on='timestamp',
    by='server_id',
    direction='backward'
)

# merge with flavors to get number of vcpus
flavors = pd.read_csv(DIR+'/../data_new/flavors.csv')
flavors = flavors.drop_duplicates(subset=['flavor_id'])
latency_df = pd.merge(latency_df, flavors[['vcpu', "flavor_id", "ram"]], on='flavor_id', how="left")

sns.scatterplot(
    data=latency_df, 
    x='activation_latency', 
    y='vcpu', 
    alpha=0.6, 
    s=60,
    edgecolor='w'
)
plt.title('First usage vs vCPUs', fontsize=14)
plt.xlabel('Usage latency (days)', fontsize=12)
plt.ylabel('vCPUs', fontsize=12)
plt.grid(True, alpha=0.3, linewidth=0.5)
plt.tight_layout()
plt.show()

sns.scatterplot(
    data=latency_df, 
    x='activation_latency', 
    y='ram', 
    alpha=0.6, 
    s=60,
    edgecolor='w'
)
plt.title('First usage vs RAM', fontsize=14)
plt.xlabel('Usage latency (days)', fontsize=12)
plt.ylabel('RAM', fontsize=12)
plt.grid(True, alpha=0.3, linewidth=0.5)
plt.tight_layout()
plt.show()

print("should be zero:",latency_df['flavor_id'].isna().sum())