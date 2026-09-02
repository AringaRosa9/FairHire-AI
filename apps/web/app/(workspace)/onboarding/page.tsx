import type { Metadata } from "next";
import { StatusBadge } from "@fairhire/ui";

export const metadata: Metadata = { title: "First audit" };

const steps = ["System", "Data", "Fields", "Basis", "Run"];

export default function OnboardingPage() {
  return (
    <div className="onboarding">
      <header className="onboarding-heading">
        <p className="eyebrow">First audit · Draft saved</p>
        <h1>Build an evidence-ready check</h1>
        <p>
          Start with the decision the system affects. Files and protected
          attributes stay in separate controlled paths.
        </p>
      </header>
      <ol className="stepper">
        {steps.map((step, index) => (
          <li key={step} aria-current={index === 0 ? "step" : undefined}>
            <span>{index + 1}</span>
            {step}
          </li>
        ))}
      </ol>
      <section className="onboarding-form">
        <div>
          <p className="eyebrow">Step 1 of 5</p>
          <h2>What decision does this system influence?</h2>
          <p>
            This determines the initial rule pack and required evidence. It is a
            technical suggestion until legal review confirms it.
          </p>
        </div>
        <form>
          <label>
            System name
            <input name="name" defaultValue="TalentRank EU" />
          </label>
          <label>
            Intended purpose
            <textarea
              name="purpose"
              defaultValue="Scores applications so recruiters can choose which CVs to review first."
            />
          </label>
          <label>
            Decision impact
            <select name="impact" defaultValue="shortlist">
              <option value="shortlist">Shortlisting or screening</option>
              <option value="recommend">Job recommendation</option>
              <option value="support">Administrative support only</option>
            </select>
          </label>
          <fieldset>
            <legend>Where is it used?</legend>
            <label className="check">
              <input type="checkbox" defaultChecked /> European Union
            </label>
            <label className="check">
              <input type="checkbox" defaultChecked /> Germany
            </label>
            <label className="check">
              <input type="checkbox" /> United Kingdom
            </label>
          </fieldset>
          <div className="form-note">
            <StatusBadge tone="review">Legal confirmation required</StatusBadge>
            <p>
              Recruitment screening is likely within the employment high-risk
              category. This is not a compliance determination.
            </p>
          </div>
          <div className="form-actions">
            <button className="fh-button" type="button">
              Save draft
            </button>
            <button className="fh-button" data-variant="primary" type="button">
              Continue to data →
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}
