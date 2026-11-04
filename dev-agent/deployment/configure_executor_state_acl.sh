#!/bin/sh
# Narrow filesystem ACLs for the capability-free supervised executor.
# Run manually as root. Does not start services or release the emergency stop.
set -eu
command -v setfacl >/dev/null || { echo 'acl package required; no changes made' >&2; exit 1; }
base=/var/lib/swayzcontrol
test -d "$base/state"
test -f "$base/state/stop.db"
test -f "$base/state/journal.db"
test ! -L "$base"
test ! -L "$base/state"
test ! -L "$base/state/stop.db"
test ! -L "$base/state/journal.db"
# This unit has User=root but CapabilityBoundingSet=, so root needs explicit
# ACL traversal/read rights to swayzcontrol-owned mode 0700/0600 files.
setfacl -m u:root:--x "$base"
setfacl -m u:root:rwx "$base/state"
setfacl -m u:root:r-- "$base/state/stop.db"
setfacl -m u:root:rw- "$base/state/journal.db"
# Do not grant the executor stop.db write access or any DAC capabilities.
echo SWAYZ_NARROW_ACL_APPLIED
