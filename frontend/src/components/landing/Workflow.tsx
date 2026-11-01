
import Icon from "./Icon";
import type { IconName } from "./Icon";
import "./landingstyles/Workflow.css";

const steps: {
  icon: IconName;
  title: string;
  copy: string;
  tone: string;
}[] = [
  {
    icon: "github",
    title: "Import Repository",
    copy: "Choose a GitHub repository to explore.",
    tone: "blue",
  },
  {
    icon: "code",
    title: "Analyze Code",
    copy: "RepoIQ indexes files, symbols, and implementations.",
    tone: "mint",
  },
  {
    icon: "file",
    title: "Generate Questions",
    copy: "Get relevant questions grounded in code.",
    tone: "coral",
  },
  {
    icon: "chat",
    title: "Practice Interview",
    copy: "Answer and respond to adaptive follow-ups.",
    tone: "mint",
  },
  {
    icon: "chart",
    title: "Get Feedback",
    copy: "See your strengths, gaps, and next steps.",
    tone: "pink",
  },
];

export default function Workflow() {
  return (
    <section id="workflow" className="rq-workflow">
      <div className="rq-shell">
        <h2>How RepoIQ Works</h2>

        <p className="rq-section-lead">
          From a GitHub repository to a focused,
          personalized interview.
        </p>

        <ol className="rq-step-grid">
          {steps.map((step, index) => (
            <li className="rq-step" key={step.title}>
              <div className="rq-step-top">
                <span
                  className={`rq-icon-bg rq-tone-${step.tone}`}
                >
                  <Icon name={step.icon} size={27} />
                </span>

                {index < steps.length - 1 && (
                  <span className="rq-step-arrow">
                    <Icon name="arrow" size={30} />
                  </span>
                )}
              </div>

              <h3>{step.title}</h3>
              <p>{step.copy}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
