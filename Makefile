.PHONY: data run score test ui deck
PYTHON ?= python3
# Event participants only: never commit the workbook or dev data.
# Drop the gitignored workbook in the root or set TRACK2_XLSX=/path/to/workbook.xlsx.
# For ready inputs: make run score DATA_DIR=/path/to/dev
DATA_DIR ?= data/dev

data:
	$(PYTHON) tools/xlsx_to_dev.py
run:
	system/run "$(DATA_DIR)" output/dev.jsonl
score:
	$(PYTHON) tools/score.py output/dev.jsonl "$(DATA_DIR)/practice_labels.jsonl" -v
test:
	$(PYTHON) tests/test_policy.py
	$(PYTHON) -m py_compile system/*.py
ui:
	$(PYTHON) ui/serve.py
deck:
	$(PYTHON) -c 'import pathlib, webbrowser; webbrowser.open(pathlib.Path("deck/index.html").resolve().as_uri())'
