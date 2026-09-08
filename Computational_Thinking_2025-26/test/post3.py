import requests

url = " https://computational-thinking-2025-26.onrender.com//Old_User_login"

data = {
    "Username": "Subrata11118",
    "Password": "Subrata@1234"
}


response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("Response:", response.text)