/// <reference types="vite/client" />
import { client } from "../api/client.gen";

// Point the generated fetch client at the backend. Override via VITE_API_BASE_URL.
client.setConfig({
  baseUrl: import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000",
});
