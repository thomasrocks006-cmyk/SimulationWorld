install:
	pip install -r requirements.txt

run:
	python cli.py run --start 2025-09-20 --until 2030-09-20

fast:
	python cli.py run --start 2025-09-20 --step week --fast

test:
	pytest -q
