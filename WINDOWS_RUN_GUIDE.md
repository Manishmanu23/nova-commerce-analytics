# NovaCommerce project: Windows setup and run guide

This guide walks through opening and running the NovaCommerce project on Windows, from checking Docker and Python to opening the dashboard. It uses **PowerShell** commands and the setup used for this project.

> **Important:** Run project commands from the inner `nova-commerce-analytics` folder, not the outer `nova-commerce-analytics-v2` folder. In the examples below, that folder is:
>
> `C:\Users\Hp\Downloads\nova-commerce-analytics-v2\nova-commerce-analytics`
>
> If your project is in a different location, change that path in the commands.

## What this project runs

- **Docker Desktop** runs PostgreSQL, the database used by the project.
- **Python** generates sample data, loads it, runs analytics, and builds the dashboard.
- **dbt** transforms and tests the data in PostgreSQL.
- **VS Code** is an editor and terminal for the commands; Docker does not need a special VS Code integration to work.
- The project also has an HTML dashboard that opens in a web browser.

## 1. Install and check the prerequisites

### Docker Desktop and WSL 2

Install Docker Desktop for Windows and start it. Wait until Docker Desktop says it is running. In Docker Desktop, check **Settings → General → Use the WSL 2 based engine**.

To let Docker commands work in PowerShell, Docker Desktop must be running. A separate Ubuntu distribution is not required for this project. WSL is Docker Desktop's Linux engine backend.

Check Docker from PowerShell:

```powershell
wsl --status
wsl --list --verbose
docker --version
docker compose version
docker version
docker ps
```

`docker version` should show both **Client** and **Server**. `docker ps` may show no containers before you start the project; that is normal.

### Python

Install Python 3.10 or newer (Python 3.11 is recommended). In the Windows installer, enable **Add python.exe to PATH**. Close and reopen PowerShell after installation.

Check it:

```powershell
python --version
```

Use `python` in the commands below. The Windows `py` launcher and `python3` command may not be installed even when `python` works.

### VS Code

Install VS Code, then open the project folder. From PowerShell:

```powershell
Set-Location "C:\Users\Hp\Downloads\nova-commerce-analytics-v2\nova-commerce-analytics"
code .
```

Or in VS Code, choose **File → Open Folder...** and select the inner `nova-commerce-analytics` folder.

Useful optional extensions can be installed from the VS Code Extensions view:

- **Python** (`ms-python.python`)
- **Docker** (`ms-azuretools.vscode-docker`)

The Docker extension is optional. The required check is that `docker version` works in the VS Code PowerShell terminal. In VS Code, open **Terminal → New Terminal** and check:

```powershell
docker version
```

## 2. Create and prepare the Python environment (first setup only)

In the VS Code PowerShell terminal, go to the project root:

```powershell
Set-Location "C:\Users\Hp\Downloads\nova-commerce-analytics-v2\nova-commerce-analytics"
```

Create a dedicated environment for this project. This guide uses `.venv-clean` because the earlier `.venv` environment had broken compiled packages:

```powershell
python -m venv .venv-clean
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv-clean\Scripts\Activate.ps1
```

The prompt should begin with `(.venv-clean)`. The execution policy change applies only to the current PowerShell process; it does not change the computer's permanent policy.

Install project dependencies:

```powershell
python -m pip install --upgrade pip
python -m pip install --no-cache-dir -e ".[dev,copilot]"
python -m pip install matplotlib
```

`matplotlib` is installed separately because the project's chart-generation command uses it, but it is not currently listed in the project's dependency declarations.

Create the local settings file if it does not already exist:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

The default `.env` uses the local database account `nova` and runs the Copilot in offline mode. No AI API key is required. Do not share the `.env` file or add secrets to Git.

### Verify the Python environment

```powershell
python -c "import sys; print(sys.executable)"
python -c "import numpy, pandas, scipy, statsmodels, psycopg, sqlalchemy, yaml; print('Core package imports OK')"
python -m pip check
dbt --version
```

The Python path should end with `.venv-clean\Scripts\python.exe`; the imports should print `Core package imports OK`; and `pip check` should say `No broken requirements found`.

The dbt version may display an update/deprecation notice. The project pins dbt to a compatible version range, so do not upgrade dbt just to dismiss that notice.

## 3. Configure the database port

This computer has a separate Windows PostgreSQL service using port `5432`. The project's Docker PostgreSQL is therefore exposed on Windows port **5433**, while PostgreSQL still listens on port `5432` inside its container.

In `docker\docker-compose.yml`, the PostgreSQL service should contain:

```yaml
ports: ["5433:5432"]
```

