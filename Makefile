.PHONY: test lint build serve

test:
	pytest -q

lint:
	ruff check src tests

build:
	python -m build

serve:
	uvicorn evidenceos.api:app --reload
