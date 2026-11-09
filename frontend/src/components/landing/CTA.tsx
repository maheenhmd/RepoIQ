
import Link from "next/link";
import Icon from "./Icon";
import "./landingstyles/CTA.css";

export default function CTA() {
  return (
    <section className="rq-cta rq-shell">
      <h2 bg-color="teal">
        Turn Your Code into
        <br />
        Interview-Ready Skills
      </h2>

      <p>
        Import a repository, practice with real
        questions, and see what to improve next.
      </p>

      <Link
        href="/auth/signup"
        className="rq-button rq-button-main"
      >
        Get Started with RepoIQ
        <Icon name="arrow" size={18} />
      </Link>
    </section>
  );
}
