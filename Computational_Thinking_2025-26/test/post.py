import requests

url = " https://computational-thinking-2025-26.onrender.com//QuestionPost"

data = {
    "Username": "Subrata11118",
    "Question": "Algorithmic thinking: determine the correct sequence of operations.",
    "Image_path": "CT_images/56e23807-adae-42ba-963f-a97d1aa87d08.png"
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Content-Type:", response.headers.get("Content-Type"))
print("Response:", response.text)