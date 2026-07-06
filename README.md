# Routes API Traffic Sampler

This project collects live driving travel times for a Brisbane to Gold Coast route using the Google Maps Routes API.

Each run records two observations:

- `Southbound`: Toowong Village -> Greenmount Beach
- `Northbound`: Greenmount Beach -> Toowong Village

The intended use is to build a historical dataset that can later be analyzed to determine the best times to travel to the beach and return with minimal traffic.

## Files

- `traffic_sampler.py`: main script that calls the Routes API and stores rows in Postgres or CSV
- `.env.example`: example environment configuration
- `traffic_log.csv`: collected travel-time dataset when using local CSV fallback
- `traffic_errors.log`: runtime error log written on failed requests
- `requirements.txt`: Python dependencies

## Requirements

- Python 3.10+ recommended
- A Google Maps Routes API key with billing enabled

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

## Configuration

Copy `.env.example` to `.env` and set your API key:

```env
GOOGLE_MAPS_API_KEY=your-google-maps-routes-api-key
TRAFFIC_TIMEZONE=Australia/Brisbane
```

Optional database configuration:

```env
DATABASE_URL=postgresql://user:password@host:5432/database
TRAFFIC_TABLE_NAME=traffic_samples
```

## How It Works

The script:

1. Loads the API key from `.env`
2. Exits immediately unless the current local hour is between `05:00` and `20:59`
3. Calls the Google Routes `computeRoutes` endpoint once per direction
4. Uses one shared sample timestamp and batch ID for both directions in the same run
5. Inserts rows into Postgres when `DATABASE_URL` is set
6. Falls back to CSV when `DATABASE_URL` is not set
7. Stores route metadata for later analysis
8. Writes any runtime failures to `traffic_errors.log`

## Output Schema

Each row in `traffic_log.csv` contains:

- `sample_timestamp`
- `sample_batch_id`
- `direction`
- `origin_label`
- `destination_label`
- `day_of_week`
- `date`
- `hour`
- `minute`
- `timezone`
- `duration_traffic_min`
- `duration_static_min`
- `delay_min`
- `delay_ratio`
- `distance_km`
- `route_description`

Notes:

- `duration_traffic_min` is the travel time with current traffic
- `duration_static_min` is the estimated travel time without traffic
- `delay_min` is the traffic penalty in minutes
- `delay_ratio` is `delay / static_duration`
- `sample_batch_id` lets you pair the northbound and southbound rows from the same scheduler run
- `route_description` helps explain changes in selected route shape over time

## Storage Modes

The script supports two persistence modes:

- `Postgres`: primary mode for cloud deployment when `DATABASE_URL` is set
- `CSV`: fallback mode for local runs when `DATABASE_URL` is not set

When using Postgres, the script automatically creates a table named `traffic_samples` unless `TRAFFIC_TABLE_NAME` overrides it.

## Running Manually

Run the script with:

```powershell
py .\traffic_sampler.py
```

If Python is installed as `python` instead of `py`, use:

```powershell
python .\traffic_sampler.py
```

If you want to test Postgres locally, set `DATABASE_URL` in `.env` before running.

## Scheduling On Windows

This script is designed to be run by Windows Task Scheduler every 15 minutes.

Suggested schedule:

- Start: `05:00`
- Repeat every: `15 minutes`
- End: `21:00`

Even if Task Scheduler runs it outside those hours, the script self-limits and exits without writing data.

The repository includes `run_traffic_sampler.bat` so Task Scheduler can invoke a stable launcher from the repo root.

## Running On GitHub Actions

This repository includes a scheduled workflow at `.github/workflows/traffic-sampler.yml`.

To enable cloud-based collection:

1. Push the repository to GitHub
2. Add a repository secret named `GOOGLE_MAPS_API_KEY`
3. Ensure GitHub Actions is enabled for the repository
4. Confirm the default branch contains the workflow file

The workflow:

- runs every 15 minutes from `05:00` to `20:59`
- uses `Australia/Brisbane` as the scheduling timezone
- runs `traffic_sampler.py`
- commits updated `traffic_log.csv` data back to the repository

Notes:

- scheduled workflows run from the default branch
- public repositories may have scheduled workflows disabled after 60 days of inactivity
- storing CSV data in Git commits is simple, but the repository history will grow over time

## Running On Render

For Render Cron Jobs, use Postgres storage instead of CSV.

Recommended environment variables:

- `GOOGLE_MAPS_API_KEY`
- `DATABASE_URL`
- `TRAFFIC_TIMEZONE=Australia/Brisbane`
- `TRAFFIC_TABLE_NAME=traffic_samples` (optional)

Recommended Render commands:

- Build command: `pip install -r requirements.txt`
- Run command: `python traffic_sampler.py`

Recommended schedule:

- Brisbane every 15 minutes from `05:00` to `20:45`
- UTC cron expression: `*/15 19-23,0-10 * * *`

## Data Compatibility

If an older `traffic_log.csv` exists with a previous schema, the script automatically migrates it and fills missing metadata where possible.

## Next Analysis Ideas

Once enough data has been collected, useful analysis could include:

- Median travel time by hour of day and direction
- Best departure windows by weekday
- Seasonal comparison across months
- Probability of exceeding a target trip duration
