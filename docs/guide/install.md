# Install and run Unlist

Unlist runs as one container with one database file. This page shows how to start it, where its data lives, how to reach it from other devices, how to upgrade it, and every setting it has.

## What you need

- A computer that can stay on while you use Unlist: a laptop, a home server, a Raspberry Pi-class machine or a small VPS.
- **Docker with the Compose plugin.** The commands below use `docker compose` (with a space).
- About **1 GB of free disk space** for the image and a first household. Your data grows with the mail you import and the replies you store. A Google Takeout file can be many gigabytes while you import it (see [first run](first-run.md#import-mail)).
- A web browser.

You do not need a database server, a mail server, an account anywhere, or an internet connection after the image is built. The instance contacts nobody unless you turn something on.

## Start it

```sh
git clone https://github.com/Hjiaky/Unlist.git
cd Unlist
docker compose up -d --build
```

Open <http://localhost:8000>. The first page asks you to create the Operator account. Continue with [first run](first-run.md).

## The compose file, line by line

`compose.yaml` in the repository root is the whole setup:

```yaml
services:
  unlist:                      # the one service. Commands below say "unlist" for this name.
    build: .                   # build the image from the Dockerfile in this folder
    image: unlist:dev          # the name the built image gets
    restart: unless-stopped    # start again after a reboot or a crash
    ports:
      - "8000:8000"            # computer-port : container-port
    volumes:
      - ./data:/data           # everything Unlist knows
      - ./key:/key             # the encryption key, kept apart on purpose
    environment:
      TZ: Europe/Berlin        # your time zone, used for dates and deadlines
      # UNLIST_PUBLIC_ORIGIN: https://unlist.example.org   # only behind your own HTTPS proxy
```

Inside the container, one start script runs two programs: the web server and a scheduler that prepares work (overdue marks, re-checks, reminder drafts). If either one stops, the container stops and `restart: unless-stopped` brings both back.

Change `TZ` to your own time zone (for example `Europe/London`). Dates in drafts and the clock for deadlines follow it.

## The two folders: `./data` and `./key`

Both are created on the first start, next to `compose.yaml`.

| Folder | What is in it | Back it up? |
|---|---|---|
| `./data` | The SQLite database `unlist.sqlite3`, the stored attachments (replies and evidence), Django's signing secret, and the `backups` folder | Yes, see [backup](backup.md). It holds personal data, so keep it private. |
| `./key` | `unlist.key`, the key that encrypts stored mailbox passwords and the language-model key | Yes, but **separately** from `./data` |

### The key

The key is kept apart from the data on purpose. Unlist encrypts only secrets with it: app passwords for a live mailbox connection and an API key for the optional language model. Everything else in the database is readable. If the key sat inside `./data`, every backup of `./data` would carry the key to its own secrets. Kept apart, a copied database or a stolen backup does not reveal your mailbox passwords.

On the **first start** Unlist creates the key if none exists and writes a note about it to the log:

```sh
docker compose logs unlist
```

**Keep a copy of the key** (for example in a password manager or on a USB stick in a drawer). If you lose it, nothing else is lost: you only have to enter mailbox and language-model passwords again. See [what happens without the key](backup.md#without-the-key).

The key file is owned by the container's user (UID 1000) and readable only by it. Your own user may need `sudo` to copy it.

You can also supply the key yourself with the `UNLIST_KEY` setting instead of a file. See [Settings](#settings).

## Reaching Unlist from other devices

By default Unlist listens on port 8000 on all network interfaces of the machine. From another device on the same network, open:

```
http://<machine name or IP address>:8000
```

Things to know:

- This is plain **HTTP**. Your password and everything you read travels unencrypted across the local network. That is acceptable on a home network you trust; it is not acceptable over the internet.
- If you cannot connect, check the firewall of the machine for port 8000.
- Logins are rate-limited: after five failed attempts from one address, further attempts are blocked for 15 minutes.
- Do not forward port 8000 on your router. To reach Unlist from outside your home, use a VPN to your network, or put it behind your own HTTPS reverse proxy as described next.

## Behind your own HTTPS reverse proxy

If you want to reach Unlist over the internet or want encryption on your own network, run a reverse proxy that handles HTTPS and forward to Unlist. Unlist does not obtain certificates itself.

1. Set `UNLIST_PUBLIC_ORIGIN` to the address people will type, with `https://` and no trailing path:

   ```yaml
   environment:
     TZ: Europe/Berlin
     UNLIST_PUBLIC_ORIGIN: https://unlist.example.org
   ```

2. If the proxy runs on the same machine, publish the port on the loopback address only, so nobody can bypass the proxy:

   ```yaml
   ports:
     - "127.0.0.1:8000:8000"
   ```

3. Restart: `docker compose up -d`.

With `UNLIST_PUBLIC_ORIGIN` set, Unlist:

- accepts requests only for that host name (and `localhost` / `127.0.0.1`),
- trusts the `X-Forwarded-Proto` header from the proxy,
- marks cookies as secure (browsers send them only over HTTPS), and
- sends an HTTP Strict Transport Security header for one year.

So: **the proxy must pass the original `Host` header and set `X-Forwarded-Proto: https`**, and after you set the option, signing in at `http://<ip>:8000` no longer works. Use the HTTPS address. (On the same machine, `http://localhost:8000` is still accepted as a host, but secure cookies mean the login may not stick over plain HTTP in some browsers.)

Two more points for the proxy: a mail export upload can be many gigabytes, so do not limit the request body size, and Unlist allows a slow request up to 10 minutes.

### Caddy

Caddy gets certificates by itself and sets the forwarded headers for you:

```caddyfile
unlist.example.org {
    reverse_proxy localhost:8000
}
```

### nginx

```nginx
server {
    listen 443 ssl;
    server_name unlist.example.org;

    # ssl_certificate and ssl_certificate_key: your own, for example from certbot

    client_max_body_size 0;          # mail exports can be very large
    proxy_read_timeout 600s;
    proxy_request_buffering off;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $remote_addr;
    }
}
```

These snippets are examples. They were not tested together with Unlist in this guide's writing; check them against your proxy's own documentation.

## Upgrading

1. **Back up first.** See [backup](backup.md). Take the backup and keep it; a downgrade means restoring it.
2. Get the new version and rebuild:

   ```sh
   git pull
   docker compose up -d --build
   ```

3. That is all. When the container starts, it brings the database up to date automatically (migrations) and reloads the bundled Organization Lists and breach list that came with the release. Your own settings, overrides and Cases stay as they are.
4. Look at `docker compose logs unlist` once if the page does not come up.

Releases are tested to upgrade without loss, but a backup is cheap and a missing one is not.

## Changing the Operator password

Run this on the machine that hosts Unlist, in the folder with `compose.yaml`. Replace `<name>` with the user name you chose when you created the Operator:

```sh
docker compose exec --user unlist unlist python manage.py changepassword <name>
```

The first `unlist` after `--user` is the user inside the container; the second is the compose service name. The command asks for the new password twice. The password must be at least 12 characters, not too common and not all digits.

If you have forgotten the user name too, you can look it up:

```sh
docker compose exec --user unlist unlist python manage.py shell -c "from django.contrib.auth.models import User; print(list(User.objects.values_list('username', flat=True)))"
```

There is no "forgot password" email, because Unlist does not send mail on its own behalf.

## Settings

Unlist works with none of these. Only `TZ` is set in the compose file by default. Set the others in the `environment:` part of `compose.yaml` and run `docker compose up -d` again.

| Setting | Default | What it does |
|---|---|---|
| `UNLIST_PUBLIC_ORIGIN` | empty (not behind a proxy) | The HTTPS address your own reverse proxy serves Unlist at, for example `https://unlist.example.org`. See [above](#behind-your-own-https-reverse-proxy). |
| `UNLIST_SOURCE_URL` | the release tag on the project's GitHub page | Where the source of this running version can be had. Shown on the About page. Change it only if you run a modified version and let others use it, as the AGPL asks. Must start with `http://` or `https://`. |
| `UNLIST_KEY` | not set | The encryption key itself, as text. If set, the key file is not used or created. Use it if you would rather keep the key in a secrets manager than in a file. Treat it like a password. |
| `UNLIST_KEY_FILE` | `/key/unlist.key` in the container | Where the key file is. Normally you leave it and use the `./key` folder. |
| `UNLIST_DATA_DIR` | `/data` in the container | Where Unlist keeps its database and files. Normally you leave it and use the `./data` folder. |
| `TZ` | `UTC` in Unlist; `Europe/Berlin` in the shipped `compose.yaml` | Your time zone, for example `Europe/London`. |
| `UNLIST_PORT` | `8000` | The port the web server listens on **inside** the container. If you change it, change the container side of `ports:` too (`"8000:9000"` for `UNLIST_PORT: 9000`). Most people leave it and change only the left number of `ports:`. |
| `UNLIST_WORKERS` | `2` | How many web server processes run. One household rarely needs more. |
| `UNLIST_DEBUG` | off (`1` turns it on) | Development only. It switches on detailed error pages and changes how static files are served. Never use it on an instance that holds real data. |

`UNLIST_TESTING` also exists in the code, but only for the project's own tests. Do not set it.

## Stopping, starting, and removing

```sh
docker compose stop           # stop, keep everything
docker compose up -d          # start again
docker compose down           # remove the container; ./data and ./key stay on disk
```

To delete everything, stop it and delete the `data` and `key` folders yourself. Nothing else holds your data.

## Next

[First run](first-run.md).
