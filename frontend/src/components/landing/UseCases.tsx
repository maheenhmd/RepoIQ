
import Icon from "./Icon";
import type { IconName } from "./Icon";
import "./landingstyles/UseCases.css";

const useCases: {
  icon: IconName;
  title: string;
  copy: string;
  tone: string;
}[] = [
  {
    icon: "graduation",
    title: "Students",
    copy: "Turn course projects into meaningful practice and build confidence.",
    tone: "mint",
  },
  {
    icon: "code",
    title: "Developers",
    copy: "Sharpen your understanding of code you actually write.",
    tone: "coral",
  },
  {
    icon: "briefcase",
    title: "Job Seekers",
    copy: "Prepare to explain implementations and design choices in interviews.",
    tone: "blue",
  },
  {
    icon: "users",
    title: "Teams",
    copy: "Explore project knowledge through practical technical discussions.",
    tone: "pink",
  },
];

export default function UseCases() {
  return (
    <section
      className="rq-usecases rq-shell"
      id="use-cases"
    >
      <div className="rq-usecases-intro">
        <h2>
          Built for
          <br />
          Real Use Cases
        </h2>

        <p>
          Whether you’re learning, interviewing,
          or sharing your project with a team,
          practice with context.
        </p>
      </div>

      <div className="rq-usecases-grid">
        {useCases.map((item) => (
          <article
            className={`rq-usecase rq-usecase-${item.tone}`}
            key={item.title}
          >
            <Icon name={item.icon} size={32} />
            <h3>{item.title}</h3>
            <p>{item.copy}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
