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