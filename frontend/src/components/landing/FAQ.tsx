
import Icon from "./Icon";
import "./landingstyles/FAQ.css";

const faqs = [
  {
    question: "How does RepoIQ generate interview questions?",
    answer:
      "RepoIQ indexes a repository, retrieves relevant code for your topic, and uses a local AI model to generate implementation-focused interview questions with source references.",
  },
  {
    question: "Do I need to make my repository public?",
    answer:
      "The current development workflow supports repositories accessible through the configured GitHub integration. Private repository support depends on the permissions and authentication configured for the app.",
  },
  {
    question: "What kind of feedback will I receive?",
    answer:
      "You receive an assessment, an explanation, follow-up questions when appropriate, and a final report when the interview is complete.",
  },
  {
    question: "Who is RepoIQ best for?",
    answer:
      "Students, developers, and job seekers who want to discuss real project code rather than memorize generic interview question lists.",
  },
];

export default function FAQ() {
  return (
    <section id="faq" className="rq-faq rq-shell">
      <div>
        <h2>
          Frequently
          <br />
          Asked Questions
        </h2>

        <p>
          Have a question about RepoIQ?
          <br />
          Here are some quick answers.
        </p>
      </div>

      <div className="rq-faq-items">
        {faqs.map((item) => (
          <details key={item.question}>
            <summary>
              {item.question}
              <span aria-hidden="true">+</span>
            </summary>

            <p>{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}
