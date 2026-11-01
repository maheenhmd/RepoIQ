
import Image from "next/image";
import Icon from "./Icon";
import type { IconName } from "./Icon";
import "./landingstyles/Intelligence.css";

const intelligence: {
  icon: IconName;
  title: string;
  copy: string;
  tone: string;
}[] = [
  {
    icon: "code",
    title: "Code Understanding",
    copy: "Explores architecture, functions, and key implementation details.",
    tone: "mint",
  },
  {
    icon: "layers",
    title: "Grounded Questions",
    copy: "Asks about real repository code rather than random trivia.",
    tone: "blue",
  },
  {
    icon: "chart",
    title: "Answer Evaluation",
    copy: "Reviews technical correctness and depth of explanation.",
    tone: "pink",
  },
  {
    icon: "branch",
    title: "Follow-up Questions",
    copy: "Goes deeper when your answer reveals a knowledge gap.",
    tone: "mint",
  },
  {
    icon: "circle-check",
    title: "Detailed Feedback",
    copy: "Returns useful feedback and code references for review.",
    tone: "coral",
  },
];

export default function Intelligence() {
  return (
    <section className="rq-intelligence rq-shell">
      <div className="rq-code-scene" aria-hidden="true">
        <div className="rq-code-disc" />

        <div className="rq-code-panel">
          <div className="rq-code-dots">
            <i />
            <i />
            <i />
          </div>

          <span className="rq-code-row wide" />
          <span className="rq-code-row mid" />
          <span className="rq-code-row narrow" />
          <span className="rq-code-row medium" />
          <span className="rq-code-row slim" />
        </div>

        <span className="rq-code-chip">
          <Icon name="code" size={37} />
        </span>

        <div className="rq-mini-mascot">
          <Image
            src="/repoiq-mascot.png"
            alt=""
            width={260}
            height={260}
          />
        </div>
      </div>

      <div className="rq-intelligence-copy">
        <h2>Repository-Aware Intelligence</h2>

        <p className="rq-section-lead">
          More than a question generator.
          RepoIQ finds relevant implementations
          and uses them to guide real technical
          discussions.
        </p>

        <div className="rq-intelligence-list">
          {intelligence.map((item) => (
            <div
              className="rq-intelligence-row"
              key={item.title}
            >
              <span
                className={`rq-small-icon rq-tone-${item.tone}`}
              >
                <Icon name={item.icon} size={22} />
              </span>

              <h3>{item.title}</h3>
              <p>{item.copy}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
