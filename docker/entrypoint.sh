#!/bin/sh
# Drops from root to a PUID/PGID-controlled user before running the CMD, the same
# convention linuxserver.io images use (see docker-compose.dev.yml's sonarr service) —
# so files legendarr writes into the bind-mounted /config and /media volumes are owned
# by the host user running docker, not by container root. Defaults to 1000:1000 (set as
# ENV in the Dockerfile) since that's the first non-system uid/gid on most Linux hosts;
# override PUID/PGID to match your own user when it isn't.
set -e

PUID="${PUID:-1000}"
PGID="${PGID:-1000}"

if ! getent group "$PGID" >/dev/null 2>&1; then
    groupadd -g "$PGID" legendarr
fi
group_name="$(getent group "$PGID" | cut -d: -f1)"

if ! getent passwd "$PUID" >/dev/null 2>&1; then
    useradd -u "$PUID" -g "$PGID" -M -s /usr/sbin/nologin legendarr
fi
user_name="$(getent passwd "$PUID" | cut -d: -f1)"

# /config is legendarr's own data (SQLite DB, cache, secrets) — it's fine to take
# ownership of everything there. /media is the user's existing library, mounted
# read/write only so legendarr can write subtitle siblings next to the video files;
# it's never chowned, so files Sonarr/Radarr (or the user) already own stay that way.
chown -R "$user_name":"$group_name" /config

exec gosu "$user_name":"$group_name" "$@"
