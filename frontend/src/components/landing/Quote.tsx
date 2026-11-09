
"use client";

import { useState } from "react";
import Image from "next/image";
import Link from "next/link";
import "./landingstyles/Quote.css";

export default function Quote() {
  const [replayKey, setReplayKey] = useState(0);

  return (
    <section className="rq-live-section" id="experience">
      <div className="rq-shell rq-live-layout">

        {/* Left: Section intro */}
        <div className="rq-live-intro">
          <div className="rq-live-eyebrow">
            <span className="rq-live-pulse" />
            THE INTERVIEW EXPERIENCE
          </div>

          <h2>
            Not another
            <br />
            question bank.
            <br />
            <span>A real conversation.</span>
          </h2>

          <p>
            RepoIQ doesn't just ask what you know.
            It asks how your code works, listens to your
            reasoning, and shows you where to improve.
          </p>

          <div className="rq-live-points">
            <div>
              <span className="rq-live-point-icon coral">
                01
              </span>
              Questions about your repository
            </div>

            <div>
              <span className="rq-live-point-icon teal">
                02
              </span>
              Natural technical discussions
            </div>

            <div>
              <span className="rq-live-point-icon blue">
                03
              </span>
              Feedback grounded in code
            </div>
          </div>

          <Link
            href="/auth/signup"
            className="rq-live-start"
          >
            Experience it yourself
            <span aria-hidden="true">↗</span>
          </Link>
        </div>

        {/* Right: Animated interview demonstration */}
        <div className="rq-live-demo" key={replayKey}>
          <div className="rq-demo-header">
            <div className="rq-demo-header-left">
              <div className="rq-demo-avatar">
                <Image
                  src="/repoiq-mascot.png"
                  alt="RepoIQ"
                  width={44}
                  height={44}
                />
              </div>

              <div>
                <strong>RepoIQ Interview</strong>
                <span>
                  <i className="rq-demo-online" />
                  Sample session
                </span>
              </div>
            </div>

            <button
              type="button"
              className="rq-demo-replay"
              onClick={() => setReplayKey((key) => key + 1)}
              aria-label="Replay interview preview"
              title="Replay animation"
            >
              <svg
                width="17"
                height="17"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M3 11a9 9 0 1 1 2.6 6.4M3 4v7h7" />
              </svg>
              Replay
            </button>
          </div>

          <div className="rq-demo-context">
            <span>
              <svg
                viewBox="0 0 24 24"
                width="14"
                height="14"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
                aria-hidden="true"
              >
                <path d="M9 19c-4 1-4-2-6-3m12 6v-3c0-2-.5-3 0-4 3 0 5-2 5-6 0-1-.4-3-1-4 0-1 0-2-.2-3-2-.5-3 1-4 1.5a11 11 0 0 0-6 0C7 3 6 2 4 2c-.5 2 0 3 0 3a7 7 0 0 0-1 4c0 4 2 6 5 6 .5 1 0 2 0 4v3" />
              </svg>
              psf/requests
            </span>

            <span>Intermediate</span>

            <span className="rq-demo-progress">
              Question 1 of 4
            </span>
          </div>

          <div className="rq-demo-conversation">

            {/* AI Question */}
            <div className="rq-demo-message rq-demo-question">
              <div className="rq-demo-message-label">
                <span className="rq-demo-bot-symbol">✦</span>
                RepoIQ
              </div>

              <div className="rq-demo-bubble rq-demo-ai-bubble">
                <p>
                  In your repository, how does{" "}
                  <code>raise_for_status()</code> handle
                  unsuccessful HTTP responses?
                </p>

                <div className="rq-demo-source">
                  <span className="rq-demo-source-icon">
                    {"</>"}
                  </span>
                  src/requests/models.py
                </div>
              </div>
            </div>

            {/* User answer */}
            <div className="rq-demo-message rq-demo-answer">
              <div className="rq-demo-message-label rq-demo-user-label">
                You
                <span className="rq-demo-user-avatar">Y</span>
              </div>

              <div className="rq-demo-bubble rq-demo-user-bubble">
                It checks the HTTP status code and
                raises an HTTPError for unsuccessful
                client or server responses.
              </div>
            </div>

            {/* Feedback */}
            <div className="rq-demo-message rq-demo-feedback">
              <div className="rq-demo-message-label">
                <span className="rq-demo-bot-symbol">✦</span>
                RepoIQ Feedback
              </div>

              <div className="rq-demo-feedback-card">
                <div className="rq-demo-feedback-heading">
                  <span className="rq-demo-check">
                    ✓
                  </span>
                  Good understanding
                  <span className="rq-demo-feedback-badge">
                    On track
                  </span>
                </div>

                <p>
                  You identified the core behavior.
                  To strengthen your answer, explain
                  how the exception retains the
                  response for further inspection.
                </p>

                <div className="rq-demo-insight">
                  <span>↗</span>
                  Go deeper into exception handling.
                </div>
              </div>
            </div>
          </div>

          <div className="rq-demo-footer">
            <span>
              <span className="rq-demo-footer-dot" />
              Repository-grounded practice
            </span>
            <span>Powered by RepoIQ</span>
          </div>
        </div>
      </div>
    </section>
  );
}
