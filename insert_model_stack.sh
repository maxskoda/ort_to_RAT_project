#!/usr/bin/env bash
# Usage: ./insert_model_stack.sh file.ort "Si | (SiO2 1.5) | (Cr 5.0) | (Au 20.0) | D2O"

FILE="$1"
STACK="$2"

if [[ -z "$FILE" || -z "$STACK" ]]; then
    echo "Usage: $0 input.ort \"Si | (SiO2 1.5) | ...\""
    exit 1
fi

# Backup
cp "$FILE" "$FILE.bak"

awk -v stack="$STACK" '
    BEGIN { inserted = 0 }

    # Detect the exact line: "#     name: ..."
    /^# *name:/ {
        print
        if (!inserted) {
            print "#     model:"
            print "#       stack: " stack
            inserted = 1
        }
        next
    }

    { print }
' "$FILE.bak" > "$FILE"
