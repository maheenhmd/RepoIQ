
"use client";

import Image from "next/image";
import Link from "next/link";
import type { PointerEvent } from "react";
import Icon from "./Icon";
import "./landingstyles/Hero.css";

export default function Hero() {
  function handlePointerMove(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "mouse") return;

    const element = event.currentTarget;
    const rect = element.getBoundingClientRect();

    const x = (event.clientX - rect.left) / rect.width - 0.5;
    const y = (event.clientY - rect.top) / rect.height - 0.5;

    element.style.setProperty("--hero-rotate-x", `${-y * 9}deg`);
    element.style.setProperty("--hero-rotate-y", `${x * 12}deg`);
  }

  function handlePointerLeave(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.style.setProperty("--hero-rotate-x", "0deg");
    event.currentTarget.style.setProperty("--hero-rotate-y", "0deg");
  }

  return (
    <section
      className="rq-hero"
      aria-labelledby="rq-hero-heading"
    >
      {/* Decorative background */}
      <div className="rq-hero-glow rq-hero-glow-one" />
      <div className="rq-hero-glow rq-hero-glow-two" />

      <div className="rq-hero-wash rq-wash-left" />
      <div className="rq-hero-wash rq-wash-right" />

      <div className="rq-shell rq-hero-grid">
        {/* LEFT CONTENT */}
        <div className="rq-hero-copy">
          <div className="rq-hero-eyebrow">
            <span className="rq-hero-eyebrow-dot" />
            YOUR CODE. YOUR INTERVIEW.
          </div>

          <h1 id="rq-hero-heading">
            RepoIQ turns GitHub repositories into{" "}
            <span className="rq-hero-highlight">
              technical interviews
            </span>{" "}
            and feedback.
          </h1>

          <p>
            An AI-powered interview platform that
            understands your code, asks relevant
            technical questions, and gives actionable
            feedback to help you practice and get
            job-ready.
          </p>

          <div className="rq-hero-actions">
            <Link
              href="/auth/signup"
              className="rq-button rq-button-main rq-hero-primary"
            >
              <span>Get Started</span>
              <Icon name="arrow" size={19} />
            </Link>

            <a
              className="rq-button rq-button-light rq-hero-secondary"
              href="https://github.com/maheenhmd/RepoIQ"
              target="_blank"
              rel="noopener noreferrer"
            >
              <Icon name="github" size={20} />
              View on GitHub
            </a>
          </div>

          <div className="rq-hero-footnote">
            <span className="rq-hero-footnote-icon">
              <Icon name="check" size={14} />
            </span>
            Practice with real code, not generic questions.
          </div>
        </div>

        {/* RIGHT - INTERACTIVE 3D VISUAL */}
        <div
          className="rq-hero-art"
          onPointerMove={handlePointerMove}
          onPointerLeave={handlePointerLeave}
        >
          <div className="rq-hero-visual">
            {/* Ambient light */}
            <div className="rq-hero-ambient" />

            {/* 3D layer */}
            <div className="rq-hero-tilt">
              <div className="rq-hero-halo" />

              <div className="rq-hero-orbit rq-orbit-one" />
              <div className="rq-hero-orbit rq-orbit-two" />

              {/* Decorative particles */}
              <span className="rq-hero-particle rq-particle-one" />
              <span className="rq-hero-particle rq-particle-two" />
              <span className="rq-hero-particle rq-particle-three" />

              {/* Robot */}
              <Image
                src="/repoiq-mascot.png"
                width={670}
                height={670}
                priority
                alt="RepoIQ AI robot helping developers practice technical interviews"
                className="rq-hero-mascot"
              />

              {/* Floating status 1 */}
              <div className="rq-hero-float rq-hero-float-code">
                <span className="rq-hero-float-icon rq-float-coral">
                  <Icon name="code" size={19} />
                </span>

                <span>
                  <strong>Code understood</strong>
                  <small>Repository analyzed</small>
                </span>

                <span className="rq-hero-status-check">
                  <Icon name="check" size={13} />
                </span>
              </div>

              {/* Floating status 2 */}
              <div className="rq-hero-float rq-hero-float-feedback">
                <span className="rq-hero-float-icon rq-float-teal">
                  <Icon name="chart" size={19} />
                </span>

                <span>
                  <strong>Interview ready</strong>
                  <small>Personalized practice</small>
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
