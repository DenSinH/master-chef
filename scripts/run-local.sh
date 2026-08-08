#!/usr/bin/env bash

docker compose -f docker-compose.local.yml build web
docker compose -f docker-compose.local.yml up