PY := python

.PHONY: download data notebook test all

all: download data notebook

download:   ## every day 2015–2024 from the CNEMC archive; cached, resumable (~2 h first run)
	$(PY) scripts/download_cnemc.py

data:       ## daily, monthly and annual tables by the GB 3095-2012 validity rules
	$(PY) scripts/build_dataset.py

notebook:   ## run the analysis and regenerate every figure
	cd notebooks && $(PY) -m jupyter nbconvert --to notebook --execute --inplace analysis.ipynb

test:
	$(PY) -m pytest -q
