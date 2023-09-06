# mod-cloud-builder

This is a [docker-compose](https://docs.docker.com/compose/) setup for hosting an audio plugin building service targeting [MOD devices](https://mod.audio/), including pushing plugin builds into MOD units.

The official instance runs at [builder.mod.audio](http://builder.mod.audio/) and is intentionally kept as HTTP only, due to it needing to send requests into the local network (for connecting to MOD units over websockets).

## Architecture

The cloud builder architecture consists of a combination of docker instances, managed through docker-compose.
A central, public-facing webserver actively listens for requests using [socket.io](https://socket.io/) and dispatches the actual build process to another docker instance.
There is 1 docker "build" instance per MOD unit target (duo, duox and dwarf).

The build request types implemented so far are:

- FAUST (through [max-gen-skeleton](https://github.com/moddevices/faust-skeleton))
- MAX gen~ (through [faust-skeleton](https://github.com/moddevices/max-gen-skeleton))
- Pure Data (through [hvcc](https://github.com/Wasted-Audio/hvcc/))

Behind the scenes the build is done using [mod-plugin-builder](https://github.com/moddevices/mod-plugin-builder), which runs locally in each builder instance.
