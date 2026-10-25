# A one-year measurement of quota-induced waste in private clouds

Code and figures for our study of resource provisioning, allocation, and usage in a
production private OpenStack cloud operated by LSD/UFCG. Private clouds rely on
administrative quotas rather than pricing to regulate access, and this repository measures
how those quotas lead to inefficiency through two analyses: quota exhaustion and resource
hoarding.

Based on the dataset:

> Marques, Paola; Mendes, Mariana; Pereira, Thiago Emmanuel; Farias, Giovanni (2026).
> *Dataset on Resource Allocation and Usage for a Private Cloud*. Mendeley Data, V2.
> doi: [10.17632/trvb5k4x5m.2](https://doi.org/10.17632/trvb5k4x5m.2)

## Structure

- `notebooks/` (R), quota and potential-failure analysis:
  - [quota-allocation-pressure.Rmd](notebooks/quota-allocation-pressure.Rmd):
    provisioned quota versus allocated resources against the cluster's physical and
    overcommit capacity, and the resulting per-project potential-failure exposure.
- `scripts/` (Python), resource-hoarding analysis:
  - [hoarding_preprocess.py](scripts/hoarding_preprocess.py): per-VM vCPU and RAM
    utilization preprocessing (alignment to a 5-minute grid, interpolation of short gaps).
  - [block_analysis.py](scripts/block_analysis.py): meaningful and idle block
    segmentation and hoarding metrics (idle versus meaningful time, time to first
    meaningful use).
- `plots/`: all generated figures.

## Data

The analyses read the dataset CSVs (`servers_utilization.csv`, `servers_specs.csv`,
`flavors.csv`, `projects_quota.csv`, `servers_ownerships.csv`):

- R notebook: set the `DATASET_PATH` environment variable to the dataset folder
  (it defaults to `data/`).
- Python scripts: expect the CSVs in a `data_new/` folder next to the repository.

Figures are written to `plots/`.
