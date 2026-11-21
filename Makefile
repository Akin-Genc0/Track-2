.PHONY: data run score test ui deck
PYTHON ?= python3

data:
	$(PYTHON) tools/xlsx_to_dev.py
run:
	system/run data/dev output/dev.jsonl
score:
	$(PYTHON) tools/score.py output/dev.jsonl data/dev/practice_labels.jsonl -v
test:
	$(PYTHON) tests/test_policy.py
	$(PYTHON) -m py_compile system/*.py
ui:
	$(PYTHON) ui/serve.py
deck:
	$(PYTHON) -c 'import pathlib, webbrowser; webbrowser.open(pathlib.Path("deck/index.html").resolve().as_uri())'
