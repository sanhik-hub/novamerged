const supabaseUrl = (import.meta.env.VITE_SUPABASE_URL ?? "").trim().replace(/\/$/, "");
const supabaseKey = (import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY ?? "").trim();
export const SUPABASE_BUCKET = (import.meta.env.VITE_SUPABASE_BUCKET ?? "Images").trim();

if (!supabaseUrl || !supabaseKey) {
  console.warn(
    "Nova AI: Supabase browser configuration is missing. Image uploads will be unavailable until VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY are configured.",
  );
}

export async function uploadQuestionImage(file: File): Promise<string> {
  if (!supabaseUrl || !supabaseKey) {
    throw new Error("Image upload is not configured. Please add the Supabase browser credentials to the frontend environment.");
  }

  const extension = file.name.split(".").pop()?.toLowerCase() ?? "png";
  const uuid =
    typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  const filePath = `CT_images/${uuid}.${extension}`;
  const encodedPath = filePath.split("/").map(encodeURIComponent).join("/");
  const uploadUrl = `${supabaseUrl}/storage/v1/object/${encodeURIComponent(SUPABASE_BUCKET)}/${encodedPath}`;

  let response: Response;
  try {
    response = await fetch(uploadUrl, {
      method: "POST",
      headers: {
        apikey: supabaseKey,
        Authorization: `Bearer ${supabaseKey}`,
        "Content-Type": file.type || "application/octet-stream",
        "x-upsert": "false",
      },
      body: file,
    });
  } catch {
    throw new Error("Unable to connect to Supabase. Please try again.");
  }

  if (!response.ok) {
    const errorText = await response.text();

    let errorMessage = errorText;
    try {
      const errorData = JSON.parse(errorText) as { message?: string; error?: string };
      errorMessage = errorData.message || errorData.error || errorText;
    } catch {
      // Keep the plain response when Supabase does not return JSON.
    }

    throw new Error(
      `Image upload failed (${response.status}): ${errorMessage || "Unknown Supabase error"}`,
    );
  }

  return filePath;
}
