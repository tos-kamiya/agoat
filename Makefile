.PHONY: test

test:
	cd test; \
	rm -rf htmlcov && \
	python -m coverage erase && \
	python -m coverage run -m unittest discover && \
	python -m coverage html

sample:
	cd test/sample-hello; \
	python ../../src/ags.py index all; \
	cd ../sample-ifs; \
	python ../../src/ags.py index all; \
	cd ../sample-interf; \
	python ../../src/ags.py index all; \
	cd ../sample-nihongo; \
	python ../../src/ags.py index all;

.PHONY: clean

clean:
	rm -rf test/htmlcov
	rm -rf sample/javapOutput
	rm -rf sample/sootOutput
	rm sample/MonthlyCalendar.class
	rm sample/agoat.*.gz
	find . -name "*.pyc" -exec rm -f {} \;

