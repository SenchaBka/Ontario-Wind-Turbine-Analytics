#!/bin/bash
set -e

echo "Downloading large data files from S3..."

mkdir -p analysis/api

aws s3 sync s3://ontario-wind-turbine-analytics-bucket/analysis/api/ analysis/api/

echo "Download complete"