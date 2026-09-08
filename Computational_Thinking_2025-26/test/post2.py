import requests

url = " https://computational-thinking-2025-26.onrender.com//NewUser_login"

data = {
    "Username": "User3254354",
    "NewPassword": "12345"
}


response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("Response:", response.text)