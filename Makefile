PYTHON = .venv/bin/python

install:
	python -m virtualenv .venv
	curl -sS https://bootstrap.pypa.io/pip/3.8/get-pip.py | .venv/bin/python
	.venv/bin/pip install -r requirements.txt

prepare:
	$(PYTHON) Task2/01_download.py
	$(PYTHON) Task2/02_replace.py

chunks:
	$(PYTHON) Task3/01_chunking.py
	$(PYTHON) Task3/02_embeddings.py

index:
	$(PYTHON) Task3/03_index.py

search:
	$(PYTHON) Task3/04_search.py "$(QUERY)"

bot:
	$(PYTHON) Task4/bot.py

cli:
	$(PYTHON) Task4/cli.py $(QUERY)

test:
	$(PYTHON) Task5/test_rag.py

update-index:
	$(PYTHON) Task6/update_index.py

evaluate:
	$(PYTHON) Task7/evaluate.py
