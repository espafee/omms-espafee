import Link from "next/link";

import styles from "../omms.module.css";
import { featureCards, lifecycle, navLinks, pages, proofPoints, type OmmsPageContent } from "../content";

function MarketingNav() {
  return (
    <nav className={styles.nav} aria-label="OMMS website navigation">
      <Link className={styles.brand} href="/omms">
        <span className={styles.brandMark}>V</span>
        <span>
          <strong>VistaAi</strong>
          <small>OMMS</small>
        </span>
      </Link>
      <div className={styles.navLinks}>
        {navLinks.map((link) => (
          <Link key={link.href} href={link.href}>
            {link.label}
          </Link>
        ))}
      </div>
      <Link className={styles.navCta} href="/login">
        Login
      </Link>
    </nav>
  );
}

export function OmmsHomePage() {
  return (
    <main className={styles.site}>
      <header className={styles.hero}>
        <MarketingNav />
        <section className={styles.heroContent}>
          <p className={styles.kicker}>VistaAi presents OMMS</p>
          <h1>Outdoor media operations, execution, billing, and proof in one control room.</h1>
          <p className={styles.heroCopy}>
            OMMS helps outdoor media owners, agencies, operations teams, field staff, and finance teams manage the full
            journey from campaign estimate to payment collection.
          </p>
          <div className={styles.heroActions}>
            <Link className={styles.primaryButton} href="/omms/features">
              Explore platform
            </Link>
            <Link className={styles.secondaryButton} href="/omms/training">
              View training
            </Link>
          </div>
        </section>
      </header>

      <section className={styles.lifecycleBand} aria-label="OMMS lifecycle">
        {lifecycle.map((step) => (
          <span key={step}>{step}</span>
        ))}
      </section>

      <section className={styles.section}>
        <div className={styles.sectionIntro}>
          <p className={styles.kicker}>Why OMMS</p>
          <h2>Built for the real outdoor media business lifecycle.</h2>
          <p>
            The platform separates proposed work, approved work, field execution, proof, issue resolution, finance, and
            payment tracking so every team works from the same truth.
          </p>
        </div>
        <div className={styles.proofGrid}>
          {proofPoints.map((point, index) => (
            <article key={point} className={styles.proofItem}>
              <span>{String(index + 1).padStart(2, "0")}</span>
              <p>{point}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.section}>
        <div className={styles.sectionIntro}>
          <p className={styles.kicker}>Platform coverage</p>
          <h2>One product for inventory, campaigns, field proof, billing, and operations.</h2>
        </div>
        <div className={styles.cardGrid}>
          {featureCards.map((feature) => (
            <article key={feature.title} className={styles.featureCard}>
              <h3>{feature.title}</h3>
              <p>{feature.copy}</p>
            </article>
          ))}
        </div>
      </section>

      <section className={styles.splitSection}>
        <div>
          <p className={styles.kicker}>Field execution</p>
          <h2>POE with GPS confidence and issue resolution.</h2>
          <p>
            Field staff upload proof from mobile, GPS is captured during execution, suspicious POE is flagged, and issues
            can become tasks that close only after verified proof.
          </p>
        </div>
        <div className={styles.workflowPanel}>
          {["Assigned work", "POE upload", "GPS validation", "Issue task", "Resolution proof"].map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>

      <section className={styles.ctaSection}>
        <p className={styles.kicker}>Ready for client demos and team training</p>
        <h2>Use OMMS as the operating layer for outdoor media growth.</h2>
        <p>
          Start with the brand website, then use the training manual and module decks to onboard every role inside the
          organization.
        </p>
        <Link className={styles.primaryButton} href="/omms/workflows">
          See the workflow
        </Link>
      </section>
    </main>
  );
}

export function OmmsContentPage({ page }: { page: OmmsPageContent }) {
  const relatedPages = Object.values(pages).filter((item) => item.slug !== page.slug).slice(0, 3);

  return (
    <main className={styles.site}>
      <header className={styles.subHero}>
        <MarketingNav />
        <section className={styles.subHeroContent}>
          <div>
            <p className={styles.kicker}>{page.eyebrow}</p>
            <h1>{page.title}</h1>
            <p>{page.intro}</p>
          </div>
          <aside className={styles.statCard}>
            <strong>{page.heroStat}</strong>
            <span>{page.heroStatLabel}</span>
          </aside>
        </section>
      </header>

      <section className={styles.detailGrid}>
        {page.sections.map((section) => (
          <article key={section.title} className={styles.detailCard}>
            <h2>{section.title}</h2>
            <p>{section.copy}</p>
            <ul>
              {section.bullets.map((bullet) => (
                <li key={bullet}>{bullet}</li>
              ))}
            </ul>
          </article>
        ))}
      </section>

      <section className={styles.relatedSection}>
        <div>
          <p className={styles.kicker}>Continue exploring</p>
          <h2>{page.cta}</h2>
        </div>
        <div className={styles.relatedLinks}>
          {relatedPages.map((item) => (
            <Link key={item.slug} href={`/omms/${item.slug}`}>
              {item.eyebrow}
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}
