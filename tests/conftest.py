import os

# Tests run against the bundled CSV, never the live API (setdefault in load_dotenv keeps this).
os.environ["CONDUIT_API_KEY"] = ""

# The sample CSV keeps test expectations fixed, whatever archive is present.
os.environ["WEATHER_CSV"] = "Data/weatherdata.csv"
