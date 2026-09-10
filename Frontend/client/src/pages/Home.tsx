/*
  Coastal Utility Atelier: warm daylight, editorial asymmetry, crisp rental utility,
  tactile artwork, and restrained clay-red interaction cues.

  The customer path (landing, catalogue, booking, my rides) runs on the FastAPI
  service. The staff and admin screens are still local prototypes because their
  routers do not expose endpoints yet; they are labelled as such in the UI.
*/
import { AuthDialog } from "@/components/AuthDialog";
import foldingBike from "@/assets/folding-bike.jpg";
import japaneseBike from "@/assets/japanese-bike.jpg";
import lingapRouteCard from "@/assets/lingap_routecard.jpg";
import mountainBike from "@/assets/mountain-bike.jpg";
import munozBikeFront from "@/assets/munoz-bike-front.png";
import { BikeArt, BrandMark } from "@/components/Artwork";
import { MapView } from "@/components/Map";
import { useAuth } from "@/contexts/AuthContext";
import { useBikes, useMyBookings } from "@/hooks/useApi";
import { api, ApiError } from "@/lib/api";
import { CLSU_POSITION, WAIVER_VERSION } from "@/lib/constants";
import {
  formatDateLabel,
  formatDateTimeLabel,
  formatPeso,
  toAmount,
  todayIso,
} from "@/lib/format";
import {
  BIKE_TYPE_LABELS,
  PAYMENT_STATUS_LABELS,
  RENTAL_STATUS_LABELS,
  type Bike,
  type BikeType,
  type Booking,
  type PaymentMethod,
  type RateSelected,
} from "@/lib/types";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowRight,
  ArrowUpRight,
  Bike as BikeIcon,
  CalendarDays,
  Check,
  CheckCircle2,
  ChevronDown,
  ClipboardCheck,
  Clock3,
  CreditCard,
  FileCheck2,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  MapPin,
  Menu,
  MoreHorizontal,
  PackageCheck,
  Search,
  Settings2,
  ShieldCheck,
  UserRound,
  Users,
  WalletCards,
  X,
} from "lucide-react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

type View = "landing" | "selection" | "customer" | "staff" | "admin";

const BIKE_TYPES: BikeType[] = ["japanese", "folding", "mountain"];

const TYPE_COPY: Record<BikeType, { tint: string; tagline: string; blurb: string; photo: string }> = {
  japanese: {
    tint: "selection-sage",
    tagline: "City comfort",
    blurb: "Upright comfort, baskets, and an easy pace for the waterfront.",
    photo: japaneseBike,
  },
  folding: {
    tint: "selection-clay",
    tagline: "Compact utility",
    blurb: "Small, nimble, and ready for the city between stops.",
    photo: foldingBike,
  },
  mountain: {
    tint: "selection-forest",
    tagline: "Trail ready",
    blurb: "Confident control for open roads, climbs, and the edge of town.",
    photo: mountainBike,
  },
};

function rateFor(bike: Bike, rate: RateSelected): number {
  return toAmount(rate === "weekly" ? bike.weekly_rate : bike.daily_rate);
}

function Pill({ children, tone = "neutral" }: { children: React.ReactNode; tone?: string }) {
  return <span className={`app-pill pill-${tone}`}>{children}</span>;
}

