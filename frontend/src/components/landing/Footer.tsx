
import Link from "next/link";
import Icon from "./Icon";
import "./landingstyles/Footer.css";

const footerLinks = [
  {
    title: "Explore",
    links: [
      { label: "Product", href: "#benefits" },
      { label: "How it works", href: "/how-it-works" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Interviews", href: "/interview" },
      { label: "FAQs", href: "/faq" },
      {
        label: "GitHub",
        href: "https://github.com/maheenhmd/RepoIQ",
        external: true,
      },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="rq-enterprise-footer">
      <div className="rq-shell">
        <div className="rq-footer-main">
          <div className="rq-footer-brand">
            <Link
              href="/"
              className="rq-footer-logo"
              aria-label="RepoIQ home"
            >
              Repo<span>I</span><strong>Q</strong>
              <span className="rq-footer-logo-dot" />
            </Link>

            <h2>
              Understand your code.
              <br />
              <span>Own your interview.</span>
            </h2>

            <p>
              Repository-aware technical interviews
              built around real code, meaningful
              questions, and actionable feedback.
            </p>
          </div>

          <Link
            href="/interview"
            className="rq-footer-cta"
          >
            Start practicing
            <Icon name="arrow" size={19} />
          </Link>
        </div>

        <div className="rq-footer-divider" />

        <div className="rq-footer-middle">
          <div className="rq-footer-message">
            <span className="rq-footer-accent-line" />

            <p>
              Less memorization.
              <br />
              More understanding.
            </p>
          </div>

          <div className="rq-footer-navigation">
            {footerLinks.map((group) => (
              <div
                className="rq-footer-link-group"
                key={group.title}
              >
                <h3>{group.title}</h3>

                <nav aria-label={`${group.title} links`}>
                  {group.links.map((item) =>
                    item.external ? (
                      <a
                        key={item.label}
                        href={item.href}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {item.label}
                        <span aria-hidden="true">↗</span>
                      </a>
                    ) : (
                      <Link
                        key={item.label}
                        href={item.href}
                      >
                        {item.label}
                      </Link>
                    )
                  )}
                </nav>
              </div>
            ))}
          </div>
        </div>

        <div className="rq-footer-divider" />

        <div className="rq-footer-bottom">
          <p>
            © {new Date().getFullYear()} RepoIQ.
            All rights reserved.
          </p>

          <p>
            Built for developers. Grounded in code.
          </p>
        </div>
      </div>
    </footer>
  );
}
