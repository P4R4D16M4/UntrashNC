.PHONY: help test test-nextcloud app

# UntrashNC: the UntrashOS app for Nextcloud ("untrash") and its tunnel helper.
# The NAS side lives in UntrashOS; its contract is docs/architecture/cloud-api.md there.

help:
	@echo "UntrashNC"
	@echo "  make test            PC tests (no Nextcloud, no root)"
	@echo "  make test-nextcloud  UNTRASHOS=<UntrashOS checkout> APACHEROOT=<dir> [NC_IMAGE=nextcloud:25-apache]"
	@echo "                       the app against a real Nextcloud and the NAS side (Docker, sudo -n)"
	@echo "  make app             release archives -> build/"

test:
	python3 tests/test_cloud_wg_checks.py
	python3 l10n/build.py --check
	python3 tests/test_package.py

NC_IMAGE ?= nextcloud:25-apache
UNTRASHOS ?= ../UntrashOS
test-nextcloud:
	@test -n "$(APACHEROOT)" || { echo "APACHEROOT=<unpacked apache2-bin libapr1 libaprutil1 debs> needed"; exit 1; }
	UNTRASHOS=$(UNTRASHOS) python3 tests/test_nextcloud_docker.py $(APACHEROOT) $(NC_IMAGE)

app:
	python3 package.py build
