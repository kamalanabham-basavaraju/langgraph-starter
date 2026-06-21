#!/bin/sh
set -e

if [ -n "$EMPLOYEE_PORTAL_PATH" ]; then
  git config --global --add safe.directory "$EMPLOYEE_PORTAL_PATH"
fi

exec "$@"
