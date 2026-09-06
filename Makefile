.PHONY: install lint typecheck test check up down

install:
	py -3.12 -m pip install -e ".[dev]"

lint:
	py -3.12 -m ruff check .

typecheck:
	py -3.12 -m mypy

test:
	py -3.12 -m pytest

check: lint typecheck test

up:
	docker compose up --build -d

down:
	docker compose down

