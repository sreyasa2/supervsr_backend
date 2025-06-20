from api import create_app
from dotenv import load_dotenv
import argparse

load_dotenv()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--local', action='store_true', help='Store screenshots locally as well as in GCS')
    args = parser.parse_args()

    # Pass config to create_app
    app = create_app({'LOCAL_SCREENSHOT_STORAGE': args.local})
    app.run(host='0.0.0.0', port=8000, debug=False)  # Disable debug mode
else:
    app = create_app()