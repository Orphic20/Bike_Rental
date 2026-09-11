/**
 * Mirrors the response models in `src/bike_rental/models.py`.
 *
 * Money arrives as a string: the backend columns are `numeric(10,2)` and
 * Pydantic serialises Decimal to a string in JSON mode to avoid float drift.
 * Use `toAmount` from `@/lib/format` before doing arithmetic on it.
 */

export type BikeType = "japanese" | "folding" | "mountain";

export type BikeStatus = "available" | "rented" | "maintenance" | "retired";

export type PaymentMethod = "gcash" | "cash";

export type PaymentStatus =
  | "pending_verification"
  | "unpaid_pending_pickup"
  | "paid"
  | "refunded"
  | "cancelled"
  | "rejected";

export type RateSelected = "daily" | "weekly";

export type BookingType = "new" | "extension";

export type RentalStatus =
  | "reserved"
  | "active"
  | "overdue"
  | "returned"
  | "cancelled"
  | "no_show";

export type RoleName = "customer" | "staff" | "admin";

export interface Bike {
  id: string;
  name: string;
  type: BikeType;
  status: BikeStatus;
  daily_rate: string;
  weekly_rate: string | null;
  image_url: string | null;
  available: boolean;
}

export interface User {
  id: string;
  email: string;
  name: string;
  role: RoleName;
  created_at: string | null;
  name_confirmed: boolean;
  tos_version_accepted: string | null;
  tos_accepted_at: string | null;
  is_active: boolean;
}

export interface Rental {
  id: string;
  bike_id: string;
  bike_name: string | null;
  bike_type: BikeType | null;
  released_at: string | null;
  due_at: string | null;
  returned_at: string | null;
  price: string;
  status: RentalStatus;
}

export interface Booking {
  id: string;
  booking_ref: string | null;
  expected_pickup_date: string;
  rate_selected: RateSelected;
  total_price: string;
  amount_paid: string;
  balance_due: string;
  payment_method: PaymentMethod;
  payment_status: PaymentStatus;
  booking_type: BookingType;
  created_at: string | null;
  rentals: Rental[];
}

export interface StaffBooking extends Booking {
  customer_name: string;
  customer_email: string;
  gcash_ref_no: string | null;
  gcash_receipt_url: string | null;
}

export interface BookingCreate {
  bikes: { bike_id: string }[];
  expected_pickup_date: string;
  rate_selected: RateSelected;
  payment_method: PaymentMethod;
  gcash_ref_no?: string | null;
  gcash_receipt_url?: string | null;
  waiver_version: string;
}

export const BIKE_TYPE_LABELS: Record<BikeType, string> = {
  japanese: "Japanese bike",
  folding: "Folding bike",
  mountain: "Mountain bike",
};

export const PAYMENT_STATUS_LABELS: Record<PaymentStatus, string> = {
  pending_verification: "GCash verification",
  unpaid_pending_pickup: "Pay at pickup",
  paid: "Paid",
  refunded: "Refunded",
  cancelled: "Cancelled",
  rejected: "Rejected",
};

export const RENTAL_STATUS_LABELS: Record<RentalStatus, string> = {
  reserved: "Reserved",
  active: "Active",
  overdue: "Overdue",
  returned: "Returned",
  cancelled: "Cancelled",
  no_show: "No show",
};
