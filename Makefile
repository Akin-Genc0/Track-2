.PHONY: data run score test ui deck
PYTHON ?= python3
# Event participants only: never commit the workbook or dev data.
# Official layout: place the organisers dev/ folder here (gitignored).
# Workbook conversion is optional: set TRACK2_XLSX or drop the xlsx in the root, then `make data`.
# Override with: make run score DATA_DIR=/path/to/dev
DATA_DIR ?= dev

data:
	$(PYTHON) tools/xlsx_to_dev.py
run:
	system/run "$(DATA_DIR)" output/dev.jsonl
score:
	$(PYTHON) tools/score.py output/dev.jsonl "$(DATA_DIR)/practice_labels.jsonl" -v
test:
	$(PYTHON) tests/test_policy.py
	$(PYTHON) tests/test_ages.py
	$(PYTHON) tests/test_loader.py
	$(PYTHON) tests/test_runner_boundary.py
	$(PYTHON) tests/test_real_format.py
	$(PYTHON) tests/test_packaging.py
	$(PYTHON) -m py_compile system/*.py
ui:
	$(PYTHON) ui/serve.py
deck:
	$(PYTHON) -c 'import pathlib, webbrowser; webbrowser.open(pathlib.Path("deck/index.html").resolve().as_uri())'
