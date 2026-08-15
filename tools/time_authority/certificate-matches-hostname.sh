#!/bin/sh
set -eu

CERTIFICATE=${1:-}
HOSTNAME_TO_CHECK=${2:-}

[ -n "$CERTIFICATE" ] || {
  echo "usage: $0 CERTIFICATE HOSTNAME" >&2
  exit 2
}
[ -n "$HOSTNAME_TO_CHECK" ] || {
  echo "usage: $0 CERTIFICATE HOSTNAME" >&2
  exit 2
}
[ -r "$CERTIFICATE" ] || {
  echo "certificate is not readable: $CERTIFICATE" >&2
  exit 2
}
command -v openssl >/dev/null 2>&1 || {
  echo "openssl is required" >&2
  exit 2
}

# OpenSSL 3.0's `openssl x509 -checkhost` can report a hostname mismatch in
# its diagnostic text while still returning a zero process status.  Treat the
# affirmative diagnostic as the match signal and fail closed on anything else.
set +e
CHECK_OUTPUT=$(openssl x509 -in "$CERTIFICATE" -noout -checkhost "$HOSTNAME_TO_CHECK" 2>&1)
CHECK_RC=$?
set -e

case "$CHECK_OUTPUT" in
  *"does match certificate"*)
    exit 0
    ;;
  *"does NOT match certificate"*)
    exit 1
    ;;
esac

if [ "$CHECK_RC" -ne 0 ]; then
  exit 1
fi

printf 'Could not determine hostname match from openssl x509 -checkhost output for %s\n' "$CERTIFICATE" >&2
[ -n "$CHECK_OUTPUT" ] && printf '%s\n' "$CHECK_OUTPUT" >&2
exit 2
