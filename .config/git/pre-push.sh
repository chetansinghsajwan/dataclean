#!/bin/sh

# List of branches to guard (space-separated)
TARGET_BRANCHES="dev main"

# Args: local_ref local_sha remote_ref remote_sha
while read -r _ _ remote_ref _; do
    # Extract short branch name (e.g., refs/heads/main -> main)
    branch=$(basename "$remote_ref")

    case " $TARGET_BRANCHES " in
        *" $branch "*)
            echo "[Guardrail] Target branch '$branch' is protected."

            devbox run task check
            exit $?
            ;;
        *)
            # Fall through silently for untracked lines to keep developer workflows fast
            ;;
    esac
done

exit 0
