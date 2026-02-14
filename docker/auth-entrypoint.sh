#!/bin/bash
set -e # Exit immediately if a command exits with a non-zero status.

echo "Starting Auth Server Setup..."

# --- DocumentDB CA Bundle Download ---
if [[ "${DOCUMENTDB_HOST}" == *"docdb-elastic.amazonaws.com"* ]]; then
    echo "Detected DocumentDB Elastic cluster"
    echo "Downloading DocumentDB Elastic CA bundle..."
    CA_BUNDLE_URL="https://www.amazontrust.com/repository/SFSRootCAG2.pem"
    CA_BUNDLE_PATH="/app/global-bundle.pem"
    if [ ! -f "$CA_BUNDLE_PATH" ]; then
        curl -fsSL "$CA_BUNDLE_URL" -o "$CA_BUNDLE_PATH"
        echo "DocumentDB Elastic CA bundle (SFSRootCAG2.pem) downloaded successfully to $CA_BUNDLE_PATH"
    fi
elif [[ "${DOCUMENTDB_HOST}" == *"docdb.amazonaws.com"* ]]; then
    echo "Detected regular DocumentDB cluster"
    echo "Downloading regular DocumentDB CA bundle..."
    CA_BUNDLE_URL="https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem"
    CA_BUNDLE_PATH="/app/global-bundle.pem"
    if [ ! -f "$CA_BUNDLE_PATH" ]; then
        curl -fsSL "$CA_BUNDLE_URL" -o "$CA_BUNDLE_PATH"
        echo "DocumentDB CA bundle (global-bundle.pem) downloaded successfully to $CA_BUNDLE_PATH"
    fi
else
    echo "No DocumentDB host detected or DOCUMENTDB_HOST is empty - skipping CA bundle download"
fi

echo "Starting Auth Server..."
cd /app
source .venv/bin/activate
exec uvicorn server:app --host 0.0.0.0 --port 8888 --proxy-headers --forwarded-allow-ips='*'
