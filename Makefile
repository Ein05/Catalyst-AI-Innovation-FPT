.PHONY: api test preflight demo

api:
	python -m apps.api.main

test:
	python -m pytest

preflight:
	python scripts/preflight.py

demo:
	python scripts/preflight.py && python scripts/run_demo.py

