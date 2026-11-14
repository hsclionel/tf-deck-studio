#!/bin/sh
# Key login for spruce's Dropbear (run on the handheld as root):
#   ssh spruce@<ip> sh < spruce_key_login.sh
#
# spruce's home is the vfat SD card, where every file is rwxrwxrwx and chmod does nothing, so
# Dropbear ignores /mnt/SDCARD/.ssh/authorized_keys (it refuses key files that others could edit,
# checking each folder up to /). This keeps the keys on internal ext4 storage instead and starts
# Dropbear with -D pointing there. Password login keeps working. Safe to run again (e.g. after a
# spruce update replaces sshFunctions.sh).
set -e
F=/mnt/SDCARD/spruce/scripts/network/sshFunctions.sh
K=/mnt/UDISK/dropbear

mkdir -p "$K"
sort -u /mnt/SDCARD/.ssh/authorized_keys > "$K/authorized_keys"
chmod 700 "$K"
chmod 600 "$K/authorized_keys"
chmod go-w / /mnt /mnt/UDISK          # Dropbear checks every folder above the key file
ls -ld / /mnt /mnt/UDISK "$K" "$K/authorized_keys"
echo "keys: $(wc -l < "$K/authorized_keys")"

if grep -q -- "-D $K" "$F"; then
    echo "sshFunctions.sh already starts Dropbear with -D $K"
else
    cp "$F" "$F.bak-before-key"
    # plain-text match (index), not a regex: escaping the trailing backslash differs between awks
    awk -v k="$K" '{ print } index($0, "-r \"$SSH_KEYS/dropbear_ed25519_host_key\" \\") { print "            -D " k " \\" }' \
        "$F.bak-before-key" > "$F"
    grep -q -- "-D $K" "$F" || { cp "$F.bak-before-key" "$F"; echo "PATCH FAILED, original restored"; exit 1; }
    echo "patched $F (backup: $F.bak-before-key)"
fi
grep -n -A2 'dropbear_ed25519_host_key" \\' "$F"
echo "Done. Reboot the handheld (or turn SSH off and on in spruce) so Dropbear restarts with the new option."
