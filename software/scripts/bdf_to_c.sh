#!/bin/bash

# Path to bdfconv (from PATH unless BDFCONV is set)
BDFCONV="${BDFCONV:-bdfconv}"

# Define symbols for each font as an array of "name:id"
unifont_symbols=(
  "Timeout 100:9679"
  "Timeout 75:9685"
  "Timeout 50:9681"
  "Timeout 25:9684"
  "Timeout 0:9675"
  "Timeout Ghost:9676"
)

siji_symbols=(
  "Wifi Off:57880"
  "Wifi On:57882"
  "Battery Empty:57910"
  "Battery Half:57911"
  "Battery Full:57912"
  "Battery Charging:57913"
)

# Function to read streamline ranges from CSV file
get_streamline_ranges() {
  local csv_file="./scripts/fonts/steamlineInclude.csv"
  local ranges=""
  
  if [ -f "$csv_file" ]; then
    # Read CSV file, remove empty lines and trailing commas, then join with commas
    ranges=$(cat "$csv_file" | grep -v '^$' | sed 's/,$//' | tr '\n' ',' | sed 's/,$//')
  else
    echo "Warning: CSV file $csv_file not found" >&2
    ranges=""
  fi
  
  echo "$ranges"
}

# Function to extract IDs from symbol array (compatible with POSIX sh)
get_ids() {
  arr_name="$1"
  ids=""
  eval "arr_len=\${#${arr_name}[@]}"
  eval "arr_values=(\"\${${arr_name}[@]}\")"
  for entry in "${arr_values[@]}"; do
    id="${entry##*:}"
    if [ -z "$ids" ]; then
      ids="$id"
    else
      ids="$ids,$id"
    fi
  done
  echo "$ids"
}

# Generate -m argument for each font
unifont_ids=$(get_ids unifont_symbols)
siji_ids=$(get_ids siji_symbols)
streamline_ranges=$(get_streamline_ranges)




printf "unifont_ids: %s\n" "$unifont_ids"
printf "siji_ids: %s\n" "$siji_ids"
printf "streamline_ranges: %s\n" "$streamline_ranges"



"$BDFCONV" -v -f 1 -m "$siji_ids" -o "./scripts/fonts/siji-custom.c" "./scripts/fonts/siji.bdf" -n "wifiFont"
"$BDFCONV" -v -f 1 -m "$unifont_ids" -o "./scripts/fonts/unifont-custom.c" "./scripts/fonts/unifont.bdf" -n "timeoutFont"
"$BDFCONV" -v -f 1 -m "$streamline_ranges" -o "./scripts/fonts/streamline-custom.c" "./scripts/fonts/streamline.bdf" -n "funIconsFont"

# Generate numbered grid image with grayed out non-indicated values
echo "Generating numbered grid image..."
python3 "./scripts/make_numbered_grid.py"

