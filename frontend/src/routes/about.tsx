import { createFileRoute } from "@tanstack/react-router";
import { ChevronDown, Code2, Mail } from "lucide-react";
import { AboutRings, AboutSphere } from "@/components/about/AboutShapes";
import { CopyButton } from "@/components/ui/CopyButton";
import { GlassSurface } from "@/components/ui/GlassSurface";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Eyebrow } from "@/components/ui/editorial";
import "./about.css";

export const Route = createFileRoute("/about")({
  component: AboutPage,
});

const CITATION_TEXT =
  "Jiro, O. (2026). Rancang Bangun Herbaflow Platform Web Network Pharmacology dengan " +
  "Studi Kasus Tumbuhan Obat Indonesia. Unpublished thesis project.";

function AboutPage() {
  // The app shell (__root) provides <main>, <Nav>, <Footer>, and the BackgroundFX
  // dotted-glow layer. This route renders page content only.
  return (
    <article className="ab-page">
      <header className="ab-masthead">
        <AboutSphere />
        <div className="ab-dateline">A Network-Pharmacology Thesis Project · 2026</div>
        <hr className="ab-ruleline" />
        <h1 className="ab-title">
          About <em>Herbaflow</em>
        </h1>
        <hr className="ab-ruleline" />
        <p className="ab-standfirst">
          Why this exists, how it works, and what it can honestly tell you.
        </p>
      </header>

      <section className="ab-section" id="sec-01">
        <div className="ab-section-head">
          <span className="ab-num">01</span>
          <Eyebrow>The idea</Eyebrow>
        </div>
        <h2>What network pharmacology is</h2>
        <div className="ab-dropcap">
          <p>
            Most drug research follows one molecule to one protein. Network pharmacology takes the
            wider view. A medicinal plant carries many bioactive compounds at once, each able to act
            on several human proteins, and those proteins sit inside the larger network that drives
            a disease. Herbaflow maps that network: it links a plant&apos;s compounds to the human
            proteins they act on (their targets), and links those targets to the disease you want to
            study. The result lets you read a plant as a system, not a single ingredient.
          </p>
        </div>
      </section>

      <section className="ab-section" id="sec-02">
        <div className="ab-section-head">
          <span className="ab-num">02</span>
          <Eyebrow>The reason</Eyebrow>
        </div>
        <h2>Why this exists</h2>
        <p>
          I came to this after watching a friend do network-pharmacology research. The science was
          fascinating. The process was not. The work was spread across a dozen separate databases
          and tools, stitched together by hand, with results copied from one place to the next. I
          asked whether there was a better way to do it. He said no: he, his lab, and most of the
          published papers all work this way, connecting the dots manually, and it takes a long
          time.
        </p>
        <blockquote className="ab-pullquote">
          &ldquo;I asked whether there was a better way. He said no.&rdquo;
        </blockquote>
        <p>
          Herbaflow is my attempt to take some of that weight off. It will not replace a
          researcher&apos;s judgment, and it does not pretend to. What it can do is carry the
          repetitive computational work from start to finish, in one place, with every step open to
          review, so the time goes into the thinking instead of the plumbing.
        </p>
      </section>

      <section className="ab-section" id="sec-03">
        <div className="ab-section-head">
          <span className="ab-num">03</span>
          <Eyebrow>The approach</Eyebrow>
        </div>
        <h2>How Herbaflow approaches it</h2>
        <div className="ab-specsheet">
          <div className="ab-spec-row">
            <div className="ab-spec-label">Reviewable</div>
            <p>
              The whole pipeline runs as one continuous flow, and you can review, edit, or augment
              the intermediate set at every step before it moves on.
            </p>
          </div>
          <div className="ab-spec-row">
            <div className="ab-spec-label">Measured</div>
            <p>
              Compound-target links come from measured experimental bioactivity, not prediction,
              unless you choose to add predictions yourself.
            </p>
          </div>
          <div className="ab-spec-row">
            <div className="ab-spec-label">Sourced</div>
            <p>
              Every association carries a link back to the database it came from, so any result can
              be traced and checked.
            </p>
          </div>
          <div className="ab-spec-row">
            <div className="ab-spec-label">Yours to set</div>
            <p>
              You control the parameters at each step. The defaults are sensible, and none of them
              are hidden from you.
            </p>
          </div>
        </div>
      </section>

      <section className="ab-section" id="sec-04">
        <div className="ab-section-head">
          <span className="ab-num">04</span>
          <Eyebrow>Scope</Eyebrow>
        </div>
        <h2>What it can and can&apos;t tell you</h2>
        <GlassSurface tier="raised" className="ab-box ab-scope">
          <div className="ab-box-label">A note on scope</div>
          <p>
            Herbaflow is a research and education tool. Its results are hypotheses to test, not
            clinical or diagnostic advice. They are a place to start experiments, not a substitute
            for them.
          </p>
        </GlassSurface>
      </section>

      <section className="ab-section" id="sec-05">
        <div className="ab-section-head">
          <span className="ab-num">05</span>
          <Eyebrow>Roadmap</Eyebrow>
        </div>
        <h2>What&apos;s next</h2>
        <GlassSurface tier="raised" className="ab-box">
          <div className="ab-timeline">
            <div className="ab-tl-item">
              <div className="ab-tl-label">More sources</div>
              <p>
                Additional bioactivity and disease databases, to widen and cross-check the evidence.
              </p>
            </div>
            <div className="ab-tl-item">
              <div className="ab-tl-label">More plants</div>
              <p>Broader coverage of Indonesian medicinal plant data.</p>
            </div>
          </div>
        </GlassSurface>
      </section>

      <section className="ab-section" id="sec-06">
        <AboutRings />
        <div className="ab-section-head">
          <span className="ab-num">06</span>
          <Eyebrow>Colophon</Eyebrow>
        </div>
        <h2>The project and author</h2>
        <GlassSurface tier="raised" className="ab-box">
          <div className="ab-colo-row">
            <div className="ab-colo-label">Author</div>
            <div className="ab-colo-val">
              <span className="ab-serif">Oscar Jiro</span>
            </div>
          </div>
          <div className="ab-colo-row">
            <div className="ab-colo-label">Type</div>
            <div className="ab-colo-val">Solo thesis project in computational biology</div>
          </div>
          <div className="ab-colo-row">
            <div className="ab-colo-label">Contact</div>
            <div className="ab-colo-val">
              <div className="ab-contacts">
                <a className="ab-contact hf-link" href="mailto:oscarjiroj@gmail.com">
                  <Mail className="size-4" aria-hidden="true" />
                  oscarjiroj@gmail.com
                </a>
                <a
                  className="ab-contact hf-link"
                  href="https://github.com/oscarjiro"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <Code2 className="size-4" aria-hidden="true" />
                  github.com/oscarjiro
                </a>
              </div>
            </div>
          </div>
          <div className="ab-colo-row">
            <div className="ab-colo-label">Cite</div>
            <div className="ab-colo-val">
              <Collapsible>
                <CollapsibleTrigger asChild>
                  <button className="ab-cite-trigger" type="button">
                    <span>How to cite</span>
                    <ChevronDown className="ab-cite-chevron size-4" aria-hidden="true" />
                  </button>
                </CollapsibleTrigger>
                <CollapsibleContent className="ab-cite-content">
                  <div className="ab-cite-note">
                    Provisional. Thesis not yet published or submitted.
                  </div>
                  <div className="ab-cite-text">
                    Jiro, O. (2026).{" "}
                    <span className="ab-ital">
                      Rancang Bangun Herbaflow Platform Web Network Pharmacology dengan Studi Kasus
                      Tumbuhan Obat Indonesia.
                    </span>{" "}
                    Unpublished thesis project.
                  </div>
                  <CopyButton label="Copy citation" text={CITATION_TEXT} />
                </CollapsibleContent>
              </Collapsible>
            </div>
          </div>
        </GlassSurface>
      </section>
    </article>
  );
}
