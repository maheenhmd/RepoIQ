
import Link from "next/link";
import Icon from "./Icon";
import "./landingstyles/Navbar.css";

export default function Navbar() {
  return (
    <header className="rq-nav">
      <div className="rq-shell rq-nav-inner">
        <Link
          href="/"
          className="rq-wordmark"
          aria-label="RepoIQ home"
        >
          Repo<span>I</span><strong>Q</strong>
        </Link>

        <nav className="rq-links" aria-label="Main navigation">
          <a href="#benefits">Benefits</a>
          <Link href="/how-it-works">How it works</Link>
          <Link href="/faq">FAQ</Link>
        </nav>

        <Link
          href="/auth/signup"
          className="rq-button rq-button-main rq-nav-cta"
        >
          Get Started
          <Icon name="arrow" size={18} />
        </Link>
      </div>
    </header>
  );
}
