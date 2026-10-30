#!/usr/bin/env bash
# The hosted demo copy: a GitHub Codespace created from the private repo (docs/JUDGE_DAY.md, "The link to give judges").
#
#   scripts/hosted.sh status      codespace state and the public URL
#   scripts/hosted.sh wake        start the codespace if stopped and (re)start the API and the frontend in it
#   scripts/hosted.sh keepalive   hold an ssh session open so the codespace is not stopped for idleness (Ctrl-C to end)
#   scripts/hosted.sh logs        last lines of the backend and frontend logs
#   scripts/hosted.sh ssh         a shell in the codespace
#
# The codespace name comes from `gh codespace list` (display name "concours-demo") unless CODESPACE is set.
set -euo pipefail
CS="${CODESPACE:-$(gh codespace list --json name,displayName --jq '.[] | select(.displayName=="concours-demo") | .name' | head -1)}"
[ -n "$CS" ] || { echo "no codespace named concours-demo; see docs/JUDGE_DAY.md to create one" >&2; exit 2; }
url() { gh codespace ports -c "$CS" --json sourcePort,browseUrl,visibility --jq '.[] | select(.sourcePort==3000) | "\(.browseUrl) (\(.visibility))"'; }
quiet() { grep -vE 'WARNING|post-quantum|store now|openssh.com' || true; }

case "${1:-status}" in
  status)
    gh codespace list --json name,state,machineName,lastUsedAt --jq ".[] | select(.name==\"$CS\") | \"\(.name) \(.state) \(.machineName) last used \(.lastUsedAt)\""
    echo "link: $(url)"
    ;;
  wake)
    echo "[hosted] starting the servers in $CS (starts the codespace first if it is stopped)"
    gh codespace ssh -c "$CS" -- 'cd /workspaces/concours && bash .devcontainer/start.sh' 2>&1 | quiet
    echo "link: $(url)"
    ;;
  keepalive)
    echo "[hosted] holding a session open on $CS; leave this running during the demo, Ctrl-C to end"
    gh codespace ssh -c "$CS" -- 'while true; do date +%T; sleep 300; done' 2>&1 | quiet
    ;;
  logs)
    gh codespace ssh -c "$CS" -- 'cd /workspaces/concours && echo "--- backend"; tail -15 workspace/backend.log; echo "--- frontend"; tail -8 workspace/frontend.log' 2>&1 | quiet
    ;;
  ssh) exec gh codespace ssh -c "$CS" ;;
  *) sed -n 2,10p "$0"; exit 2 ;;
esac
