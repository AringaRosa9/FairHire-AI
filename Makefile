.PHONY: bootstrap dev down api-test web-test contract lint

bootstrap:
	cp .env.example .env
	npm install

dev:
	docker compose up --build

down:
	docker compose down

api-test:
	docker compose run --rm api pytest

web-test:
	npm test

contract:
	docker compose run --rm api python scripts/export_openapi.py
	npm run generate:client

lint:
	npm run lint
	docker compose run --rm api ruff check .

