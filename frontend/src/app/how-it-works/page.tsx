
import type { Metadata } from "next";
import Link from "next/link";
import Navbar from "@/components/landing/Navbar";
import Footer from "@/components/landing/Footer";
import Icon from "@/components/landing/Icon";
import type { IconName } from "@/components/landing/Icon";

import "@/components/landing/landingstyles/base.css";
import "./HowItWorks.css";

export const metadata: Metadata = {
  title: "How It Works | RepoIQ",
  description:
    "Discover how RepoIQ turns GitHub repositories into personalized technical interviews.",
};

const steps: {
  number: string;
  icon: IconName;
  title: string;
  description: string;
  details: string[];
  color: string;
}[] = [
  {
    number: "01",
    icon: "github",
    title: "Connect Your Repository",
    description:
      "Start with a GitHub repository. RepoIQ uses your project's source code as the foundation for interview practice.",
    details: [
      "Select a repository",
      "Discover relevant source files",
      "Prepare the code for analysis",
    ],
    color: "coral",
  },
  {
    number: "02",
    icon: "code",
    title: "Understand the Codebase",
    description:
      "RepoIQ explores the repository structure and indexes useful code so it can find implementations relevant to your interview topics.",
    details: [
      "Explore files and symbols",
      "Index meaningful code",
      "Retrieve relevant implementations",
    ],
    color: "teal",
  },
  {
    number: "03",
    icon: "file",
    title: "Generate Relevant Questions",
    description:
      "Instead of generic interview trivia, RepoIQ builds technical questions around code from your repository.",
    details: [
      "Select interview difficulty",
      "Choose a technical topic",
      "Generate code-grounded questions",
    ],
    color: "blue",
  },
  {
    number: "04",
    icon: "chat",
    title: "Practice Your Interview",
    description:
      "Explain how your code works, discuss implementation decisions, and respond to follow-up questions.",
    details: [
      "Answer technical questions",
      "Explain your reasoning",
      "Explore deeper concepts",
    ],
    color: "pink",
  },
  {
    number: "05",
    icon: "chart",
    title: "Review Your Feedback",
    description:
      "Receive feedback on your responses and review the areas where your technical explanations can improve.",
    details: [
      "Review answer assessments",
      "Identify knowledge gaps",
      "Read your interview report",
    ],
    color: "teal",
  },
];

export default function HowItWorksPage() {
  return (
    <div className="rq-page rqh-page">
      <Navbar />

      <main>
        {/* HERO */}
        <section className="rqh-hero">
          <div className="rq-shell rqh-hero-content">
            <span className="rqh-eyebrow">
              <span className="rqh-eyebrow-dot" />
              THE PROCESS
            </span>

            <h1>
              Your code.
              <br />
              Your interview.
              <br />
              <span>Your growth.</span>
            </h1>

            <p>
              Discover how RepoIQ transforms an ordinary
              GitHub repository into a personalized
              technical interview experience.
            </p>

            <Link href="#process" className="rqh-hero-button">
              Explore the process
              <Icon name="arrow" size={18} />
            </Link>

            <div className="rqh-hero-decoration" aria-hidden="true">
              <div className="rqh-decoration-circle">
                <Icon name="code" size={65} />
              </div>
              <span className="rqh-decoration-orbit orbit-a" />
              <span className="rqh-decoration-orbit orbit-b" />
              <span className="rqh-decoration-dot dot-a" />
              <span className="rqh-decoration-dot dot-b" />
              <span className="rqh-decoration-dot dot-c" />
            </div>
          </div>
        </section>

        {/* INTRO */}
        <section className="rqh-intro rq-shell">
          <span className="rqh-section-label">
            SIMPLE WORKFLOW
          </span>

          <h2>
            From repository to
            <br />
            real understanding.
          </h2>

          <p>
            Five connected steps. One focused goal:
            helping you understand and explain the
            code you actually work with.
          </p>
        </section>

        {/* STEPS */}
        <section id="process" className="rqh-process rq-shell">
          <div className="rqh-timeline">
            {steps.map((step) => (
              <article className="rqh-step" key={step.number}>
                <div className="rqh-step-marker">
                  <span>{step.number}</span>
                </div>

                <div className="rqh-step-content">
                  <div className={`rqh-step-icon ${step.color}`}>
                    <Icon name={step.icon} size={28} />
                  </div>

                  <div className="rqh-step-text">
                    <span className="rqh-step-label">
                      STEP {step.number}
                    </span>

                    <h3>{step.title}</h3>
                    <p>{step.description}</p>

                    <div className="rqh-step-details">
                      {step.details.map((detail) => (
                        <span key={detail}>
                          <Icon name="check" size={15} />
                          {detail}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>

        {/* EXAMPLE */}
        <section className="rqh-example-section">
          <div className="rq-shell rqh-example-layout">
            <div className="rqh-example-copy">
              <span className="rqh-section-label">
                WHAT MAKES IT DIFFERENT
              </span>

              <h2>
                Less theory.
                <br />
                More context.
              </h2>

              <p>
                Traditional interview preparation often
                starts with a generic list of questions.
                RepoIQ starts with your repository.
              </p>

              <p>
                It can ask you to explain specific
                functions, error handling, architecture,
                or implementation decisions from your code.
              </p>

              <Link href="/interview" className="rqh-text-link">
                Try an interview
                <Icon name="arrow" size={18} />
              </Link>
            </div>

            <div className="rqh-example-panel">
              <div className="rqh-example-topbar">
                <span className="rqh-example-dots">
                  <i />
                  <i />
                  <i />
                </span>
                <span>Example interview question</span>
              </div>

              <div className="rqh-example-code">
                <span className="rqh-example-file">
                  <Icon name="code" size={16} />
                  src/requests/models.py
                </span>

                <div className="rqh-example-snippet">
                  <span className="rqh-code-keyword">def</span>{" "}
                  <span className="rqh-code-function">
                    raise_for_status
                  </span>
                  (self):
                  <br />
                  {"    "}
                  <span className="rqh-code-comment">
                    # Handle HTTP errors
                  </span>
                  <br />
                  {"    "}...
                </div>

                <div className="rqh-example-question">
                  <span className="rqh-example-ai">
                    <Icon name="chat" size={17} />
                    REPOIQ ASKS
                  </span>

                  <p>
                    How does this implementation handle
                    unsuccessful HTTP responses, and why
                    is that useful to callers?
                  </p>
                </div>
              </div>

              <div className="rqh-example-caption">
                <Icon name="target" size={16} />
                Questions grounded in actual code
              </div>
            </div>
          </div>
        </section>

        {/* CTA */}
        <section className="rqh-bottom rq-shell">
          <div>
            <span className="rqh-section-label">
              READY TO BEGIN?
            </span>

            <h2>
              Your next interview starts
              with your code.
            </h2>

            <p>
              Explore your repository, practice technical
              explanations, and discover what to improve.
            </p>
          </div>

          <Link href="/interview" className="rqh-bottom-button">
            Start practicing
            <Icon name="arrow" size={19} />
          </Link>
        </section>
      </main>

      <Footer />
    </div>
  );
}
