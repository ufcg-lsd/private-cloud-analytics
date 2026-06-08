# Analysis of Computational Resources in a Private Cloud

A collection of reproducible analyses of resource provisioning, allocation, and usage in a
private OpenStack cloud operated by LSD/UFCG. 

Based on the dataset:

> Marques, Paola; Mendes, Mariana; Pereira, Thiago Emmanuel; Farias, Giovanni (2026).
> *Dataset on Resource Allocation and Usage for a Private Cloud*. Mendeley Data, V2.
> doi: [10.17632/trvb5k4x5m.2](https://doi.org/10.17632/trvb5k4x5m.2)

## Notebooks

- [`quota-allocation-pressure.Rmd`](https://github.com/ufcg-lsd/private-cloud-analytics/blob/main/notebooks/quota-allocation-pressure.Rmd):
  analyzes provisioned quota and allocated resources against the cluster's physical and
  overcommit capacity, and the resulting potential-failure exposure per project.

Figures are written to [`plots/`](https://github.com/ufcg-lsd/private-cloud-analytics/tree/main/plots).