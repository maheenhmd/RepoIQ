
"use client";

import { useState, type FormEvent } from "react";
import Image from "next/image";
import Link from "next/link";
import styles from "../../../styles/auth/signup.module.css";

export default function SignupPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [message, setMessage] = useState("");

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!name.trim() || !email.trim() || !password || !confirmPassword) {
      setMessage("Please fill in all fields.");
      return;
    }

    if (name.trim().length < 2) {
      setMessage("Please enter your full name.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setMessage("Please enter a valid email address.");
      return;
    }

    if (password.length < 8) {
      setMessage("Password must be at least 8 characters.");
      return;
    }

    if (password !== confirmPassword) {
      setMessage("Passwords do not match.");
      return;
    }

    setMessage("Account registration is not connected yet.");
  }

  return (
    <main className={styles.page}>
        <Link href="/" className={styles.backButton}>
  <span className={styles.backIcon} aria-hidden="true">←</span>
  <span>Back to Home</span>
</Link>
      <section className={styles.card}>
        <header className={styles.header}>
          <h1 className={styles.title}>Sign Up</h1>
          <span className={styles.titleUnderline} />

          <Link href="/" className={styles.logo}>
            <Image
              src="/repoiq-mascot.png"
              alt="RepoIQ Logo"
              width={90}
              height={90}
              className={styles.logoImage}
              priority
            />
          </Link>
        </header>

        <form onSubmit={handleSubmit} className={styles.form} noValidate>
          <div className={styles.field}>
            <label htmlFor="signup-name">Full Name:</label>
            <input
              id="signup-name"
              type="text"
              autoComplete="name"
              placeholder="Enter your full name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="signup-email">Email:</label>
            <input
              id="signup-email"
              type="email"
              autoComplete="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="signup-password">Password:</label>

            <div className={styles.passwordField}>
              <input
                id="signup-password"
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Create a password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                required
              />

              <button
                type="button"
                className={styles.togglePassword}
                onClick={() => setShowPassword((prev) => !prev)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <div className={styles.field}>
            <label htmlFor="signup-confirm">Confirm Password:</label>

            <div className={styles.passwordField}>
              <input
                id="signup-confirm"
                type={showConfirm ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Confirm your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
              />

              <button
                type="button"
                className={styles.togglePassword}
                onClick={() => setShowConfirm((prev) => !prev)}
                aria-label={showConfirm ? "Hide password" : "Show password"}
              >
                {showConfirm ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          {message && (
            <p className={styles.message} role="status">
              {message}
            </p>
          )}

          <button type="submit" className={styles.submitButton}>
            Create Account
          </button>
        </form>

        <p className={styles.footer}>
          Already have an account?{" "}
          <Link href="/auth/login">Login</Link>
        </p>
      </section>
    </main>
  );
}