function AsyncNote({
  message,
  onRetry,
  tone = "info",
}: {
  message: string;
  onRetry?: () => void;
  tone?: "info" | "error";
}) {
  return (
    <div className={tone === "error" ? "async-note is-error" : "async-note"} role="status">
      {tone === "error" && <AlertTriangle size={15} />}
      <span>{message}</span>
      {onRetry && (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}

// =============================================================================
// Header
// =============================================================================

function AppHeader({
  view,
  setView,
  onRequestSignIn,
}: {
  view: View;
  setView: (view: View) => void;
  onRequestSignIn: () => void;
}) {
  const { session, profile, signOut } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);

  const role = profile?.role;
  const tabs: { id: View; label: string }[] = [
    { id: "landing", label: "Home" },
    { id: "selection", label: "Bikes" },
    { id: "customer", label: "My rides" },
  ];
  // Staff and admin surfaces only exist for accounts the backend says hold that
  // role, rather than being open to every visitor as in the prototype.
  if (role === "staff" || role === "admin") tabs.push({ id: "staff", label: "Staff" });
  if (role === "admin") tabs.push({ id: "admin", label: "Admin" });

  const initials = (profile?.name ?? profile?.email ?? "")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("");

  return (
    <>
      <div className="app-topline">
        <span className="topline-date">
          Today · {formatDateLabel(todayIso())}
        </span>
      </div>
      <header className="app-header">
        <button
          className="app-brand"
          onClick={() => setView("landing")}
          aria-label="Go to Muñoz Bike Rental home"
        >
          <span className="app-brand-mark">
            <BrandMark />
          </span>
          <span>Muñoz Bike Rental</span>
        </button>

        <nav className="role-switcher" aria-label="Main navigation">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              className={view === tab.id ? "role-tab active" : "role-tab"}
              onClick={() => setView(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>

        <div className="app-header-actions">
          {session && profile ? (
            <>
              <button
                className="header-icon-button"
                onClick={() => {
                  void signOut();
                  toast.success("Signed out");
                  setView("landing");
                }}
                aria-label="Sign out"
              >
                <LogOut size={17} />
              </button>
              <button className="profile-chip" onClick={() => setView("customer")}>
                <span className="avatar">{initials || "MB"}</span>
                <span className="profile-name">{profile.name || profile.email}</span>
                <ChevronDown size={13} />
              </button>
            </>
          ) : (
            <button className="sign-in-button" onClick={onRequestSignIn}>
              <UserRound size={15} /> Sign in
            </button>
          )}
          <button
            className="mobile-menu-button"
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
          >
            {menuOpen ? <X size={19} /> : <Menu size={19} />}
          </button>
        </div>
      </header>
    </>
  );
}

// =============================================================================
// Landing
// =============================================================================

function LandingView({ onBook }: { onBook: (type?: BikeType) => void }) {
  const { data: bikes, loading, error, reload } = useBikes(null, "daily");
  const [activeType, setActiveType] = useState<BikeType>("japanese");

  // One representative price per type: the cheapest bike currently in service.
  const summary = useMemo(() => {
    const map = new Map<BikeType, { from: number; count: number }>();
    for (const bike of bikes ?? []) {
      const price = toAmount(bike.daily_rate);
      const current = map.get(bike.type);
      map.set(bike.type, {
        from: current ? Math.min(current.from, price) : price,
        count: (current?.count ?? 0) + 1,
      });
    }
    return map;
  }, [bikes]);

  const current = summary.get(activeType);

  return (
    <main className="landing-page">
      <section className="landing-hero">
        <div className="landing-hero-copy">
          <span className="landing-eyebrow">
            <span className="eyebrow-rule" /> Muñoz Bike Rental · Bagong Sikat
          </span>
          <h1>
            Take the <em>long way</em>
            <br />
            home.
          </h1>
          <p>
            Good bikes for slow mornings, salty air, and every unexpected turn. Pick
            one up by the kiosk and make a day of it.
          </p>
          <div className="landing-actions">
            <button className="primary-button landing-cta" onClick={() => onBook()}>
              Find your bike <ArrowRight size={16} />
            </button>
            <a className="quiet-link" href="#landing-way">
              See how it works <ArrowDownRight size={15} />
            </a>
          </div>
          <div className="landing-proof">
            <span>
              <CheckCircle2 size={15} /> No payment until pickup
            </span>
          </div>
        </div>
        <div className="landing-hero-art">
          <img src={munozBikeFront} alt="A Muñoz Bike Rental ride on a Muñoz street" />
          <div className="landing-art-overlay" />
          <span className="landing-art-stamp">
            MBR
            <br />
            <small>SINCE 2018</small>
          </span>
          <span className="landing-art-caption">
            <MapPin size={13} /> Bagong Sikat Science City of Muñoz
          </span>
        </div>
      </section>

      <section className="landing-booking-rail">
        <div>
          <span className="micro-label">Start with a day</span>
          <strong>Your bike is waiting.</strong>
        </div>
        <div className="landing-rail-detail">
          <span>
            <CalendarDays size={16} /> Today, {formatDateLabel(todayIso())}
          </span>
          <span>
            <Clock3 size={16} />{" "}
            Daily from {formatPeso(50)}
          </span>
          <span>
            <MapPin size={16} /> Bagong Sikat
          </span>
        </div>
        <button className="secondary-button landing-rail-button" onClick={() => onBook()}>
          Check availability <ArrowUpRight size={14} />
        </button>
      </section>

      <section className="landing-fleet" id="landing-fleet">
        <div className="landing-section-head">
          <div>
            <span className="landing-eyebrow">
              <span className="eyebrow-rule" /> The fleet
            </span>
            <h2>
              Choose your <em>kind</em>
              <br />
              of day.
            </h2>
          </div>
          <div>
            <p>
              Three ways to move through the city. Every bike is tuned, tire-checked,
              and ready to roll.
            </p>
            <a href="#landing-way" className="underlined-link">
              Find your route <ArrowUpRight size={13} />
            </a>
          </div>
        </div>

        {error ? (
          <AsyncNote tone="error" message={error} onRetry={reload} />
        ) : (
          <div className="landing-fleet-grid">
            <div className="landing-bike-list">
              {BIKE_TYPES.map((type, index) => {
                const entry = summary.get(type);
                return (
                  <button
                    key={type}
                    className={activeType === type ? "landing-bike-tab active" : "landing-bike-tab"}
                    onClick={() => setActiveType(type)}
                  >
                    <span className="landing-bike-no">0{index + 1}</span>
                    <span>
                      <small>{TYPE_COPY[type].tagline}</small>
                      <strong>{BIKE_TYPE_LABELS[type]}</strong>
                    </span>
                    <span className="landing-bike-price">
                      {loading ? "…" : entry ? formatPeso(entry.from) : "—"}
                      <small>/ day</small>
                    </span>
                    <ArrowUpRight size={15} />
                  </button>
                );
              })}
            </div>
            <div className="landing-feature-bike">
              <img
                src={TYPE_COPY[activeType].photo}
                alt={BIKE_TYPE_LABELS[activeType]}
              />
              <div className="landing-feature-copy">
                <span className="bike-kind">{TYPE_COPY[activeType].tagline}</span>
                <h3>{BIKE_TYPE_LABELS[activeType]}</h3>
                <p>{TYPE_COPY[activeType].blurb}</p>
                {!loading && (
                  <span className="micro-label">
                    {current
                      ? `${current.count} in the fleet`
                      : "None in the fleet yet"}
                  </span>
                )}
                <button className="primary-button" onClick={() => onBook(activeType)}>
                  Reserve a bike <ArrowUpRight size={14} />
                </button>
              </div>
            </div>
          </div>
        )}
      </section>

      <section className="landing-way" id="landing-way">
        <div className="landing-way-copy">
          <span className="landing-eyebrow">
            <span className="eyebrow-rule" /> A slower way through the city
          </span>
          <h2>
            Less planning.
            <br />
            <em>More noticing.</em>
          </h2>
          <p>
            We keep the process simple, the bikes comfortable, and the best routes
            close at hand.
          </p>
          <div className="landing-route-row">
            <div>
              <strong>01</strong>
              <span>
                Lingap loop
                <br />
                <small>35 minutes · easy</small>
              </span>
            </div>
            <div>
              <strong>02</strong>
              <span>
                Oval loop
                <br />
                <small>40 minutes · easy</small>
              </span>
            </div>
            <div>
              <strong>03</strong>
              <span>
                CLSU Loop
                <br />
                <small>2 hours · chill</small>
              </span>
            </div>
          </div>
        </div>
        <div className="landing-way-card">
          <div className="landing-route-illustration">
            <img src={lingapRouteCard} alt="Lingap loop route through Muñoz" />
          </div>
          <span className="micro-label">Route card</span>
          <strong>Lingap loop</strong>
          <span>Ask us at the shop for today's favorite loop.</span>
        </div>
      </section>

      <section className="landing-visit">
        <div>
          <span className="landing-eyebrow">
            <span className="eyebrow-rule" /> Come find us
          </span>
          <h2>
            Meet us near
            <br />
            <em>CLSU.</em>
          </h2>
        </div>
        <div className="landing-visit-meta">
          <span>
            <MapPin size={16} /> Bagong Sikat Science City of Muñoz
          </span>
          <span>
            <Clock3 size={16} /> Every day · 8am—7pm
          </span>
          <button className="primary-button" onClick={() => onBook()}>
            Book a bike <ArrowUpRight size={14} />
          </button>
        </div>
        <CLSULocationMap />
      </section>
    </main>
  );
}

function CLSULocationMap() {
  const [pinOpen, setPinOpen] = useState(true);
  const [mapReady, setMapReady] = useState(false);

  return (
    <div className="clsu-map-shell">
      <MapView
        className="clsu-map"
        initialCenter={CLSU_POSITION}
        initialZoom={15}
        onMapReady={(map) => {
          setMapReady(true);
          const marker = new window.google!.maps.marker.AdvancedMarkerElement({
            map,
            position: CLSU_POSITION,
            title: "Muñoz Bike Rental near CLSU",
          });
          marker.addListener("click", () => setPinOpen(true));
        }}
      />
      <div
        className={mapReady ? "clsu-map-fallback is-hidden" : "clsu-map-fallback"}
        aria-label="Illustrated map showing the CLSU location"
      >
        <span className="fallback-road road-one" />
        <span className="fallback-road road-two" />
        <span className="fallback-road road-three" />
        <span className="fallback-campus">CLSU</span>
        <button
          className="clsu-fallback-pin"
          onClick={() => setPinOpen(true)}
          aria-label="Show Muñoz Bike Rental near CLSU"
        >
          <MapPin size={20} fill="currentColor" />
        </button>
      </div>
      {pinOpen ? (
        <button
          className="clsu-map-pin-card"
          onClick={() => setPinOpen(false)}
          aria-label="Close CLSU location card"
        >
          <span className="clsu-pin-mark">
            <MapPin size={15} fill="currentColor" />
          </span>
          <span>
            <strong>Muñoz Bike Rental near CLSU</strong>
            <small>Bagong Sikat · Science City of Muñoz</small>
          </span>
          <X size={14} />
        </button>
      ) : (
        <button
          className="clsu-reopen-pin"
          onClick={() => setPinOpen(true)}
          aria-label="Show CLSU location details"
        >
          <MapPin size={15} /> Show location
        </button>
      )}
    </div>
  );
}

// =============================================================================
// Catalogue
// =============================================================================

function SelectionView({
  cart,
  setCart,
  stylePage,
  setStylePage,
  pickupDate,
  setPickupDate,
  rate,
  setRate,
  onContinue,
}: {
  cart: Bike[];
  setCart: React.Dispatch<React.SetStateAction<Bike[]>>;
  stylePage: BikeType | null;
  setStylePage: (type: BikeType | null) => void;
  pickupDate: string | null;
  setPickupDate: (date: string | null) => void;
  rate: RateSelected;
  setRate: (rate: RateSelected) => void;
  onContinue: () => void;
}) {
  const { data: bikes, loading, error, reload } = useBikes(pickupDate, rate);
  const [dateModalOpen, setDateModalOpen] = useState(false);
  const [dateMode, setDateMode] = useState<"today" | "reserve">("today");
  const [draftDate, setDraftDate] = useState(todayIso());
  const [pendingBike, setPendingBike] = useState<Bike | null>(null);

  const byType = useMemo(() => {
    const map = new Map<BikeType, Bike[]>();
    for (const type of BIKE_TYPES) map.set(type, []);
    for (const bike of bikes ?? []) map.get(bike.type)?.push(bike);
    return map;
  }, [bikes]);

  const isInCart = (id: string) => cart.some((item) => item.id === id);
  const cartTotal = cart.reduce((sum, item) => sum + rateFor(item, rate), 0);

  const openDatePrompt = (bike: Bike | null = null) => {
    setPendingBike(bike);
    setDateMode(pickupDate && pickupDate !== todayIso() ? "reserve" : "today");
    setDraftDate(pickupDate ?? todayIso());
    setDateModalOpen(true);
  };

  const addToBooking = (bike: Bike) => {
    if (!pickupDate) {
      openDatePrompt(bike);
      return;
    }
    setCart((current) =>
      current.some((item) => item.id === bike.id) ? current : [...current, bike],
    );
  };

  const removeFromBooking = (bike: Bike) =>
    setCart((current) => current.filter((item) => item.id !== bike.id));

  const confirmDates = () => {
    const next = dateMode === "today" ? todayIso() : draftDate;
    setPickupDate(next);
    if (pendingBike) {
      setCart((current) =>
        current.some((item) => item.id === pendingBike.id)
          ? current
          : [...current, pendingBike],
      );
    }
    setPendingBike(null);
    setDateModalOpen(false);
  };

  const dateLabel = pickupDate ? `Pick up · ${formatDateLabel(pickupDate)}` : null;

  const datePrompt = dateModalOpen && (
    <div
      className="booking-date-modal-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) setDateModalOpen(false);
      }}
    >
      <div
        className="booking-date-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="booking-date-title"
      >
        <button
          className="booking-date-close"
          onClick={() => setDateModalOpen(false)}
          aria-label="Close date prompt"
        >
          <X size={17} />
        </button>
        <span className="landing-eyebrow">
          <span className="eyebrow-rule" /> Plan your ride
        </span>
        <h2 id="booking-date-title">When are you riding?</h2>
        <p>
          {pendingBike
            ? `Choose a pickup date before adding ${pendingBike.name} to your group booking.`
            : "Set a pickup date so we can check the fleet against it."}
        </p>
        <div className="date-prompt-options">
          <button
            className={dateMode === "today" ? "date-prompt-option active" : "date-prompt-option"}
            onClick={() => setDateMode("today")}
          >
            <span className="choice-radio" />
            <span>
              <strong>Book today</strong>
              <small>{formatDateLabel(todayIso())} · pickup from 9:30 AM</small>
            </span>
          </button>
          <button
            className={dateMode === "reserve" ? "date-prompt-option active" : "date-prompt-option"}
            onClick={() => setDateMode("reserve")}
          >
            <span className="choice-radio" />
            <span>
              <strong>Reserve dates</strong>
              <small>Choose your pickup date</small>
            </span>
          </button>
        </div>
        {dateMode === "reserve" && (
          <div className="date-prompt-fields single-date-field">
            <label>
              Pick up date
              <input
                type="date"
                value={draftDate}
                min={todayIso()}
                onChange={(event) => setDraftDate(event.target.value)}
              />
            </label>
          </div>
        )}
        <button className="primary-button full-button" onClick={confirmDates}>
          {pendingBike ? `Add ${pendingBike.name} to group booking` : "Show availability"}{" "}
          <ArrowRight size={15} />
        </button>
        <span className="modal-note">
          Availability is checked against live reservations for the date you choose.
        </span>
      </div>
    </div>
  );

  if (!stylePage) {
    return (
      <main className="style-page">
        <div className="style-page-head">
          <div>
            <span className="landing-eyebrow">
              <span className="eyebrow-rule" /> Step 01 · Choose a bike style
            </span>
            <h1>
              Find your
              <br />
              <em>kind</em> of ride.
            </h1>
            <p>
              Explore the fleet first. Choose a style, then open its page to see every
              bike we have in that shape.
            </p>
          </div>
          <div className="style-cart-summary">
            <span className="micro-label">Your group booking</span>
            <strong>
              {cart.length} bike{cart.length === 1 ? "" : "s"}
            </strong>
            <span>{dateLabel ?? "Choose a pickup date first"}</span>
          </div>
          <button className="style-date-button" onClick={() => openDatePrompt()}>
            <CalendarDays size={15} />
            <span>{pickupDate ? "Change pickup date" : "Choose pickup date"}</span>
            <ArrowUpRight size={14} />
          </button>
        </div>
        {datePrompt}
        {error && <AsyncNote tone="error" message={error} onRetry={reload} />}
        <div className="style-page-list">
          {BIKE_TYPES.map((type, index) => {
            const count = byType.get(type)?.length ?? 0;
            const free = byType.get(type)?.filter((bike) => bike.available).length ?? 0;
            return (
              <button
                key={type}
                className={`style-page-card ${TYPE_COPY[type].tint}`}
                onClick={() => setStylePage(type)}
              >
                <div className="style-page-image">
                  <img src={TYPE_COPY[type].photo} alt={BIKE_TYPE_LABELS[type]} />
                  <span className="selection-number">0{index + 1}</span>
                  <span className="style-page-arrow">
                    <ArrowUpRight size={17} />
                  </span>
                </div>
                <div className="style-page-copy">
                  <span className="bike-kind">{TYPE_COPY[type].tagline}</span>
                  <h2>{BIKE_TYPE_LABELS[type]}</h2>
                  <p>{TYPE_COPY[type].blurb}</p>
                  <span className="style-page-link">
                    {loading
                      ? "Loading fleet…"
                      : pickupDate
                        ? `${free} of ${count} available`
                        : `View ${count} bike${count === 1 ? "" : "s"}`}{" "}
                    <ArrowRight size={14} />
                  </span>
                </div>
              </button>
            );
          })}
        </div>
      </main>
    );
  }

  const bikesOfType = byType.get(stylePage) ?? [];

  return (
    <>
      <main className="selection-page">
        <div className="selection-intro">
          <span className="landing-eyebrow">
            <span className="eyebrow-rule" /> Step 02 · {BIKE_TYPE_LABELS[stylePage]}
          </span>
          <h1>
            Choose your
            <br />
            <em>bike.</em>
          </h1>
          <p>
            Add one or build a group booking without leaving the catalogue.
          </p>
          <button className="selection-back" onClick={() => setStylePage(null)}>
            <ArrowRight size={15} /> Back to bike styles
          </button>
        </div>

        <div className="selection-content">
          <div className="selection-topline">
            <span>
              {BIKE_TYPE_LABELS[stylePage]} ·{" "}
              {dateLabel ?? "Browse base rates"}
            </span>
            <button className="change-dates-link" onClick={() => openDatePrompt()}>
              {pickupDate ? "Change dates" : "Choose dates"} <ArrowUpRight size={13} />
            </button>
          </div>

          {error ? (
            <AsyncNote tone="error" message={error} onRetry={reload} />
          ) : loading ? (
            <div className="catalog-skeleton">
              <span />
              <span />
              <span />
            </div>
          ) : bikesOfType.length === 0 ? (
            <AsyncNote message="No bikes of this style are in the fleet yet." />
          ) : (
            <div className="selection-grid inventory-grid">
              {bikesOfType.map((bike, index) => {
                const selected = isInCart(bike.id);
                const blocked = !bike.available;
                return (
                  <article
                    key={bike.id}
                    className={`selection-card ${TYPE_COPY[bike.type].tint} ${
                      selected ? "selected" : ""
                    } ${blocked ? "is-unavailable" : ""}`}
                  >
                    <div className="selection-card-image">
                      <BikeArt type={bike.type} imageUrl={bike.image_url} alt={bike.name} />
                      {blocked && (
                        <span className="unavailable-chip">
                          {bike.status === "maintenance" ? "In maintenance" : "Booked"}
                        </span>
                      )}
                      {selected && (
                        <span className="selected-chip">
                          <Check size={12} /> In group booking
                        </span>
                      )}
                      <span className="selection-number">
                        {String(index + 1).padStart(2, "0")}
                      </span>
                    </div>
                    <div className="selection-card-copy">
                      <span className="bike-kind">{BIKE_TYPE_LABELS[bike.type]}</span>
                      <h2>{bike.name}</h2>
                      <p>
                        {rate === "weekly" && bike.weekly_rate === null
                          ? "No weekly rate for this bike."
                          : "Helmet · Lock · Ready to ride"}
                      </p>
                      <div>
                        <strong>{formatPeso(rateFor(bike, rate))}</strong>
                        <small> / {rate === "weekly" ? "week" : "day"}</small>
                        <button
                          className={selected ? "cart-action added" : "cart-action"}
                          disabled={blocked}
                          onClick={() =>
                            selected ? removeFromBooking(bike) : addToBooking(bike)
                          }
                        >
                          {selected ? (
                            <>
                              <Check size={14} /> Added
                            </>
                          ) : blocked ? (
                            "Unavailable"
                          ) : (
                            "+ Add to Group Booking"
                          )}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })}
            </div>
          )}

          <div className="selection-footer booking-summary-sticky">
            <div>
              <span className="micro-label">Booking summary</span>
              <strong>
                {cart.length
                  ? `${cart.length} bike${cart.length > 1 ? "s" : ""} · ${formatPeso(
                      cartTotal,
                    )} / ${rate === "weekly" ? "week" : "day"}`
                  : "Browse the fleet first"}
              </strong>
              <span>
                {dateLabel
                  ? `${dateLabel} · ${cart.length} selection${cart.length === 1 ? "" : "s"}`
                  : "Choose Book today or Reserve dates when adding your first bike."}
              </span>
            </div>
            <button className="primary-button" disabled={!cart.length} onClick={onContinue}>
              Continue with {cart.length} bike{cart.length === 1 ? "" : "s"}{" "}
              <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </main>
      {datePrompt}
    </>
  );
}

// =============================================================================
// Booking + My rides
// =============================================================================

function CustomerSidebar({
  screen,
  setScreen,
  rideCount,
}: {
  screen: string;
  setScreen: (screen: string) => void;
  rideCount: number;
}) {
  const { profile } = useAuth();
  return (
    <aside className="app-sidebar customer-sidebar">
      <div className="sidebar-intro">
        <span className="micro-label">Your account</span>
        <strong>{profile?.name || profile?.email || "Guest"}</strong>
        <span>
          {profile?.created_at
            ? `Member since ${new Date(profile.created_at).getFullYear()}`
            : "Welcome"}
        </span>
      </div>
      <div className="sidebar-nav-label">Menu</div>
      <button
        className={screen === "booking" ? "sidebar-link active" : "sidebar-link"}
        onClick={() => setScreen("booking")}
      >
        <CalendarDays size={17} /> Book a bike
      </button>
      <button
        className={screen === "rides" ? "sidebar-link active" : "sidebar-link"}
        onClick={() => setScreen("rides")}
      >
        <BikeIcon size={17} /> My rides
        {rideCount > 0 && <span className="nav-count">{rideCount}</span>}
      </button>
      <div className="sidebar-bottom">
        <div className="sidebar-help">
          <ShieldCheck size={17} />
          <span>
            <strong>Need a hand?</strong>
            <small>Ask us at the kiosk</small>
          </span>
        </div>
      </div>
    </aside>
  );
}

function CustomerView({
  cart,
  setCart,
  pickupDate,
  setPickupDate,
  rate,
  setRate,
  initialScreen,
  onBrowse,
}: {
  cart: Bike[];
  setCart: React.Dispatch<React.SetStateAction<Bike[]>>;
  pickupDate: string | null;
  setPickupDate: (date: string | null) => void;
  rate: RateSelected;
  setRate: (rate: RateSelected) => void;
  initialScreen: string;
  onBrowse: () => void;
}) {
  const { profile } = useAuth();
  const bookings = useMyBookings();
  const [screen, setScreen] = useState(initialScreen);
  const [step, setStep] = useState(1);
  const [payment, setPayment] = useState<PaymentMethod>("cash");
  const [receiptUrl, setReceiptUrl] = useState("");
  const [receiptName, setReceiptName] = useState("");
  const [uploadingReceipt, setUploadingReceipt] = useState(false);
  const [referenceNumber, setReferenceNumber] = useState("");
  const [waiver, setWaiver] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [confirmed, setConfirmed] = useState<Booking | null>(null);

  const total = cart.reduce((sum, bike) => sum + rateFor(bike, rate), 0);
  const weeklyUnavailable = cart.some((bike) => bike.weekly_rate === null);
  const activeRides =
    bookings.data?.filter((booking) =>
      booking.rentals.some((rental) =>
        ["reserved", "active", "overdue"].includes(rental.status),
      ),
    ) ?? [];

  const onReceiptFile = async (file: File | undefined) => {
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.warning("Use a receipt image", { description: "PNG, JPG, or WEBP." });
      return;
    }
    if (file.size > 8 * 1024 * 1024) {
      toast.warning("Image is too large", { description: "Keep it under 8 MB." });
      return;
    }
    setUploadingReceipt(true);
    try {
      const { url } = await api.uploadReceipt(file);
      setReceiptUrl(url);
      setReceiptName(file.name);
    } catch (cause) {
      setReceiptUrl("");
      setReceiptName("");
      toast.error("Receipt upload failed", {
        description:
          cause instanceof ApiError ? cause.message : "Could not upload the image.",
      });
    } finally {
      setUploadingReceipt(false);
    }
  };

  const submit = async () => {
    if (!pickupDate) {
      toast.warning("Choose a pickup date first");
      setStep(1);
      return;
    }
    setSubmitting(true);
    try {
      const booking = await api.createBooking({
        bikes: cart.map((bike) => ({ bike_id: bike.id })),
        expected_pickup_date: pickupDate,
        rate_selected: rate,
        payment_method: payment,
        gcash_ref_no: payment === "gcash" ? referenceNumber.trim() : null,
        gcash_receipt_url: payment === "gcash" ? receiptUrl.trim() : null,
        waiver_version: WAIVER_VERSION,
      });
      setConfirmed(booking);
      setCart([]);
      bookings.reload();
      toast.success("Reservation confirmed", {
        description: booking.booking_ref
          ? `Reference ${booking.booking_ref}`
          : "We'll have your bike ready.",
      });
    } catch (cause) {
      const message =
        cause instanceof ApiError ? cause.message : "Could not create the booking.";
      toast.error("Booking failed", { description: message });
      // A 409 means someone took the bike while the form was open, so the
      // catalogue the customer is looking at is stale.
      if (cause instanceof ApiError && cause.status === 409) setStep(1);
    } finally {
      setSubmitting(false);
    }
  };

  const next = () => {
    if (step === 3 && !waiver) {
      toast.warning("Accept the waiver", {
        description: "You must accept the waiver and Terms to continue.",
      });
      return;
    }
    if (step === 4 && payment === "gcash") {
      if (uploadingReceipt) {
        toast.warning("Receipt is still uploading");
        return;
      }
      if (!receiptUrl.trim() || !referenceNumber.trim()) {
        toast.warning("Add your GCash proof", {
          description: "A receipt photo and reference number are both required.",
        });
        return;
      }
    }
    if (step < 5) setStep(step + 1);
    else void submit();
  };

  if (screen === "rides") {
    return (
      <div className="product-layout">
        <CustomerSidebar screen={screen} setScreen={setScreen} rideCount={activeRides.length} />
        <main className="product-main">
          <MyRides bookings={bookings} onBookAnother={() => setScreen("booking")} />
        </main>
      </div>
    );
  }

  if (confirmed) {
    return (
      <div className="product-layout">
        <CustomerSidebar screen={screen} setScreen={setScreen} rideCount={activeRides.length} />
        <main className="product-main">
          <div className="flow-card">
            <div className="step-panel confirmation-panel">
              <span className="confirmation-icon">
                <CheckCircle2 size={27} />
              </span>
              <span className="step-overline">Reservation confirmed</span>
              <h2>{confirmed.booking_ref ?? "Your booking is in."}</h2>
              <p>
                {confirmed.payment_method === "cash"
                  ? "Pay the exact total in cash at Bagong Sikat. Your bikes are released once staff records the payment."
                  : "We'll verify your GCash receipt shortly. Your bikes are released once payment is confirmed."}
              </p>
              <div className="review-list">
                <div>
                  <span>Pickup</span>
                  <strong>{formatDateLabel(confirmed.expected_pickup_date)}</strong>
                </div>
                <div>
                  <span>Bikes</span>
                  <strong>{confirmed.rentals.length}</strong>
                </div>
                <div>
                  <span>Rate</span>
                  <strong>{confirmed.rate_selected === "weekly" ? "Weekly" : "Daily"}</strong>
                </div>
                <div>
                  <span>Payment</span>
                  <strong>{PAYMENT_STATUS_LABELS[confirmed.payment_status]}</strong>
                </div>
              </div>
              <div className="total-row">
                <span>Total</span>
                <strong>{formatPeso(confirmed.total_price)}</strong>
              </div>
              <div className="ride-actions">
                <button
                  className="primary-button"
                  onClick={() => {
                    setConfirmed(null);
                    setStep(1);
                    setScreen("rides");
                  }}
                >
                  View my rides <ArrowUpRight size={15} />
                </button>
                <button
                  className="ghost-action"
                  onClick={() => {
                    setConfirmed(null);
                    setStep(1);
                    onBrowse();
                  }}
                >
                  Book another ride
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="product-layout">
      <CustomerSidebar screen={screen} setScreen={setScreen} rideCount={activeRides.length} />
      <main className="product-main">
        <div className="page-heading">
          <div>
            <span className="micro-label">New reservation</span>
            <h1>Book your ride.</h1>
            <p>Set your date, choose your rate, and we'll have it waiting at the kiosk.</p>
          </div>
          <Pill tone="sage">
            <span className="status-dot" /> {cart.length} bike
            {cart.length === 1 ? "" : "s"} in cart
          </Pill>
        </div>

        {cart.length === 0 ? (
          <div className="flow-card">
            <div className="step-panel">
              <div className="step-panel-head">
                <div>
                  <span className="step-overline">Nothing selected yet</span>
                  <h2>Pick your bikes first.</h2>
                  <p>Head to the catalogue and add one or more bikes to this booking.</p>
                </div>
                <BikeIcon size={23} />
              </div>
              <button className="primary-button" onClick={onBrowse}>
                Browse the fleet <ArrowRight size={16} />
              </button>
            </div>
          </div>
        ) : (
          <div className="flow-layout">
            <section className="flow-card">
              <div className="flow-steps">
                {["Date", "Rate", "Your details", "Payment", "Confirm"].map((label, index) => (
                  <button
                    key={label}
                    className={
                      step === index + 1
                        ? "flow-step current"
                        : step > index + 1
                          ? "flow-step done"
                          : "flow-step"
                    }
                    onClick={() => setStep(index + 1)}
                  >
                    <span>{step > index + 1 ? <Check size={12} /> : index + 1}</span>
                    <small>{label}</small>
                  </button>
                ))}
              </div>

              {step === 1 && (
                <div className="step-panel">
                  <div className="step-panel-head">
                    <div>
                      <span className="step-overline">Step 01 / 05</span>
                      <h2>When are you riding?</h2>
                      <p>Reservations take a pickup date only; the return is set at the counter.</p>
                    </div>
                    <CalendarDays size={23} />
                  </div>
                  <div className="date-choice-grid">
                    <button
                      className={pickupDate === todayIso() ? "date-choice selected" : "date-choice"}
                      onClick={() => setPickupDate(todayIso())}
                    >
                      <span className="choice-radio" />
                      <div>
                        <small>Book today</small>
                        <strong>{formatDateLabel(todayIso())}</strong>
                        <span>Pickup from 9:30 AM</span>
                      </div>
                    </button>
                    <label
                      className={
                        pickupDate && pickupDate !== todayIso()
                          ? "date-choice selected"
                          : "date-choice"
                      }
                    >
                      <span className="choice-radio" />
                      <div>
                        <small>Reserve for later</small>
                        <input
                          type="date"
                          value={pickupDate ?? ""}
                          min={todayIso()}
                          onChange={(event) => setPickupDate(event.target.value || null)}
                        />
                      </div>
                      <CalendarDays size={18} />
                    </label>
                  </div>
                  <div className="field-row">
                    <div className="field-block">
                      <label>Pick up at</label>
                      <span className="select-field">
                        <MapPin size={16} /> Bagong Sikat
                      </span>
                    </div>
                  </div>
                </div>
              )}

              {step === 2 && (
                <div className="step-panel rate-only-panel">
                  <div className="step-panel-head">
                    <div>
                      <span className="step-overline">Step 02 / 05</span>
                      <h2>Choose your rate.</h2>
                      <p>One rate applies to every bike in this booking.</p>
                    </div>
                    <Clock3 size={23} />
                  </div>
                  <div className="rate-choice-stack">
                    <button
                      className={rate === "daily" ? "rate-choice selected" : "rate-choice"}
                      onClick={() => setRate("daily")}
                    >
                      <span className="choice-radio" />
                      <span>
                        <strong>Daily rate</strong>
                        <small>Best for a single day around the city</small>
                      </span>
                      <b>
                        {formatPeso(
                          cart.reduce((sum, bike) => sum + toAmount(bike.daily_rate), 0),
                        )}
                      </b>
                    </button>
                    <button
                      className={rate === "weekly" ? "rate-choice selected" : "rate-choice"}
                      disabled={weeklyUnavailable}
                      onClick={() => setRate("weekly")}
                    >
                      <span className="choice-radio" />
                      <span>
                        <strong>Weekly rate</strong>
                        <small>
                          {weeklyUnavailable
                            ? "One of your bikes has no weekly rate"
                            : "Best value for a longer stay"}
                        </small>
                      </span>
                      <b>
                        {weeklyUnavailable
                          ? "—"
                          : formatPeso(
                              cart.reduce((sum, bike) => sum + toAmount(bike.weekly_rate), 0),
                            )}
                      </b>
                    </button>
                  </div>
                  <div className="rate-cart-note">
                    <BikeIcon size={16} />
                    <span>
                      <strong>
                        {cart.length} bike{cart.length === 1 ? "" : "s"} in this booking
                      </strong>
                      <small>
                        All of them use the {rate === "weekly" ? "weekly" : "daily"} rate.
                      </small>
                    </span>
                  </div>
                </div>
              )}

              {step === 3 && (
                <div className="step-panel">
                  <div className="step-panel-head">
                    <div>
                      <span className="step-overline">Step 03 / 05</span>
                      <h2>Tell us who is riding.</h2>
                      <p>Your name must match the physical ID presented at pickup.</p>
                    </div>
                    <UserRound size={23} />
                  </div>
                  <div className="form-grid">
                    <div className="field-block full">
                      <label>Full government name</label>
                      <div className="input-field">
                        <UserRound size={16} />
                        <span>{profile?.name || "—"}</span>
                      </div>
                      <small className="field-note">
                        <FileCheck2 size={13} /> Must match the physical ID presented at pickup.
                      </small>
                    </div>
                    <div className="field-block">
                      <label>Email address</label>
                      <div className="input-field">
                        <span>{profile?.email || "—"}</span>
                      </div>
                    </div>
                  </div>
                  <label className={waiver ? "check-row checked" : "check-row"}>
                    <input
                      type="checkbox"
                      checked={waiver}
                      onChange={(event) => setWaiver(event.target.checked)}
                    />
                    <span className="fake-check">{waiver && <Check size={12} />}</span>
                    <span>
                      I agree to the <u>Liability Waiver</u> and <u>Terms of Service</u> (v
                      {WAIVER_VERSION}).
                    </span>
                  </label>
                </div>
              )}

              {step === 4 && (
                <div className="step-panel">
                  <div className="step-panel-head">
                    <div>
                      <span className="step-overline">Step 04 / 05</span>
                      <h2>How would you like to pay?</h2>
                      <p>
                        Every booking needs one exact full payment. No partial amounts, no
                        change.
                      </p>
                    </div>
                    <WalletCards size={23} />
                  </div>
                  <div className="payment-options">
                    <button
                      className={payment === "cash" ? "payment-option selected" : "payment-option"}
                      onClick={() => setPayment("cash")}
                    >
                      <span className="payment-radio" />
                      <span>
                        <strong>Cash at pickup</strong>
                        <small>Pay the exact total when you arrive at the kiosk.</small>
                      </span>
                      <span className="payment-icon">
                        <WalletCards size={18} />
                      </span>
                    </button>
                    <button
                      className={payment === "gcash" ? "payment-option selected" : "payment-option"}
                      onClick={() => setPayment("gcash")}
                    >
                      <span className="payment-radio" />
                      <span>
                        <strong>GCash</strong>
                        <small>Send the exact total, then submit your proof.</small>
                      </span>
                      <span className="payment-icon">
                        <CreditCard size={18} />
                      </span>
                    </button>
                  </div>
                  {payment === "gcash" && (
                    <div className="gcash-preview">
                      <div className="fake-qr">QR</div>
                      <div className="gcash-proof-fields">
                        <span className="micro-label">GCash payment</span>
                        <strong>Send, then submit proof</strong>
                        <p>
                          Amount due: <b>{formatPeso(total)}</b>
                        </p>
                        <label
                          className={
                            receiptUrl ? "upload-proof uploaded" : "upload-proof"
                          }
                        >
                          <input
                            type="file"
                            accept="image/*"
                            disabled={uploadingReceipt}
                            onChange={(event) => {
                              const file = event.target.files?.[0];
                              event.target.value = "";
                              void onReceiptFile(file);
                            }}
                          />
                          <span>
                            {uploadingReceipt ? (
                              "Uploading…"
                            ) : receiptUrl ? (
                              <>
                                <FileCheck2 size={14} /> {receiptName || "Receipt uploaded"}
                              </>
                            ) : (
                              "Upload GCash receipt"
                            )}
                          </span>
                        </label>
                        {receiptUrl && (
                          <img
                            className="receipt-thumb"
                            src={receiptUrl}
                            alt="Uploaded GCash receipt"
                          />
                        )}
                        <label className="reference-field">
                          <span>GCash reference number</span>
                          <input
                            value={referenceNumber}
                            onChange={(event) => setReferenceNumber(event.target.value)}
                            placeholder="e.g. 801234567890"
                          />
                        </label>
                        <small className="proof-required">
                          A receipt photo and reference number are both required.
                        </small>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {step === 5 && (
                <div className="step-panel confirmation-panel">
                  <span className="confirmation-icon">
                    <CheckCircle2 size={27} />
                  </span>
                  <span className="step-overline">Step 05 / 05</span>
                  <h2>Review your reservation.</h2>
                  <p>One last look before we hold your bikes at the kiosk.</p>
                  <div className="review-list">
                    <div>
                      <span>Bikes</span>
                      <strong>{cart.map((bike) => bike.name).join(", ")}</strong>
                    </div>
                    <div>
                      <span>Pickup</span>
                      <strong>
                        {pickupDate ? formatDateLabel(pickupDate) : "Not set"}
                      </strong>
                    </div>
                    <div>
                      <span>Rider</span>
                      <strong>{profile?.name || profile?.email || "—"}</strong>
                    </div>
                    <div>
                      <span>Payment</span>
                      <strong>
                        {payment === "cash" ? "Cash at pickup" : "GCash · pending verification"}
                      </strong>
                    </div>
                  </div>
                  <div className="total-row">
                    <span>Total</span>
                    <strong>{formatPeso(total)}</strong>
                  </div>
                </div>
              )}

              <div className="flow-footer">
                <button
                  className="back-button"
                  disabled={step === 1 || submitting}
                  onClick={() => setStep(Math.max(1, step - 1))}
                >
                  Back
                </button>
                <button
                  className="primary-button"
                  onClick={next}
                  disabled={submitting || uploadingReceipt}
                >
                  {submitting
                    ? "Confirming…"
                    : uploadingReceipt
                      ? "Uploading…"
                      : step === 5
                        ? "Confirm reservation"
                        : "Continue"}
                  <ArrowRight size={16} />
                </button>
              </div>
            </section>

            <aside className="summary-card">
              <div className="summary-top">
                <div>
                  <span className="micro-label">Your ride</span>
                  <strong className="summary-cart-count">
                    {cart.length} bike{cart.length === 1 ? "" : "s"} selected
                  </strong>
                </div>
                <button onClick={onBrowse} aria-label="Edit selection">
                  <MoreHorizontal size={17} />
                </button>
              </div>
              <div className="summary-cart-list">
                {cart.map((bike) => (
                  <div className="summary-cart-item" key={bike.id}>
                    <div className="summary-cart-thumb">
                      <BikeArt type={bike.type} imageUrl={bike.image_url} alt={bike.name} />
                    </div>
                    <div className="summary-cart-copy">
                      <span className="bike-kind">{BIKE_TYPE_LABELS[bike.type]}</span>
                      <strong>{bike.name}</strong>
                      <small>Helmet · Lock · Ready to ride</small>
                    </div>
                    <b>{formatPeso(rateFor(bike, rate))}</b>
                  </div>
                ))}
              </div>
              <div className="summary-details">
                <div>
                  <span>Pickup</span>
                  <strong>{pickupDate ? formatDateLabel(pickupDate) : "Choose a date"}</strong>
                  <small>Bagong Sikat · 9:30 AM</small>
                </div>
                <div>
                  <span>Rate</span>
                  <strong>{rate === "weekly" ? "Weekly" : "Daily"}</strong>
                  <small>
                    {cart.length} bike{cart.length === 1 ? "" : "s"}
                  </small>
                </div>
              </div>
              <div className="summary-total">
                <span>Total</span>
                <strong>{formatPeso(total)}</strong>
              </div>
              <p className="summary-note">
                <LockKeyhole size={13} /> No payment until you confirm
              </p>
            </aside>
          </div>
        )}
      </main>
    </div>
  );
}

function MyRides({
  bookings,
  onBookAnother,
}: {
  bookings: ReturnType<typeof useMyBookings>;
  onBookAnother: () => void;
}) {
  const { data, loading, error, reload } = bookings;

  const [active, history] = useMemo(() => {
    const isLive = (booking: Booking) =>
      booking.rentals.some((rental) =>
        ["reserved", "active", "overdue"].includes(rental.status),
      );
    return [
      (data ?? []).filter(isLive),
      (data ?? []).filter((booking) => !isLive(booking)),
    ];
  }, [data]);

  return (
    <div className="product-main-inner">
      <div className="page-heading">
        <div>
          <span className="micro-label">Customer dashboard</span>
          <h1>My rides.</h1>
          <p>Your reservations, payment status, and everything you need at pickup.</p>
        </div>
        <button className="primary-button" onClick={onBookAnother}>
          Book another ride <ArrowUpRight size={15} />
        </button>
      </div>

      {error && <AsyncNote tone="error" message={error} onRetry={reload} />}
      {loading && !data && <AsyncNote message="Loading your reservations…" />}
      {!loading && !error && data?.length === 0 && (
        <AsyncNote message="No reservations yet. Your bookings will appear here." />
      )}

      {active.map((booking) => (
        <section className="rides-list-card" key={booking.id} style={{ marginBottom: 18 }}>
          <div className="card-title-row">
            <div>
              <span className="micro-label">
                Reservation {booking.booking_ref ?? booking.id.slice(0, 8)}
              </span>
              <h2>
                {formatDateLabel(booking.expected_pickup_date)} ·{" "}
                {booking.rate_selected === "weekly" ? "Weekly" : "Daily"}
              </h2>
            </div>
            <Pill tone={booking.payment_status === "paid" ? "paid" : "clay"}>
              {PAYMENT_STATUS_LABELS[booking.payment_status]}
            </Pill>
          </div>

          {toAmount(booking.balance_due) > 0 && (
            <div className="ride-status-banner">
              <div className="ride-status-mark">
                <Clock3 size={19} />
              </div>
              <div>
                <span className="micro-label">Balance due</span>
                <h3>
                  {booking.payment_method === "cash"
                    ? "Pay the exact total at the kiosk"
                    : "Awaiting GCash verification"}
                </h3>
                <p>
                  <strong>{formatPeso(booking.balance_due)}</strong> before your bikes are
                  released.
                </p>
              </div>
            </div>
          )}

          {booking.rentals.map((rental) => (
            <div className="ride-bike-row" key={rental.id}>
              <BikeArt
                type={rental.bike_type}
                alt={rental.bike_name ?? "Bike"}
              />
              <div className="ride-bike-copy">
                <span className="bike-kind">
                  {rental.bike_type ? BIKE_TYPE_LABELS[rental.bike_type] : "Bike"}
                </span>
                <h3>{rental.bike_name ?? "Bike"}</h3>
                <p>
                  {formatDateTimeLabel(rental.due_at)
                    ? `Due ${formatDateTimeLabel(rental.due_at)}`
                    : "Return time set at pickup"}
                </p>
              </div>
              <Pill tone={rental.status === "overdue" ? "clay" : "sage"}>
                {RENTAL_STATUS_LABELS[rental.status]}
              </Pill>
              <b>{formatPeso(rental.price)}</b>
            </div>
          ))}

          <div className="ride-actions">
            <button
              className="secondary-button"
              onClick={() =>
                toast("Extensions are not available yet", {
                  description: "The extensions API is still being built.",
                })
              }
            >
              Extend rent <ArrowUpRight size={14} />
            </button>
            <button
              className="ghost-action"
              onClick={() =>
                toast("Swaps are not available yet", {
                  description: "The swaps API is still being built.",
                })
              }
            >
              Request a swap
            </button>
          </div>
        </section>
      ))}

      {history.length > 0 && (
        <section className="rides-list-card history-card">
          <div className="card-title-row">
            <div>
              <span className="micro-label">Past activity</span>
              <h2>Ride history</h2>
            </div>
          </div>
          {history.map((booking) => (
            <div className="history-row" key={booking.id}>
              <span className="history-date">
                {formatDateLabel(booking.expected_pickup_date)}
              </span>
              <div>
                <strong>
                  {booking.rentals.map((rental) => rental.bike_name ?? "Bike").join(", ")}
                </strong>
                <span>
                  {booking.rate_selected === "weekly" ? "Weekly" : "Daily"} ·{" "}
                  {booking.payment_method === "cash" ? "Cash" : "GCash"} ·{" "}
                  {formatPeso(booking.total_price)}
                </span>
              </div>
              <Pill tone="paid">{PAYMENT_STATUS_LABELS[booking.payment_status]}</Pill>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}

// =============================================================================
// Staff and admin — still local prototypes, no endpoints behind them yet
// =============================================================================

function PrototypeBanner({ surface }: { surface: string }) {
  return (
    <div className="async-note" role="status">
      <AlertTriangle size={15} />
      <span>
        The {surface} screens show sample data. Their API routers are registered but do
        not expose endpoints yet, so nothing here is saved.
      </span>
    </div>
  );
}

const sampleReservations = [
  { id: "VC-4821", name: "Mia Santos", bike: "Japanese bike", time: "9:30 AM", status: "Ready for pickup", payment: "Cash at counter", tone: "ready" },
  { id: "VC-4820", name: "Daniel Cruz", bike: "Folding bike", time: "10:00 AM", status: "GCash verification", payment: "₱1,140 online", tone: "review" },
  { id: "VC-4817", name: "Ava Reyes", bike: "Mountain bike", time: "11:00 AM", status: "Ready for pickup", payment: "Cash at counter", tone: "ready" },
];

function StaffView() {
  const [idChecked, setIdChecked] = useState(false);
  const [collateralChecked, setCollateralChecked] = useState(false);

  return (
    <div className="product-layout ops-layout">
      <aside className="app-sidebar ops-sidebar">
        <div className="ops-profile">
          <span className="avatar staff-avatar">JR</span>
          <div>
            <strong>Counter</strong>
            <small>Staff · Bagong Sikat</small>
          </div>
        </div>
        <div className="sidebar-nav-label">Operations</div>
        <button className="sidebar-link active">
          <LayoutDashboard size={17} /> Today's queue
        </button>
        <button className="sidebar-link">
          <ClipboardCheck size={17} /> Swap requests
        </button>
      </aside>
      <main className="product-main">
        <div className="page-heading ops-heading">
          <div>
            <span className="micro-label">{formatDateLabel(todayIso())}</span>
            <h1>Counter overview.</h1>
            <p>Pickups, returns, and everything waiting at the kiosk.</p>
          </div>
        </div>
        <PrototypeBanner surface="staff" />
        <div className="ops-metrics">
          <div>
            <span className="metric-icon sage-icon">
              <PackageCheck size={18} />
            </span>
            <span className="micro-label">Expected pickups</span>
            <strong>3</strong>
            <small>Sample data</small>
          </div>
          <div>
            <span className="metric-icon clay-icon">
              <BikeIcon size={18} />
            </span>
            <span className="micro-label">Expected returns</span>
            <strong>4</strong>
            <small>Sample data</small>
          </div>
          <div>
            <span className="metric-icon navy-icon">
              <AlertTriangle size={18} />
            </span>
            <span className="micro-label">Needs attention</span>
            <strong>2</strong>
            <small>Sample data</small>
          </div>
        </div>
        <div className="ops-columns">
          <section className="queue-card">
            <div className="card-title-row">
              <div>
                <span className="micro-label">Handoff queue</span>
                <h2>Expected pickups</h2>
              </div>
            </div>
            <div className="reservation-list">
              {sampleReservations.map((item, index) => (
                <article
                  className={index === 0 ? "reservation-row focused" : "reservation-row"}
                  key={item.id}
                >
                  <div className="reservation-time">
                    <strong>{item.time}</strong>
                    <span>{item.id}</span>
                  </div>
                  <div className="reservation-person">
                    <span className="avatar tiny-avatar">
                      {item.name.split(" ").map((part) => part[0]).join("")}
                    </span>
                    <div>
                      <strong>{item.name}</strong>
                      <span>
                        {item.bike} · {item.payment}
                      </span>
                    </div>
                  </div>
                  <Pill tone={item.tone === "review" ? "clay" : "sage"}>{item.status}</Pill>
                </article>
              ))}
            </div>
          </section>
          <section className="handoff-card">
            <div className="card-title-row">
              <div>
                <span className="micro-label">Selected · VC-4821</span>
                <h2>Approve &amp; release</h2>
              </div>
              <Pill tone="clay">Cash pending</Pill>
            </div>
            <div className="handoff-checks">
              <label className={idChecked ? "check-row checked" : "check-row"}>
                <input
                  type="checkbox"
                  checked={idChecked}
                  onChange={(event) => setIdChecked(event.target.checked)}
                />
                <span className="fake-check">{idChecked && <Check size={12} />}</span>
                <span>Physical ID verified against name</span>
              </label>
              <label className={collateralChecked ? "check-row checked" : "check-row"}>
                <input
                  type="checkbox"
                  checked={collateralChecked}
                  onChange={(event) => setCollateralChecked(event.target.checked)}
                />
                <span className="fake-check">{collateralChecked && <Check size={12} />}</span>
                <span>Exact payment received</span>
              </label>
            </div>
            <button
              className="primary-button full-button"
              disabled={!idChecked || !collateralChecked}
              onClick={() =>
                toast("Not connected", {
                  description: "The staff release endpoint does not exist yet.",
                })
              }
            >
              Approve &amp; release <ArrowUpRight size={15} />
            </button>
          </section>
        </div>
      </main>
    </div>
  );
}

function AdminView() {
  const { data: bikes, loading, error, reload } = useBikes(null, "daily");

  const counts = useMemo(() => {
    const tally = { available: 0, rented: 0, maintenance: 0, retired: 0 };
    for (const bike of bikes ?? []) tally[bike.status] += 1;
    return tally;
  }, [bikes]);

  return (
    <div className="product-layout admin-layout">
      <aside className="app-sidebar admin-sidebar">
        <div className="admin-lockup">
          <span className="admin-badge">
            <LayoutDashboard size={17} />
          </span>
          <div>
            <strong>Muñoz HQ</strong>
            <small>Admin workspace</small>
          </div>
        </div>
        <div className="sidebar-nav-label">Overview</div>
        <button className="sidebar-link active">
          <LayoutDashboard size={17} /> Business overview
        </button>
        <button className="sidebar-link">
          <BikeIcon size={17} /> Bike management
        </button>
        <button className="sidebar-link">
          <Users size={17} /> User management
        </button>
      </aside>
      <main className="product-main">
        <div className="page-heading ops-heading">
          <div>
            <span className="micro-label">Admin workspace · {formatDateLabel(todayIso())}</span>
            <h1>Business overview.</h1>
            <p>Fleet status is live. Revenue and reservations still need their endpoints.</p>
          </div>
        </div>

        {error ? (
          <AsyncNote tone="error" message={error} onRetry={reload} />
        ) : (
          <>
            {/* Inventory health is real: it comes from GET /bikes. */}
            <section className="admin-card status-card">
              <div className="card-title-row">
                <div>
                  <span className="micro-label">Bike lifecycle · live</span>
                  <h2>Inventory health</h2>
                </div>
                <Pill tone="sage">{bikes?.length ?? 0} in fleet</Pill>
              </div>
              {(
                [
                  ["Available", counts.available, "sage"],
                  ["Rented", counts.rented, "navy"],
                  ["Maintenance", counts.maintenance, "stone"],
                  ["Retired", counts.retired, "muted"],
                ] as const
              ).map(([label, value, tone]) => (
                <div className="lifecycle-row" key={label}>
                  <span>
                    <i className={`legend-swatch ${tone}-swatch`} />
                    {label}
                  </span>
                  <strong>{loading ? "…" : value}</strong>
                  <div className="lifecycle-track">
                    <i
                      className={`${tone}-track`}
                      style={{
                        width: `${
                          bikes?.length ? (value / bikes.length) * 100 : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>
              ))}
            </section>

            <PrototypeBanner surface="revenue and reservation" />

            <section className="admin-card reservations-table">
              <div className="card-title-row">
                <div>
                  <span className="micro-label">Latest activity · sample</span>
                  <h2>Reservations</h2>
                </div>
                <button className="text-button">
                  Filter <Search size={13} />
                </button>
              </div>
              <div className="table-head">
                <span>Reference</span>
                <span>Customer</span>
                <span>Bike</span>
                <span>Status</span>
                <span>Payment</span>
                <span />
              </div>
              {sampleReservations.map((item) => (
                <div className="table-row" key={item.id}>
                  <strong>{item.id}</strong>
                  <span>{item.name}</span>
                  <span>{item.bike}</span>
                  <Pill tone={item.tone === "review" ? "clay" : "sage"}>{item.status}</Pill>
                  <span>{item.payment}</span>
                  <span />
                </div>
              ))}
            </section>
          </>
        )}
      </main>
    </div>
  );
}

// =============================================================================
// Root
// =============================================================================

export default function Home() {
  const { session, loading, error, configured } = useAuth();
  const [view, setView] = useState<View>("landing");
  const [stylePage, setStylePage] = useState<BikeType | null>(null);
  const [cart, setCart] = useState<Bike[]>([]);
  const [pickupDate, setPickupDate] = useState<string | null>(null);
  const [rate, setRate] = useState<RateSelected>("daily");
  const [authOpen, setAuthOpen] = useState(false);
  const [customerScreen, setCustomerScreen] = useState("booking");

  const goToBooking = (screen: string) => {
    if (!session) {
      setAuthOpen(true);
      return;
    }
    setCustomerScreen(screen);
    setView("customer");
  };

  const requestView = (next: View) => {
    if (next === "customer") {
      goToBooking(cart.length ? "booking" : "rides");
      return;
    }
    setView(next);
  };

  return (
    <div className="app-shell">
      <AppHeader view={view} setView={requestView} onRequestSignIn={() => setAuthOpen(true)} />

      {session && error && (
        <div style={{ padding: "0 var(--shell-pad, 24px)" }}>
          <AsyncNote tone="error" message={error} />
        </div>
      )}

      {view === "landing" && (
        <LandingView
          onBook={(type) => {
            setStylePage(type ?? null);
            setView("selection");
          }}
        />
      )}

      {view === "selection" && (
        <SelectionView
          cart={cart}
          setCart={setCart}
          stylePage={stylePage}
          setStylePage={setStylePage}
          pickupDate={pickupDate}
          setPickupDate={setPickupDate}
          rate={rate}
          setRate={setRate}
          onContinue={() => goToBooking("booking")}
        />
      )}

      {view === "customer" &&
        (loading && !session ? (
          <main className="product-main">
            <AsyncNote message="Checking your session…" />
          </main>
        ) : (
          <CustomerView
            cart={cart}
            setCart={setCart}
            pickupDate={pickupDate}
            setPickupDate={setPickupDate}
            rate={rate}
            setRate={setRate}
            initialScreen={customerScreen}
            onBrowse={() => setView("selection")}
          />
        ))}

      {view === "staff" && <StaffView />}
      {view === "admin" && <AdminView />}

      {authOpen && <AuthDialog onClose={() => setAuthOpen(false)} />}

      {!configured && (
        <div className="prototype-disclaimer">
          <span>
            <Settings2 size={12} /> Auth not configured
          </span>
          <span>
            Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in Frontend/.env to enable
            sign-in and booking.
          </span>
        </div>
      )}
    </div>
  );
}
