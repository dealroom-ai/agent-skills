/**
 * Minimal Dealroom API client with automatic OAuth2 token refresh.
 *
 * Requires: npm install simple-oauth2 axios dotenv
 *
 * Usage:
 *   import { dealroom } from "./dealroom";
 *   const { data } = await dealroom.get("/entities", {
 *     params: { limit: 10, sort: "-launch_date" },
 *   });
 */

import "dotenv/config";
import axios, { AxiosError, AxiosInstance } from "axios";
import { ClientCredentials, AccessToken } from "simple-oauth2";

const CLIENT_ID = requireEnv("DEALROOM_CLIENT_ID");
const CLIENT_SECRET = requireEnv("DEALROOM_CLIENT_SECRET");
const USER_AGENT = requireEnv("DEALROOM_USER_AGENT");
const API_BASE = process.env.DEALROOM_API_BASE ??
  "https://api-next.beta.dealroom.co";
const AUTH_HOST = new URL(
  process.env.DEALROOM_AUTH_URL ??
    "https://accounts.beta.dealroom.co/oauth/token",
);
const AUDIENCE = process.env.DEALROOM_AUDIENCE ??
  "https://api-next.beta.dealroom.co";

function requireEnv(key: string): string {
  const value = process.env[key];
  if (!value) {
    throw new Error(`Missing required env var: ${key}`);
  }
  return value;
}

const oauth = new ClientCredentials({
  client: { id: CLIENT_ID, secret: CLIENT_SECRET },
  auth: {
    tokenHost: `${AUTH_HOST.protocol}//${AUTH_HOST.host}`,
    tokenPath: AUTH_HOST.pathname,
  },
});

let token: AccessToken | null = null;

async function getToken(): Promise<string> {
  if (!token || token.expired()) {
    token = await oauth.getToken({ audience: AUDIENCE });
  }
  return token.token.access_token as string;
}

export const dealroom: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api`,
  headers: {
    "User-Agent": USER_AGENT,
    "X-Client-Id": CLIENT_ID,
  },
});

dealroom.interceptors.request.use(async (config) => {
  config.headers.Authorization = `Bearer ${await getToken()}`;
  return config;
});

dealroom.interceptors.response.use(undefined, async (error: AxiosError) => {
  if (error.response?.status === 401 && error.config && !error.config.headers["x-retried"]) {
    token = null;
    error.config.headers["x-retried"] = "1";
    error.config.headers.Authorization = `Bearer ${await getToken()}`;
    return axios.request(error.config);
  }
  throw error;
});

if (import.meta.url === `file://${process.argv[1]}`) {
  const { data } = await dealroom.get("/entities", { params: { limit: 1 } });
  console.log(JSON.stringify(data, null, 2));
}
