# mod-cloud-builder

This is a [docker-compose](https://docs.docker.com/compose/) setup for hosting an audio plugin building service targeting [MOD devices](https://mod.audio/), including pushing plugin builds into MOD units.

The official instance runs at [builder.mod.audio](http://builder.mod.audio/).
It has to be reachable over **both** plain HTTP and HTTPS, because the page connects to the MOD unit on the local network (a WebSocket to `ws://192.168.51.1/rplsocket`) and browsers disagree on which page origin may do that; see [Browser requirements](#browser-requirements).

## Architecture

The cloud builder architecture consists of a combination of docker instances, managed through docker-compose.
A central, public-facing webserver actively listens for requests using [socket.io](https://socket.io/) and dispatches the actual build process to another docker instance.
There is 1 docker "build" instance per MOD unit target (duo, duox and dwarf).

The build request types implemented so far are:

- FAUST (through [faust-skeleton](https://github.com/moddevices/faust-skeleton))
- MAX gen~ (through [max-gen-skeleton](https://github.com/moddevices/max-gen-skeleton))
- Pure Data (through [hvcc](https://github.com/Wasted-Audio/hvcc/))

Behind the scenes the build is done using [mod-plugin-builder](https://github.com/moddevices/mod-plugin-builder), which runs locally in each builder instance.

## Browser requirements

The builder page talks to the MOD unit directly from the browser, over a WebSocket to
`ws://192.168.51.1/rplsocket` (the unit's USB network address, served by mod-ui since
1.13.3). That is a request from a public web page into the user's local network, and
browsers restrict it in two incompatible ways:

- **Chromium-based browsers** (Chrome, Edge, Brave, Opera...) apply
  [Local Network Access](https://developer.chrome.com/blog/local-network-access) rules:
  from a non-secure `http://` page the connection is refused outright, with no prompt
  (`fetch` since Chrome 142, WebSockets since Chrome 147). From an `https://` page it is
  allowed after the user accepts a one-time "access devices on your local network"
  permission prompt, and the plain `ws://` scheme is then exempt from mixed-content
  blocking because the destination is an IP literal on the local network.
- **Firefox and Safari** have no such permission yet, but do apply the regular
  mixed-content rule: an `https://` page may not open `ws://` to anything but loopback.
  From an `http://` page the connection works.

So the site must be served on both schemes, on the **same hostname**, and each browser has
to end up on the one it can use. Two things make that work together:

- **nginx decides by browser on the https listener.** Firefox and Safari upgrade an http
  address to https on their own as soon as the hostname answers on 443 (Firefox's
  HTTPS-First does it even for an explicitly typed `http://` URL, and re-upgrades a
  script redirect back to http). The one thing that makes them stop is the https URL
  answering with a redirect to the *same* URL on http: they take that as "this site does
  not want https" and stay on http. So on 443 nginx serves Chromium user agents (all of
  them carry a `Chrome/` token: Chrome, Edge, Brave, Opera; Chrome on iOS says `CriOS`,
  is WebKit, and correctly goes to http) and answers every other browser with a 302 to
  http. The http listener never redirects.
- **`webserver/static/mod-connect.js` handles the Chromium direction.** On the http site a
  Chromium browser new enough to be blocked is redirected to the same path on https,
  provided the webserver runs with `MCB_HTTPS_AVAILABLE=1` (see `docker-compose.yml`).
  Without that flag the page only explains the problem and links the https URL when the
  connection fails. It also keeps a fallback for a non-Chromium browser that somehow
  lands on https (redirect to http, hint with the http link), shows "waiting for local
  network permission" while Chromium's prompt is up, and reminds Safari users on macOS 15+
  of the per-app "Local Network" switch in System Settings.

The `socket.io` connection to this webserver follows the page scheme (`ws://` or
`wss://`) automatically, and the reverse proxy must pass WebSocket upgrades on both
listeners. The nginx site used on builder.mod.audio, with certificates from Let's Encrypt
(`certbot --nginx --no-redirect`):

```nginx
map $http_upgrade $connection_upgrade {
    default upgrade;
    ''      close;
}

# 1 for Chromium-based browsers
map $http_user_agent $mod_chromium {
    default    0;
    "~Chrome/" 1;
}

# 1 when an https request comes from a non-Chromium browser
map "$scheme$mod_chromium" $mod_downgrade {
    default  0;
    "https0" 1;
}

server {
    listen 80;
    listen [::]:80;
    listen 443 ssl;
    listen [::]:443 ssl ipv6only=on;
    server_name builder.mod.audio;

    ssl_certificate     /etc/letsencrypt/live/builder.mod.audio/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/builder.mod.audio/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # no http->https redirect here: Firefox and Safari need the http site

    if ($mod_downgrade) {
        return 302 http://$host$request_uri;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection $connection_upgrade;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        client_max_body_size 64m;
    }
}
```

The device side needs no change: mod-ui's `RemotePluginWebSocket.check_origin` already
accepts both `http` and `https` origins on `*.mod.audio` (and `localhost:8010` for a
local instance, which Chromium also treats as a secure context).

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
