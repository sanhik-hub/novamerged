# Nova AI — V1 Frontend

React + TypeScript + Vite frontend for the supplied Nova AI Flask backend.

## Run

```bash
cd client
npm install
npm run dev
```

From this directory:

```bash
npm run build
npm run lint
```

## Environment

Copy `.env.example` to `.env` and configure:

```env
VITE_API_URL=https://computational-thinking-2025-26.onrender.com
VITE_SUPABASE_URL=
VITE_SUPABASE_PUBLISHABLE_KEY=
VITE_SUPABASE_BUCKET=Images
```

Only browser-safe Supabase credentials belong in Vite environment variables. Never put `DATABASE_URL`, `SUPABASE_SECRET_KEY`, Gemini/API secrets, or other private credentials in the client.

## Backend contract used

The frontend was implemented against the routes found in the supplied Flask server:

- `POST /NewUser_login` — `{ Username, NewPassword }`
- `POST /Old_User_login` — `{ Username, Password }`
- `POST /QuestionPost` — `{ Username, Question, Image_path }`
- `POST /DoubtQuestionPost` — `{ Username, WrongAnsweredquestion, QuestionJson }`
- `POST /ScorePost` exists on the server but is intentionally not called because V1 does not require persistence of quiz scores.

The server's question schema uses `correct_option` values `1` through `4`; the frontend preserves that mapping.

`is_relevant` is validated as a top-level response property. Relevant responses require a valid `ai_questions` array and `user_question`; malformed responses are shown as user-friendly errors rather than rendered.

## Image uploads

The supplied server expects `Image_path` and its server-side Supabase service signs paths from the `Images` bucket. The frontend validates JPG/JPEG/PNG images, limits them to 10 MB, creates a UUID filename, uploads to the configured Supabase Storage bucket using the browser-safe publishable key, and sends the resulting storage path to `/QuestionPost`.

The backend does not expose a dedicated difficulty parameter. Therefore **Learn Again** uses the supplied `/DoubtQuestionPost` contract and lets the backend determine the new practice level; the frontend does not fabricate easier questions.

## Session

The frontend stores only `id` and `username` in localStorage. Passwords are never stored.
