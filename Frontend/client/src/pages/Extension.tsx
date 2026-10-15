import { BikeArt, BrandMark } from "@/components/Artwork";
import { useAuth } from "@/contexts/AuthContext";
import { useMyBookings } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { formatDateTimeLabel, formatPeso } from "@/lib/format";
import type { PaymentMethod, RateSelected } from "@/lib/types";
import { ArrowLeft, CheckCircle2, FileCheck2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { useRoute } from "wouter";

export default function Extension() {
  const [, params] = useRoute("/extensions/:rentalId");
  const { session, loading: authLoading } = useAuth();
  const bookings = useMyBookings();
  const rental = bookings.data
    ?.flatMap((booking) => booking.rentals)
    .find((item) => item.id === params?.rentalId);

  const [rate, setRate] = useState<RateSelected>("daily");
  const [payment, setPayment] = useState<PaymentMethod>("cash");
  const [reference, setReference] = useState("");
  const [receiptUrl, setReceiptUrl] = useState("");
  const [receiptName, setReceiptName] = useState("");
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [confirmedRef, setConfirmedRef] = useState<string | null>(null);

  const price = rate === "weekly" ? rental?.bike_weekly_rate : rental?.bike_daily_rate;

  const uploadReceipt = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/") || file.size > 8 * 1024 * 1024) {
      toast.warning("Use an image under 8 MB");
      return;
    }
    setUploading(true);
    try {
      const result = await api.uploadReceipt(file);
      setReceiptUrl(result.url);
      setReceiptName(file.name);
    } catch (cause) {
      toast.error(cause instanceof ApiError ? cause.message : "Receipt upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const submit = async () => {
    if (!rental || !price) return;
    if (payment === "gcash" && (!reference.trim() || !receiptUrl)) {
      toast.warning("Add the GCash reference and receipt");
      return;
    }
    setSubmitting(true);
    try {
      const extension = await api.createExtension(rental.id, {
        rate_selected: rate,
        payment_method: payment,
        ...(payment === "gcash"
          ? {
              gcash_ref_no: reference.trim(),
              gcash_receipt_url: receiptUrl,
            }
          : {}),
      });
      setConfirmedRef(extension.booking_ref ?? extension.id.slice(0, 8));
      bookings.reload();
    } catch (cause) {
      toast.error(cause instanceof ApiError ? cause.message : "Could not request extension.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="extension-page">
      <header className="extension-header">
        <a className="app-brand" href="/">
          <span className="app-brand-mark"><BrandMark /></span>
          <span>Muñoz Bike Rental</span>
        </a>
        <a className="quiet-link" href="/"><ArrowLeft size={14} /> Back to My Rides</a>
      </header>

      <div className="extension-shell">
        {confirmedRef ? (
          <section className="extension-card extension-confirmed">
            <CheckCircle2 size={42} />
            <span className="micro-label">Request received</span>
            <h1>Extension requested.</h1>
            <p>
              Reference {confirmedRef}. The exact amount must be paid and approved by
              staff before your due time changes.
            </p>
            <a className="primary-button" href="/">Return to My Rides</a>
          </section>
        ) : authLoading || bookings.loading ? (
          <section className="extension-card"><p>Loading your rental…</p></section>
        ) : !session ? (
          <section className="extension-card">
            <h1>Sign in required.</h1>
            <p>Please sign in from the home page to extend your rental.</p>
            <a className="primary-button" href="/">Return home</a>
          </section>
        ) : bookings.error ? (
          <section className="extension-card">
            <h1>Could not load this rental.</h1>
            <p>{bookings.error}</p>
            <button className="secondary-button" type="button" onClick={bookings.reload}>Try again</button>
          </section>
        ) : !rental || rental.status !== "active" ? (
          <section className="extension-card">
            <h1>Rental unavailable.</h1>
            <p>This rental was not found or is no longer active.</p>
            <a className="primary-button" href="/">Return to My Rides</a>
          </section>
        ) : (
          <>
            <section className="extension-intro">
              <span className="micro-label">Rental extension</span>
              <h1>Keep the ride going.</h1>
              <p>
                Choose an additional day or week. Staff applies the new due time only
                after exact payment.
              </p>
              <div className="extension-bike">
                <BikeArt
                  type={rental.bike_type}
                  imageUrl={rental.bike_image_url}
                  alt={rental.bike_name ?? "Bike"}
                />
                <div>
                  <span className="bike-kind">Your current bike</span>
                  <h2>{rental.bike_name ?? "Bike"}</h2>
                  <p>Currently due {formatDateTimeLabel(rental.due_at)}</p>
                </div>
              </div>
            </section>

            <section className="extension-card">
              <span className="micro-label">Extension details</span>
              <div className="form-grid extension-form-grid">
                <label className="field-block">
                  <span>Extension period</span>
                  <select value={rate} onChange={(event) => setRate(event.target.value as RateSelected)}>
                    <option value="daily">One additional day</option>
                    <option value="weekly" disabled={!rental.bike_weekly_rate}>One additional week</option>
                  </select>
                </label>
                <label className="field-block">
                  <span>Payment method</span>
                  <select value={payment} onChange={(event) => setPayment(event.target.value as PaymentMethod)}>
                    <option value="cash">Exact cash at the counter</option>
                    <option value="gcash">GCash</option>
                  </select>
                </label>
              </div>

              {payment === "gcash" && (
                <div className="form-grid extension-form-grid">
                  <label className="field-block">
                    <span>GCash reference number</span>
                    <input value={reference} onChange={(event) => setReference(event.target.value)} />
                  </label>
                  <label className={receiptUrl ? "field-block upload-proof uploaded" : "field-block upload-proof"}>
                    <input
                      type="file"
                      accept="image/*"
                      disabled={uploading}
                      onChange={(event) => {
                        void uploadReceipt(event.target.files?.[0]);
                        event.target.value = "";
                      }}
                    />
                    <span>
                      {uploading ? "Uploading…" : receiptUrl ? <><FileCheck2 size={14} /> {receiptName}</> : "Upload receipt"}
                    </span>
                  </label>
                </div>
              )}

              <div className="extension-total">
                <span>Exact extension total</span>
                <strong>{price ? formatPeso(price) : "Unavailable"}</strong>
              </div>
              <p className="extension-note">
                Submitting does not change your current due time. Staff must first
                confirm exact payment and approve the extension.
              </p>
              <button
                className="primary-button full-button"
                type="button"
                disabled={submitting || uploading || !price}
                onClick={submit}
              >
                {submitting ? "Sending request…" : "Request extension"}
              </button>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
