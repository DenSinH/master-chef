#!/usr/bin/env bash

uvx ty check --fix
uv run ruff check --fix .
uv run black .

uvx ty check
uv run ruff check .
uv run black --check .