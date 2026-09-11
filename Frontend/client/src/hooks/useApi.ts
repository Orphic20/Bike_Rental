import { useAuth } from "@/contexts/AuthContext";
import { api, ApiError } from "@/lib/api";
import type { Bike, Booking, RateSelected, StaffBooking } from "@/lib/types";
import { useCallback, useEffect, useState } from "react";

interface Resource<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

function describe(cause: unknown): string {
  if (cause instanceof ApiError) return cause.message;
  if (cause instanceof Error) return cause.message;
  return "Something went wrong.";
}

/**
 * The catalogue is public, so this runs whether or not anyone is signed in.
 * Passing a pickup date makes the backend mark bikes already reserved for that
 * window as unavailable.
 */
export function useBikes(pickupDate: string | null, rate: RateSelected): Resource<Bike[]> {
  const [data, setData] = useState<Bike[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);

    api
      .listBikes(
        { pickup_date: pickupDate ?? undefined, rate: pickupDate ? rate : undefined },
        controller.signal,
      )
      .then((bikes) => {
        setData(bikes);
        setError(null);
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setError(describe(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [pickupDate, rate, nonce]);

  return { data, loading, error, reload };
}

/** Every booking the signed-in customer owns. Resolves to null when signed out. */
export function useMyBookings(): Resource<Booking[]> {
  const { session } = useAuth();
  const [data, setData] = useState<Booking[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    if (!session) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);

    api
      .listMyBookings(controller.signal)
      .then((bookings) => {
        setData(bookings);
        setError(null);
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setError(describe(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [session, nonce]);

  return { data, loading, error, reload };
}

/** Counter queue. `q` is the search box; empty means every booking. */
export function useStaffBookings(q: string): Resource<StaffBooking[]> {
  const { session } = useAuth();
  const [data, setData] = useState<StaffBooking[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  const reload = useCallback(() => setNonce((value) => value + 1), []);

  useEffect(() => {
    if (!session) {
      setData(null);
      setError(null);
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);

    api
      .listStaffBookings({ q: q.trim() || undefined }, controller.signal)
      .then((bookings) => {
        setData(bookings);
        setError(null);
      })
      .catch((cause) => {
        if (controller.signal.aborted) return;
        setError(describe(cause));
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [session, q, nonce]);

  return { data, loading, error, reload };
}
