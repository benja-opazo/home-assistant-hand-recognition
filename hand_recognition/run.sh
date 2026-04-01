#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Hand Recognition Add-on..."

# Export HA options as environment variables for the Python app
export MQTT_HOST=$(bashio::config 'mqtt_host')
export MQTT_PORT=$(bashio::config 'mqtt_port')
export MQTT_USERNAME=$(bashio::config 'mqtt_username')
export MQTT_PASSWORD=$(bashio::config 'mqtt_password')
export FRIGATE_URL=$(bashio::config 'frigate_url')
export SCORE_THRESHOLD=$(bashio::config 'score_threshold')
export OUTPUT_TOPIC_TEMPLATE=$(bashio::config 'output_topic_template')
export WEB_UI_PORT=$(bashio::config 'web_ui_port')

exec python3 /app/main.py
