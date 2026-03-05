# Update Bayes classifier using https://untroubled.org/spam/

```bash
#!/bin/bash

BASE_URL="https://untroubled.org"

echo "Targeting last 12 months (excluding current month)..."

# Loop from 12 months ago to 1 month ago
for i in {12..1}; do
    # Generate filename (YYYY-MM.7z)
    FILENAME=$(date -d "$i month ago" +%Y-%m).7z
    FULL_URL="${BASE_URL}/spam/${FILENAME}"
    DIR_NAME="${FILENAME%.7z}"
    
    echo "Fetching: $FULL_URL"
    
    if wget -nc -q --show-progress "$FULL_URL"; then
        # 2. Extract into its own directory
        # -o specifies output directory, -y assumes 'yes' to prompts
        7z x "$FILENAME" -o"$DIR_NAME" -y > /dev/null
        echo "Extracted to: $DIR_NAME/"
    else
        echo "Failed to download $FILENAME (it may not exist yet)."
    fi
done

echo "Download process complete."
```

## feed rspamd with the extracted emails

```bash
#!/bin/bash

# Directory where the extracted month folders are located
BASE_DIR="."

# Check if rspamc is available
if ! command -v rspamc &> /dev/null; then
    echo "Error: rspamc not found. Please ensure Rspamd is installed."
    exit 1
fi

echo "Starting Rspamd learning process..."

# Find all .txt files within directories and pipe them to rspamc
# -print0 and xargs -0 handle filenames with spaces or weird characters safely
find "$BASE_DIR" -mindepth 2 -type f -name "*.txt" -print0 | xargs -0 -n 100 rspamc learn_spam

echo "Learning complete."