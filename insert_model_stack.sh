#!/usr/bin/env bash
# Usage: ./insert_model_stack.sh file.ort "Si | (SiO2 1.5) | ..."

FILE="$1"
STACK="$2"

if [[ -z "$FILE" || -z "$STACK" ]]; then
    echo "Usage: $0 input.ort \"Si | (SiO2 1.5) | ...\""
    exit 1
fi

cp "$FILE" "$FILE.bak"

awk -v stack="$STACK" '
    BEGIN {
        in_sample = 0
        inserted = 0
    }

    # Detect start of the sample section
    /^# *sample:/ {
        in_sample = 1
    }

    # Detect other top-level headers → exit sample section
    /^# *(experiment:|measurement:|data_source:)/ && !/^# *sample:/ {
        in_sample = 0
    }

    # We only react to the *sample* name:
    in_sample == 1 && /^# *name:/ {
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
