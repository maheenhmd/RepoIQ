
import Icon from "./Icon";
import type { IconName } from "./Icon";
import "./landingstyles/Benefits.css";

const benefits: {
  icon: IconName;
  title: string;
  copy: string;
  tone: string;
}[] = [
  {
    icon: "github",
    title: "Repository-Aware Interviews",
    copy: "Questions grounded in your actual code, structure, and tech stack.",
    tone: "coral",
  },
  {
    icon: "chart",
    title: "Actionable Feedback",
    copy: "See where your explanation was strong and what needs more work.",
    tone: "mint",
  },
  {
    icon: "layers",
    title: "Realistic & Practical",
    copy: "Discuss implementation details, trade-offs, and engineering decisions.",
    tone: "blue",
  },
  {
    icon: "target",
    title: "Personalized Growth",
    copy: "Practice the parts of your own projects that matter most.",
    tone: "pink",
  },
];

export default function Benefits() {
  return (
    <section
      id="benefits"
      className="rq-benefits rq-shell"
    >
      <div className="rq-benefits-intro">
        <h2>Why RepoIQ?</h2>
        <p>
          Stop rehearsing generic answers.
          Have a more useful conversation about
          the code you actually built.
        </p>
        <span className="rq-small-rule" />
      </div>

      <div className="rq-benefits-grid">
        {benefits.map((item) => (
          <div className="rq-benefit" key={item.title}>
            <span
              className={`rq-icon-bg rq-tone-${item.tone}`}
            >
              <Icon name={item.icon} size={26} />
            </span>

            <div>
              <h3>{item.title}</h3>
              <p>{item.copy}</p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
