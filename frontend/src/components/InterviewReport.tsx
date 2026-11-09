
"use client";

import {
  useEffect,
  useRef,
  useState,
  type CSSProperties,
} from "react";
import Link from "next/link";
import type { Report } from "@/types";
import { Sources } from "./QuestionCard";
import styles from "./InterviewReport.module.css";

type Mood = "excellent" | "great" | "growing" | "practice";

const confettiPieces = Array.from({ length: 28 }, (_, i) => ({
  left: `${(i * 37 + 13) % 100}%`,
  delay: `${(i % 9) * 0.13}s`,
  duration: `${2.2 + (i % 5) * 0.3}s`,
}));

const moods = {
  excellent: {
    emoji: "🏆",
    eyebrow: "OUTSTANDING PERFORMANCE",
    title: "You absolutely crushed it!",
    subtitle:
      "Your hard work is showing. Celebrate this milestone, then keep pushing your limits.",
    badge: "Excellent performance",
  },
  great: {
    emoji: "✨",
    eyebrow: "GREAT PROGRESS",
    title: "Look at you growing!",
    subtitle:
      "You are building stronger technical understanding with every challenge.",
    badge: "Strong progress",
  },
  growing: {
    emoji: "🚀",
    eyebrow: "PROGRESS IN MOTION",
    title: "You're getting there!",
    subtitle:
      "Every question you explored is helping you become a more confident engineer.",
    badge: "Keep building",
  },
  practice: {
    emoji: "🌱",
    eyebrow: "YOUR GROWTH STARTS HERE",
    title: "Every expert was once a beginner.",
    subtitle:
      "This is a learning checkpoint, not a judgment. You now have a clearer path forward.",
    badge: "An opportunity to grow",
  },
};

function validScore(value: number | null | undefined): number | null {
  if (
    typeof value !== "number" ||
    !Number.isFinite(value) ||
    value < 0 ||
    value > 100
  ) {
    return null;
  }

  return Math.round(value);
}

function getMood(score: number | null): Mood {
  if (score === null) return "practice";
  if (score >= 85) return "excellent";
  if (score >= 65) return "great";
  if (score >= 40) return "growing";
  return "practice";
}

function FindingCard({
  icon,
  title,
  items,
  kind,
}: {
  icon: string;
  title: string;
  items: string[];
  kind: "strength" | "growth" | "next";
}) {
  return (
    <section className={`${styles.findingCard} ${styles[kind]}`}>
      <div className={styles.findingHeader}>
        <span className={styles.findingIcon} aria-hidden="true">
          {icon}
        </span>
        <h3>{title}</h3>
      </div>

      {items.length > 0 ? (
        <ul className={styles.findingList}>
          {items.map((item, index) => (
            <li key={`${kind}-${index}`}>
              <span className={styles.listMarker} aria-hidden="true">
                {kind === "strength" ? "✦" : "↗"}
              </span>
              <span>{item}</span>
            </li>
          ))}
        </ul>
      ) : (
        <p className={styles.empty}>
          {kind === "strength"
            ? "No specific strengths were recorded."
            : kind === "growth"
              ? "No specific improvement areas were recorded."
              : "No additional recommendations were recorded."}
        </p>
      )}
    </section>
  );
}

