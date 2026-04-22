/** Типы, разделяемые фронтендом и дублирующие Pydantic-схемы бэкенда. */

export type UserRole = "student" | "teacher" | "admin";

export interface User {
  user_id:      number;
  login:        string;
  email:        string;
  display_name: string | null;
  role:         UserRole;
  created_at:   string;
}

export interface LoginResponse {
  access_token: string;
  token_type:   string;
}

export interface RegisterRequest {
  login:         string;
  email:         string;
  password:      string;
  display_name?: string;
}
