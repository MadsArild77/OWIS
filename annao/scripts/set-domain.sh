#!/usr/bin/env bash
# Bytter domenet i canonical-URL, Open Graph, sitemap og robots.txt.
#
#   ./scripts/set-domain.sh anna-o.no
#
# Kjøres fra annao/-mappen. Standardverdi i repoet er annao.no.
set -euo pipefail

NEW="${1:-}"
if [ -z "$NEW" ]; then
  echo "Bruk: $0 <domene>   (f.eks. annao.no eller anna-o.no)" >&2
  exit 1
fi

cd "$(dirname "$0")/.."

# Finn domenet som ligger inne nå
OLD=$(grep -ho 'https://[a-z0-9.-]*\.no' index.html | head -n1 | sed 's#https://##')
if [ -z "$OLD" ]; then
  echo "Fant ingen canonical-URL i index.html" >&2
  exit 1
fi

if [ "$OLD" = "$NEW" ]; then
  echo "Domenet er allerede $NEW — ingen endring."
  exit 0
fi

echo "Bytter $OLD -> $NEW"
grep -rl "https://$OLD" --include='*.html' --include='*.xml' --include='*.txt' . \
  | xargs sed -i.bak "s#https://$OLD#https://$NEW#g"
find . -name '*.bak' -delete

echo "Ferdig. Husk å oppdatere domenet i .htaccess og i Hostinger hPanel også."
