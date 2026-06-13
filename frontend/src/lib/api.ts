/// <reference types="vite/client" />
import { client } from "../api/client.gen";

// Single canonical home for the backend base URL. Override via VITE_API_BASE_URL.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Point the generated fetch client at the backend.
client.setConfig({ baseUrl: API_BASE_URL });
