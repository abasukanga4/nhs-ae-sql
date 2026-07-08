#!/usr/bin/env bash
#
# download.sh — fetch NHS England A&E Attendances & Emergency Admissions
# (monthly, provider-level) for Apr 2024 -> Mar 2026.
#
# Source page : https://www.england.nhs.uk/statistics/statistical-work-areas/ae-waiting-times-and-activity/
# Retrieved on : 2026-07-08
# Notes        : Some months are the NHS England "revised" republication (see per-URL comments).
#                CSV schema is identical across all files. Files land as data/raw/<YYYY-MM>.csv.
#
# Reproducibility: this script plus the SQL fully reconstruct the analysis DB.
# The raw CSVs and the built .duckdb are gitignored; only this script is tracked.

set -euo pipefail

# Resolve the directory this script lives in, so it works from any CWD.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

UA="Mozilla/5.0"

# fetch <label> <url> : download to <label>.csv, fail loudly on HTTP error.
fetch() {
  local label="$1" url="$2"
  echo "-> ${label}.csv"
  # --fail: non-2xx becomes a curl error (caught by set -e).
  # -L: follow redirects. -sS: quiet but show errors.
  curl --fail -sSL -A "$UA" -o "${label}.csv" "$url"
}

# --- 2024 ---
fetch 2024-04 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/11/Monthly-AE-April-2024-revised.csv"      # Apr 2024 (revised)
fetch 2024-05 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/06/Monthly-AE-May-2024.csv"                # May 2024
fetch 2024-06 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/07/Monthly-AE-June-2024.csv"               # Jun 2024
fetch 2024-07 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/11/Monthly-AE-July-2024-revised.csv"       # Jul 2024 (revised)
fetch 2024-08 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/09/Monthly-AE-August-2024.csv"             # Aug 2024
fetch 2024-09 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2024/10/Monthly-AE-September-2024.csv"          # Sep 2024
fetch 2024-10 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/05/Monthly-AE-October-2024-revised.csv"    # Oct 2024 (revised)
fetch 2024-11 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/05/Monthly-AE-November-2024-revised.csv"   # Nov 2024 (revised)
fetch 2024-12 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/01/Monthly-AE-December-2024.csv"           # Dec 2024

# --- 2025 ---
fetch 2025-01 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/02/Monthly-AE-January-2025.csv"            # Jan 2025
fetch 2025-02 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/05/Monthly-AE-February-2025-revised.csv"   # Feb 2025 (revised)
fetch 2025-03 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/04/Monthly-AE-March-2025.csv"              # Mar 2025
fetch 2025-04 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/April-2025-CSV-revised.csv"             # Apr 2025 (revised)
fetch 2025-05 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/May-2025-CSV-revised.csv"               # May 2025 (revised)
fetch 2025-06 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/June-2025-CSV-revised.csv"              # Jun 2025 (revised)
fetch 2025-07 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/July-2025-CSV-revised.csv"              # Jul 2025 (revised)
fetch 2025-08 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/August-2025-CSV-revised.csv"            # Aug 2025 (revised)
fetch 2025-09 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2025/11/September-2025-CSV-revised.csv"          # Sep 2025 (revised)
fetch 2025-10 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/05/Monthly-AE-October-2025-revised-fly02sk.csv"  # Oct 2025 (revised)
fetch 2025-11 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/05/Monthly-AE-Nov-25-CSV-revised.csv"      # Nov 2025 (revised)
fetch 2025-12 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/05/Monthly-AE-December-2025-revised-g9Hy6.csv"   # Dec 2025 (revised)

# --- 2026 ---
fetch 2026-01 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/05/Monthly-AE-January-2026-revised-3dker.csv"    # Jan 2026 (revised)
fetch 2026-02 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/03/February-2026-CSV-Dl8t54.csv"           # Feb 2026
fetch 2026-03 "https://www.england.nhs.uk/statistics/wp-content/uploads/sites/2/2026/05/Monthly-AE-March-2026-revised-flkg42.csv"     # Mar 2026 (revised)

echo "All downloads complete: $(ls -1 *.csv | wc -l | tr -d ' ') files."