In `.env`, use:

```text
PGHOST=localhost
PGPORT=5433
PGUSER=nova
PGPASSWORD=nova
PGDATABASE=nova
```

If you edit either file, save it before starting Docker. Do not uninstall the Windows PostgreSQL service; the project can run alongside it on port 5433.

## 4. Start and verify the project database

Make sure the terminal is at the project root, `.venv-clean` is active, and start the database:

```powershell
docker compose -f docker\docker-compose.yml up -d --wait
docker compose -f docker\docker-compose.yml ps
docker exec nova_pg pg_isready -U nova -d nova
```

The `nova_pg` container should be healthy, and `pg_isready` should report that it is accepting connections.

Set the connection settings in the current PowerShell window. These variables tell the Python tools to connect to Docker on port 5433:

```powershell
$env:PGHOST = "localhost"
$env:PGPORT = "5433"
$env:PGUSER = "nova"
$env:PGPASSWORD = "nova"
$env:PGDATABASE = "nova"
$env:PYTHONPATH = Join-Path (Get-Location) "python"
$env:PYTHONUTF8 = "1"
```

The UTF-8 setting is needed on this Windows setup because some generated reports contain the rupee symbol (`₹`).

Test the database login:

```powershell
python -c "import psycopg; c=psycopg.connect(host='localhost', port=5433, user='nova', password='nova', dbname='nova'); print('Docker database login OK'); c.close()"
```

Continue only if this prints `Docker database login OK`.

## 5. Generate and load the data

Run these commands from the project root:

```powershell
python -m nova.generator.run --customers 30000 --out data/landing
python ingestion\load_raw.py --landing data/landing
```

The generator creates synthetic source data under `data\landing`. The loader copies those CSVs into the PostgreSQL `raw` schema. The full sample includes over a million web sessions and takes a few minutes to generate and load.

The loader should finish with a summary similar to:

```text
summary: {'loaded': 17}
```

If you run the loader again, already loaded files may be skipped; this is expected because loading is idempotent.

## 6. Build and test the dbt models

From the project root, enter the dbt project folder and install its dbt package:

```powershell
Push-Location dbt\nova_dbt
dbt deps --profiles-dir .
```

The `.` after `--profiles-dir` means “use this current folder” for dbt's profiles. After `dbt deps` succeeds, build the models and run their tests:

```powershell
dbt build --profiles-dir .
```

The full build takes a few minutes. This project intentionally includes data-quality issues, so dbt can report warnings. A successful run should finish with **`ERROR=0`**. For the generated full dataset, an example summary is:

```text
Done. PASS=173 WARN=8 ERROR=0 SKIP=0 NO-OP=0 TOTAL=181
```

After the build succeeds, return to the project root and collect its results:

```powershell
Pop-Location
python -m nova.dq.collect_dbt_results
```

If a dbt command fails, return to the root manually with `Pop-Location` before continuing, if PowerShell is still inside `dbt\nova_dbt`.

## 7. Run data quality, analytics, and reports

Run each command from the project root, in order:

```powershell
python -m nova.dq.scorecard
python -m nova.analytics.run_all
python -m nova.anomaly.run
python -m nova.simulator.engine --example
python -m nova.copilot.evals
python -m nova.common.data_dictionary
python -m nova.common.charts
python -m nova.dashboard.export
```

These commands:

1. Calculate a data-quality scorecard.
2. Generate statistical, experiment, causal, customer segmentation, and forecast reports.
3. Detect unusual business patterns and write an anomaly report.
4. Run decision scenarios and write a simulator report.
5. Evaluate the offline Analytics Copilot and its numeric-grounding checks.
6. Generate the data dictionary.
7. Generate charts.
8. Export the HTML dashboard and Power BI CSV data pack.

The chart command requires the separately installed `matplotlib` package.

## 8. Open the dashboard and validate the project

Open the dashboard in your default browser:

```powershell
Start-Process .\powerbi\dashboard\NovaCommerce_Dashboard.html
```

Run unit tests and code style checks:

```powershell
python -m pytest -q
ruff check python ingestion tests
```

Successful checks should report passing tests and `All checks passed!` from Ruff.

## 9. Commands after restarting the laptop

The database data is stored in a Docker volume, so it remains when the laptop is restarted or the container is stopped normally. After a restart:

1. Start Docker Desktop and wait for it to be running.
2. Open VS Code and open the inner `nova-commerce-analytics` folder.
3. Open a new PowerShell terminal in VS Code.
4. Run this startup block:

