# Copyright The Linux Foundation and each contributor to LFX.
# SPDX-License-Identifier: MIT

.PHONY: all clean test

all: requirements.txt

clean:
	rm -Rf __pycache__ .ruff_cache megalinter-reports

lint:
	docker run --rm --platform linux/amd64 -v '$(CURDIR):/tmp/lint:rw' oxsecurity/megalinter-python:v7

test:
	@echo "No tests to run ... would you like to 'make lint'?"

requirements.txt: Pipfile.lock .license-header
	cat .license-header > requirements.txt
	# Because we are avoiding pinning dep versions, we also prune them from the
	# generated requirements.txt file.
	pipenv requirements --exclude-markers | sed 's/=.*$$//' >> requirements.txt

Pipfile.lock: Pipfile
	pipenv lock