export default function InterviewReport({
  report,
}: {
  report: Report;
}) {
  const reportRef = useRef<HTMLElement>(null);

  const [animate, setAnimate] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");

  const score = validScore(report.overall_score);
  const mood = getMood(score);
  const content = moods[mood];

  const celebratory = mood === "excellent";
  const sparkly = mood === "great";

  useEffect(() => {
    const timer = window.setTimeout(() => setAnimate(true), 100);
    return () => window.clearTimeout(timer);
  }, []);

  const countItems = Object.entries(report.assessment_counts ?? {});

  const totalAnswers = countItems.reduce(
    (total, [, count]) =>
      total + (Number.isFinite(count) ? count : 0),
    0
  );

  const ringStyle = {
    "--score": score ?? 0,
  } as CSSProperties;

  // PDF DOWNLOAD

async function downloadReportPDF() {
  const element = reportRef.current;
  if (!element || exporting) return;

  setExporting(true);
  setExportError("");

  try {
    const [{ toCanvas }, { jsPDF }] = await Promise.all([
      import("html-to-image"),
      import("jspdf"),
    ]);

    await document.fonts.ready;

    const canvas = await toCanvas(element, {
      backgroundColor: "#1b1d26",
      pixelRatio: 2,
      cacheBust: true,
      filter: (node) => {
        if (
          node instanceof HTMLElement &&
          node.dataset.pdfExclude === "true"
        ) {
          return false;
        }
        return true;
      },
    });

    if (!canvas.width || !canvas.height) {
      throw new Error("Report capture is empty.");
    }

    // One continuous PDF page matching the report's aspect ratio.
    const pageWidth = 210;
    const margin = 6;

    const imageWidth = pageWidth - margin * 2;
    const imageHeight =
      (canvas.height / canvas.width) * imageWidth;

    const pageHeight = imageHeight + margin * 2;

    const pdf = new jsPDF({
      orientation: "portrait",
      unit: "mm",
      format: [pageWidth, pageHeight],
      compress: true,
    });

    const image = canvas.toDataURL("image/png");

    pdf.addImage(
      image,
      "PNG",
      margin,
      margin,
      imageWidth,
      imageHeight
    );

    pdf.save("RepoIQ-Interview-Report.pdf");
  } catch (error) {
    console.error("PDF export failed:", error);
    setExportError(
      "Could not generate the PDF. Please try again."
    );
  } finally {
    setExporting(false);
  }
}


  return (
    <section
      ref={reportRef}
      className={`${styles.report} ${styles[mood]}`}
      aria-label="RepoIQ interview performance report"
    >
      {/* Animated confetti */}
      {animate && celebratory && (
        <div
          className={styles.confetti}
          data-pdf-exclude="true"
          aria-hidden="true"
        >
          {confettiPieces.map((piece, index) => (
            <span
              key={index}
              style={{
                left: piece.left,
                animationDelay: piece.delay,
                animationDuration: piece.duration,
              }}
            />
          ))}
        </div>
      )}

      {/* Ambient lighting */}
      <div className={styles.backgroundGlow} aria-hidden="true">
        <span className={styles.orbOne} />
        <span className={styles.orbTwo} />
      </div>

      {/* Hero */}
      <header className={styles.hero}>
        <div className={styles.eyebrow}>
          <span className={styles.eyebrowDot} />
          REPOIQ / INTERVIEW COMPLETE
        </div>

        <div
          className={`${styles.heroEmoji} ${
            animate ? styles.emojiAnimated : ""
          }`}
          aria-hidden="true"
        >
          {content.emoji}
        </div>

        {(celebratory || sparkly) && (
          <div className={styles.sparkleField} aria-hidden="true">
            <span>✦</span>
            <span>✧</span>
            <span>✦</span>
            <span>✧</span>
          </div>
        )}

        <p className={styles.heroKicker}>
          {content.eyebrow}
        </p>

        <h2>{content.title}</h2>

        <p className={styles.heroDescription}>
          {content.subtitle}
        </p>

        <span className={styles.achievementBadge}>
          <span aria-hidden="true">
            {celebratory ? "🏅" : sparkly ? "💫" : "🌿"}
          </span>
          {content.badge}
        </span>
      </header>

      {/* Score section */}
      <section
        className={styles.scorePanel}
        aria-label="Overall score"
      >
        <div className={styles.scoreRing} style={ringStyle}>
          <svg
            viewBox="0 0 160 160"
            className={styles.ringSvg}
            aria-hidden="true"
          >
            <circle
              className={styles.ringTrack}
              cx="80"
              cy="80"
              r="69"
              pathLength="100"
            />

            <circle
              className={`${styles.ringProgress} ${
                animate ? styles.ringAnimated : ""
              }`}
              cx="80"
              cy="80"
              r="69"
              pathLength="100"
              strokeDasharray={`${score ?? 0} 100`}
            />
          </svg>

          <div className={styles.scoreCenter}>
            <strong className={styles.scoreValue}>
              {score === null ? "—" : score}
            </strong>

            <span className={styles.scoreTotal}>
              {score === null
                ? "Not scored"
                : "out of 100"}
            </span>
          </div>
        </div>

        <div className={styles.scoreDetails}>
          <span className={styles.sectionEyebrow}>
            YOUR PERFORMANCE SNAPSHOT
          </span>

          <h3>
            {score === null
              ? "Your answers have been recorded."
              : score >= 85
                ? "A milestone worth celebrating."
                : score >= 65
                  ? "A strong foundation to build on."
                  : "Your next chapter starts here."}
          </h3>

          <p>{report.summary}</p>

          <p className={styles.scoreDisclaimer}>
            AI-generated practice assessment, not a
            professional hiring evaluation.
          </p>
        </div>
      </section>

      {/* Answer statistics */}
      <section className={styles.statsSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.sectionEyebrow}>
              BY THE NUMBERS
            </span>
            <h3>Your interview at a glance</h3>
          </div>
        </div>

        <div className={styles.statsGrid}>
          <div className={styles.statCard}>
            <span
              className={styles.statIcon}
              aria-hidden="true"
            >
              🎯
            </span>
            <strong>{totalAnswers}</strong>
            <span>Answers assessed</span>
          </div>

          {countItems.map(([name, count]) => (
            <div className={styles.statCard} key={name}>
              <span
                className={styles.statIcon}
                aria-hidden="true"
              >
                {name === "correct"
                  ? "✅"
                  : name === "partial"
                    ? "🧩"
                    : name === "incorrect"
                      ? "📚"
                      : "🔎"}
              </span>

              <strong>{count}</strong>
              <span>
                {name.charAt(0).toUpperCase() +
                  name.slice(1)}
              </span>
            </div>
          ))}
        </div>
      </section>

      {/* Topic performance */}
      <section className={styles.topicsSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.sectionEyebrow}>
              YOUR KNOWLEDGE MAP
            </span>
            <h3>Topic performance</h3>
          </div>

          <span
            className={styles.sectionEmoji}
            aria-hidden="true"
          >
            📊
          </span>
        </div>

        {report.topics.length > 0 ? (
          <div className={styles.topicList}>
            {report.topics.map((topic, index) => {
              const topicScore = validScore(
                topic.correctness_score
              );

              const depth = validScore(
                topic.depth_score
              );

              return (
                <article
                  className={styles.topicCard}
                  key={`${topic.topic}-${index}`}
                >
                  <div className={styles.topicTop}>
                    <div className={styles.topicInfo}>
                      <span
                        className={styles.topicNumber}
                      >
                        TOPIC{" "}
                        {String(index + 1).padStart(
                          2,
                          "0"
                        )}
                      </span>

                      <h4>{topic.topic}</h4>
                    </div>

                    <strong
                      className={styles.topicScore}
                    >
                      {topicScore === null
                        ? "—"
                        : `${topicScore}%`}
                    </strong>
                  </div>

                  <div
                    className={styles.progressTrack}
                    role="progressbar"
                    aria-label={`${topic.topic} correctness`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={
                      topicScore ?? undefined
                    }
                    aria-valuetext={
                      topicScore === null
                        ? "Not assessed"
                        : `${topicScore} out of 100`
                    }
                  >
                    <div
                      className={styles.progressFill}
                      style={{
                        width: animate
                          ? `${topicScore ?? 0}%`
                          : "0%",
                      }}
                    />
                  </div>

                  <div className={styles.topicFooter}>
                    <span>Correctness</span>
                    <span>
                      Depth:{" "}
                      {depth === null
                        ? "Not assessed"
                        : `${depth}/100`}
                    </span>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className={styles.emptyPanel}>
            No topic-level assessments available.
          </div>
        )}
      </section>

      {/* Personalized findings */}
      <section className={styles.findingsSection}>
        <div className={styles.sectionHeading}>
          <div>
            <span className={styles.sectionEyebrow}>
              PERSONALIZED REFLECTION
            </span>

            <h3>
              What this interview revealed
            </h3>
          </div>

          <span
            className={styles.sectionEmoji}
            aria-hidden="true"
          >
            💡
          </span>
        </div>

        <div className={styles.findingsGrid}>
          <FindingCard
            icon="💎"
            title="Your strengths"
            items={report.strengths}
            kind="strength"
          />

          <FindingCard
            icon="🌱"
            title="Opportunities to grow"
            items={report.weaknesses}
            kind="growth"
          />
        </div>

        <FindingCard
          icon="🧭"
          title="Your next steps"
          items={report.recommendations}
          kind="next"
        />
      </section>

      {/* Encouragement */}
      <aside className={styles.motivation}>
        <div
          className={styles.motivationIcon}
          aria-hidden="true"
        >
          💜
        </div>

        <div>
          <h3>
            One interview doesn't define your potential.
          </h3>
          <p>
            The important part is showing up,
            learning from your answers, and
            coming back a little stronger every time.
          </p>
        </div>
      </aside>

      {/* Evidence and scoring */}
      <details className={styles.evidence}>
        <summary className={styles.evidenceSummary}>
          <span className={styles.evidenceTitle}>
            <span aria-hidden="true">⌘</span>
            Evidence & scoring details
          </span>

          <span
            className={styles.expandIcon}
            aria-hidden="true"
          >
            ⌄
          </span>
        </summary>

        <div className={styles.evidenceContent}>
          <h3>How your answers were assessed</h3>

          <p>
            {report.score_explanation ||
              "No detailed scoring explanation was recorded."}
          </p>

          {report.evaluations.map(
            (evaluation, index) => (
              <section
                key={`${evaluation.turn}-${index}`}
                className={styles.evaluation}
              >
                <h4>Answer {evaluation.turn}</h4>

                {evaluation.sources.length > 0 ? (
                  <Sources
                    sources={evaluation.sources}
                  />
                ) : (
                  <p>
                    No code references recorded
                    for this answer.
                  </p>
                )}
              </section>
            )
          )}
        </div>
      </details>

      {/* Buttons — excluded from PDF */}
      <footer
        className={styles.actions}
        data-pdf-exclude="true"
      >
        <Link
          href="/interview?new=1"
          className={styles.primaryButton}
        >
          <span aria-hidden="true">✦</span>
          Practice Again
          <span aria-hidden="true">↗</span>
        </Link>

        <Link
          href="/dashboard"
          className={styles.secondaryButton}
        >
          Back to Dashboard
        </Link>

        <button
          type="button"
          className={styles.printButton}
          onClick={() => void downloadReportPDF()}
          disabled={exporting}
        >
          {exporting
            ? "Generating PDF..."
            : "↓ Download PDF"}
        </button>
      </footer>

      {exportError && (
        <p
          role="alert"
          className={styles.exportError}
          data-pdf-exclude="true"
        >
          {exportError}
        </p>
      )}

      <p className={styles.closingLine}>
        Keep learning. Keep building.
        Keep becoming. ✨
      </p>
    </section>
  );
}
