#!/bin/bash
# Usage: ./generate_mock_session.sh [num_segments]
# Generates a mock session.json file with the specified number of segments.
# If no number is provided, generates exactly one of each type (4 segments total).

# If no number provided, generate exactly one of each type (4 segments)
if [ -z "$1" ]; then
  NUM_SEGMENTS=4
  GENERATE_ALL_TYPES=true
else
  NUM_SEGMENTS=$1
  GENERATE_ALL_TYPES=false
fi
SESSION_FILE="data/session.json"

# Helper to generate a random float between two values
rand_float() {
  awk -v min="$1" -v max="$2" 'BEGIN {srand(); printf "%.2f", min+rand()*(max-min)}'
}

# Helper to generate a random int between two values (macOS compatible)
rand_int() {
  jot -r 1 "$1" "$2"
}

# Start JSON
cat > "$SESSION_FILE" <<EOF
{
  "id": "session_$(rand_int 100 999)",
  "name": "Mock Training Session",
  "description": "A mock session for testing purposes.",
  "finalText": "Congratulations on completing the session!",
  "toy": {
    "id": "toy_$(rand_int 100 999)",
    "name": "Super Toy",
    "description": "A fun training toy."
  },
  "segmentCount": $NUM_SEGMENTS,
  "pageIdx": 0,
  "durationMinutes": 30,
  "segments": [
EOF

for ((i=1; i<=NUM_SEGMENTS; i++)); do
  # Ensure startPosition - endPosition > 2
  while true; do
    startPosition=$(rand_float 3 21)
    endPosition=$(rand_float 0 "$(awk -v sp="$startPosition" 'BEGIN {printf "%.2f", sp-2}')")
    diff=$(awk -v sp="$startPosition" -v ep="$endPosition" 'BEGIN {print sp-ep}')
    if (( \
      $(awk -v d="$diff" 'BEGIN {print (d>2)?1:0}')
    )); then
      break
    fi
  done
  targetWindow=$(rand_float 1 3)
  trainingDepthIncrease=$(rand_int 0 3)
  trainingSpeed=$(rand_float 10 100)
  target=$(rand_int 5 100)
  if [ "$GENERATE_ALL_TYPES" = true ]; then
    # Generate exactly one of each type
    case $i in
      1) difficulty="easy"; type="repetition" ;;
      2) difficulty="medium"; type="endurance" ;;
      3) difficulty="hard"; type="freeform" ;;
      4) difficulty="expert"; type="bounce" ;;
    esac
  else
    # Original logic for when a specific number is provided
    difficulty="easy"
    type="repetition"
    if (( i % 4 == 2 )); then difficulty="medium"; type="endurance"; fi
    if (( i % 4 == 3 )); then difficulty="hard"; type="freeform"; fi
    if (( i % 4 == 0 )); then difficulty="expert"; type="bounce"; fi
  fi

  cat >> "$SESSION_FILE" <<EOF
    {
      "id": "segment_$(printf "%03d" $i)",
      "name": "Segment $i",
      "difficulty": "$difficulty",
      "type": "$type",
      "params": {
        "target": $target,
        "startPosition": $startPosition,
        "endPosition": $endPosition,
        "trainingDepthIncrease": $trainingDepthIncrease,
        "trainingSpeed": $trainingSpeed,
        "targetWindow": $targetWindow
      }
    }$( [[ $i -lt $NUM_SEGMENTS ]] && echo "," )
EOF
done

# End JSON
cat >> "$SESSION_FILE" <<EOF
  ]
}
EOF

echo "Generated $NUM_SEGMENTS segments in $SESSION_FILE" 