```powershell
Set-Location "C:\Users\Hp\Downloads\nova-commerce-analytics-v2\nova-commerce-analytics"
.\.venv-clean\Scripts\Activate.ps1
$env:PGHOST = "localhost"
$env:PGPORT = "5433"
$env:PGUSER = "nova"
$env:PGPASSWORD = "nova"
$env:PGDATABASE = "nova"
$env:PYTHONPATH = Join-Path (Get-Location) "python"
$env:PYTHONUTF8 = "1"
docker compose -f docker\docker-compose.yml up -d --wait
docker compose -f docker\docker-compose.yml ps
```

This reuses the existing environment and database. Do **not** recreate the virtual environment or regenerate and reload all the data just to reopen the dashboard.

To reopen the existing dashboard:

```powershell
Start-Process .\powerbi\dashboard\NovaCommerce_Dashboard.html
```

To rerun analytics using the existing database:

```powershell
python -m nova.dq.scorecard
python -m nova.analytics.run_all
python -m nova.anomaly.run
python -m nova.simulator.engine --example
python -m nova.copilot.evals
python -m nova.common.data_dictionary
python -m nova.common.charts
python -m nova.dashboard.export
```

Only repeat the data generation and ingestion steps if you intentionally want to create/load a new dataset.

## 10. Stop or restart the database safely

Stop the container but keep its database volume:

```powershell
docker compose -f docker\docker-compose.yml down
```

Start it again later:

```powershell
docker compose -f docker\docker-compose.yml up -d --wait
```

> **Data warning:** Do not add `-v` to the `down` command unless you intentionally want to delete the Docker database volume and all database data stored in it.

## Quick meaning of the main commands

| Command | What it does |
|---|---|
| `Set-Location "...\nova-commerce-analytics"` | Changes the terminal to the project root folder. |
| `.\.venv-clean\Scripts\Activate.ps1` | Activates this project's Python environment in the current PowerShell window. |
| `$env:NAME = "value"` | Sets a setting for commands run from this PowerShell window. Run these again in each new terminal. |
| `python -m venv .venv-clean` | Creates an isolated Python environment for this project. First setup only. |
| `python -m pip install -e ".[dev,copilot]"` | Installs project packages, development/test tools, and Copilot dependencies. |
| `docker compose ... up -d --wait` | Starts the database container in the background and waits for it to become healthy. |
| `docker compose ... ps` | Shows the status of the project's containers. |
| `docker exec nova_pg pg_isready ...` | Checks whether PostgreSQL inside the container accepts connections. |
| `python -m nova.generator.run ...` | Generates the synthetic source CSV files. |
| `python ingestion\load_raw.py ...` | Loads generated CSVs into the database's raw schema. |
| `Push-Location` / `Pop-Location` | Temporarily changes folders and then returns to the previous folder. |
| `dbt deps --profiles-dir .` | Downloads dbt packages required by this dbt project. |
| `dbt build --profiles-dir .` | Builds dbt models and runs dbt tests. |
| `python -m pytest -q` | Runs the Python test suite with concise output. |
| `ruff check python ingestion tests` | Checks Python files for style and common errors. |
| `docker compose ... down` | Stops/removes the container but preserves the database volume. |
| `Start-Process ...html` | Opens the generated dashboard file in the default browser. |

## Troubleshooting

### `docker version` shows only Client or cannot connect

Start Docker Desktop, wait until it is running, then retry:

```powershell
docker version
```

### Password authentication fails

Confirm that the project uses port 5433 and set the variables again in the current terminal:

```powershell
$env:PGPORT = "5433"
$env:PGUSER = "nova"
$env:PGPASSWORD = "nova"
$env:PGDATABASE = "nova"
```

Test the Docker database directly:

```powershell
python -c "import psycopg; c=psycopg.connect(host='localhost', port=5433, user='nova', password='nova', dbname='nova'); print('Docker database login OK'); c.close()"
```

Do not uninstall Windows PostgreSQL just to run this project; Docker uses host port 5433 to avoid its port 5432.

### `UnicodeEncodeError` when writing reports

Set UTF-8 mode and retry the failed report command:

```powershell
$env:PYTHONUTF8 = "1"
```

### `ModuleNotFoundError: matplotlib`

Install it in the active `.venv-clean` environment:

```powershell
python -m pip install matplotlib
```

### PowerShell shows `>>`

`>>` is PowerShell's continuation prompt. It usually means the previous command is incomplete. Press `Ctrl+C` once, then enter the full command again. Do not type `>>` as part of a command.

### The dashboard looks blank

The HTML dashboard may need internet access to load its chart library. Try opening it in an up-to-date version of Edge or Chrome.
