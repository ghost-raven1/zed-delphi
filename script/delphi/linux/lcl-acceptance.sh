#!/usr/bin/env bash
# Run in a disposable x86_64 distribution container with /repo and /verification mounts.
set -euo pipefail

test "$(uname -m)" = x86_64
test -f /repo/script/delphi/tests/smoke_lcl.py
mkdir -p /verification
cp /etc/os-release /verification/os-release.txt
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates curl unzip python3 build-essential file \
  fp-compiler fp-units-base fp-units-fcl fp-units-gtk2 \
  lcl-utils lcl-gtk2 lazarus-src libgtk2.0-dev \
  xvfb xauth xdotool imagemagick tesseract-ocr
dpkg-query -W > /verification/installed-packages.txt
fpc -iV > /verification/fpc-version.txt
lazbuild --version > /verification/lazbuild-version.txt

curl --fail --location --retry 3 \
  https://github.com/vadimcn/codelldb/releases/download/v1.12.3/codelldb-linux-x64.vsix \
  -o /tmp/codelldb.vsix
printf '%s  %s\n' \
  1cd7f386598022b51a5b93b9ffa23e812b23f519cfe1833384ec4bef4bfd1be1 \
  /tmp/codelldb.vsix | sha256sum -c - | tee /verification/codelldb-checksum.txt
unzip -q /tmp/codelldb.vsix -d /opt/codelldb
ldd /opt/codelldb/extension/adapter/codelldb > /verification/adapter-libraries.txt

export LANG=C.UTF-8
export LC_ALL=C.UTF-8
export OMP_THREAD_LIMIT=1
xvfb-run -a -s '-screen 0 1280x900x24' bash -euo pipefail -c '
  python3 -u /repo/script/delphi/tests/smoke_lcl.py \
    --fixture /repo/script/delphi/examples/lcl_demo \
    --lazbuild /usr/bin/lazbuild \
    --codelldb /opt/codelldb/extension/adapter/codelldb \
    --widgetset gtk2 --output /verification/debug
  python3 -u /repo/script/delphi/linux/lcl-gui.py \
    --binary "/verification/debug/Проект Lazarus с пробелами/LclDemo" \
    --output /verification/gui
'
