import { getAccessToken } from "@/lib/supabase";
import type {
  Bike,
  BikeType,
  Booking,
  BookingCreate,
  RateSelected,
  User,
} from "@/lib/types";

const BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  /** Send the Supabase access token; requests fail fast when signed out. */
  auth?: boolean;
  query?: Record<string, string | number | undefined | null>;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, auth = false, query, signal } = options;

  const url = new URL(`${BASE_URL}${path}`);
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== "") {
      url.searchParams.set(key, String(value));
    }
  }

  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";

  if (auth) {
    const token = await getAccessToken();
    if (!token) throw new ApiError(401, "Please sign in to continue.");
    headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(url, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") throw error;
    // A network-level failure here almost always means the API is not running
    // or CORS_ORIGINS does not include this origin.
    throw new ApiError(0, `Cannot reach the API at ${BASE_URL}.`);
  }

  if (response.status === 204) return undefined as T;

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new ApiError(response.status, extractDetail(payload, response.status));
  }

  return payload as T;
}

/** FastAPI puts errors in `detail`, either a string or a list of validation objects. */
function extractDetail(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String((item as { msg: unknown }).msg)
            : null,
        )
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
  }
  return `Request failed with status ${status}.`;
}

export const api = {
  health: () => request<{ status: string }>("/health"),

  listBikes: (
    params: {
      type?: BikeType;
      pickup_date?: string;
      rate?: RateSelected;
    } = {},
    signal?: AbortSignal,
  ) => request<Bike[]>("/bikes", { query: params, signal }),

  me: (signal?: AbortSignal) => request<User>("/users/me", { auth: true, signal }),

  listMyBookings: (signal?: AbortSignal) =>
    request<Booking[]>("/bookings", { auth: true, signal }),

  getBooking: (id: string, signal?: AbortSignal) =>
    request<Booking>(`/bookings/${id}`, { auth: true, signal }),

  createBooking: (body: BookingCreate) =>
    request<Booking>("/bookings", { method: "POST", body, auth: true }),
};
