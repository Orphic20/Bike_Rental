export default function Privacy() {
  return (
    <main className="privacy-page">
      <p className="landing-eyebrow">
        <span className="eyebrow-rule" /> Muñoz Bike Rental
      </p>
      <h1>Privacy policy</h1>
      <p>Last updated: 23 September 2026</p>
      <p>
        This policy explains what Muñoz Bike Rental (“we”, the shop in Bagong Sikat,
        Science City of Muñoz) collects when you use this site or sign in with
        Google.
      </p>
      <h2>Who we are</h2>
      <p>
        We are a student-built booking site for a local bike shop. Contact:{" "}
        <a href="mailto:loewinvillanueva07@gmail.com">loewinvillanueva07@gmail.com</a>.
      </p>
      <h2>What we collect</h2>
      <ul>
        <li>Name and email (from Google or from the account you create)</li>
        <li>Google account ID if you use Continue with Google</li>
        <li>Bookings: bike, dates, rate, and payment method</li>
        <li>GCash reference number and receipt image, if you pay with GCash</li>
        <li>Bike photos uploaded by staff or admin</li>
        <li>Shop open/closed notes entered by admin</li>
      </ul>
      <p>We do not sell your data. We do not show ads.</p>
      <h2>Why we collect it</h2>
      <ul>
        <li>Create and keep your account</li>
        <li>Reserve bikes, take payment, and run pickup and return at the shop</li>
        <li>Let staff verify GCash and let admin manage the fleet</li>
      </ul>
      <h2>Who processes it</h2>
      <ul>
        <li>Supabase — accounts and the database</li>
        <li>Google — only if you choose Google sign-in</li>
        <li>Cloudflare Pages — the website</li>
        <li>Render — the booking API</li>
        <li>Cloudinary — uploaded photos and receipts</li>
      </ul>
      <h2>How long we keep it</h2>
      <p>
        Account and booking records stay while the shop uses this system. Email us
        to ask for a copy or to have your account closed.
      </p>
      <p>
        <a href="/">Back to Muñoz Bike Rental</a>
      </p>
    </main>
  );
}
