
import type { Metadata } from "next";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import "@/components/landing/landingstyles/base.css";
import "./FAQPage.css";

export const metadata: Metadata = {
  title: "FAQs | RepoIQ",
  description:
    "Find answers to frequently asked questions about RepoIQ.",
};

const faqs = [
  {
    question: "How does RepoIQ generate interview questions?",
    answer:
      "RepoIQ analyzes your repository and retrieves relevant code to generate technical questions based on your actual project, architecture, and implementation.",
  },
  {
    question: "Do I need to make my repository public?",
    answer:
      "RepoIQ supports repositories accessible through its configured GitHub integration. Private repository access depends on the authentication and permissions configured.",
  },
  {
    question: "What kind of feedback will I receive?",
    answer:
      "You'll receive an assessment of your answer, explanations of strengths and gaps, relevant code references, and a final interview report.",
  },
  {
    question: "Can I choose the difficulty of my interview?",
    answer:
      "Yes. You can configure the difficulty and other available interview settings before starting your session.",
  },
  {
    question: "Does RepoIQ ask follow-up questions?",
    answer:
      "Yes. RepoIQ can ask follow-up questions based on your responses to explore your understanding of the code in more depth.",
  },
  {
    question: "Who is RepoIQ designed for?",
    answer:
      "RepoIQ is built for students, software developers, and job seekers who want to practice explaining real project code instead of memorizing generic interview questions.",
  },
];

export default function FAQPage() {
  return (
    <div className="rq-page rq-faq-page">
      <Navbar />

      <main>
        <section className="rq-faq-page-hero">
          <div className="rq-shell">
            <span className="rq-faq-page-eyebrow">
              SUPPORT & GUIDANCE
            </span>

            <h1>
              Frequently Asked
              <br />
              <span>Questions.</span>
            </h1>

            <p>
              Everything you need to know about RepoIQ,
              your repositories, and the interview experience.
            </p>
          </div>
        </section>

        <section className="rq-faq-page-content rq-shell">
          <div className="rq-faq-page-heading">
            <h2>Explore common questions</h2>
            <p>
              Find quick answers to help you get started.
            </p>
          </div>

          <div className="rq-faq-page-list">
            {faqs.map((faq, index) => (
              <details
                className="rq-faq-page-item"
                key={faq.question}
              >
                <summary>
                  <span className="rq-faq-page-number">
                    {String(index + 1).padStart(2, "0")}
                  </span>

                  <span className="rq-faq-page-question">
                    {faq.question}
                  </span>

                  <span
                    className="rq-faq-page-plus"
                    aria-hidden="true"
                  >
                    +
                  </span>
                </summary>

                <p>{faq.answer}</p>
              </details>
            ))}
          </div>
        </section>

        <section className="rq-faq-page-bottom rq-shell">
          <div>
            <h2>Ready to put your code to the test?</h2>
            <p>
              Start a repository-aware technical interview.
            </p>
          </div>

          <a
            href="/interview"
            className="rq-faq-page-button"
          >
            Start Interview
            <span aria-hidden="true">→</span>
          </a>
        </section>
      </main>

      <Footer />
    </div>
  );
}
