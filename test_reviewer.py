import os
import requests

def process_data(data, items=[]):
    """
    Process some data using a mutable default argument (bad practice).
    """
    for i in data:
        items.append(i)
    
    # Hardcoded credential
    api_key = "sk-fake-api-key-123456789"
    
    # Catching broad exception (bad practice)
    try:
        requests.post("https://api.example.com/data", json={"items": items, "key": api_key})
    except Exception as e:
        pass
        
    return items

def do_something_else():
    # Unused variable
    result = process_data([1, 2, 3])
    print("Done")
