export type User = {
  id: number | string;
  username: string;
};

export type AuthResponse = {
  message: string;
  data: User;
};

export type Question = {
  question: string;
  options: string[];
  hint: string;
  correct_option: number;
  solution?: string;
  coordinates?: Coordinate[];
};

export type Coordinate = [number, number];

export type QuestionResponse = {
  is_relevant: boolean;
  error_message: string;
  ai_questions: Question[];
  user_question: Question;
};

export type QuizAnswer = {
  questionIndex: number;
  selectedOption: number;
  correct: boolean;
};

export type QuizResult = {
  score: number;
  total: number;
  percentage: number;
};

export type LearnAgainResponse = {
  ai_questions: Question[];
  user_question: Question;
};

export type HistoryEntry = {
  id: number;
  user_question: string;
  score: string;
};

export type HistoryDetail = {
  id: number;
  user_question: string;
  ai_questions: string;
  ai_answers: string;
  score: string;
  wrong_answered_question: string | null;
};

