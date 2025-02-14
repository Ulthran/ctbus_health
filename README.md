# ctbus_health
Fun with body data. This project is half ETL pipeline (gather data from Google docs I record things in, Garmin stats, etc.) and half analytics with ML/AI (the "fun" part).

## Architecture

-  APIs for each of the data sources we want to access
  -  `ctbus-diet-gdoc-api`: Read diet GDoc and push each entry (houly) to SQS
  -  `ctbus-weight-gdoc-api`: Read weight GSheet and push each entry (daily) to SQS
  -  Once the rest of the pipeline is in place, we might want to create simple web forms for inputting/updating this info instead of the google docs to make it easier to trigger ingest on data entry
  -  `ctbus-garmin-api`: Read Garmin data and push to SQS (hasn't been fully thought through yet)
-  Ingest data into database
  -  `ctbus-health-ingest`: Read from SQS, transform diet data with Bedrock and FDC API, push to Aurora Serverless v2 database
-  Analysis dashboard
  -  Not sure if there are good prebuilt solutions for what we're looking for here yet... ZeroETL integration with RedShift is almost certainly too heavy duty for the datasets we're working with. Might end up making our own simple dashboard and expanding it as we find interesting things worth displaying

## Dev notes

Activate env `conda activate sam_py3_13`

Test function locally: `sam local invoke --env-vars env.json`