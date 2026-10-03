#!/bin/sh
# Git reads the publisher token only for the fixed public destination.
# The helper stores no credential and never receives the managed Codex auth.
set -eu
[ "${1:-}" = get ] || exit 0

credential_protocol=
credential_host=
credential_path=
while IFS= read -r credential_line && [ -n "$credential_line" ]; do
    case "$credential_line" in
        protocol=*) credential_protocol=${credential_line#protocol=} ;;
        host=*) credential_host=${credential_line#host=} ;;
        path=*) credential_path=${credential_line#path=} ;;
    esac
done

[ "$credential_protocol" = https ] || exit 0
[ "$credential_host" = github.com ] || exit 0
case "$credential_path" in
    murphyGo/investo|murphyGo/investo.git) ;;
    *) exit 0 ;;
esac
[ -n "${INVESTO_PUBLIC_PUBLISH_TOKEN:-}" ] || exit 1
printf 'username=x-access-token\npassword=%s\n\n' "$INVESTO_PUBLIC_PUBLISH_TOKEN"
