# ctbus_health
Fun with body data. This project is half ETL pipeline (gather data from Google docs I record things in, Garmin stats, etc.) and half analytics with ML/AI (the "fun" part).

## ETL Pipeline

-  Create microservices to provide APIs for each of the data sources we want to access
-  Transform that data to a structured format (probably JSON) and augment it with other info (e.g. including detailed nutrition data for each food item recorded)
-  Load all this into dbs (probably Mongo) for analysis

This pipeline should be running somewhat routinely (once a day? once a week? idk) to keep everything up to date

## Analysis

Not quite sure yet what this will entail! Will likely depend on how much of my complete picture of the data pipeline comes together.