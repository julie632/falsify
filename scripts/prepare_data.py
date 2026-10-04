"""Fetch the attributed public dataset without making model API calls."""
import json

from falsify.science import prepare_data

if __name__ == "__main__":
    print(json.dumps(prepare_data(), indent=2))
