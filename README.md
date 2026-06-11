# mod-cloud-builder

This is a [docker-compose](https://docs.docker.com/compose/) setup for hosting an audio plugin building service targeting [MOD devices](https://mod.audio/), including pushing plugin builds into MOD units.

The official instance runs at [builder.mod.audio](http://builder.mod.audio/) and is intentionally kept as HTTP only, due to it needing to send requests into the local network (for connecting to MOD units over websockets).

## Architecture

The cloud builder architecture consists of a combination of docker instances, managed through docker-compose.
A central, public-facing webserver actively listens for requests using [socket.io](https://socket.io/) and dispatches the actual build process to another docker instance.
There is 1 docker "build" instance per MOD unit target (duo, duox and dwarf).

The build request types implemented so far are:

- FAUST (through [faust-skeleton](https://github.com/moddevices/faust-skeleton))
- MAX gen~ (through [max-gen-skeleton](https://github.com/moddevices/max-gen-skeleton))
- Pure Data (through [hvcc](https://github.com/Wasted-Audio/hvcc/))

Behind the scenes the build is done using [mod-plugin-builder](https://github.com/moddevices/mod-plugin-builder), which runs locally in each builder instance.

## Host requirements

The cross-compile build ends by running aarch64 binaries on the build host —
specifically, DPF's `lv2_ttl_generator` is cross-compiled to the target and
then executed during the build to emit LV2 turtle metadata. The host kernel
must be able to transparently route those execs through `qemu-user-static`,
or the build will fail at the TTL-generation step with a misleading "Exec
format error" deep in the log, and no `.lv2` bundle will be produced.

On Debian/Ubuntu hosts:

```bash
sudo apt install -y qemu-user-static binfmt-support
# verify aarch64 is registered (file should exist with "enabled" inside)
cat /proc/sys/fs/binfmt_misc/qemu-aarch64
```

The `binfmt-support` systemd unit registers the handler at boot, so this
survives reboots. The `F` (fix-binary) flag means the registration is
inherited by Docker containers without any per-container setup.

Other distributions: use the equivalent multi-arch / qemu-user-static
mechanism. The end state needed is that aarch64 ELFs can be transparently
exec'd on the host, including inside Docker containers.
