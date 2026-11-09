
"use client";

import { useState, type FormEvent } from "react";
import Image from "next/image";
import Link from "next/link";
import styles from "../../../styles/auth/login.module.css";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [message, setMessage] = useState("");

  function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();

    if (!email.trim() || !password) {
      setMessage("Please fill in all fields.");
      return;
    }

    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setMessage("Please enter a valid email address.");
      return;
    }

    setMessage("Authentication is not connected yet.");
  }

  return (
    <main className={styles.page}>
        <Link href="/" className={styles.backButton}>
  <span className={styles.backIcon} aria-hidden="true">←</span>
  <span>Back to Home</span>
</Link>
      <section className={styles.card}>
        <header className={styles.header}>
          <h1 className={styles.title}>Login</h1>
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
            <label htmlFor="login-email">Email:</label>
            <input
              id="login-email"
              type="email"
              autoComplete="email"
              placeholder="Enter your email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div className={styles.field}>
            <label htmlFor="login-password">Password:</label>

            <div className={styles.passwordField}>
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                placeholder="Enter your password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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

          {message && (
            <p className={styles.message} role="status">
              {message}
            </p>
          )}

          <button type="submit" className={styles.submitButton}>
            Login
          </button>
        </form>

        <p className={styles.footer}>
          Don't have an account?{" "}
          <Link href="/auth/signup">Sign up</Link>
        </p>
      </section>
    </main>
  );
}
