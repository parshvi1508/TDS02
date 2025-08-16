#!/bin/bash

# ================= INSTRUCTIONS =================
echo "=============================================="
echo " How to get the required credentials:"
echo ""
echo " 1. Get your Google API key here:"
echo "    https://aistudio.google.com/apikey"
echo ""
echo " 2. Register at ngrok and get your authtoken:"
echo "    https://ngrok.com/"
echo ""
echo " This script will:"
echo "    - Install all requirements from requirements.txt"
echo "    - Install ngrok (if not already installed)"
echo "    - Start your FastAPI app with uvicorn"
echo "    - Create a public ngrok URL for your app"
echo "=============================================="
echo ""


# ================= CREATE & ACTIVATE VENV =================
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
# Activate venv depending on shell
source venv/bin/activate

# ngrok Auth Token
if [ -z "$NGROK_AUTHTOKEN" ]; then
    read -p "Enter your ngrok authtoken: " NGROK_AUTHTOKEN
fi
export NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN

# ================= INSTALL REQUIREMENTS (First time only) =================
if [ ! -f ".deps_installed" ]; then
    echo "Installing dependencies from requirements.txt (first time only)..."
    pip install -r requirements.txt
    touch .deps_installed
else
    echo "Dependencies already installed. Skipping pip install."
fi
# ================= INSTALL NGROK =================
if ! command -v ngrok &> /dev/null; then
    echo "ngrok not found, installing..."
    pip install pyngrok
    NGROK_BIN=$(python3 -m pyngrok config get-path)
else
    NGROK_BIN=$(command -v ngrok)
fi

# ================= CONFIGURE NGROK =================
$NGROK_BIN config add-authtoken "$NGROK_AUTHTOKEN"

# ================= DETECT APP FILE =================
# Default to "app:main" unless a file called main.py exists
if [ -f "main.py" ]; then
    APP_TARGET="main:app"
elif [ -f "app.py" ]; then
    APP_TARGET="app:app"
else
    echo "Could not detect FastAPI entry file. Please enter module:variable (e.g., app:app)"
    read -p "Module:Variable => " APP_TARGET
fi

# ================= START UVICORN =================
echo "Starting uvicorn server..."
uvicorn $APP_TARGET --reload --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

# Trap Ctrl+C to stop uvicorn too
trap "echo -e '\nStopping servers...'; kill $UVICORN_PID; exit" INT

# Countdown timer (3 seconds)
echo "Waiting for uvicorn to start..."
for i in {3..1}; do
    echo -ne "Starting in $i seconds...\r"
    sleep 1
done
echo -e "\nServer should be ready now."

# ================= START NGROK (FOREGROUND) =================
echo "Starting ngrok tunnel on port 8000..."
$NGROK_BIN http 8000
