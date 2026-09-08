import os

from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL or SUPABASE_SECRET_KEY is not configured")


supabase = create_client(
    SUPABASE_URL,
    SUPABASE_KEY
)

def create_signedURL(img_path):
    if not img_path:
        raise ValueError("img_path is required")

    signed_response = (
        supabase.storage
        .from_("Images")
        .create_signed_url(
            img_path,
            300
        )
    )

    if not isinstance(signed_response, dict):
        raise RuntimeError(f"Unexpected Supabase response: {signed_response!r}")

    if signed_response.get("error") or signed_response.get("statusCode", 200) >= 400:
        raise RuntimeError(f"Supabase signed URL request failed: {signed_response}")

    signed_url = signed_response.get("signedURL")
    if not signed_url:
        raise RuntimeError(f"Supabase did not return a signed URL: {signed_response}")

    return signed_url

   
        

