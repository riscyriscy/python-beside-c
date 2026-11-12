#!/usr/bin/env bash
# Copy the VS Code configuration between this repository and the editor.
#   vscode-config.sh apply     repository -> editor, then install the listed extensions
#   vscode-config.sh capture   editor -> repository, and write the extension list
# CODE=codium selects another build. USER_DIR=PATH overrides the folder of the user files.
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
code=${CODE:-code}

if [[ -z ${USER_DIR:-} ]]; then
    case "$(uname -s)" in
        Linux)          USER_DIR=${XDG_CONFIG_HOME:-$HOME/.config}/Code/User ;;
        Darwin)         USER_DIR="$HOME/Library/Application Support/Code/User" ;;
        MINGW* | MSYS*) USER_DIR=$APPDATA/Code/User ;;
        *)              echo "unknown system: $(uname -s)" >&2; exit 2 ;;
    esac
fi
files=(settings.json keybindings.json)

apply() {
    mkdir -p "$USER_DIR"
    for f in "${files[@]}"; do
        [[ -f $here/$f ]] || continue
        if [[ -f $USER_DIR/$f ]]; then
            if cmp -s "$here/$f" "$USER_DIR/$f"; then
                echo "same      $f"
                continue
            fi
            cp "$USER_DIR/$f" "$USER_DIR/$f.bak"
            echo "backup    $f.bak"
        fi
        cp "$here/$f" "$USER_DIR/$f"
        echo "copied    $f"
    done
    installed=$("$code" --list-extensions)
    while IFS= read -r id; do
        [[ -z $id || $id == \#* ]] && continue
        if grep -qixF -- "$id" <<<"$installed"; then
            echo "present   $id"
        else
            "$code" --install-extension "$id" >/dev/null
            echo "installed $id"
        fi
    done <"$here/extensions.txt"
}

capture() {
    for f in "${files[@]}"; do
        [[ -f $USER_DIR/$f ]] || continue
        cp "$USER_DIR/$f" "$here/$f"
        echo "captured  $f"
    done
    "$code" --list-extensions | tr '[:upper:]' '[:lower:]' | sort >"$here/extensions.txt"
    echo "wrote     extensions.txt ($(wc -l <"$here/extensions.txt") extensions)"
}

case ${1:-} in
    apply)   apply ;;
    capture) capture ;;
    *)       echo "usage: $0 apply|capture" >&2; exit 2 ;;
esac
