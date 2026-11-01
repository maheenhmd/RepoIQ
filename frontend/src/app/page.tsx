import "@/components/landing/landingstyles/base.css";

import Navbar from "@/components/landing/Navbar";
import Hero from "@/components/landing/Hero";
import Benefits from "@/components/landing/Benefits";
import UseCases from "@/components/landing/UseCases";
import Intelligence from "@/components/landing/Intelligence";
import Quote from "@/components/landing/Quote";
import CTA from "@/components/landing/CTA";
import Footer from "@/components/landing/Footer";

export default function HomePage() {
  return (
    <div className="rq-page">
      <Navbar />

      <main>
        <Hero />
        <Benefits />
        <UseCases />
        <Intelligence />
        <Quote />
        <CTA />
      </main>

      <Footer />
    </div>
  );
}
