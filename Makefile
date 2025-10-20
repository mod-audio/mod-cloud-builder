# MOD Cloud Builder
# SPDX-FileCopyrightText: 2023-2025 MOD Audio UG
# SPDX-License-Identifier: AGPL-3.0-or-later

all: webserver

# TODO make images target use a single job

modduo: .stamp-modduo-new-builder

modduox: .stamp-modduox-new-builder

modduox: .stamp-moddwarf-new-builder

webserver: .stamp-webserver .stamp-darkglass-anagram-builder .stamp-modduo-new-builder .stamp-modduox-new-builder .stamp-moddwarf-new-builder

.stamp-%-builder: .stamp-%-image builder/Dockerfile builder/builder.py
	$(shell which docker) build builder --build-arg platform=$* --tag mcb-builder-$* && touch $@

.stamp-%-image: mod-plugin-builder/docker/Dockerfile
	$(shell which docker) build mod-plugin-builder/docker --build-arg platform=$* --build-arg target=minimal --tag mpb-minimal-$* && touch $@

.stamp-webserver: webserver/Dockerfile webserver/server.py webserver/templates/*.html
	$(shell which docker) build webserver --tag mcb-webserver && touch $@

run: webserver
	$(shell which docker-compose) down -t 1
	$(shell which docker-compose) up -d
	$(shell which docker) logs mod-cloud-builder_webserver_1 -t -f

clean:
	rm -f .stamp*
	$(shell which docker) rmi -f mpb-minimal-darkglass-anagram
	$(shell which docker) rmi -f mpb-minimal-modduo-new
	$(shell which docker) rmi -f mpb-minimal-modduox-new
	$(shell which docker) rmi -f mpb-minimal-moddwarf-new
	$(shell which docker) rmi -f mcb-builder-darkglass-anagram
	$(shell which docker) rmi -f mcb-builder-modduo
	$(shell which docker) rmi -f mcb-builder-modduox
	$(shell which docker) rmi -f mcb-builder-moddwarf
	$(shell which docker) rmi -f mcb-webserver
