
# etl-pipeline

> 🚧 **In progress** — check back for updates as this builds out.

An end-to-end data pipeline built with Python, pulling from a public API, transforming the data, loading it to a local database, and surfacing insights through a dashboard.

---

## What this project covers

- **Ingestion** — pulls data from a public REST API on a schedule
- **Transformation** — cleans, validates, and reshapes data with Python and pandas
- **Loading** — stores processed data in a local database
- **Visualization** — connected Tableau / Power BI dashboard for analysis

## Stack

| Tool | Role |
|---|---|
| Python + pandas | Ingestion and transformation |
| Airflow | Orchestration and scheduling |
| DuckDB / SQLite | Local storage |
| Tableau / Power BI | Dashboard and visualization |
| Git | Version control |

## Pipeline architecture

```
[Public API]
     ↓
[Python ingestion script]
     ↓
[Transform + validate]
     ↓
[DuckDB / local DB]
     ↓
[Tableau dashboard]
```

## Status

- [ ] API source selected
- [ ] Ingestion script complete
- [ ] Transformation logic complete
- [ ] Airflow DAG configured
- [ ] Dashboard live

---

*Part of my data engineering portfolio — see [github.com/amritperera](https://github.com/amritperera) for more.*
    
