import { BikeArt, BrandMark } from "@/components/Artwork";
import { useAuth } from "@/contexts/AuthContext";
import { useStaffBookings } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { formatDateTimeLabel, formatPeso } from "@/lib/format";
import {
  BIKE_TYPE_LABELS,
  PAYMENT_STATUS_LABELS,
  type StaffBooking,
} from "@/lib/types";
import { ArrowLeft, ArrowUpRight, CheckCircle2, Clock3 } from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

function extensionStatus(row: StaffBooking) {
  if (row.extension_applied_at) return "Approved";
  if (row.payment_status === "paid") return "Ready for approval";
  return PAYMENT_STATUS_LABELS[row.payment_status];
}

export default function StaffExtensions() {
  const { profile, loading: authLoading } = useAuth();
  const queue = useStaffBookings("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const extensions = useMemo(
    () => (queue.data ?? []).filter((row) => row.booking_type === "extension"),
    [queue.data],
  );

  const rentalById = useMemo(() => {
    const map = new Map(
      (queue.data ?? [])
        .flatMap((booking) => booking.rentals)
        .map((rental) => [rental.id, rental] as const),
    );
    return map;
  }, [queue.data]);

  const run = async (
    row: StaffBooking,
    label: string,
    action: () => Promise<unknown>,
  ) => {
    setBusyId(row.id);
    try {
      await action();
      toast.success(label);
      queue.reload();
    } catch (cause) {
      toast.error(cause instanceof ApiError ? cause.message : "Request failed.");
    } finally {
      setBusyId(null);
    }
  };

  if (!authLoading && profile?.role !== "staff" && profile?.role !== "admin") {
    return (
      <main className="privacy-page">
        <h1>Staff access required.</h1>
        <a href="/">Return home</a>
      </main>
    );
  }

  return (
    <div className="product-layout ops-layout staff-extensions-page">
      <aside className="app-sidebar ops-sidebar">
        <a className="app-brand" href="/">
          <span className="app-brand-mark"><BrandMark /></span>
          <span>Muñoz Bike Rental</span>
        </a>
        <div className="sidebar-nav-label">Operations</div>
        <a className="sidebar-link" href="/">
          <ArrowLeft size={17} /> Today&apos;s queue
        </a>
        <a className="sidebar-link active" href="/staff/extensions">
          <Clock3 size={17} /> Extension requests
        </a>
      </aside>

      <main className="product-main">
        <div className="page-heading ops-heading">
          <div>
            <span className="micro-label">Staff decisions</span>
            <h1>Extension requests.</h1>
            <p>Take exact payment, verify GCash, then approve the new due time.</p>
          </div>
        </div>

        {queue.error && (
          <div className="async-note error">
            <span>{queue.error}</span>
            <button type="button" onClick={queue.reload}>Try again</button>
          </div>
        )}
        {queue.loading && !queue.data && <p>Loading extension requests…</p>}
        {!queue.loading && !queue.error && extensions.length === 0 && (
          <section className="rides-list-card">
            <p>No extension requests yet.</p>
          </section>
        )}

        <div className="staff-extension-grid">
          {extensions.map((row) => {
            const rental = row.rental_id ? rentalById.get(row.rental_id) : undefined;
            const busy = busyId === row.id;
            return (
              <section className="staff-extension-card" key={row.id}>
                <div className="card-title-row">
                  <div>
                    <span className="micro-label">
                      {row.booking_ref ?? row.id.slice(0, 8)}
                    </span>
                    <h2>{row.customer_name}</h2>
                    <p className="handoff-email">{row.customer_email}</p>
                  </div>
                  <span className={row.extension_applied_at ? "app-pill pill-paid" : "app-pill pill-neutral"}>
                    {extensionStatus(row)}
                  </span>
                </div>

                <div className="staff-extension-bike">
                  <BikeArt
                    type={rental?.bike_type ?? null}
                    imageUrl={rental?.bike_image_url}
                    alt={rental?.bike_name ?? "Rental bike"}
                  />
                  <div>
                    <span className="bike-kind">
                      {rental?.bike_type ? BIKE_TYPE_LABELS[rental.bike_type] : "Rental"}
                    </span>
                    <h3>{rental?.bike_name ?? "Bike"}</h3>
                    <p>
                      Current due: {formatDateTimeLabel(rental?.due_at ?? null) ?? "—"}
                    </p>
                  </div>
                </div>

                <dl className="staff-extension-details">
                  <div><dt>Period</dt><dd>{row.rate_selected === "weekly" ? "One week" : "One day"}</dd></div>
                  <div><dt>Exact total</dt><dd>{formatPeso(row.total_price)}</dd></div>
                  <div><dt>Payment</dt><dd>{row.payment_method === "gcash" ? "GCash" : "Cash"}</dd></div>
                </dl>

                {row.gcash_ref_no && <p className="handoff-meta">GCash ref: {row.gcash_ref_no}</p>}
                {row.gcash_receipt_url && (
                  <a href={row.gcash_receipt_url} target="_blank" rel="noreferrer">
                    <img className="staff-extension-receipt" src={row.gcash_receipt_url} alt="GCash receipt" />
                  </a>
                )}

                <div className="staff-extension-actions">
                  {row.payment_method === "cash" &&
                    row.payment_status === "unpaid_pending_pickup" && (
                      <button
                        className="primary-button"
                        type="button"
                        disabled={busy}
                        onClick={() => void run(row, "Cash recorded", () => api.recordCash(row.id))}
                      >
                        Record exact cash
                      </button>
                    )}
                  {row.payment_method === "gcash" &&
                    row.payment_status === "pending_verification" && (
                      <>
                        <button
                          className="primary-button"
                          type="button"
                          disabled={busy}
                          onClick={() => void run(row, "GCash accepted", () => api.verifyGcash(row.id, "accepted"))}
                        >
                          Accept GCash
                        </button>
                        <button
                          className="ghost-action"
                          type="button"
                          disabled={busy}
                          onClick={() => void run(row, "GCash rejected", () => api.verifyGcash(row.id, "rejected"))}
                        >
                          Reject
                        </button>
                      </>
                    )}
                  {row.payment_status === "paid" && !row.extension_applied_at && (
                    <button
                      className="primary-button"
                      type="button"
                      disabled={busy}
                      onClick={() => void run(row, "Extension approved", () => api.approveExtension(row.id))}
                    >
                      Approve extension <ArrowUpRight size={15} />
                    </button>
                  )}
                  {row.extension_applied_at && (
                    <span className="extension-approved-note">
                      <CheckCircle2 size={16} /> Due time updated
                    </span>
                  )}
                </div>
              </section>
            );
          })}
        </div>
      </main>
    </div>
  );
}
