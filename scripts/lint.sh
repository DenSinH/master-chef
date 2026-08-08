#!/usr/bin/env bash

uv run ruff check --fix .
uv run black .

uv run ruff check .
uv run black --check .
