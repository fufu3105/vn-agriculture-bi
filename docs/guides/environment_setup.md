# Environment Setup

[Project overview](../README.md)

Verified versions: Python 3.12.14, Microsoft OpenJDK 21.0.13.0.2, and PySpark 4.0.5. Use Python 3.12 and JDK 17 or 21 for rebuilding the PySpark dataset. Java is not required to run the current Streamlit dashboard from its CSV snapshots.

## Python Environment

After cloning the repository on a new device, install [Python 3.12](https://www.python.org/downloads/windows/) and run these commands from the repository root. Create `.venv` only if it does not already exist:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Use a Python 3.12 interpreter for the first command (`python --version` to check). Calling `.venv`'s Python directly does not require PowerShell activation.

## Use the Existing Datasets

When the generated datasets have been committed and pushed with the repository, another device can use them immediately after cloning and installing the Python dependencies. Skip ETL and follow [Run the Dashboard](dashboard.md) to use the included CSV snapshots. The shared Parquet file can also be reused without rebuilding it.

Before sharing the repository, include the source Excel files, `data/vietnam_regions_provinces.json`, the generated Parquet dataset and `quality_report.json`, and the dashboard CSV snapshots in the commit. Files present only on the original device are not transferred by cloning. Do not commit `.venv`, JDK installations, or installed libraries; `.venv/` is ignored by Git and must be recreated per device.

## Prepare Java for Rebuilding on Windows

For a fresh **Windows x64** device, the following block installs a portable Microsoft JDK 21 and the local-filesystem adapter used by Spark. It does not change system Java settings. Run it once after creating `.venv`; skip it if both runtime components are already available in the locations below.

```powershell
New-Item -ItemType Directory -Force .venv/java, .venv/spark-jars | Out-Null

$jdkUrl = 'https://aka.ms/download-jdk/microsoft-jdk-21.0.13.0.2-windows-x64.zip'
Invoke-WebRequest -Uri $jdkUrl -OutFile .venv/jdk21.zip
if ((Get-FileHash .venv/jdk21.zip -Algorithm SHA256).Hash -ne 'C5706A9CF482EF1A0622A86EEA5B13D557B07F04554572AF061E2D02B58C0F99') {
    throw 'JDK checksum mismatch'
}
Expand-Archive -LiteralPath .venv/jdk21.zip -DestinationPath .venv/java
Remove-Item -LiteralPath .venv/jdk21.zip

$adapterUrl = 'https://repo.maven.apache.org/maven2/com/globalmentor/hadoop-bare-naked-local-fs/0.1.0/hadoop-bare-naked-local-fs-0.1.0.jar'
$adapterPath = '.venv/spark-jars/hadoop-bare-naked-local-fs-0.1.0.jar'
Invoke-WebRequest -Uri $adapterUrl -OutFile $adapterPath
if ((Get-FileHash $adapterPath -Algorithm SHA256).Hash -ne 'E0CC30FB0531EB0B59468DC0ABF5B257533D2365B5E9F45E795EDD707AA78C62') {
    throw 'Filesystem adapter checksum mismatch'
}
```

The entry point automatically selects the JDK under `.venv/java/<jdk-folder>/` and the adapter under `.venv/spark-jars/`. Java 25 cannot be used with this pipeline. Alternatively, use an installed JDK 17 or 21 via `JAVA_HOME`; the filesystem adapter is still needed for the documented Windows setup. Other operating systems require a compatible JDK and their own Python virtual environment paths; the ZIP above is specific to Windows x64.

Once the runtime is ready, follow [Build Processed Agriculture Data](etl_pipeline.md) to regenerate the Parquet dataset and report from the raw Excel inputs. This replaces the previous generated outputs. Full environment details are in the [data dictionary](data_dictionary.md#running-the-shared-etl).
